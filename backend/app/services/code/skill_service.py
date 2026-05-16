"""
BOS Code skill draft storage and safe file writing.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.models import CodeSkill, CodeSkillRevision, CodeWorkspace, User
from app.services.code.workspace_guard import WorkspaceGuard

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

_SLUG_RE = re.compile(r"[^a-z0-9._-]+")


class CodeSkillService:
    SKILLS_ROOT = "skills"
    AUTO_DEMOTE_NEGATIVE_DELTA = 2
    AUTO_PROMOTE_POSITIVE_DELTA = 2

    @staticmethod
    def normalize_slug(value: str) -> str:
        slug = _SLUG_RE.sub("-", value.strip().lower()).strip("-")
        return slug or "skill"

    @staticmethod
    def _skills_guard(workspace: CodeWorkspace) -> WorkspaceGuard:
        return WorkspaceGuard(
            workspace.worktree_root,
            max_read_bytes=262144,
            max_write_bytes=131072,
        )

    @classmethod
    def _skill_dir(cls, workspace: CodeWorkspace, slug: str) -> str:
        return f"{cls.SKILLS_ROOT}/{slug}"

    @classmethod
    async def list_skills(cls, db: AsyncSession, *, workspace_id: int) -> list[CodeSkill]:
        result = await db.execute(
            select(CodeSkill)
            .where(CodeSkill.workspace_id == workspace_id)
            .order_by(CodeSkill.updated_at.desc(), CodeSkill.id.desc())
        )
        return list(result.scalars().all())

    @classmethod
    async def get_skill(cls, db: AsyncSession, *, workspace_id: int, skill_id: int) -> CodeSkill | None:
        result = await db.execute(
            select(CodeSkill).where(CodeSkill.workspace_id == workspace_id, CodeSkill.id == skill_id)
        )
        return result.scalar_one_or_none()

    @classmethod
    def validate_supporting_files(cls, supporting_files: dict[str, str]) -> None:
        for relative_path, content in supporting_files.items():
            normalized = relative_path.replace("\\", "/")
            if normalized.startswith("/") or ".." in normalized.split("/"):
                raise ValueError("skill_supporting_file_path_invalid")
            if not normalized.startswith("references/") and not normalized.startswith("templates/") and not normalized.startswith("scripts/") and not normalized.startswith("assets/"):
                raise ValueError("skill_supporting_file_scope_invalid")
            if len(content.encode("utf-8")) > 131072:
                raise ValueError("skill_supporting_file_too_large")

    @classmethod
    def _write_skill_files(
        cls,
        *,
        workspace: CodeWorkspace,
        directory_path: str,
        content_markdown: str,
        supporting_files: dict[str, str],
    ) -> None:
        guard = cls._skills_guard(workspace)
        skill_md_path = guard.assert_writable(f"{directory_path}/SKILL.md", content_size=len(content_markdown.encode("utf-8")))
        skill_md_path.parent.mkdir(parents=True, exist_ok=True)
        skill_md_path.write_text(content_markdown, encoding="utf-8")

        cls.validate_supporting_files(supporting_files)
        for relative_path, content in supporting_files.items():
            target = guard.assert_writable(
                f"{directory_path}/{relative_path}",
                content_size=len(content.encode("utf-8")),
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

    @classmethod
    async def create_skill(
        cls,
        db: AsyncSession,
        *,
        workspace: CodeWorkspace,
        user: User,
        name: str,
        slug: str,
        description: str | None,
        content_markdown: str,
        supporting_files: dict[str, str],
        origin_task_id: int | None = None,
        reflection_run_id: int | None = None,
        revision_status: str = "draft",
        skill_status: str = "draft",
        change_summary: str | None = None,
    ) -> CodeSkill:
        normalized_slug = cls.normalize_slug(slug)
        existing = await db.execute(
            select(CodeSkill).where(CodeSkill.workspace_id == workspace.id, CodeSkill.slug == normalized_slug)
        )
        if existing.scalar_one_or_none() is not None:
            raise ValueError("skill_slug_conflict")

        directory_path = cls._skill_dir(workspace, normalized_slug)
        cls._write_skill_files(
            workspace=workspace,
            directory_path=directory_path,
            content_markdown=content_markdown,
            supporting_files=supporting_files,
        )

        skill = CodeSkill(
            tenant_id=user.tenant_id,
            workspace_id=workspace.id,
            origin_task_id=origin_task_id,
            created_by_user_id=user.id,
            name=name,
            slug=normalized_slug,
            description=description,
            skill_status=skill_status,
            directory_path=directory_path,
            latest_revision_number=1,
        )
        db.add(skill)
        await db.flush()
        revision = CodeSkillRevision(
            skill_id=skill.id,
            reflection_run_id=reflection_run_id,
            revision_number=1,
            revision_status=revision_status,
            change_summary=change_summary,
            content_markdown=content_markdown,
            supporting_files=supporting_files,
        )
        db.add(revision)
        await db.flush()
        return skill

    @classmethod
    async def update_skill(
        cls,
        db: AsyncSession,
        *,
        workspace: CodeWorkspace,
        skill: CodeSkill,
        description: str | None = None,
        skill_status: str | None = None,
        change_summary: str | None = None,
        content_markdown: str | None = None,
        supporting_files: dict[str, str] | None = None,
        reflection_run_id: int | None = None,
    ) -> CodeSkill:
        if description is not None:
            skill.description = description
        if skill_status is not None:
            skill.skill_status = skill_status

        if content_markdown is not None:
            next_revision_number = int(skill.latest_revision_number or 0) + 1
            supporting_files = supporting_files or {}
            cls._write_skill_files(
                workspace=workspace,
                directory_path=skill.directory_path,
                content_markdown=content_markdown,
                supporting_files=supporting_files,
            )
            revision = CodeSkillRevision(
                skill_id=skill.id,
                reflection_run_id=reflection_run_id,
                revision_number=next_revision_number,
                revision_status=skill.skill_status,
                change_summary=change_summary,
                content_markdown=content_markdown,
                supporting_files=supporting_files,
            )
            db.add(revision)
            skill.latest_revision_number = next_revision_number

        await db.flush()
        return skill

    @classmethod
    async def record_feedback(
        cls,
        db: AsyncSession,
        *,
        skill: CodeSkill,
        sentiment: str,
        note: str | None = None,
    ) -> CodeSkill:
        if sentiment == "positive":
            skill.positive_feedback_count = int(skill.positive_feedback_count or 0) + 1
        elif sentiment == "negative":
            skill.negative_feedback_count = int(skill.negative_feedback_count or 0) + 1
        else:
            raise ValueError("skill_feedback_invalid")

            skill.last_feedback_at = datetime.now(UTC)
        if note:
            skill.description = ((skill.description or "").strip() + f"\nFeedback: {note}").strip()
        negative_delta = int(skill.negative_feedback_count or 0) - int(skill.positive_feedback_count or 0)
        if negative_delta >= cls.AUTO_DEMOTE_NEGATIVE_DELTA and skill.skill_status == "active":
            skill.skill_status = "draft"
            skill.description = ((skill.description or "").strip() + "\nAuto-demoted after repeated negative feedback.").strip()
        positive_delta = int(skill.positive_feedback_count or 0) - int(skill.negative_feedback_count or 0)
        if positive_delta >= cls.AUTO_PROMOTE_POSITIVE_DELTA and skill.skill_status == "draft":
            skill.skill_status = "active"
            skill.description = ((skill.description or "").strip() + "\nAuto-promoted after sustained positive feedback.").strip()
        await db.flush()
        return skill

    @classmethod
    async def latest_revision(cls, db: AsyncSession, *, skill_id: int) -> CodeSkillRevision | None:
        result = await db.execute(
            select(CodeSkillRevision)
            .where(CodeSkillRevision.skill_id == skill_id)
            .order_by(CodeSkillRevision.revision_number.desc(), CodeSkillRevision.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @classmethod
    async def find_similar_skill(cls, db: AsyncSession, *, workspace_id: int, objective: str) -> CodeSkill | None:
        skills = await cls.list_skills(db, workspace_id=workspace_id)
        scored: list[tuple[int, CodeSkill]] = []
        for skill in skills:
            score = cls._score_skill_relevance(skill=skill, revision=None, query=objective)
            if score > 0:
                scored.append((score, skill))
        if not scored:
            return skills[0] if skills else None
        scored.sort(key=lambda item: (-item[0], item[1].id))
        return scored[0][1]

    @staticmethod
    def _tokenize_query(query: str) -> list[str]:
        return [token for token in re.findall(r"[a-zA-Z0-9_]+", query.lower()) if len(token) > 2]

    @classmethod
    def _score_skill_relevance(
        cls,
        *,
        skill: CodeSkill,
        revision: CodeSkillRevision | None,
        query: str,
    ) -> int:
        tokens = cls._tokenize_query(query)
        if not tokens:
            return 0

        haystack = " ".join(
            part
            for part in [
                skill.name,
                skill.slug,
                skill.description or "",
                revision.content_markdown if revision is not None else "",
            ]
            if part
        ).lower()

        score = 3 if skill.skill_status == "active" else 1
        score += int(skill.positive_feedback_count or 0) * 2
        score -= int(skill.negative_feedback_count or 0) * 2
        if query.lower() in haystack:
            score += 5
        for token in tokens:
            if token in haystack:
                score += 2
        if skill.slug.replace("-", " ") in query.lower():
            score += 3
        return score

    @classmethod
    async def build_injection_context(
        cls,
        db: AsyncSession,
        *,
        workspace_id: int,
        query: str,
        session_id: int | None = None,
        include_drafts: bool = False,
    ) -> str:
        skills = await cls.list_skills(db, workspace_id=workspace_id)
        if not skills:
            return ""

        ranked: list[tuple[int, CodeSkill, CodeSkillRevision | None]] = []
        for skill in skills:
            if skill.skill_status != "active" and not include_drafts:
                continue
            revision = await cls.latest_revision(db, skill_id=skill.id)
            score = cls._score_skill_relevance(skill=skill, revision=revision, query=query)
            if score > 1:
                ranked.append((score, skill, revision))

        if not ranked:
            return ""

        ranked.sort(key=lambda item: (-item[0], item[1].id))
        blocks: list[str] = []
        for _score, skill, revision in ranked[:2]:
            if revision is None:
                continue
            skill.usage_count = int(skill.usage_count or 0) + 1
            skill.last_used_at = datetime.now(UTC)
            blocks.append(
                f"### Skill: {skill.name} ({skill.skill_status})\n"
                f"{revision.content_markdown[:2200]}"
            )
        if not blocks:
            return ""
        await db.flush()
        return (
            "Relevant BOS Code skills from prior reflections. Reuse these procedures when they fit the current task.\n\n"
            + "\n\n".join(blocks)
        )

"""
Session orchestration for BOS Code.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.code import (
    SESSION_STATUS_BLOCKED,
    SESSION_STATUS_FAILED,
    SESSION_STATUS_PROMPT_ACCEPTED,
    SESSION_STATUS_READY_FOR_PROMPT,
    SESSION_STATUS_RUNNING,
    SESSION_STATUS_SPAWNING,
    SESSION_STATUS_TRUST_REQUIRED,
)
from app.config import get_settings
from app.models import CodeArtifact, CodeSession, CodeToolCall, CodeTurn, CodeWorkspaceLease, User
from app.services.code.event_service import CodeEventService
from app.services.code.maintenance_service import CodeMaintenanceService
from app.services.code.memory_service import CodeMemoryService
from app.services.code.permissions import CodePermissionPolicy
from app.services.code.runtime_service import CodeRuntimeService
from app.services.code.provider_budget_service import CodeProviderBudgetService
from app.services.code.providers import (
    CodeProviderError,
    OpenAICodexProvider,
    ProviderRequest,
    resolve_provider_profile,
)
from app.services.code.reflection_service import CodeReflectionService
from app.services.code.skill_service import CodeSkillService
from app.services.code.verification_service import CodeVerificationService
from app.services.code.workspace_service import CodeWorkspaceService

settings = get_settings()

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class CodeSessionLeaseConflictError(RuntimeError):
    """Raised when a write lease is already occupied by another session."""


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _derive_session_title(user_message: str) -> str:
    cleaned = " ".join(user_message.split()).lstrip("- ").strip()
    if not cleaned:
        return "New thread"

    lowered = cleaned.lower()
    for prefix in ("please ", "can you ", "could you ", "help me "):
        if lowered.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
            break

    sentence = cleaned.split(". ", 1)[0].split("? ", 1)[0].split("! ", 1)[0].strip()
    sentence = sentence.rstrip(".?!,:;").strip()
    if not sentence:
        return "New thread"
    return sentence[:1].upper() + sentence[1:42]


class CodeSessionService:
    def __init__(self) -> None:
        self.provider = OpenAICodexProvider()

    @staticmethod
    def _status_event_payload(
        *,
        session_status: str,
        verification_status: str | None = None,
        headline: str,
        phase: str,
        recommended_actions: list[str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "session_status": session_status,
            "headline": headline,
            "phase": phase,
            "recommended_actions": recommended_actions or [],
        }
        if verification_status is not None:
            payload["verification_status"] = verification_status
        if extra:
            payload.update(extra)
        return payload

    @staticmethod
    def _failure_contract(*, blocked_reason: str | None, retry_after_seconds: int | None = None) -> dict[str, Any]:
        if blocked_reason == "provider_cooldown":
            return {
                "failure_class": "infra",
                "headline": "The model pool is cooling down before another turn can start.",
                "recommended_actions": [
                    "Wait for the cooldown window, then retry the prompt.",
                    "Avoid treating this as a code regression until provider capacity recovers.",
                ],
            }
        if blocked_reason == "provider_unavailable":
            return {
                "failure_class": "infra",
                "headline": "Live provider execution is unavailable right now.",
                "recommended_actions": [
                    "Verify the provider configuration and API key posture.",
                    "Keep the thread open, but do not assume live execution is available yet.",
                ],
            }
        if blocked_reason == "client_cancelled":
            return {
                "failure_class": "prompt_delivery",
                "headline": "The current prompt was interrupted before the provider finished.",
                "recommended_actions": [
                    "Resend the last prompt if work should continue.",
                    "Treat partial output carefully until a full turn completes.",
                ],
            }
        if blocked_reason == "prompt_misdelivery":
            return {
                "failure_class": "prompt_delivery",
                "headline": "The prompt may have landed in the wrong runtime surface.",
                "recommended_actions": [
                    "Resend the prompt after confirming the session is ready for prompt.",
                    "Check the latest session and worker events before assuming execution has started.",
                ],
            }
        if blocked_reason == "trust_required":
            return {
                "failure_class": "trust_gate",
                "headline": "A trust gate must be cleared before the session can continue.",
                "recommended_actions": [
                    "Resolve the trust prompt before sending more work.",
                    "Keep the session visible until the gate is cleared or explicitly rejected.",
                ],
            }
        return {
            "failure_class": "infra" if blocked_reason else None,
            "headline": "Provider dispatch failed and the session needs operator attention.",
            "recommended_actions": [
                "Inspect the latest provider error details before retrying.",
                "Retry the turn only after the runtime posture looks healthy again.",
            ],
            "retry_after_seconds": retry_after_seconds,
        }

    async def list_sessions(self, db: AsyncSession, *, tenant_id: int) -> list[CodeSession]:
        result = await db.execute(
            select(CodeSession).where(CodeSession.tenant_id == tenant_id).order_by(CodeSession.created_at.desc())
        )
        return list(result.scalars().all())

    async def create_session(
        self,
        db: AsyncSession,
        *,
        user: User,
        acquire_write_lease: bool = True,
        provider_name: str | None = None,
        model_name: str | None = None,
    ) -> CodeSession:
        workspace = await CodeWorkspaceService.ensure_workspace(db, user=user)
        permission_mode = CodePermissionPolicy.mode_for_role(user.role)
        provider_profile = resolve_provider_profile(provider_name)
        selected_model = (model_name or provider_profile.default_model).strip()

        lease_result = await db.execute(select(CodeWorkspaceLease).where(CodeWorkspaceLease.workspace_id == workspace.id))
        lease = lease_result.scalar_one_or_none()
        now = datetime.now(UTC)
        lease_expires_at = _as_utc(lease.lease_expires_at) if lease is not None else None
        if (
            acquire_write_lease
            and lease is not None
            and lease.lease_status == "active"
            and lease.lease_owner_user_id not in {None, user.id}
            and lease_expires_at is not None
            and lease_expires_at > now
        ):
            raise CodeSessionLeaseConflictError("workspace lease is currently occupied")
        if acquire_write_lease and lease is not None:
            lease.lease_status = "active"
            lease.lease_owner_user_id = user.id
            lease.lease_expires_at = now + timedelta(seconds=settings.BOS_CODE_LEASE_TTL_SEC)
            lease.heartbeat_at = now

        session = CodeSession(
            tenant_id=user.tenant_id,
            user_id=user.id,
            workspace_id=workspace.id,
            provider=provider_profile.name,
            model=selected_model,
            permission_mode=permission_mode,
            session_branch=f"boscode/tenant-{user.tenant_id}/session-pending",
            session_status=SESSION_STATUS_SPAWNING,
            verification_status="pending",
            token_usage={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            estimated_cost=0.0,
        )
        db.add(session)
        await db.flush()
        session.session_branch = f"boscode/tenant-{user.tenant_id}/session-{session.id}"
        if lease is not None and acquire_write_lease:
            lease.active_session_id = session.id
            await CodeEventService.append_event(
                db,
                session_id=session.id,
                event_type="code.workspace.lease_changed",
                payload={
                    "workspace_id": workspace.id,
                    "lease_status": lease.lease_status,
                    "lease_owner_user_id": lease.lease_owner_user_id,
                },
            )

        await CodeEventService.append_event(
            db,
            session_id=session.id,
            event_type="code.session.status",
            payload=self._status_event_payload(
                session_status=SESSION_STATUS_SPAWNING,
                verification_status="pending",
                headline="Session is spawning and preparing the runtime handshake.",
                phase="startup",
                recommended_actions=["Wait for the runtime handshake before sending the first prompt."],
            ),
        )
        session.session_status = SESSION_STATUS_READY_FOR_PROMPT
        await CodeEventService.append_event(
            db,
            session_id=session.id,
            event_type="code.session.status",
            payload=self._status_event_payload(
                session_status=SESSION_STATUS_READY_FOR_PROMPT,
                verification_status="pending",
                headline="Session is ready for the first prompt.",
                phase="startup",
                recommended_actions=["Send the first prompt whenever you want BOS Code to begin execution."],
            ),
        )
        await CodeVerificationService.ensure_default_runs(db, session_id=session.id)
        await db.flush()
        return session

    async def initialize_turn(
        self,
        db: AsyncSession,
        *,
        session: CodeSession,
        user_message: str,
        prompt_prelude: str | None = None,
    ) -> tuple[CodeTurn, str]:
        turn_count = await db.execute(select(CodeTurn).where(CodeTurn.session_id == session.id))
        turn_index = len(list(turn_count.scalars().all())) + 1

        turn = CodeTurn(
            session_id=session.id,
            turn_index=turn_index,
            user_message=user_message,
            turn_status="running",
        )
        if not session.title:
            session.title = _derive_session_title(user_message)
        session.session_status = SESSION_STATUS_PROMPT_ACCEPTED
        db.add(turn)
        await db.flush()

        await CodeEventService.append_event(
            db,
            session_id=session.id,
            event_type="code.session.status",
            payload=self._status_event_payload(
                session_status=SESSION_STATUS_PROMPT_ACCEPTED,
                headline="Prompt accepted and queued for provider dispatch.",
                phase="startup",
                recommended_actions=["Wait for provider dispatch to finish before assuming the turn is complete."],
                extra={"turn_id": turn.id, "turn_index": turn.turn_index},
            ),
        )
        session.session_status = SESSION_STATUS_RUNNING
        await CodeEventService.append_event(
            db,
            session_id=session.id,
            event_type="code.session.status",
            payload=self._status_event_payload(
                session_status=SESSION_STATUS_RUNNING,
                headline="Provider dispatch is now running for the current turn.",
                phase="execution",
                recommended_actions=["Keep the thread stable until provider output or a structured blocker appears."],
                extra={"turn_id": turn.id, "turn_index": turn.turn_index},
            ),
        )

        await CodeEventService.append_event(
            db,
            session_id=session.id,
            event_type="code.turn.delta",
            payload={"turn_id": turn.id, "turn_index": turn.turn_index, "message": user_message[:400]},
        )
        if turn_index == 1 and session.title:
            await CodeEventService.append_event(
                db,
                session_id=session.id,
                event_type="code.session.titled",
                payload={"title": session.title},
            )

        memory_context = await CodeMemoryService.build_prompt_memory_context(db, session_id=session.id)
        brain_context = await CodeMaintenanceService.build_brain_context(
            db,
            workspace_id=session.workspace_id,
            tenant_id=session.tenant_id,
            query=user_message,
            current_session_id=session.id,
        )
        skill_context = await CodeSkillService.build_injection_context(
            db,
            workspace_id=session.workspace_id,
            query=user_message,
            session_id=session.id,
            include_drafts=False,
        )
        prompt = user_message
        context_parts = [part for part in (brain_context, memory_context, skill_context) if part]
        if context_parts:
            prompt = "\n\n".join([*context_parts, f"Current request:\n{user_message}"])
        if prompt_prelude:
            prompt = f"{prompt_prelude.strip()}\n\n{prompt}"
        return turn, prompt

    async def fail_turn(
        self,
        db: AsyncSession,
        *,
        session: CodeSession,
        turn: CodeTurn,
        user_message: str,
        exc: CodeProviderError,
    ) -> tuple[CodeTurn, str]:
        turn.assistant_summary = exc.user_message
        turn.turn_status = "failed"
        if exc.blocked_reason == "trust_required":
            session.session_status = SESSION_STATUS_TRUST_REQUIRED
        elif exc.blocked_reason in {"provider_cooldown", "provider_budget_paused", "prompt_misdelivery", "client_cancelled"}:
            session.session_status = SESSION_STATUS_BLOCKED
        else:
            session.session_status = SESSION_STATUS_FAILED
        await self.record_tool_call(
            db,
            session_id=session.id,
            turn_id=turn.id,
            tool_name="provider_dispatch",
            tool_class="provider",
            input_summary=user_message[:500],
            result_summary=exc.user_message,
            duration_ms=None,
            exit_code=None,
            was_denied=True,
            denial_reason=exc.blocked_reason,
        )
        await CodeEventService.append_event(
            db,
            session_id=session.id,
            event_type="code.session.failed",
            payload={
                "session_status": session.session_status,
                "reason": exc.blocked_reason,
                "detail": str(exc),
                "user_message": exc.user_message,
                "retry_after_seconds": exc.retry_after_seconds,
                "phase": "execution",
                **self._failure_contract(
                    blocked_reason=exc.blocked_reason,
                    retry_after_seconds=exc.retry_after_seconds,
                ),
            },
        )
        if session.session_status in {SESSION_STATUS_BLOCKED, SESSION_STATUS_FAILED, SESSION_STATUS_TRUST_REQUIRED}:
            workspace = await CodeWorkspaceService.get_workspace(db, tenant_id=session.tenant_id)
            user_result = await db.execute(select(User).where(User.id == session.user_id))
            user = user_result.scalar_one_or_none()
            if workspace is not None and user is not None:
                if exc.blocked_reason in {"provider_cooldown", "provider_error"}:
                    cooldown_seconds = exc.retry_after_seconds if exc.retry_after_seconds is not None else 120
                    await CodeRuntimeService.record_provider_backpressure(
                        db,
                        workspace_id=workspace.id,
                        failure_class=exc.blocked_reason,
                        cooldown_until=datetime.now(UTC) + timedelta(seconds=cooldown_seconds),
                        recorded_at=datetime.now(UTC),
                    )
                from app.services.code.recovery_loop_service import CodeRecoveryLoopService

                recovery_task = await CodeRecoveryLoopService.ensure_recovery_task(
                    db,
                    workspace=workspace,
                    user=user,
                    session=session,
                    failure_class=exc.blocked_reason or "provider_error",
                    origin="session_failure",
                    summary=exc.user_message,
                    checklist=self._failure_contract(
                        blocked_reason=exc.blocked_reason,
                        retry_after_seconds=exc.retry_after_seconds,
                    ).get("recommended_actions", []),
                )
                await CodeRecoveryLoopService.ensure_postmortem_reflection(
                    db,
                    workspace=workspace,
                    session=session,
                    user=user,
                    trigger_source="session_failure",
                    task_id=recovery_task.id,
                )
        await db.flush()
        return turn, exc.user_message

    async def complete_turn(
        self,
        db: AsyncSession,
        *,
        session: CodeSession,
        turn: CodeTurn,
        user_message: str,
        output_text: str,
        usage: dict[str, int] | None = None,
        estimated_cost: float | None = None,
        blocked_reason: str | None = None,
    ) -> tuple[CodeTurn, str]:
        turn.assistant_summary = output_text or "Provider returned no text output."
        turn.turn_status = "completed"
        if usage is not None:
            session.token_usage = usage
        if estimated_cost is not None:
            session.estimated_cost = estimated_cost
        if blocked_reason == "trust_required":
            session.session_status = SESSION_STATUS_TRUST_REQUIRED
        else:
            session.session_status = SESSION_STATUS_BLOCKED if blocked_reason else SESSION_STATUS_READY_FOR_PROMPT

        await self.record_tool_call(
            db,
            session_id=session.id,
            turn_id=turn.id,
            tool_name="provider_dispatch",
            tool_class="provider",
            input_summary=user_message[:500],
            result_summary=turn.assistant_summary,
            duration_ms=None,
            exit_code=None,
            was_denied=blocked_reason is not None,
            denial_reason=blocked_reason,
        )
        await self.record_diff_artifact(
            db,
            session=session,
            changed_files=[],
            diff_summary=output_text[:2000],
        )

        await CodeEventService.append_event(
            db,
            session_id=session.id,
            event_type="code.session.status",
            payload=self._status_event_payload(
                session_status=session.session_status,
                headline="Turn completed and the session is ready for the next prompt."
                if blocked_reason is None
                else "Turn completed but the session is blocked pending recovery.",
                phase="turn_complete",
                recommended_actions=[
                    "Send the next prompt when you are ready."
                ]
                if blocked_reason is None
                else self._failure_contract(blocked_reason=blocked_reason).get("recommended_actions", []),
                extra={
                    "blocked_reason": blocked_reason,
                    "turn_id": turn.id,
                    **(
                        {}
                        if blocked_reason is None
                        else {
                            "failure_class": self._failure_contract(blocked_reason=blocked_reason).get("failure_class"),
                        }
                    ),
                },
            ),
        )
        runtime = await CodeRuntimeService.ensure_runtime_state(db, workspace_id=session.workspace_id)
        CodeProviderBudgetService.record_dispatch(
            runtime,
            estimated_cost=estimated_cost,
            now=datetime.now(UTC),
        )
        await CodeMemoryService.touch_runtime_on_turn(db, session=session)
        await CodeRuntimeService.clear_provider_backpressure(
            db,
            workspace_id=session.workspace_id,
            cleared_at=datetime.now(UTC),
        )
        await CodeMemoryService.refresh_snapshot(db, session=session, force=False)
        if await CodeReflectionService.should_trigger_background_review(
            db,
            session_id=session.id,
            trigger_source="turn_complete",
        ):
            user_result = await db.execute(select(User).where(User.id == session.user_id))
            user = user_result.scalar_one_or_none()
            workspace = await CodeWorkspaceService.get_workspace(db, tenant_id=session.tenant_id)
            if user is not None and workspace is not None:
                await CodeReflectionService.run_reflection(
                    db,
                    workspace=workspace,
                    session=session,
                    user=user,
                    trigger_source="turn_complete",
                )
        await db.flush()
        return turn, turn.assistant_summary

    async def create_turn(
        self,
        db: AsyncSession,
        *,
        session: CodeSession,
        user_message: str,
        prompt_prelude: str | None = None,
    ) -> tuple[CodeTurn, str]:
        turn, prompt = await self.initialize_turn(
            db,
            session=session,
            user_message=user_message,
            prompt_prelude=prompt_prelude,
        )
        runtime = await CodeRuntimeService.ensure_runtime_state(db, workspace_id=session.workspace_id)
        budget_decision = CodeProviderBudgetService.evaluate(runtime)
        if not budget_decision.allowed:
            CodeProviderBudgetService.record_pause(
                runtime,
                resume_at=budget_decision.resume_at or (datetime.now(UTC) + timedelta(seconds=settings.BOS_CODE_PROVIDER_BUDGET_COOLDOWN_SEC)),
            )
            await CodeRuntimeService.record_provider_budget_pause(
                db,
                workspace_id=session.workspace_id,
                pause_until=budget_decision.resume_at or (datetime.now(UTC) + timedelta(seconds=settings.BOS_CODE_PROVIDER_BUDGET_COOLDOWN_SEC)),
                recorded_at=datetime.now(UTC),
            )
            exc = CodeProviderError(
                budget_decision.headline,
                blocked_reason=budget_decision.blocked_reason or "provider_budget_paused",
                user_message=budget_decision.headline,
                retry_after_seconds=settings.BOS_CODE_PROVIDER_BUDGET_COOLDOWN_SEC,
            )
            return await self.fail_turn(db, session=session, turn=turn, user_message=user_message, exc=exc)

        try:
            provider_response = await self.provider.run(
                ProviderRequest(
                    session_id=session.id,
                    prompt=prompt,
                    model=session.model,
                    provider=session.provider,
                    permission_mode=session.permission_mode,
                    tool_names=["read_file", "glob_search", "grep_search", "safe_bash", "git_ops"],
                )
            )
        except CodeProviderError as exc:
            return await self.fail_turn(db, session=session, turn=turn, user_message=user_message, exc=exc)
        return await self.complete_turn(
            db,
            session=session,
            turn=turn,
            user_message=user_message,
            output_text=provider_response.output_text,
            usage=provider_response.usage,
            estimated_cost=provider_response.estimated_cost,
            blocked_reason=provider_response.blocked_reason,
        )

    async def cancel_session(self, db: AsyncSession, *, session: CodeSession, reason: str | None = None) -> CodeSession:
        session.session_status = "cancelled"
        lease_result = await db.execute(select(CodeWorkspaceLease).where(CodeWorkspaceLease.active_session_id == session.id))
        lease = lease_result.scalar_one_or_none()
        if lease is not None:
            lease.lease_status = "available"
            lease.active_session_id = None
            lease.lease_owner_user_id = None
            lease.lease_expires_at = None
            lease.heartbeat_at = datetime.now(UTC)
        await CodeEventService.append_event(
            db,
            session_id=session.id,
            event_type="code.session.failed",
            payload={"session_status": "cancelled", "reason": reason},
        )
        if lease is not None:
            await CodeEventService.append_event(
                db,
                session_id=session.id,
                event_type="code.workspace.lease_changed",
                payload={"workspace_id": session.workspace_id, "lease_status": "available"},
            )
        await db.flush()
        return session

    async def record_tool_call(
        self,
        db: AsyncSession,
        *,
        session_id: int,
        turn_id: int | None,
        tool_name: str,
        tool_class: str,
        input_summary: str | None,
        result_summary: str | None,
        duration_ms: float | None = None,
        exit_code: int | None = None,
        was_denied: bool = False,
        denial_reason: str | None = None,
    ) -> CodeToolCall:
        tool_call = CodeToolCall(
            session_id=session_id,
            turn_id=turn_id,
            tool_name=tool_name,
            tool_class=tool_class,
            input_summary=input_summary,
            result_summary=result_summary,
            duration_ms=duration_ms,
            exit_code=exit_code,
            was_denied=was_denied,
            denial_reason=denial_reason,
        )
        db.add(tool_call)
        await db.flush()
        return tool_call

    async def record_diff_artifact(
        self,
        db: AsyncSession,
        *,
        session: CodeSession,
        changed_files: list[str],
        diff_summary: str,
    ) -> CodeArtifact:
        artifact = CodeArtifact(
            session_id=session.id,
            artifact_type="diff",
            changed_files=changed_files,
            diff_summary=diff_summary,
            verification_summary={"status": session.verification_status},
        )
        db.add(artifact)
        await CodeEventService.append_event(
            db,
            session_id=session.id,
            event_type="code.diff.ready",
            payload={"changed_files": changed_files, "diff_summary": diff_summary},
        )
        await db.flush()
        return artifact

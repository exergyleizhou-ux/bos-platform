"""
Minimal LSP lifecycle and diagnostics/symbols service for BOS Code v2.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.models import CodeLspSession, CodeWorkspace

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class CodeLspService:
    @staticmethod
    async def ensure_session(
        db: AsyncSession,
        *,
        workspace: CodeWorkspace,
        language: str,
        server_name: str,
    ) -> CodeLspSession:
        result = await db.execute(
            select(CodeLspSession).where(
                CodeLspSession.workspace_id == workspace.id,
                CodeLspSession.language == language,
            )
        )
        lsp_session = result.scalar_one_or_none()
        if lsp_session is None:
            lsp_session = CodeLspSession(
                workspace_id=workspace.id,
                language=language,
                server_name=server_name,
                status="idle",
                root_uri=workspace.worktree_root,
            )
            db.add(lsp_session)
            await db.flush()
        return lsp_session

    @staticmethod
    async def get_diagnostics(
        db: AsyncSession,
        *,
        workspace: CodeWorkspace,
        language: str = "python",
    ) -> tuple[CodeLspSession, list[dict]]:
        lsp_session = await CodeLspService.ensure_session(
            db,
            workspace=workspace,
            language=language,
            server_name=f"{language}-stub-lsp",
        )
        lsp_session.status = "ready"
        lsp_session.error_message = None
        lsp_session.last_heartbeat_at = datetime.now(UTC)

        diagnostics = [
            {
                "path": "backend/app/services/code/session_service.py",
                "severity": "info",
                "message": "Session service diagnostics are running in synthetic v2 mode.",
                "line": 1,
                "code": "bos.lsp.synthetic",
            }
        ]
        await db.flush()
        return lsp_session, diagnostics

    @staticmethod
    async def get_symbols(
        db: AsyncSession,
        *,
        workspace: CodeWorkspace,
        language: str = "python",
    ) -> tuple[CodeLspSession, list[dict]]:
        lsp_session = await CodeLspService.ensure_session(
            db,
            workspace=workspace,
            language=language,
            server_name=f"{language}-stub-lsp",
        )
        lsp_session.status = "ready"
        lsp_session.error_message = None
        lsp_session.last_heartbeat_at = datetime.now(UTC)

        symbols = [
            {
                "name": "CodeSessionService",
                "kind": "class",
                "path": "backend/app/services/code/session_service.py",
            },
            {
                "name": "CodeVerificationService",
                "kind": "class",
                "path": "backend/app/services/code/verification_service.py",
            },
        ]
        await db.flush()
        return lsp_session, symbols

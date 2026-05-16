"""
Minimal MCP lifecycle service for BOS Code v2.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CodeMcpServer, CodeWorkspace


class CodeMcpService:
    @staticmethod
    def _server_capabilities(
        *,
        resources: bool,
        tools: bool,
        startup_phase: str,
        discovery_status: str,
        resource_count: int,
        tool_count: int,
        failure_class: str | None = None,
        degraded_scope: str | None = None,
        recovery_recommendations: list[str] | None = None,
    ) -> dict:
        capabilities = {
            "resources": resources,
            "tools": tools,
            "startup_phase": startup_phase,
            "discovery_status": discovery_status,
            "resource_count": resource_count,
            "tool_count": tool_count,
            "recovery_recommendations": recovery_recommendations or [],
        }
        if failure_class:
            capabilities["failure_class"] = failure_class
        if degraded_scope:
            capabilities["degraded_scope"] = degraded_scope
        return capabilities

    @staticmethod
    async def list_servers(db: AsyncSession, *, workspace_id: int) -> list[CodeMcpServer]:
        result = await db.execute(
            select(CodeMcpServer).where(CodeMcpServer.workspace_id == workspace_id).order_by(CodeMcpServer.server_name.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def connect_server(
        db: AsyncSession,
        *,
        workspace: CodeWorkspace,
        tenant_id: int,
        server_name: str,
        transport: str,
    ) -> CodeMcpServer:
        result = await db.execute(
            select(CodeMcpServer).where(
                CodeMcpServer.workspace_id == workspace.id,
                CodeMcpServer.server_name == server_name,
            )
        )
        server = result.scalar_one_or_none()
        if server is None:
            server = CodeMcpServer(
                tenant_id=tenant_id,
                workspace_id=workspace.id,
                server_name=server_name,
                transport=transport,
            )
            db.add(server)

        server.transport = transport
        if server_name == "demo":
            server.connection_status = "connected"
            server.capabilities = CodeMcpService._server_capabilities(
                resources=True,
                tools=False,
                startup_phase="ready",
                discovery_status="completed",
                resource_count=2,
                tool_count=0,
                recovery_recommendations=["Inspect workspace and verification summary resources when you need context."],
            )
            server.error_message = None
            server.last_connected_at = datetime.now(UTC)
        elif server_name == "auth-demo":
            server.connection_status = "auth_required"
            server.capabilities = CodeMcpService._server_capabilities(
                resources=True,
                tools=False,
                startup_phase="auth_gate",
                discovery_status="blocked",
                resource_count=0,
                tool_count=0,
                failure_class="trust_gate",
                degraded_scope="authentication",
                recovery_recommendations=[
                    "Authenticate the MCP server before expecting resource discovery.",
                    "Keep the connector visible, but do not treat it as usable until auth clears.",
                ],
            )
            server.error_message = "Authentication required for auth-demo."
        else:
            server.connection_status = "degraded"
            server.capabilities = CodeMcpService._server_capabilities(
                resources=False,
                tools=False,
                startup_phase="degraded_startup",
                discovery_status="failed",
                resource_count=0,
                tool_count=0,
                failure_class="mcp_startup",
                degraded_scope="server_registration",
                recovery_recommendations=[
                    "Inspect the server registration and transport configuration.",
                    "Reconnect after the startup error is resolved.",
                ],
            )
            server.error_message = f"Server '{server_name}' is registered in degraded mode."
        await db.flush()
        return server

    @staticmethod
    async def disconnect_server(
        db: AsyncSession,
        *,
        workspace_id: int,
        server_name: str,
    ) -> CodeMcpServer | None:
        result = await db.execute(
            select(CodeMcpServer).where(
                CodeMcpServer.workspace_id == workspace_id,
                CodeMcpServer.server_name == server_name,
            )
        )
        server = result.scalar_one_or_none()
        if server is None:
            return None
        server.connection_status = "disconnected"
        server.capabilities = CodeMcpService._server_capabilities(
            resources=False,
            tools=False,
            startup_phase="disconnected",
            discovery_status="idle",
            resource_count=0,
            tool_count=0,
            recovery_recommendations=["Reconnect the server when you want MCP resources back in scope."],
        )
        server.error_message = None
        await db.flush()
        return server

    @staticmethod
    async def list_resources(
        db: AsyncSession,
        *,
        workspace_id: int,
        server_name: str,
    ) -> list[dict]:
        result = await db.execute(
            select(CodeMcpServer).where(
                CodeMcpServer.workspace_id == workspace_id,
                CodeMcpServer.server_name == server_name,
            )
        )
        server = result.scalar_one_or_none()
        if server is None:
            raise ValueError("mcp_server_not_found")
        if server.connection_status == "auth_required":
            raise PermissionError("mcp_auth_required")
        if server.connection_status != "connected":
            raise RuntimeError("mcp_server_not_connected")

        return [
            {
                "uri": f"mcp://{server_name}/workspace-summary",
                "name": "Workspace Summary",
                "description": "Synthetic MCP resource describing current BOS Code workspace posture.",
                "mime_type": "application/json",
            },
            {
                "uri": f"mcp://{server_name}/verification-summary",
                "name": "Verification Summary",
                "description": "Synthetic MCP resource describing verification posture.",
                "mime_type": "application/json",
            },
        ]

    @staticmethod
    async def read_resource(
        db: AsyncSession,
        *,
        workspace: CodeWorkspace,
        server_name: str,
        uri: str,
    ) -> dict:
        resources = await CodeMcpService.list_resources(db, workspace_id=workspace.id, server_name=server_name)
        resource = next((item for item in resources if item["uri"] == uri), None)
        if resource is None:
            raise ValueError("mcp_resource_not_found")

        if uri.endswith("workspace-summary"):
            return {
                "uri": uri,
                "contents": {
                    "workspace_status": workspace.workspace_status,
                    "active_branch": workspace.active_branch,
                    "dirty_state": workspace.dirty_state,
                },
            }
        return {
            "uri": uri,
            "contents": {
                "workspace_status": workspace.workspace_status,
                "message": "Verification summary MCP stub.",
            },
        }

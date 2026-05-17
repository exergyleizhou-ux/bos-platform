import pytest
import asyncio
from httpx import AsyncClient

pytestmark = pytest.mark.skip(
    reason="legacy-deferred per Phase 0.5/D5 - Code Cockpit subsystem deferred"
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.main import app
from app.models import CodeBranchState, CodeReflectionRun, CodeSession, CodeSubagentRun, CodeTask, CodeToolCall, CodeVerificationRun, User
from app.routers.auth import pwd_context
from app.routers.code import session_service as code_router_session_service, subagent_service as code_router_subagent_service
from app.services.code.providers import OpenAICodexProvider
from app.services.feature_flags import set_db_override
from tests.conftest import TestSessionLocal


async def _enable_bos_code(db_session: AsyncSession, user: User) -> None:
    await set_db_override(
        db_session,
        flag_name="bos_code",
        tenant_id=user.tenant_id,
        enabled=True,
    )


@pytest.fixture(autouse=True)
def _force_stub_provider_for_code_router_integration():
    original_provider = code_router_session_service.provider
    original_subagent_provider = code_router_subagent_service.provider
    code_router_session_service.provider = OpenAICodexProvider(enabled=False)
    code_router_subagent_service.provider = OpenAICodexProvider(enabled=False)
    try:
        yield
    finally:
        code_router_session_service.provider = original_provider
        code_router_subagent_service.provider = original_subagent_provider


class TestCodeRouter:
    @pytest.mark.asyncio
    async def test_workspace_init_and_status(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        operator_user: User,
        operator_headers: dict[str, str],
    ):
        await _enable_bos_code(db_session, operator_user)

        init_response = await client.post("/api/v1/code/workspace/init", json={}, headers=operator_headers)
        assert init_response.status_code == 201
        init_body = init_response.json()
        assert init_body["tenant_id"] == operator_user.tenant_id
        assert init_body["base_branch"] == f"boscode/tenant-{operator_user.tenant_id}/base"

        tree_response = await client.get(
            "/api/v1/code/workspace/tree",
            params={"path": "."},
            headers=operator_headers,
        )
        assert tree_response.status_code == 200
        tree_items = tree_response.json()["items"]
        assert any(item["name"] == "app" and item["node_type"] == "directory" for item in tree_items)

        status_response = await client.get("/api/v1/code/workspace/status", headers=operator_headers)
        assert status_response.status_code == 200
        status_body = status_response.json()
        assert status_body["workspace"]["workspace_status"] == "ready"
        assert status_body["permission_mode"] == "read-only"

        session_response = await client.post(
            "/api/v1/code/sessions",
            json={"acquire_write_lease": False},
            headers=operator_headers,
        )
        assert session_response.status_code == 201
        session_id = session_response.json()["id"]

        branch_state_response = await client.get(
            f"/api/v1/code/sessions/{session_id}/git/branch-state",
            headers=operator_headers,
        )
        assert branch_state_response.status_code == 200
        branch_state_body = branch_state_response.json()
        assert branch_state_body["branch_name"] == f"boscode/tenant-{operator_user.tenant_id}/session-{session_id}"
        assert branch_state_body["branch_status"] in {"clean", "degraded", "dirty", "stale"}

        readiness_response = await client.get(
            f"/api/v1/code/sessions/{session_id}/readiness",
            headers=operator_headers,
        )
        assert readiness_response.status_code == 200
        readiness_body = readiness_response.json()
        assert readiness_body["session_id"] == session_id
        assert readiness_body["readiness"] in {"ready", "blocked", "degraded", "merge_ready", "needs_recovery"}

        workers_response = await client.get(
            "/api/v1/code/workspace/workers",
            headers=operator_headers,
        )
        assert workers_response.status_code == 200
        workers_body = workers_response.json()
        assert len(workers_body) >= 3
        assert {worker["worker_name"] for worker in workers_body} >= {"architect", "executor", "reviewer"}
        reviewer_worker = next(worker for worker in workers_body if worker["worker_name"] == "reviewer")
        assert "mark_reviewer_blocked" in reviewer_worker["allowed_actions"]
        assert reviewer_worker["allowed_action_policies"]["mark_reviewer_blocked"] == "automation_safe"

        orchestration_response = await client.get(
            "/api/v1/code/workspace/orchestration",
            headers=operator_headers,
        )
        assert orchestration_response.status_code == 200
        orchestration_body = orchestration_response.json()
        assert orchestration_body["totals"]["workers"] >= 3
        assert orchestration_body["focus_task_id"] is None
        assert isinstance(orchestration_body["automation_actions"], list)
        assert isinstance(orchestration_body["automation_blockers"], list)
        assert isinstance(orchestration_body["automation_ready"], bool)
        assert orchestration_body["next_automation_action"] in {None, *orchestration_body["automation_actions"]}
        lane_names = {lane["lane"] for lane in orchestration_body["lanes"]}
        assert {"architect", "executor", "reviewer"}.issubset(lane_names)

    @pytest.mark.asyncio
    async def test_session_create_turn_and_events(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        scientist_user: User,
        scientist_headers: dict[str, str],
    ):
        await _enable_bos_code(db_session, scientist_user)

        await client.post("/api/v1/code/workspace/init", json={}, headers=scientist_headers)

        session_response = await client.post(
            "/api/v1/code/sessions",
            json={"acquire_write_lease": True},
            headers=scientist_headers,
        )
        assert session_response.status_code == 201
        session_body = session_response.json()
        session_id = session_body["id"]
        assert session_body["session_status"] == "ready_for_prompt"
        assert session_body["verification_status"] == "pending"

        turn_response = await client.post(
            f"/api/v1/code/sessions/{session_id}/turns",
            json={"user_message": "Summarize the current workspace posture.", "stream": True},
            headers=scientist_headers,
        )
        assert turn_response.status_code == 200
        turn_body = turn_response.json()
        assert turn_body["turn_index"] == 1
        assert turn_body["turn_status"] == "completed"

        events_response = await client.get(
            f"/api/v1/code/sessions/{session_id}/events",
            headers=scientist_headers,
        )
        assert events_response.status_code == 200
        events_body = events_response.json()
        assert len(events_body["items"]) >= 2
        assert events_body["next_seq"] is not None
        session_status_events = [
            item for item in events_body["items"] if item["event_type"] == "code.session.status"
        ]
        assert session_status_events
        assert any(
            item["payload"].get("session_status") == "ready_for_prompt"
            for item in session_status_events
        )
        assert any(
            item["payload"].get("session_status") in {"prompt_accepted", "running"}
            for item in session_status_events
        )

        verification_response = await client.get(
            f"/api/v1/code/sessions/{session_id}/verification",
            headers=scientist_headers,
        )
        assert verification_response.status_code == 200
        verification_body = verification_response.json()
        assert len(verification_body["stages"]) == 5

        run_verification_response = await client.post(
            f"/api/v1/code/sessions/{session_id}/verification/run",
            json={"stage": "lint", "stop_on_failure": True},
            headers=scientist_headers,
        )
        assert run_verification_response.status_code == 200
        run_verification_body = run_verification_response.json()
        stage_map = {item["verification_stage"]: item for item in run_verification_body["stages"]}
        assert stage_map["lint"]["verification_status"] in {"passed", "failed"}

        pipeline_response = await client.post(
            f"/api/v1/code/sessions/{session_id}/verification/run",
            json={"stop_on_failure": True},
            headers=scientist_headers,
        )
        assert pipeline_response.status_code == 200
        pipeline_body = pipeline_response.json()
        assert len(pipeline_body["stages"]) == 5

        diff_response = await client.get(
            f"/api/v1/code/sessions/{session_id}/diff",
            headers=scientist_headers,
        )
        assert diff_response.status_code == 200
        diff_body = diff_response.json()
        assert diff_body["session_id"] == session_id
        assert diff_body["diff_summary"] is not None

        artifact_response = await client.get(
            f"/api/v1/code/sessions/{session_id}/artifacts",
            headers=scientist_headers,
        )
        assert artifact_response.status_code == 200
        artifact_body = artifact_response.json()
        assert len(artifact_body) >= 1

        cancel_response = await client.post(
            f"/api/v1/code/sessions/{session_id}/cancel",
            json={"reason": "test_cancel"},
            headers=scientist_headers,
        )
        assert cancel_response.status_code == 200
        cancel_body = cancel_response.json()
        assert cancel_body["session_status"] == "cancelled"

        status_response = await client.get("/api/v1/code/workspace/status", headers=scientist_headers)
        assert status_response.status_code == 200
        status_body = status_response.json()
        assert status_body["lease"]["lease_status"] == "available"

    @pytest.mark.asyncio
    async def test_runtime_memory_reflection_and_skill_endpoints(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        scientist_user: User,
        scientist_headers: dict[str, str],
    ):
        await _enable_bos_code(db_session, scientist_user)
        await client.post("/api/v1/code/workspace/init", json={}, headers=scientist_headers)

        session_response = await client.post(
            "/api/v1/code/sessions",
            json={"acquire_write_lease": False},
            headers=scientist_headers,
        )
        session_id = session_response.json()["id"]

        create_job_response = await client.post(
            "/api/v1/code/workspace/automations",
            json={
                "name": "heartbeat-review",
                "job_type": "heartbeat",
                "schedule_kind": "manual",
                "enabled": True,
                "prompt_template": "[system automation] Review BOS Code posture.",
            },
            headers=scientist_headers,
        )
        assert create_job_response.status_code == 201
        job_id = create_job_response.json()["id"]

        run_job_response = await client.post(
            f"/api/v1/code/workspace/automations/{job_id}/run",
            headers=scientist_headers,
        )
        assert run_job_response.status_code == 200

        runtime_response = await client.get(
            "/api/v1/code/workspace/runtime",
            headers=scientist_headers,
        )
        assert runtime_response.status_code == 200
        runtime_body = runtime_response.json()
        assert runtime_body["runtime_state"]["workspace_id"] > 0
        assert isinstance(runtime_body["automation_jobs"], list)
        assert isinstance(runtime_body["available_providers"], list)
        heartbeat_artifact = runtime_body["runtime_state"]["runtime_metrics"]["last_run_ledger_artifact"]
        assert heartbeat_artifact["target_surface"] == "orchestrator"
        assert heartbeat_artifact["target_route"] == "/bos/orchestrator"
        assert heartbeat_artifact["slice"].startswith("BOS Code heartbeat:")

        refresh_memory_response = await client.post(
            f"/api/v1/code/memory/{session_id}/refresh",
            headers=scientist_headers,
        )
        assert refresh_memory_response.status_code == 200
        snapshot_id = refresh_memory_response.json()["snapshot"]["id"]
        assert snapshot_id > 0

        reflection_response = await client.post(
            "/api/v1/code/workspace/reflections/run",
            json={"session_id": session_id, "trigger_source": "manual"},
            headers=scientist_headers,
        )
        assert reflection_response.status_code == 200
        reflection_body = reflection_response.json()
        assert reflection_body["reflection_status"] == "completed"

        runtime_after_reflection_response = await client.get(
            "/api/v1/code/workspace/runtime",
            headers=scientist_headers,
        )
        assert runtime_after_reflection_response.status_code == 200
        runtime_after_reflection = runtime_after_reflection_response.json()
        reflection_artifact = runtime_after_reflection["runtime_state"]["runtime_metrics"]["last_run_ledger_artifact"]
        assert reflection_artifact["target_surface"] == "brain"
        assert reflection_artifact["target_route"] == "/bos/brain"
        assert reflection_artifact["slice"] == "BOS Code reflection review"

        list_reflections_response = await client.get(
            "/api/v1/code/workspace/reflections",
            headers=scientist_headers,
        )
        assert list_reflections_response.status_code == 200
        assert len(list_reflections_response.json()) >= 1

        list_skills_response = await client.get(
            "/api/v1/code/workspace/skills",
            headers=scientist_headers,
        )
        assert list_skills_response.status_code == 200
        assert isinstance(list_skills_response.json(), list)
        if list_skills_response.json():
            skill_id = list_skills_response.json()[0]["id"]
            feedback_response = await client.post(
                f"/api/v1/code/workspace/skills/{skill_id}/feedback",
                json={"sentiment": "positive"},
                headers=scientist_headers,
            )
            assert feedback_response.status_code == 200
            assert feedback_response.json()["positive_feedback_count"] >= 1

        session_search_response = await client.post(
            "/api/v1/code/session-search",
            json={"query": "review BOS Code posture", "limit": 3},
            headers=scientist_headers,
        )
        assert session_search_response.status_code == 200
        assert "results" in session_search_response.json()

    @pytest.mark.asyncio
    async def test_session_create_respects_provider_alias(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        scientist_user: User,
        scientist_headers: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ):
        from app.services.code.providers import settings as provider_settings

        monkeypatch.setattr(provider_settings, "OPENAI_API_KEY", "default-key")
        monkeypatch.setattr(provider_settings, "OPENAI_BASE_URL", "https://default.example/v1")
        monkeypatch.setattr(provider_settings, "OPENAI_PUBLIC_API_KEY", "public-key")
        monkeypatch.setattr(provider_settings, "OPENAI_PUBLIC_BASE_URL", "https://public.example/v1")
        monkeypatch.setattr(provider_settings, "OPENAI_TEAM_API_KEY", "team-key")
        monkeypatch.setattr(provider_settings, "OPENAI_TEAM_BASE_URL", "https://team.example/v1")

        await _enable_bos_code(db_session, scientist_user)
        await client.post("/api/v1/code/workspace/init", json={}, headers=scientist_headers)

        session_response = await client.post(
            "/api/v1/code/sessions",
            json={"acquire_write_lease": False, "provider": "openai-team", "model": "gpt-5.4"},
            headers=scientist_headers,
        )
        assert session_response.status_code == 201
        session_body = session_response.json()
        assert session_body["provider"] == "openai-team"
        assert session_body["model"] == "gpt-5.4"

        session_id = session_body["id"]
        turn_response = await client.post(
            f"/api/v1/code/sessions/{session_id}/turns",
            json={"user_message": "Switch to 5.5 for this thread.", "provider": "openai-team", "model": "gpt-5.5"},
            headers=scientist_headers,
        )
        assert turn_response.status_code == 200

        session_detail_response = await client.get(
            f"/api/v1/code/sessions/{session_id}",
            headers=scientist_headers,
        )
        assert session_detail_response.status_code == 200
        assert session_detail_response.json()["session"]["provider"] == "openai-team"
        assert session_detail_response.json()["session"]["model"] == "gpt-5.5"

    @pytest.mark.asyncio
    async def test_runtime_exposes_team_model_catalog(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        scientist_user: User,
        scientist_headers: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ):
        await _enable_bos_code(db_session, scientist_user)
        await client.post("/api/v1/code/workspace/init", json={}, headers=scientist_headers)

        async def _fake_team_models():
            return ["gpt-5.5", "gpt-5.4"]

        monkeypatch.setattr("app.routers.code.list_team_chat_models", _fake_team_models)

        runtime_response = await client.get(
            "/api/v1/code/workspace/runtime",
            headers=scientist_headers,
        )
        assert runtime_response.status_code == 200
        assert runtime_response.json()["team_models"] == ["gpt-5.5", "gpt-5.4"]

    @pytest.mark.asyncio
    async def test_workspace_init_seeds_default_runtime_jobs(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        scientist_user: User,
        scientist_headers: dict[str, str],
    ):
        await _enable_bos_code(db_session, scientist_user)

        init_response = await client.post("/api/v1/code/workspace/init", json={}, headers=scientist_headers)
        assert init_response.status_code == 201

        runtime_response = await client.get(
            "/api/v1/code/workspace/runtime",
            headers=scientist_headers,
        )
        assert runtime_response.status_code == 200
        runtime_body = runtime_response.json()
        job_names = {job["name"] for job in runtime_body["automation_jobs"]}
        assert {"heartbeat-monitor", "reflection-review"}.issubset(job_names)

    @pytest.mark.asyncio
    async def test_create_turn_can_trigger_background_reflection_when_session_is_complex(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        scientist_user: User,
        scientist_headers: dict[str, str],
    ):
        await _enable_bos_code(db_session, scientist_user)
        await client.post("/api/v1/code/workspace/init", json={}, headers=scientist_headers)

        session_response = await client.post(
            "/api/v1/code/sessions",
            json={"acquire_write_lease": False},
            headers=scientist_headers,
        )
        assert session_response.status_code == 201
        session_id = session_response.json()["id"]

        for tool_name in ("read_file", "safe_bash"):
            db_session.add(
                CodeToolCall(
                    session_id=session_id,
                    turn_id=None,
                    tool_name=tool_name,
                    tool_class="runtime",
                    input_summary=tool_name,
                    result_summary="seeded",
                )
            )
        await db_session.commit()

        turn_response = await client.post(
            f"/api/v1/code/sessions/{session_id}/turns",
            json={"user_message": "Carry this BOS Code task over the line.", "stream": True},
            headers=scientist_headers,
        )
        assert turn_response.status_code == 200

        reflections_result = await db_session.execute(
            select(CodeReflectionRun).where(CodeReflectionRun.session_id == session_id)
        )
        reflections = list(reflections_result.scalars().all())
        assert reflections
        assert reflections[-1].reflection_status == "completed"

    @pytest.mark.asyncio
    async def test_write_lease_conflict_is_rejected(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        scientist_user: User,
        scientist_headers: dict[str, str],
    ):
        await _enable_bos_code(db_session, scientist_user)
        await client.post("/api/v1/code/workspace/init", json={}, headers=scientist_headers)

        other_user = User(
            username="test_scientist_peer",
            email="test_scientist_peer@bos.io",
            full_name="Peer Scientist",
            hashed_password=pwd_context.hash("PeerScientist123!"),
            role="scientist",
            is_active=True,
            tenant_id=scientist_user.tenant_id,
        )
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)

        from app.routers.auth import create_access_token

        other_headers = {
            "Authorization": f"Bearer {create_access_token(other_user.id, other_user.role, other_user.tenant_id)}"
        }

        first_response = await client.post(
            "/api/v1/code/sessions",
            json={"acquire_write_lease": True},
            headers=scientist_headers,
        )
        assert first_response.status_code == 201

        second_response = await client.post(
            "/api/v1/code/sessions",
            json={"acquire_write_lease": True},
            headers=other_headers,
        )
        assert second_response.status_code == 409
        assert "lease" in second_response.json()["detail"]

    @pytest.mark.asyncio
    async def test_tool_endpoints_return_structured_results(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        operator_user: User,
        operator_headers: dict[str, str],
    ):
        await _enable_bos_code(db_session, operator_user)
        await client.post("/api/v1/code/workspace/init", json={}, headers=operator_headers)

        session_response = await client.post(
            "/api/v1/code/sessions",
            json={"acquire_write_lease": False},
            headers=operator_headers,
        )
        assert session_response.status_code == 201
        session_id = session_response.json()["id"]

        safe_bash_response = await client.post(
            f"/api/v1/code/sessions/{session_id}/tools/safe-bash",
            json={"command": "pwd"},
            headers=operator_headers,
        )
        assert safe_bash_response.status_code == 200
        safe_bash_body = safe_bash_response.json()
        assert safe_bash_body["tool_name"] == "safe_bash"
        assert "denied_reason" in safe_bash_body

        git_status_response = await client.get(
            f"/api/v1/code/sessions/{session_id}/git/status",
            headers=operator_headers,
        )
        assert git_status_response.status_code == 200
        git_status_body = git_status_response.json()
        assert git_status_body["session_id"] == session_id
        assert "success" in git_status_body

        denied_response = await client.post(
            f"/api/v1/code/sessions/{session_id}/tools/safe-bash",
            json={"command": "rm -rf ."},
            headers=operator_headers,
        )
        assert denied_response.status_code == 200
        denied_body = denied_response.json()
        assert denied_body["success"] is False
        assert denied_body["denied_reason"] == "unsafe_command"

        events_response = await client.get(
            f"/api/v1/code/sessions/{session_id}/events",
            headers=operator_headers,
        )
        assert events_response.status_code == 200
        event_types = [item["event_type"] for item in events_response.json()["items"]]
        assert "code.tool.finished" in event_types
        assert "code.permission.denied" in event_types

    @pytest.mark.asyncio
    async def test_mcp_minimal_lifecycle(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        scientist_user: User,
        scientist_headers: dict[str, str],
    ):
        await _enable_bos_code(db_session, scientist_user)
        await client.post("/api/v1/code/workspace/init", json={}, headers=scientist_headers)

        connect_response = await client.post(
            "/api/v1/code/workspace/mcp/servers/connect",
            json={"server_name": "demo", "transport": "stub"},
            headers=scientist_headers,
        )
        assert connect_response.status_code == 200
        connect_body = connect_response.json()
        assert connect_body["connection_status"] == "connected"

        list_response = await client.get(
            "/api/v1/code/workspace/mcp/servers",
            headers=scientist_headers,
        )
        assert list_response.status_code == 200
        list_body = list_response.json()
        assert any(server["server_name"] == "demo" for server in list_body)

        resources_response = await client.get(
            "/api/v1/code/workspace/mcp/resources",
            params={"server_name": "demo"},
            headers=scientist_headers,
        )
        assert resources_response.status_code == 200
        resources_body = resources_response.json()
        assert len(resources_body) >= 1

        resource_response = await client.get(
            "/api/v1/code/workspace/mcp/resource",
            params={"server_name": "demo", "uri": "mcp://demo/workspace-summary"},
            headers=scientist_headers,
        )
        assert resource_response.status_code == 200
        resource_body = resource_response.json()
        assert resource_body["uri"] == "mcp://demo/workspace-summary"

        auth_required_response = await client.post(
            "/api/v1/code/workspace/mcp/servers/connect",
            json={"server_name": "auth-demo", "transport": "stub"},
            headers=scientist_headers,
        )
        assert auth_required_response.status_code == 200
        assert auth_required_response.json()["connection_status"] == "auth_required"

        auth_read_response = await client.get(
            "/api/v1/code/workspace/mcp/resources",
            params={"server_name": "auth-demo"},
            headers=scientist_headers,
        )
        assert auth_read_response.status_code == 403

    @pytest.mark.asyncio
    async def test_lsp_minimal_contracts(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        operator_user: User,
        operator_headers: dict[str, str],
    ):
        await _enable_bos_code(db_session, operator_user)
        await client.post("/api/v1/code/workspace/init", json={}, headers=operator_headers)

        diagnostics_response = await client.get(
            "/api/v1/code/workspace/lsp/diagnostics",
            params={"language": "python"},
            headers=operator_headers,
        )
        assert diagnostics_response.status_code == 200
        diagnostics_body = diagnostics_response.json()
        assert diagnostics_body["session"]["status"] in {"idle", "starting", "ready", "degraded", "failed"}
        assert len(diagnostics_body["diagnostics"]) >= 1

        symbols_response = await client.get(
            "/api/v1/code/workspace/lsp/symbols",
            params={"language": "python"},
            headers=operator_headers,
        )
        assert symbols_response.status_code == 200
        symbols_body = symbols_response.json()
        assert symbols_body["session"]["language"] == "python"
        assert len(symbols_body["symbols"]) >= 1

    @pytest.mark.asyncio
    async def test_task_and_worker_foundations(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        scientist_user: User,
        scientist_headers: dict[str, str],
    ):
        await _enable_bos_code(db_session, scientist_user)
        await client.post("/api/v1/code/workspace/init", json={}, headers=scientist_headers)

        session_response = await client.post(
            "/api/v1/code/sessions",
            json={"acquire_write_lease": False},
            headers=scientist_headers,
        )
        session_id = session_response.json()["id"]

        task_response = await client.post(
            "/api/v1/code/workspace/tasks",
            json={
                "title": "Stabilize BOS Code worker flow",
                "objective": "Prepare a structured worker/task foundation for v3 orchestration.",
                "scope": "code/runtime/tasking",
                "session_id": session_id,
            },
            headers=scientist_headers,
        )
        assert task_response.status_code == 201
        task_body = task_response.json()
        assert task_body["title"] == "Stabilize BOS Code worker flow"
        assert task_body["session_id"] == session_id
        assert task_body["task_status"] == "created"

        tasks_response = await client.get(
            "/api/v1/code/workspace/tasks",
            headers=scientist_headers,
        )
        assert tasks_response.status_code == 200
        assert len(tasks_response.json()) >= 1

        workers_response = await client.get(
            "/api/v1/code/workspace/workers",
            headers=scientist_headers,
        )
        assert workers_response.status_code == 200
        workers_body = workers_response.json()
        assert len(workers_body) >= 3
        assert any(worker["worker_name"] == "executor" for worker in workers_body)
        assert all(isinstance(worker["allowed_action_policies"], dict) for worker in workers_body)

        architect_plan_response = await client.post(
            f"/api/v1/code/workspace/tasks/{task_body['id']}/architect-plan",
            json={
                "regenerate": True,
                "summary": "Architect drafted acceptance criteria and suggested executor routing.",
            },
            headers=scientist_headers,
        )
        assert architect_plan_response.status_code == 200
        architect_plan_body = architect_plan_response.json()
        assert architect_plan_body["route_to"] == "executor"
        assert architect_plan_body["task"]["task_status"] == "created"
        assert len(architect_plan_body["acceptance_criteria"]) >= 4

        architect_route_response = await client.post(
            f"/api/v1/code/workspace/tasks/{task_body['id']}/architect-route",
            json={
                "acceptance_criteria": architect_plan_body["acceptance_criteria"],
                "summary": "Architect decomposed and routed the task to executor.",
                "route_to": "executor",
            },
            headers=scientist_headers,
        )
        assert architect_route_response.status_code == 200
        architect_route_body = architect_route_response.json()
        assert architect_route_body["task_status"] in {"running", "review_pending"}
        assert architect_route_body["acceptance_criteria"] == architect_plan_body["acceptance_criteria"]

        subagent_runs_result = await db_session.execute(
            select(CodeSubagentRun).where(CodeSubagentRun.task_id == task_body["id"])
        )
        subagent_runs = list(subagent_runs_result.scalars().all())
        assert subagent_runs
        assert len(subagent_runs) >= 3
        assert subagent_runs[-1].run_status in {"completed", "failed"}

        task_refresh_response = await client.get(
            "/api/v1/code/workspace/tasks",
            headers=scientist_headers,
        )
        refreshed_task = next(item for item in task_refresh_response.json() if item["id"] == task_body["id"])
        if refreshed_task["task_status"] == "running":
            review_request_response = await client.post(
                f"/api/v1/code/workspace/tasks/{task_body['id']}/review-request",
                json={"summary": "Executor submitted implementation for review."},
                headers=scientist_headers,
            )
            assert review_request_response.status_code == 200
            assert review_request_response.json()["task_status"] == "review_pending"

        begin_review_response = await client.post(
            "/api/v1/code/workspace/workers/reviewer/status",
            json={
                "worker_status": "running",
                "last_event_summary": f"Reviewer is actively evaluating task #{task_body['id']}.",
                "lane": "reviewer",
                "event_name": "lane.progressed",
                "payload": {"task_id": task_body["id"], "review_state": "in_review"},
            },
            headers=scientist_headers,
        )
        assert begin_review_response.status_code == 200

        reject_response = await client.post(
            f"/api/v1/code/workspace/tasks/{task_body['id']}/review-decision",
            json={
                "decision": "reject",
                "summary": "Reviewer rejected the implementation.",
                "reason": "Please revise.",
                "reason_code": "changes_requested",
                "checklist": ["Refresh verification", "Tighten event schema"],
            },
            headers=scientist_headers,
        )
        assert reject_response.status_code == 200
        assert reject_response.json()["task_status"] == "running"

        second_review_request_response = await client.post(
            f"/api/v1/code/workspace/tasks/{task_body['id']}/review-request",
            json={"summary": "Executor resubmitted implementation for review."},
            headers=scientist_headers,
        )
        assert second_review_request_response.status_code == 200
        assert second_review_request_response.json()["task_status"] == "review_pending"

        accept_response = await client.post(
            f"/api/v1/code/workspace/tasks/{task_body['id']}/review-decision",
            json={"decision": "accept", "summary": "Reviewer accepted the implementation."},
            headers=scientist_headers,
        )
        assert accept_response.status_code == 200
        assert accept_response.json()["task_status"] == "verification_pending"

        orchestration_gate_response = await client.get(
            "/api/v1/code/workspace/orchestration",
            headers=scientist_headers,
        )
        assert orchestration_gate_response.status_code == 200
        orchestration_gate_body = orchestration_gate_response.json()
        assert orchestration_gate_body["verification_gate"] in {"pending", "running"}
        assert "verification_pending" in orchestration_gate_body["merge_blockers"]
        assert orchestration_gate_body["operator_posture"] in {"verification_gate", "recovery_required", "pending"}
        assert len(orchestration_gate_body["operator_actions"]) >= 1
        assert isinstance(orchestration_gate_body["operator_action_policies"], dict)
        assert isinstance(orchestration_gate_body["operator_action_classes"], dict)
        assert orchestration_gate_body["operator_action_policies"] == orchestration_gate_body["operator_action_classes"]
        assert isinstance(orchestration_gate_body["automation_actions"], list)
        assert isinstance(orchestration_gate_body["human_actions"], list)
        assert isinstance(orchestration_gate_body["review_gated_actions"], list)
        assert isinstance(orchestration_gate_body["automation_blockers"], list)
        assert isinstance(orchestration_gate_body["automation_ready"], bool)
        assert isinstance(orchestration_gate_body["automation_summary"], str)
        if orchestration_gate_body["next_automation_action"] is not None:
            assert orchestration_gate_body["next_automation_action"] in orchestration_gate_body["automation_actions"]
        if orchestration_gate_body["next_human_action"] is not None:
            assert orchestration_gate_body["next_human_action"] in (
                orchestration_gate_body["human_actions"] + orchestration_gate_body["review_gated_actions"]
            )
        assert orchestration_gate_body["merge_summary"]
        assert orchestration_gate_body["merge_next_action"]
        assert len(orchestration_gate_body["merge_evidence"]) >= 2
        assert orchestration_gate_body["focus_task_id"] == task_body["id"]
        assert orchestration_gate_body["focus_task_title"] == task_body["title"]

        verification_pipeline_response = await client.post(
            f"/api/v1/code/sessions/{session_id}/verification/run",
            json={"stop_on_failure": True},
            headers=scientist_headers,
        )
        assert verification_pipeline_response.status_code == 200
        pipeline_body = verification_pipeline_response.json()
        assert pipeline_body["overall_status"] in {"passed", "failed"}

        orchestration_response = await client.get(
            "/api/v1/code/workspace/orchestration",
            headers=scientist_headers,
        )
        assert orchestration_response.status_code == 200
        orchestration_body = orchestration_response.json()
        assert orchestration_body["workspace_id"] is not None
        assert orchestration_body["totals"]["tasks"] >= 1
        assert orchestration_body["totals"]["workers"] >= 3
        architect_lane = next(lane for lane in orchestration_body["lanes"] if lane["lane"] == "architect")
        assert architect_lane["latest_event_name"] == "lane.completed"
        assert isinstance(architect_lane["lane_actions"], list)
        assert isinstance(architect_lane["lane_action_policies"], dict)
        assert set(architect_lane["lane_action_policies"]).issubset(set(architect_lane["lane_actions"]))
        assert any(lane["lane"] == "executor" for lane in orchestration_body["lanes"])
        executor_lane = next(lane for lane in orchestration_body["lanes"] if lane["lane"] == "executor")
        assert executor_lane["task_title"] == "Stabilize BOS Code worker flow"
        assert executor_lane["headline"]
        expected_executor_status = "ready" if pipeline_body["overall_status"] == "passed" else "blocked"
        assert executor_lane["worker_status"] == expected_executor_status
        assert isinstance(executor_lane["lane_actions"], list)
        assert isinstance(executor_lane["lane_action_policies"], dict)
        assert set(executor_lane["lane_action_policies"]).issubset(set(executor_lane["lane_actions"]))
        assert isinstance(executor_lane["automation_actions"], list)
        assert isinstance(executor_lane["human_actions"], list)
        assert isinstance(executor_lane["review_gated_actions"], list)
        assert isinstance(executor_lane["automation_blockers"], list)
        assert isinstance(executor_lane["automation_ready"], bool)
        if executor_lane["next_automation_action"] is not None:
            assert executor_lane["next_automation_action"] in executor_lane["automation_actions"]
        if executor_lane["primary_action"] is not None:
            assert executor_lane["primary_action_policy"] in {"automation_safe", "human_only", "review_gated"}
        reviewer_lane = next(lane for lane in orchestration_body["lanes"] if lane["lane"] == "reviewer")
        assert reviewer_lane["latest_event_name"] == "review.accepted"
        assert isinstance(reviewer_lane["lane_actions"], list)
        assert isinstance(reviewer_lane["lane_action_policies"], dict)
        assert set(reviewer_lane["lane_action_policies"]).issubset(set(reviewer_lane["lane_actions"]))
        assert isinstance(reviewer_lane["automation_actions"], list)
        assert isinstance(reviewer_lane["human_actions"], list)
        assert isinstance(reviewer_lane["review_gated_actions"], list)
        assert isinstance(reviewer_lane["automation_blockers"], list)
        assert isinstance(reviewer_lane["automation_ready"], bool)
        if reviewer_lane["next_automation_action"] is not None:
            assert reviewer_lane["next_automation_action"] in reviewer_lane["automation_actions"]
        if reviewer_lane["primary_action"] is not None:
            assert reviewer_lane["primary_action_policy"] in {"automation_safe", "human_only", "review_gated"}
        assert orchestration_body["verification_gate"] in {"passed", "failed"}
        assert orchestration_body["operator_posture"]
        assert len(orchestration_body["operator_actions"]) >= 1
        assert isinstance(orchestration_body["operator_action_policies"], dict)
        assert isinstance(orchestration_body["operator_action_classes"], dict)
        assert orchestration_body["operator_action_policies"] == orchestration_body["operator_action_classes"]
        assert isinstance(orchestration_body["automation_actions"], list)
        assert isinstance(orchestration_body["human_actions"], list)
        assert isinstance(orchestration_body["review_gated_actions"], list)
        assert isinstance(orchestration_body["automation_blockers"], list)
        assert isinstance(orchestration_body["automation_ready"], bool)
        assert isinstance(orchestration_body["automation_summary"], str)
        if orchestration_body["next_automation_action"] is not None:
            assert orchestration_body["next_automation_action"] in orchestration_body["automation_actions"]
        if orchestration_body["next_human_action"] is not None:
            assert orchestration_body["next_human_action"] in (
                orchestration_body["human_actions"] + orchestration_body["review_gated_actions"]
            )
        assert orchestration_body["merge_summary"]
        assert len(orchestration_body["merge_evidence"]) >= 2
        assert orchestration_body["focus_task_id"] == task_body["id"]
        assert orchestration_body["focus_task_title"] == task_body["title"]
        assert orchestration_body["focus_task_status"] in {"verification_pending", "completed", "blocked"}
        assert orchestration_body["focus_task_headline"]
        if orchestration_body["verification_gate"] == "passed":
            assert orchestration_body["merge_readiness"] in {"merge_ready", "pending", "needs_recovery"}
        else:
            assert orchestration_body["merge_readiness"] in {"blocked", "pending", "needs_recovery"}

        worker_events_response = await client.get(
            "/api/v1/code/workspace/worker-events",
            headers=scientist_headers,
        )
        assert worker_events_response.status_code == 200
        worker_events_body = worker_events_response.json()
        assert worker_events_body["next_id"] is not None
        assert len(worker_events_body["items"]) >= 5
        assert any(item["event_name"] == "task.created" for item in worker_events_body["items"])
        assert any(item["event_name"] == "lane.progressed" and item["lane"] == "architect" for item in worker_events_body["items"])
        assert any(item["event_name"] == "lane.completed" and item["lane"] == "architect" for item in worker_events_body["items"])
        assert any(item["event_name"] == "task.routed" and item["lane"] == "executor" for item in worker_events_body["items"])
        assert any(item["event_name"] == "review.requested" for item in worker_events_body["items"])
        assert any(item["event_name"] == "review.rejected" for item in worker_events_body["items"])
        assert any(item["event_name"] == "review.accepted" for item in worker_events_body["items"])
        assert any(item["event_name"] == "merge.readiness.updated" for item in worker_events_body["items"])
        assert any(item["event_name"] in {"task.completed", "task.failed"} for item in worker_events_body["items"])
        rejected_event = next(item for item in worker_events_body["items"] if item["event_name"] == "review.rejected")
        assert rejected_event["payload"]["reason_code"] == "changes_requested"
        assert rejected_event["payload"]["checklist"] == ["Refresh verification", "Tighten event schema"]

        executor_lane_response = await client.get(
            "/api/v1/code/workspace/worker-events",
            params={"lane": "executor"},
            headers=scientist_headers,
        )
        assert executor_lane_response.status_code == 200
        executor_lane_body = executor_lane_response.json()
        assert executor_lane_body["items"]
        assert all(item["lane"] == "executor" for item in executor_lane_body["items"])

        task_events_response = await client.get(
            "/api/v1/code/workspace/worker-events",
            params={"task_id": task_body["id"]},
            headers=scientist_headers,
        )
        assert task_events_response.status_code == 200
        task_events_body = task_events_response.json()
        assert task_events_body["items"]
        assert all(item["task_id"] == task_body["id"] for item in task_events_body["items"])

    @pytest.mark.asyncio
    async def test_recovery_and_readiness_surfaces(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        operator_user: User,
        operator_headers: dict[str, str],
    ):
        await _enable_bos_code(db_session, operator_user)
        await client.post("/api/v1/code/workspace/init", json={}, headers=operator_headers)

        session_response = await client.post(
            "/api/v1/code/sessions",
            json={"acquire_write_lease": False},
            headers=operator_headers,
        )
        assert session_response.status_code == 201
        session_id = session_response.json()["id"]

        # Force a denied tool path to create a concrete recovery signal.
        denied_response = await client.post(
            f"/api/v1/code/sessions/{session_id}/tools/safe-bash",
            json={"command": "rm -rf ."},
            headers=operator_headers,
        )
        assert denied_response.status_code == 200

        readiness_response = await client.get(
            f"/api/v1/code/sessions/{session_id}/readiness",
            headers=operator_headers,
        )
        assert readiness_response.status_code == 200
        readiness_body = readiness_response.json()
        assert readiness_body["session_id"] == session_id
        assert "failure_class" in readiness_body
        assert "recommended_actions" in readiness_body
        assert "evidence" in readiness_body

        recovery_response = await client.get(
            f"/api/v1/code/sessions/{session_id}/recovery",
            headers=operator_headers,
        )
        assert recovery_response.status_code == 200
        recovery_body = recovery_response.json()
        assert recovery_body["session_id"] == session_id
        assert recovery_body["status"] in {"ready", "blocked", "degraded", "merge_ready", "needs_recovery"}
        assert "headline" in recovery_body
        if recovery_body["failure_class"] == "prompt_delivery":
            assert recovery_body["next_safe_action"] == "reset_session_ready"

    @pytest.mark.asyncio
    async def test_branch_state_and_readiness_requests_are_race_safe(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        scientist_user: User,
        scientist_headers: dict[str, str],
    ):
        await _enable_bos_code(db_session, scientist_user)
        await client.post("/api/v1/code/workspace/init", json={}, headers=scientist_headers)

        session_response = await client.post(
            "/api/v1/code/sessions",
            json={"acquire_write_lease": False},
            headers=scientist_headers,
        )
        assert session_response.status_code == 201
        session_id = session_response.json()["id"]

        async def _override():
            async with TestSessionLocal() as session:
                yield session

        app.dependency_overrides[get_async_session] = _override
        try:
            async with AsyncClient(transport=client._transport, base_url="http://test") as branch_client:
                async with AsyncClient(transport=client._transport, base_url="http://test") as readiness_client:
                    branch_state_response, readiness_response = await asyncio.gather(
                        branch_client.get(
                            f"/api/v1/code/sessions/{session_id}/git/branch-state",
                            headers=scientist_headers,
                        ),
                        readiness_client.get(
                            f"/api/v1/code/sessions/{session_id}/readiness",
                            headers=scientist_headers,
                        ),
                    )
        finally:
            app.dependency_overrides.pop(get_async_session, None)

        assert branch_state_response.status_code == 200
        assert readiness_response.status_code == 200

    @pytest.mark.asyncio
    async def test_lane_control_status_updates_are_lane_aware(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        scientist_user: User,
        scientist_headers: dict[str, str],
    ):
        await _enable_bos_code(db_session, scientist_user)
        await client.post("/api/v1/code/workspace/init", json={}, headers=scientist_headers)

        session_response = await client.post(
            "/api/v1/code/sessions",
            json={"acquire_write_lease": False},
            headers=scientist_headers,
        )
        session_id = session_response.json()["id"]

        task_response = await client.post(
            "/api/v1/code/workspace/tasks",
            json={
                "title": "Lane control semantics",
                "objective": "Validate explicit lane control actions.",
                "scope": "code/orchestration/lane-controls",
                "session_id": session_id,
            },
            headers=scientist_headers,
        )
        task_id = task_response.json()["id"]

        draft_response = await client.post(
            f"/api/v1/code/workspace/tasks/{task_id}/architect-plan",
            json={"regenerate": True, "summary": "Architect drafted acceptance criteria and suggested executor routing."},
            headers=scientist_headers,
        )
        draft_body = draft_response.json()

        await client.post(
            f"/api/v1/code/workspace/tasks/{task_id}/architect-route",
            json={
                "acceptance_criteria": draft_body["acceptance_criteria"],
                "summary": "Architect decomposed and routed the task to executor.",
                "route_to": draft_body["route_to"],
            },
            headers=scientist_headers,
        )

        block_executor_response = await client.post(
            "/api/v1/code/workspace/workers/executor/status",
            json={
                "worker_status": "blocked",
                "last_event_summary": "Executor lane is blocked and needs operator attention.",
                "lane": "executor",
                "event_name": "lane.blocked",
            },
            headers=scientist_headers,
        )
        assert block_executor_response.status_code == 200

        tasks_response = await client.get("/api/v1/code/workspace/tasks", headers=scientist_headers)
        blocked_task = next(item for item in tasks_response.json() if item["id"] == task_id)
        assert blocked_task["task_status"] == "blocked"

        workers_response = await client.get("/api/v1/code/workspace/workers", headers=scientist_headers)
        executor_worker = next(item for item in workers_response.json() if item["worker_name"] == "executor")
        assert "mark_executor_ready" in executor_worker["allowed_actions"]
        assert "mark_executor_blocked" not in executor_worker["allowed_actions"]
        assert executor_worker["allowed_action_policies"]["mark_executor_ready"] == "automation_safe"

        ready_executor_response = await client.post(
            "/api/v1/code/workspace/workers/executor/status",
            json={
                "worker_status": "ready",
                "last_event_summary": "executor lane is ready for the next handoff.",
                "lane": "executor",
                "event_name": "lane.progressed",
            },
            headers=scientist_headers,
        )
        assert ready_executor_response.status_code == 200

        tasks_response = await client.get("/api/v1/code/workspace/tasks", headers=scientist_headers)
        resumed_task = next(item for item in tasks_response.json() if item["id"] == task_id)
        assert resumed_task["task_status"] == "running"

        invalid_status_response = await client.post(
            "/api/v1/code/workspace/workers/executor/status",
            json={
                "worker_status": "teleporting",
                "last_event_summary": "Impossible state.",
                "lane": "executor",
                "event_name": "lane.progressed",
            },
            headers=scientist_headers,
        )
        assert invalid_status_response.status_code == 409
        assert invalid_status_response.json()["detail"] == "worker_status_invalid"

    @pytest.mark.asyncio
    async def test_operator_control_plane_transitions_follow_review_lifecycle(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        scientist_user: User,
        scientist_headers: dict[str, str],
    ):
        await _enable_bos_code(db_session, scientist_user)
        await client.post("/api/v1/code/workspace/init", json={}, headers=scientist_headers)

        session_response = await client.post(
            "/api/v1/code/sessions",
            json={"acquire_write_lease": False},
            headers=scientist_headers,
        )
        session_id = session_response.json()["id"]

        task_response = await client.post(
            "/api/v1/code/workspace/tasks",
            json={
                "title": "Operator control-plane lifecycle",
                "objective": "Validate control-plane transitions across review lifecycle.",
                "scope": "code/orchestration/control-plane-lifecycle",
                "session_id": session_id,
            },
            headers=scientist_headers,
        )
        task_id = task_response.json()["id"]

        draft_response = await client.post(
            f"/api/v1/code/workspace/tasks/{task_id}/architect-plan",
            json={"regenerate": True, "summary": "Architect drafted acceptance criteria and suggested executor routing."},
            headers=scientist_headers,
        )
        draft_body = draft_response.json()

        await client.post(
            f"/api/v1/code/workspace/tasks/{task_id}/architect-route",
            json={
                "acceptance_criteria": draft_body["acceptance_criteria"],
                "summary": "Architect decomposed and routed the task to executor.",
                "route_to": draft_body["route_to"],
            },
            headers=scientist_headers,
        )
        await client.post(
            f"/api/v1/code/workspace/tasks/{task_id}/review-request",
            json={"summary": "Executor submitted implementation for reviewer decision."},
            headers=scientist_headers,
        )

        review_queue_snapshot = (
            await client.get("/api/v1/code/workspace/orchestration", headers=scientist_headers)
        ).json()
        assert review_queue_snapshot["operator_posture"] in {"review_queue", "recovery_required"}
        assert "begin_review" in review_queue_snapshot["operator_actions"] or "refresh_branch" in review_queue_snapshot["operator_actions"]
        assert isinstance(review_queue_snapshot["operator_action_policies"], dict)
        workers_response = await client.get("/api/v1/code/workspace/workers", headers=scientist_headers)
        reviewer_worker = next(item for item in workers_response.json() if item["worker_name"] == "reviewer")
        assert "begin_review" in reviewer_worker["allowed_actions"]
        assert reviewer_worker["allowed_action_policies"]["begin_review"] == "human_only"

        begin_review_response = await client.post(
            "/api/v1/code/workspace/workers/reviewer/status",
            json={
                "worker_status": "running",
                "last_event_summary": f"Reviewer is actively evaluating task #{task_id}.",
                "lane": "reviewer",
                "event_name": "lane.progressed",
                "payload": {"task_id": task_id, "review_state": "in_review"},
            },
            headers=scientist_headers,
        )
        assert begin_review_response.status_code == 200

        review_active_snapshot = (
            await client.get("/api/v1/code/workspace/orchestration", headers=scientist_headers)
        ).json()
        assert review_active_snapshot["focus_task_status"] == "in_review"
        assert "accept_review" in review_active_snapshot["operator_actions"]
        assert review_active_snapshot["operator_action_policies"].get("accept_review") == "review_gated"
        assert review_active_snapshot["next_human_action"] in {"accept_review", "reject_review"}
        assert review_active_snapshot["automation_ready"] is False
        assert "review_gate_present" in review_active_snapshot["automation_blockers"]
        reviewer_lane = next(lane for lane in review_active_snapshot["lanes"] if lane["lane"] == "reviewer")
        assert reviewer_lane["headline"] == "Reviewer is actively evaluating the implementation."
        assert reviewer_lane["primary_action"] == "begin_review" or reviewer_lane["primary_action"] == "accept_review"
        assert reviewer_lane["primary_action_policy"] in {"human_only", "review_gated"}
        assert isinstance(reviewer_lane["lane_action_policies"], dict)
        assert isinstance(reviewer_lane["review_gated_actions"], list)
        assert reviewer_lane["automation_ready"] is False
        assert "review_gate_present" in reviewer_lane["automation_blockers"]

        accept_response = await client.post(
            f"/api/v1/code/workspace/tasks/{task_id}/review-decision",
            json={"decision": "accept", "summary": "Reviewer accepted the implementation."},
            headers=scientist_headers,
        )
        assert accept_response.status_code == 200

        verification_snapshot = (
            await client.get("/api/v1/code/workspace/orchestration", headers=scientist_headers)
        ).json()
        assert verification_snapshot["focus_task_status"] == "verification_pending"
        assert any(
            action in verification_snapshot["operator_actions"]
            for action in {"run_verification", "refresh_branch", "inspect_diff"}
        )
        assert isinstance(verification_snapshot["operator_action_policies"], dict)
        assert verification_snapshot["next_automation_action"] in {None, *verification_snapshot["automation_actions"]}
        if verification_snapshot["next_automation_action"] is not None:
            assert isinstance(verification_snapshot["automation_ready"], bool)

    @pytest.mark.asyncio
    async def test_execute_next_automation_action_respects_gate_and_executes_when_ready(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        scientist_user: User,
        scientist_headers: dict[str, str],
    ):
        await _enable_bos_code(db_session, scientist_user)
        await client.post("/api/v1/code/workspace/init", json={}, headers=scientist_headers)

        session_response = await client.post(
            "/api/v1/code/sessions",
            json={"acquire_write_lease": False},
            headers=scientist_headers,
        )
        session_id = session_response.json()["id"]

        task_response = await client.post(
            "/api/v1/code/workspace/tasks",
            json={
                "title": "Automation executor gate",
                "objective": "Validate execute-next-automation guard semantics.",
                "scope": "code/orchestration/automation-executor",
                "session_id": session_id,
            },
            headers=scientist_headers,
        )
        task_id = task_response.json()["id"]

        draft_response = await client.post(
            f"/api/v1/code/workspace/tasks/{task_id}/architect-plan",
            json={"regenerate": True, "summary": "Architect drafted acceptance criteria and suggested executor routing."},
            headers=scientist_headers,
        )
        draft_body = draft_response.json()

        await client.post(
            f"/api/v1/code/workspace/tasks/{task_id}/architect-route",
            json={
                "acceptance_criteria": draft_body["acceptance_criteria"],
                "summary": "Architect decomposed and routed the task to executor.",
                "route_to": draft_body["route_to"],
            },
            headers=scientist_headers,
        )
        await client.post(
            f"/api/v1/code/workspace/tasks/{task_id}/review-request",
            json={"summary": "Executor submitted implementation for reviewer decision."},
            headers=scientist_headers,
        )
        await client.post(
            "/api/v1/code/workspace/workers/reviewer/status",
            json={
                "worker_status": "running",
                "last_event_summary": f"Reviewer is actively evaluating task #{task_id}.",
                "lane": "reviewer",
                "event_name": "lane.progressed",
                "payload": {"task_id": task_id, "review_state": "in_review"},
            },
            headers=scientist_headers,
        )

        gated_response = await client.post(
            "/api/v1/code/workspace/orchestration/execute-next-automation",
            headers=scientist_headers,
        )
        assert gated_response.status_code == 409
        assert gated_response.json()["detail"] == "automation_not_ready"

        await client.post(
            f"/api/v1/code/workspace/tasks/{task_id}/review-decision",
            json={"decision": "accept", "summary": "Reviewer accepted the implementation."},
            headers=scientist_headers,
        )

        execute_response = await client.post(
            "/api/v1/code/workspace/orchestration/execute-next-automation",
            headers=scientist_headers,
        )
        assert execute_response.status_code == 200
        execute_body = execute_response.json()
        assert execute_body["executed_action"] == "run_verification"
        assert execute_body["execution_status"] == "completed"
        assert execute_body["snapshot"]["workspace_id"] is not None
        assert isinstance(execute_body["snapshot"]["automation_ready"], bool)

    @pytest.mark.asyncio
    async def test_execute_next_automation_action_can_soft_reset_runtime(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        scientist_user: User,
        scientist_headers: dict[str, str],
    ):
        await _enable_bos_code(db_session, scientist_user)
        await client.post("/api/v1/code/workspace/init", json={}, headers=scientist_headers)

        session_response = await client.post(
            "/api/v1/code/sessions",
            json={"acquire_write_lease": False},
            headers=scientist_headers,
        )
        assert session_response.status_code == 201
        session_id = session_response.json()["id"]

        session_result = await db_session.execute(
            select(CodeSession).where(CodeSession.id == session_id)
        )
        session = session_result.scalar_one()
        session.session_status = "blocked"
        db_session.add(
            CodeToolCall(
                session_id=session_id,
                turn_id=None,
                tool_name="provider_dispatch",
                tool_class="provider",
                input_summary="Resume the thread",
                result_summary="Prompt was delivered to the wrong shell target.",
                was_denied=True,
                denial_reason="prompt_misdelivery",
            )
        )
        await db_session.commit()

        orchestration_response = await client.get(
            "/api/v1/code/workspace/orchestration",
            headers=scientist_headers,
        )
        assert orchestration_response.status_code == 200
        orchestration_body = orchestration_response.json()
        assert orchestration_body["next_automation_action"] == "reset_session_ready"
        assert orchestration_body["automation_ready"] is True

        execute_response = await client.post(
            "/api/v1/code/workspace/orchestration/execute-next-automation",
            headers=scientist_headers,
        )
        assert execute_response.status_code == 200
        execute_body = execute_response.json()
        assert execute_body["executed_action"] == "reset_session_ready"
        assert execute_body["execution_status"] == "completed"

        refreshed_session_response = await client.get(
            f"/api/v1/code/sessions/{session_id}",
            headers=scientist_headers,
        )
        assert refreshed_session_response.status_code == 200
        refreshed_session = refreshed_session_response.json()["session"]
        assert refreshed_session["session_status"] == "ready_for_prompt"

    @pytest.mark.asyncio
    async def test_execute_next_automation_action_can_refresh_branch_for_stale_posture(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        scientist_user: User,
        scientist_headers: dict[str, str],
    ):
        await _enable_bos_code(db_session, scientist_user)
        await client.post("/api/v1/code/workspace/init", json={}, headers=scientist_headers)

        session_response = await client.post(
            "/api/v1/code/sessions",
            json={"acquire_write_lease": False},
            headers=scientist_headers,
        )
        assert session_response.status_code == 201
        session_id = session_response.json()["id"]

        session_result = await db_session.execute(
            select(CodeSession).where(CodeSession.id == session_id)
        )
        session = session_result.scalar_one()
        db_session.add(
            CodeBranchState(
                workspace_id=session.workspace_id,
                branch_name=session.session_branch,
                base_branch="main",
                head_commit="abc",
                base_commit="def",
                merge_base_commit="aaa",
                is_dirty=False,
                is_stale_against_base=True,
                ahead_count=0,
                behind_count=2,
                branch_status="stale",
            )
        )
        await db_session.commit()

        recovery_response = await client.get(
            f"/api/v1/code/sessions/{session_id}/recovery",
            headers=scientist_headers,
        )
        assert recovery_response.status_code == 200
        recovery_body = recovery_response.json()
        assert recovery_body["next_safe_action"] == "refresh_branch"

        orchestration_response = await client.get(
            "/api/v1/code/workspace/orchestration",
            headers=scientist_headers,
        )
        assert orchestration_response.status_code == 200
        orchestration_body = orchestration_response.json()
        assert orchestration_body["next_automation_action"] == "refresh_branch"
        assert orchestration_body["automation_ready"] is True

        execute_response = await client.post(
            "/api/v1/code/workspace/orchestration/execute-next-automation",
            headers=scientist_headers,
        )
        assert execute_response.status_code == 200
        execute_body = execute_response.json()
        assert execute_body["executed_action"] == "refresh_branch"

    @pytest.mark.asyncio
    async def test_execute_next_automation_action_can_rerun_verification_for_failed_stage(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        scientist_user: User,
        scientist_headers: dict[str, str],
    ):
        await _enable_bos_code(db_session, scientist_user)
        await client.post("/api/v1/code/workspace/init", json={}, headers=scientist_headers)

        session_response = await client.post(
            "/api/v1/code/sessions",
            json={"acquire_write_lease": False},
            headers=scientist_headers,
        )
        assert session_response.status_code == 201
        session_id = session_response.json()["id"]

        session_result = await db_session.execute(
            select(CodeSession).where(CodeSession.id == session_id)
        )
        session = session_result.scalar_one()
        session.verification_status = "failed"
        db_session.add(
            CodeVerificationRun(
                session_id=session_id,
                verification_stage="lint",
                verification_status="failed",
                summary="lint failed",
                log_excerpt="example lint failure",
            )
        )
        await db_session.commit()

        recovery_response = await client.get(
            f"/api/v1/code/sessions/{session_id}/recovery",
            headers=scientist_headers,
        )
        assert recovery_response.status_code == 200
        recovery_body = recovery_response.json()
        assert recovery_body["next_safe_action"] == "run_verification"

        orchestration_response = await client.get(
            "/api/v1/code/workspace/orchestration",
            headers=scientist_headers,
        )
        assert orchestration_response.status_code == 200
        orchestration_body = orchestration_response.json()
        assert orchestration_body["next_automation_action"] == "run_verification"
        assert orchestration_body["automation_ready"] is True

        execute_response = await client.post(
            "/api/v1/code/workspace/orchestration/execute-next-automation",
            headers=scientist_headers,
        )
        assert execute_response.status_code == 200
        execute_body = execute_response.json()
        assert execute_body["executed_action"] == "run_verification"

    @pytest.mark.asyncio
    async def test_recovery_endpoint_does_not_offer_run_verification_while_review_gate_is_active(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        scientist_user: User,
        scientist_headers: dict[str, str],
    ):
        await _enable_bos_code(db_session, scientist_user)
        await client.post("/api/v1/code/workspace/init", json={}, headers=scientist_headers)

        session_response = await client.post(
            "/api/v1/code/sessions",
            json={"acquire_write_lease": False},
            headers=scientist_headers,
        )
        assert session_response.status_code == 201
        session_id = session_response.json()["id"]

        session_result = await db_session.execute(
            select(CodeSession).where(CodeSession.id == session_id)
        )
        session = session_result.scalar_one()
        session.verification_status = "failed"
        db_session.add(
            CodeTask(
                tenant_id=scientist_user.tenant_id,
                user_id=scientist_user.id,
                workspace_id=session.workspace_id,
                session_id=session_id,
                title="Review gate still active",
                objective="Prevent automatic verification reruns while review is pending.",
                scope="code/runtime",
                task_status="review_pending",
                priority="normal",
                acceptance_criteria=[],
            )
        )
        db_session.add(
            CodeVerificationRun(
                session_id=session_id,
                verification_stage="lint",
                verification_status="failed",
                summary="lint failed",
                log_excerpt="example lint failure",
            )
        )
        await db_session.commit()

        recovery_response = await client.get(
            f"/api/v1/code/sessions/{session_id}/recovery",
            headers=scientist_headers,
        )
        assert recovery_response.status_code == 200
        recovery_body = recovery_response.json()
        assert recovery_body["failure_class"] == "verification_failed"
        assert recovery_body["next_safe_action"] is None
        assert recovery_body["evidence"]["review_gate_task_ids"]
        assert any("review gate" in action.lower() for action in recovery_body["recommended_actions"])

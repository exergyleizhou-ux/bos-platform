import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path

from app.services.feature_flags import set_db_override


async def enable_flag(db_session: AsyncSession, tenant_id: int, flag_name: str) -> None:
    await set_db_override(
        db_session,
        flag_name=flag_name,
        tenant_id=tenant_id,
        enabled=True,
    )


async def create_batch(client: AsyncClient, headers: dict[str, str], batch_id: str) -> dict:
    response = await client.post(
        "/api/v1/batches",
        json={
            "batch_id": batch_id,
            "dm_in": 10.0,
            "dm_out": 2.4,
            "temperature": 28.0,
            "moisture": 66.0,
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


async def create_control_profile(client: AsyncClient, headers: dict[str, str]) -> dict:
    response = await client.post(
        "/api/v1/control-profiles",
        json={
            "name": "Test control",
            "version": "CTRL-1.0",
            "mtt": 6.0,
            "dose_window_min": 0.1,
            "dose_window_max": 0.3,
            "stability_window_hours": 8.0,
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


async def create_locality_profile(client: AsyncClient, headers: dict[str, str]) -> dict:
    response = await client.post(
        "/api/v1/locality-profiles",
        json={
            "name": "Shanghai Site A",
            "site_code": "SHA-A",
            "dose_window_shift_pct": 8.0,
            "mtt_shift_pct": 4.0,
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


async def create_executor_profile(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    locality_profile_id: int | None = None,
) -> dict:
    response = await client.post(
        "/api/v1/executor-profiles",
        json={
            "locality_profile_id": locality_profile_id,
            "executor_code": "exec-sha-a",
            "name": "Shanghai Executor",
            "executor_type": "larval",
            "hal_min": 0.1,
            "hal_max": 0.2,
            "plugin_mode": "adaptive",
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


class TestBosFeatureFlags:
    @pytest.mark.asyncio
    async def test_guidance_endpoint_requires_feature_flag(
        self,
        client: AsyncClient,
        admin_headers,
    ):
        batch = await create_batch(client, admin_headers, "FLAG-GUIDANCE-001")

        response = await client.get(
            f"/api/v1/guidance/batch/{batch['id']}",
            headers=admin_headers,
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "bos_guidance_disabled"

    @pytest.mark.asyncio
    async def test_signal_compile_requires_feature_flag(
        self,
        client: AsyncClient,
        admin_headers,
    ):
        batch = await create_batch(client, admin_headers, "FLAG-COMPILE-001")

        response = await client.post(
            "/api/v1/signals/compile",
            json={"batch_id": batch["id"]},
            headers=admin_headers,
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "bos_signal_compile_disabled"

    @pytest.mark.asyncio
    async def test_audit_export_requires_feature_flag(
        self,
        client: AsyncClient,
        admin_headers,
    ):
        batch = await create_batch(client, admin_headers, "FLAG-EXPORT-001")

        response = await client.get(
            f"/api/v1/audit-packets/batch/{batch['id']}/export?format=json",
            headers=admin_headers,
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "bos_audit_export_disabled"


class TestBosGuidanceAndSignals:
    @pytest.mark.asyncio
    async def test_guidance_endpoint_returns_gap_items(
        self,
        client: AsyncClient,
        admin_headers,
        db_session: AsyncSession,
        test_tenant,
    ):
        await enable_flag(db_session, test_tenant.id, "bos_guidance")
        batch = await create_batch(client, admin_headers, "GUIDE-001")

        response = await client.get(
            f"/api/v1/guidance/batch/{batch['id']}",
            headers=admin_headers,
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["batch_id"] == batch["id"]
        assert any(item["code"] == "missing_signal_batch" for item in payload["gap_items"])
        assert payload["recommended_actions"]
        assert all("寤" not in action for action in payload["recommended_actions"])

    @pytest.mark.asyncio
    async def test_guidance_endpoint_reflects_release_blockers(
        self,
        client: AsyncClient,
        admin_headers,
        scientist_headers,
        db_session: AsyncSession,
        test_tenant,
    ):
        await enable_flag(db_session, test_tenant.id, "bos_guidance")
        batch = await create_batch(client, admin_headers, "GUIDE-RELEASE-001")
        control_profile = await create_control_profile(client, scientist_headers)

        signal_response = await client.post(
            "/api/v1/signals",
            json={
                "batch_id": batch["id"],
                "signal_api_version": "SIG-1.0",
                "compiled_signal_id": "SIG-GUIDE-RELEASE-001",
                "potency": 0.5,
                "stability_window_hours": 8.0,
                "freshness_state": "Fresh",
            },
            headers=admin_headers,
        )
        assert signal_response.status_code == 201

        evaluate_response = await client.post(
            "/api/v1/release-decisions/evaluate",
            json={
                "batch_id": batch["id"],
                "signal_batch_id": signal_response.json()["id"],
                "control_profile_id": control_profile["id"],
            },
            headers=admin_headers,
        )
        assert evaluate_response.status_code == 200

        response = await client.get(
            f"/api/v1/guidance/batch/{batch['id']}",
            headers=admin_headers,
        )

        assert response.status_code == 200
        payload = response.json()
        items_by_code = {item["code"]: item for item in payload["gap_items"]}
        assert items_by_code["release_blocked"]["blocking"] is True
        assert (
            items_by_code["release_blocked"]["recommended_action"]
            == "Retune the control profile or compile a signal that fits the dose window."
        )

    @pytest.mark.asyncio
    async def test_signal_compile_creates_compiled_signal(
        self,
        client: AsyncClient,
        admin_headers,
        scientist_headers,
        db_session: AsyncSession,
        test_tenant,
    ):
        await enable_flag(db_session, test_tenant.id, "bos_signal_compile")
        batch = await create_batch(client, admin_headers, "COMPILE-001")
        control_profile = await create_control_profile(client, scientist_headers)

        response = await client.post(
            "/api/v1/signals/compile",
            json={
                "batch_id": batch["id"],
                "control_profile_id": control_profile["id"],
            },
            headers=admin_headers,
        )

        assert response.status_code == 201
        payload = response.json()
        assert payload["batch_id"] == batch["id"]
        assert payload["compile_status"] == "compiled"
        assert payload["source_mode"] == "compiled"
        assert payload["freshness_state"] in {"Fresh", "Stable", "Stale"}

    @pytest.mark.asyncio
    async def test_signal_refresh_updates_signal_state(
        self,
        client: AsyncClient,
        admin_headers,
        db_session: AsyncSession,
        test_tenant,
    ):
        await enable_flag(db_session, test_tenant.id, "bos_signal_compile")
        batch = await create_batch(client, admin_headers, "REFRESH-001")
        compile_response = await client.post(
            "/api/v1/signals/compile",
            json={"batch_id": batch["id"]},
            headers=admin_headers,
        )
        assert compile_response.status_code == 201
        signal_batch_id = compile_response.json()["id"]

        response = await client.post(
            f"/api/v1/signals/{signal_batch_id}/refresh",
            headers=admin_headers,
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["signal_batch"]["id"] == signal_batch_id
        assert payload["refreshed_state"] in {"Fresh", "Stable", "Stale"}
        assert isinstance(payload["freshness_score"], float)
        assert isinstance(payload["release_readiness_score"], float)

    @pytest.mark.asyncio
    async def test_native_models_endpoint_returns_catalog(
        self,
        client: AsyncClient,
        admin_headers,
    ):
        response = await client.get(
            "/api/v1/native-models",
            headers=admin_headers,
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["catalog_version"] == "BOS-NATIVE-2026.04"
        assert any(item["key"] == "yolo11_dsconv" for item in payload["models"])
        assert any(item["key"] == "vision_forecast_closed_loop" for item in payload["recommendations"])

    @pytest.mark.asyncio
    async def test_native_model_runtime_endpoint_returns_status(
        self,
        client: AsyncClient,
        admin_headers,
    ):
        response = await client.get(
            "/api/v1/native-models/runtime",
            headers=admin_headers,
        )

        assert response.status_code == 200
        payload = response.json()
        assert "runtimes" in payload
        assert any(item["key"] == "chronos_bolt" for item in payload["runtimes"])

    @pytest.mark.asyncio
    async def test_native_model_download_plan_endpoint_returns_entries(
        self,
        client: AsyncClient,
        admin_headers,
    ):
        response = await client.get(
            "/api/v1/native-models/download-plan",
            headers=admin_headers,
        )

        assert response.status_code == 200
        payload = response.json()
        assert any(item["model_key"] == "timer_s1" for item in payload)

    @pytest.mark.asyncio
    async def test_native_model_infer_endpoint_returns_fallback_projection(
        self,
        client: AsyncClient,
        admin_headers,
    ):
        batch = await create_batch(client, admin_headers, "NATIVE-INFER-001")

        response = await client.post(
            "/api/v1/native-models/infer",
            json={
                "model_key": "timer_s1",
                "batch_id": batch["id"],
                "dry_run": False,
                "payload": {
                    "metric_name": "decomposition_rate",
                    "horizon": 4,
                    "sensor_history": [0.22, 0.3, 0.36, 0.44, 0.49],
                },
            },
            headers=admin_headers,
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["execution_mode"] == "bos_fallback_projection"
        assert len(payload["result"]["forecast"]) == 4

    @pytest.mark.asyncio
    async def test_model_backed_batch_risk_endpoint_returns_contract(
        self,
        client: AsyncClient,
        admin_headers,
    ):
        batch = await create_batch(client, admin_headers, "CHRONOS-RISK-001")

        response = await client.get(
            f"/api/v1/bos/risk/batch/{batch['id']}",
            headers=admin_headers,
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["batch_id"] == batch["id"]
        assert payload["model_name"] == "chronos_bolt"
        assert 0 <= payload["future_risk_score"] <= 1
        assert 0 <= payload["freshness_drift_score"] <= 1
        assert 0 <= payload["release_warning_score"] <= 1
        assert payload["driver_features"]
        assert payload["forecast_window"]
        assert payload["confidence_band"]["lower"] <= payload["confidence_band"]["upper"]

    @pytest.mark.asyncio
    async def test_recent_model_backed_risks_endpoint_returns_items(
        self,
        client: AsyncClient,
        admin_headers,
    ):
        await create_batch(client, admin_headers, "CHRONOS-RISK-RECENT-001")

        response = await client.get(
            "/api/v1/bos/risk/recent?limit=3",
            headers=admin_headers,
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["count"] >= 1
        assert payload["items"]
        assert "release_warning_score" in payload["items"][0]

    @pytest.mark.asyncio
    async def test_native_model_runs_endpoint_returns_artifacts(
        self,
        client: AsyncClient,
        admin_headers,
    ):
        await client.post(
            "/api/v1/native-models/infer",
            json={
                "model_key": "timer_s1",
                "dry_run": False,
                "payload": {
                    "metric_name": "decomposition_rate",
                    "horizon": 3,
                    "sensor_history": [0.2, 0.28, 0.34, 0.39],
                },
            },
            headers=admin_headers,
        )

        response = await client.get(
            "/api/v1/native-models/runs?limit=5",
            headers=admin_headers,
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload
        assert "artifact_path" in payload[0]

    @pytest.mark.asyncio
    async def test_native_model_runs_endpoint_can_filter_by_batch(
        self,
        client: AsyncClient,
        admin_headers,
    ):
        batch = await create_batch(client, admin_headers, "NATIVE-RUNS-BATCH-001")

        await client.post(
            "/api/v1/native-models/infer",
            json={
                "model_key": "timer_s1",
                "batch_id": batch["id"],
                "dry_run": False,
                "payload": {
                    "metric_name": "decomposition_rate",
                    "horizon": 3,
                    "sensor_history": [0.21, 0.29, 0.33, 0.4],
                },
            },
            headers=admin_headers,
        )

        response = await client.get(
            f"/api/v1/native-models/runs?batch_id={batch['id']}&limit=10",
            headers=admin_headers,
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload
        assert all(item["result"]["batch_context"]["batch_id"] == batch["id"] for item in payload)

    @pytest.mark.asyncio
    async def test_native_model_download_endpoint_downloads_when_dependencies_are_available(
        self,
        client: AsyncClient,
        admin_headers,
        monkeypatch,
        tmp_path: Path,
    ):
        from app.services import bos_native_runtime

        downloaded_path = tmp_path / "chronos-bolt"
        downloaded_path.mkdir()

        monkeypatch.setattr(
            bos_native_runtime,
            "_download_hf_snapshot",
            lambda model_key: (str(downloaded_path), str(downloaded_path)),
        )

        response = await client.post(
            "/api/v1/native-models/chronos_bolt/download",
            headers=admin_headers,
        )

        assert response.status_code == 200
        assert response.json()["downloaded"] is True

    @pytest.mark.asyncio
    async def test_timer_s1_download_endpoint_is_gated_by_default(
        self,
        client: AsyncClient,
        admin_headers,
    ):
        response = await client.post(
            "/api/v1/native-models/timer_s1/download",
            headers=admin_headers,
        )

        assert response.status_code == 409
        assert "BOS_NATIVE_TIMER_S1_ENABLE_DOWNLOAD" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_brain_runtime_endpoint_returns_runtime_documents(
        self,
        client: AsyncClient,
        admin_headers,
    ):
        response = await client.get(
            "/api/v1/brain/runtime",
            headers=admin_headers,
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["root_path"] == ".agents/runtime"
        assert len(payload["documents"]) == 4
        assert {item["key"] for item in payload["documents"]} == {
            "project_brain",
            "decision_journal",
            "evolution_log",
            "run_ledger",
        }

    @pytest.mark.asyncio
    async def test_brain_runtime_document_can_be_updated(
        self,
        client: AsyncClient,
        admin_headers,
    ):
        root = Path(__file__).resolve().parents[3] / ".agents" / "runtime"
        target = root / "evolution-log.md"
        original = target.read_text(encoding="utf-8")
        updated = original.rstrip() + "\n- Test heuristic written by integration test.\n"

        try:
            response = await client.put(
                "/api/v1/brain/runtime/evolution_log",
                json={"content": updated},
                headers=admin_headers,
            )

            assert response.status_code == 200
            payload = response.json()
            assert payload["key"] == "evolution_log"
            assert "Test heuristic written by integration test." in payload["content"]
            assert "Test heuristic written by integration test." in target.read_text(encoding="utf-8")
        finally:
            target.write_text(original, encoding="utf-8")

    @pytest.mark.asyncio
    async def test_brain_runtime_document_rejects_unexpected_headings(
        self,
        client: AsyncClient,
        admin_headers,
    ):
        response = await client.put(
            "/api/v1/brain/runtime/project_brain",
            json={
                "content": """# Project Brain

## Mission
- Protect the BOS runtime contract.

## Surprise Section
- This heading should not be accepted.
""",
            },
            headers=admin_headers,
        )

        assert response.status_code == 422
        payload = response.json()["detail"]
        assert payload["message"] == "Project Brain must preserve the required runtime-memory structure."
        assert payload["unexpected_headings"] == ["Surprise Section"]
        assert "Current Focus" in payload["missing_headings"]

    @pytest.mark.asyncio
    async def test_brain_runtime_document_rejects_run_ledger_without_explicit_target_contract(
        self,
        client: AsyncClient,
        admin_headers,
    ):
        response = await client.put(
            "/api/v1/brain/runtime/run_ledger",
            json={
                "content": """# Autonomy Run Ledger

## Latest Run
- Slice: Batch 101 signal review
- Outcome: Verified
- Verification: cmd /c npm run type-check
- Remaining Risk: release mapping still pending
- Next Step: connect audit packet 900 to release center

## Recent Runs
- 2026-04-16 12:00 | Batch 101 signal review | Verified | Added explicit target contract
""",
            },
            headers=admin_headers,
        )

        assert response.status_code == 422
        payload = response.json()["detail"]
        assert payload["message"] == "Autonomy Run Ledger must preserve the required runtime-memory structure."
        assert "Latest Run must include '- Target Surface: ...'" in payload["invalid_lines"]
        assert "Latest Run must include '- Target ID: ...'" in payload["invalid_lines"]
        assert "Latest Run must include '- Target Route: ...'" in payload["invalid_lines"]


class TestBosAuditExport:
    @pytest.mark.asyncio
    async def test_audit_packet_response_includes_portability_recommendation_metadata(
        self,
        client: AsyncClient,
        admin_headers,
        scientist_headers,
    ):
        batch = await create_batch(client, admin_headers, "PORTABILITY-PACKET-001")
        control_profile = await create_control_profile(client, scientist_headers)
        locality_profile = await create_locality_profile(client, scientist_headers)
        executor_profile = await create_executor_profile(
            client,
            scientist_headers,
            locality_profile_id=locality_profile["id"],
        )

        signal_response = await client.post(
            "/api/v1/signals",
            json={
                "batch_id": batch["id"],
                "signal_api_version": "SIG-1.0",
                "compiled_signal_id": "SIG-PORTABILITY-PACKET-001",
                "potency": 0.22,
                "stability_window_hours": 8.0,
                "freshness_state": "Fresh",
            },
            headers=admin_headers,
        )
        assert signal_response.status_code == 201
        signal_batch = signal_response.json()

        evaluate_response = await client.post(
            "/api/v1/release-decisions/evaluate",
            json={
                "batch_id": batch["id"],
                "signal_batch_id": signal_batch["id"],
                "control_profile_id": control_profile["id"],
            },
            headers=admin_headers,
        )
        assert evaluate_response.status_code == 200

        portability_response = await client.post(
            "/api/v1/portability-audits",
            json={
                "signal_batch_id": signal_batch["id"],
                "executor_profile_id": executor_profile["id"],
                "locality_profile_id": locality_profile["id"],
                "outcome": "PASS_WITH_RETUNING",
                "retuning_required": True,
                "trigger_metrics": {"hal_margin": 0.08},
            },
            headers=scientist_headers,
        )
        assert portability_response.status_code == 201

        response = await client.get(
            f"/api/v1/audit-packets/batch/{batch['id']}",
            headers=admin_headers,
        )

        assert response.status_code == 200
        payload = response.json()
        portability_entry = payload["packet"]["portability_audits"][0]
        assert portability_entry["outcome"] == "PASS_WITH_RETUNING"
        assert portability_entry["recommended_outcome"] == "PASS_WITH_RETUNING"
        assert portability_entry["rationale"]
        assert portability_entry["recommended_action"]
        assert portability_entry["requires_requalification"] is False
        assert portability_entry["retuning_axes"]
        assert portability_entry["portability_score"] is not None

    @pytest.mark.asyncio
    async def test_audit_export_returns_json_payload(
        self,
        client: AsyncClient,
        admin_headers,
        scientist_headers,
        db_session: AsyncSession,
        test_tenant,
    ):
        await enable_flag(db_session, test_tenant.id, "bos_audit_export")
        batch = await create_batch(client, admin_headers, "EXPORT-JSON-001")
        control_profile = await create_control_profile(client, scientist_headers)
        signal_response = await client.post(
            "/api/v1/signals",
            json={
                "batch_id": batch["id"],
                "signal_api_version": "SIG-1.0",
                "compiled_signal_id": "SIG-EXPORT-JSON-001",
                "potency": 0.22,
                "stability_window_hours": 8.0,
                "freshness_state": "Fresh",
            },
            headers=admin_headers,
        )
        assert signal_response.status_code == 201

        evaluate_response = await client.post(
            "/api/v1/release-decisions/evaluate",
            json={
                "batch_id": batch["id"],
                "signal_batch_id": signal_response.json()["id"],
                "control_profile_id": control_profile["id"],
            },
            headers=admin_headers,
        )
        assert evaluate_response.status_code == 200

        response = await client.get(
            f"/api/v1/audit-packets/batch/{batch['id']}/export?format=json",
            headers=admin_headers,
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        assert "attachment; filename=" in response.headers["content-disposition"]
        assert '"packet_version"' in response.text

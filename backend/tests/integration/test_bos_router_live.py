import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_executor_profile_without_locality_succeeds(
    client: AsyncClient,
    scientist_headers: dict[str, str],
):
    response = await client.post(
        "/api/v1/executor-profiles",
        json={
            "executor_code": "EXEC-001",
            "name": "Primary Executor",
            "executor_type": "pilot",
            "active": True,
        },
        headers=scientist_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["executor_code"] == "EXEC-001"
    assert data["locality_profile_id"] is None


@pytest.mark.asyncio
async def test_create_portability_audit_without_locality_override_succeeds(
    client: AsyncClient,
    scientist_headers: dict[str, str],
):
    batch_response = await client.post(
        "/api/v1/batches",
        json={
            "batch_id": "BOS-LIVE-001",
            "species": "BSF",
            "dm_in": 10.0,
            "dm_out": 2.0,
        },
        headers=scientist_headers,
    )
    assert batch_response.status_code == 201
    batch_id = batch_response.json()["id"]

    signal_response = await client.post(
        "/api/v1/signals",
        json={
            "batch_id": batch_id,
            "compiled_signal_id": "SIG-LIVE-001",
            "potency": 0.14,
            "freshness_state": "Fresh",
        },
        headers=scientist_headers,
    )
    assert signal_response.status_code == 201
    signal_id = signal_response.json()["id"]

    executor_response = await client.post(
        "/api/v1/executor-profiles",
        json={
            "executor_code": "EXEC-002",
            "name": "Portability Executor",
            "active": True,
        },
        headers=scientist_headers,
    )
    assert executor_response.status_code == 201
    executor_id = executor_response.json()["id"]

    portability_response = await client.post(
        "/api/v1/portability-audits",
        json={
            "signal_batch_id": signal_id,
            "executor_profile_id": executor_id,
            "outcome": "PASS",
            "retuning_required": False,
        },
        headers=scientist_headers,
    )

    assert portability_response.status_code == 201
    data = portability_response.json()
    assert data["signal_batch_id"] == signal_id
    assert data["executor_profile_id"] == executor_id
    assert data["locality_profile_id"] is None
    assert data["recommended_outcome"] in {"PASS", "PASS_WITH_RETUNING", "FAIL"}
    assert "portability_score" in data


@pytest.mark.asyncio
async def test_portability_recommendation_endpoint_returns_structured_recommendation(
    client: AsyncClient,
    scientist_headers: dict[str, str],
):
    batch_response = await client.post(
        "/api/v1/batches",
        json={
            "batch_id": "BOS-LIVE-REC-001",
            "species": "BSF",
            "dm_in": 11.0,
            "dm_out": 3.0,
        },
        headers=scientist_headers,
    )
    batch_id = batch_response.json()["id"]

    signal_response = await client.post(
        "/api/v1/signals",
        json={
            "batch_id": batch_id,
            "compiled_signal_id": "SIG-LIVE-REC-001",
            "potency": 0.12,
            "freshness_state": "Stable",
            "stability_window_hours": 4.0,
        },
        headers=scientist_headers,
    )
    signal_id = signal_response.json()["id"]

    executor_response = await client.post(
        "/api/v1/executor-profiles",
        json={
            "executor_code": "EXEC-REC-001",
            "name": "Recommendation Executor",
            "plugin_mode": "adaptive",
            "active": True,
        },
        headers=scientist_headers,
    )
    executor_id = executor_response.json()["id"]

    response = await client.post(
        "/api/v1/portability-audits/recommendation",
        json={
            "signal_batch_id": signal_id,
            "executor_profile_id": executor_id,
        },
        headers=scientist_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["signal_batch_id"] == signal_id
    assert data["executor_profile_id"] == executor_id
    assert isinstance(data["retuning_axes"], list)
    assert data["recommended_outcome"] in {"PASS", "PASS_WITH_RETUNING", "FAIL"}


@pytest.mark.asyncio
async def test_missing_audit_packet_for_batch_returns_404(
    client: AsyncClient,
    scientist_headers: dict[str, str],
):
    response = await client.get("/api/v1/audit-packets/batch/999999", headers=scientist_headers)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_audit_packet_export_returns_markdown_and_json(
    client: AsyncClient,
    scientist_headers: dict[str, str],
    admin_headers: dict[str, str],
):
    await client.put("/api/v1/feature-flags/bos_audit_export", json={"enabled": True}, headers=admin_headers)

    batch_response = await client.post(
        "/api/v1/batches",
        json={
            "batch_id": "BOS-EXPORT-001",
            "species": "BSF",
            "dm_in": 10.0,
            "dm_out": 2.0,
            "n_in": 1.0,
            "n_larvae": 0.5,
            "n_frass": 0.2,
        },
        headers=scientist_headers,
    )
    batch_id = batch_response.json()["id"]

    signal_response = await client.post(
        "/api/v1/signals",
        json={
            "batch_id": batch_id,
            "compiled_signal_id": "SIG-EXPORT-001",
            "potency": 0.18,
            "freshness_state": "Fresh",
            "stability_window_hours": 8.0,
        },
        headers=scientist_headers,
    )
    signal_id = signal_response.json()["id"]

    control_response = await client.post(
        "/api/v1/control-profiles",
        json={
            "name": "Export Control",
            "version": "CTRL-EXPORT-1.0",
            "mtt": 6.0,
            "dose_window_min": 0.1,
            "dose_window_max": 0.3,
        },
        headers=scientist_headers,
    )
    control_id = control_response.json()["id"]

    release_response = await client.post(
        "/api/v1/release-decisions/evaluate",
        json={
            "batch_id": batch_id,
            "signal_batch_id": signal_id,
            "control_profile_id": control_id,
            "persist": True,
        },
        headers=scientist_headers,
    )
    assert release_response.status_code == 200

    md_response = await client.get(f"/api/v1/audit-packets/batch/{batch_id}/export?format=md", headers=scientist_headers)
    assert md_response.status_code == 200
    assert md_response.headers["content-type"].startswith("text/markdown")
    assert "BOS Code Technical Audit Report" in md_response.text
    assert "## Batch Summary" in md_response.text

    json_response = await client.get(f"/api/v1/audit-packets/batch/{batch_id}/export?format=json", headers=scientist_headers)
    assert json_response.status_code == 200
    assert json_response.headers["content-type"].startswith("application/json")
    payload = json_response.json()
    assert payload["batch_id"] == batch_id
    assert payload["packet"]["signal_batch"]["compiled_signal_id"] == "SIG-EXPORT-001"


@pytest.mark.asyncio
async def test_signal_compile_and_refresh_endpoints_work(
    client: AsyncClient,
    scientist_headers: dict[str, str],
    admin_headers: dict[str, str],
):
    await client.put("/api/v1/feature-flags/bos_signal_compile", json={"enabled": True}, headers=admin_headers)

    batch_response = await client.post(
        "/api/v1/batches",
        json={
            "batch_id": "BOS-COMPILE-001",
            "species": "BSF",
            "dm_in": 12.0,
            "dm_out": 3.2,
            "n_in": 1.1,
            "n_larvae": 0.6,
            "n_frass": 0.2,
        },
        headers=scientist_headers,
    )
    batch_id = batch_response.json()["id"]

    control_response = await client.post(
        "/api/v1/control-profiles",
        json={
            "name": "Compile Control",
            "version": "CTRL-COMPILE-1.0",
            "mtt": 6.0,
            "dose_window_min": 0.1,
            "dose_window_max": 0.3,
            "stability_window_hours": 12.0,
        },
        headers=scientist_headers,
    )
    control_id = control_response.json()["id"]

    compile_response = await client.post(
        "/api/v1/signals/compile",
        json={
            "batch_id": batch_id,
            "control_profile_id": control_id,
            "compiler_version": "BOS-2.0",
            "apply_locality_shifts": True,
        },
        headers=scientist_headers,
    )
    assert compile_response.status_code == 201
    compile_payload = compile_response.json()
    assert compile_payload["compile_status"] == "compiled"
    assert compile_payload["compiled_signal_id"]
    assert "mechanistic_context" in compile_payload["qc_markers"]["compile_context"]
    assert compile_payload["qc_markers"]["compile_context"]["mechanistic_context"]["c_di_ser"]["score"] > 0
    signal_id = compile_payload["id"]

    refresh_response = await client.post(f"/api/v1/signals/{signal_id}/refresh", headers=scientist_headers)
    assert refresh_response.status_code == 200
    refresh_payload = refresh_response.json()
    assert refresh_payload["signal_batch"]["id"] == signal_id
    assert refresh_payload["refreshed_state"] in {"Fresh", "Stable", "Stale"}
    assert isinstance(refresh_payload["freshness_score"], float)


@pytest.mark.asyncio
async def test_supervisor_and_handover_endpoints_return_mechanistic_state(
    client: AsyncClient,
    scientist_headers: dict[str, str],
    admin_headers: dict[str, str],
):
    await client.put("/api/v1/feature-flags/bos_signal_compile", json={"enabled": True}, headers=admin_headers)

    batch_response = await client.post(
        "/api/v1/batches",
        json={
            "batch_id": "BOS-SUP-001",
            "species": "BSF",
            "dm_in": 10.0,
            "dm_out": 3.0,
        },
        headers=scientist_headers,
    )
    batch_id = batch_response.json()["id"]

    compile_response = await client.post(
        "/api/v1/signals/compile",
        json={"batch_id": batch_id, "compiler_version": "BOS-2.1"},
        headers=scientist_headers,
    )
    assert compile_response.status_code == 201
    signal_id = compile_response.json()["id"]

    observation = {
        "uv254": 2.4,
        "od280": 2.0,
        "do": 5.1,
        "ph": 7.1,
        "elapsed_hours": 8.0,
        "previous_c_signal_hat": 0.58,
        "previous_elapsed_hours": 7.0,
        "previous_dc_dt_hat": 0.03,
    }

    supervisor_response = await client.post(
        f"/api/v1/signals/{signal_id}/supervisor",
        json=observation,
        headers=scientist_headers,
    )
    assert supervisor_response.status_code == 200
    supervisor_payload = supervisor_response.json()
    assert supervisor_payload["signal_batch_id"] == signal_id
    assert supervisor_payload["channels_used"] == ["uv254", "od280", "do", "ph"]
    assert 0.0 <= supervisor_payload["observability_score"] <= 1.0
    assert "mechanistic_context" in supervisor_payload
    assert supervisor_payload["mechanistic_context"]["handover_envelope"]["tau_star_min"] > 0
    assert supervisor_payload["mechanistic_context"]["supervisor_snapshot"]["mode"] == "supervisor"

    handover_response = await client.post(
        f"/api/v1/signals/{signal_id}/handover-recommendation",
        json=observation,
        headers=scientist_headers,
    )
    assert handover_response.status_code == 200
    handover_payload = handover_response.json()
    assert handover_payload["signal_batch_id"] == signal_id
    assert handover_payload["trigger_reason"] in {
        "monitor_signal",
        "confidence_threshold",
        "negative_slope_persistence",
    }
    assert "mechanistic_context" in handover_payload
    assert 0.0 <= handover_payload["confidence"] <= 1.0
    assert handover_payload["mechanistic_context"]["supervisor_snapshot"]["mode"] == "handover"

    signals_response = await client.get("/api/v1/signals", headers=scientist_headers)
    assert signals_response.status_code == 200
    persisted_signal = next(item for item in signals_response.json() if item["id"] == signal_id)
    assert persisted_signal["qc_markers"]["supervisor_latest"]["mode"] == "handover"
    assert len(persisted_signal["qc_markers"]["supervisor_history"]) >= 2

    audit_packet_response = await client.get(
        f"/api/v1/audit-packets/batch/{batch_id}",
        headers=scientist_headers,
    )
    assert audit_packet_response.status_code == 200
    audit_packet_payload = audit_packet_response.json()
    assert audit_packet_payload["signal_validity"]["supervisor_snapshot"]["mode"] == "handover"


@pytest.mark.asyncio
async def test_audit_export_includes_mechanistic_section_for_compiled_signal(
    client: AsyncClient,
    scientist_headers: dict[str, str],
    admin_headers: dict[str, str],
):
    await client.put("/api/v1/feature-flags/bos_audit_export", json={"enabled": True}, headers=admin_headers)
    await client.put("/api/v1/feature-flags/bos_signal_compile", json={"enabled": True}, headers=admin_headers)

    batch_response = await client.post(
        "/api/v1/batches",
        json={
            "batch_id": "BOS-EXPORT-MECH-001",
            "species": "BSF",
            "dm_in": 12.0,
            "dm_out": 3.4,
            "n_in": 1.2,
            "n_larvae": 0.7,
            "n_frass": 0.2,
        },
        headers=scientist_headers,
    )
    batch_id = batch_response.json()["id"]

    control_response = await client.post(
        "/api/v1/control-profiles",
        json={
            "name": "Mechanistic Export Control",
            "version": "CTRL-EXPORT-MECH-1.0",
            "mtt": 6.0,
            "dose_window_min": 0.1,
            "dose_window_max": 0.3,
            "stability_window_hours": 10.0,
        },
        headers=scientist_headers,
    )
    control_id = control_response.json()["id"]

    compile_response = await client.post(
        "/api/v1/signals/compile",
        json={
            "batch_id": batch_id,
            "control_profile_id": control_id,
            "compiler_version": "BOS-2.2",
        },
        headers=scientist_headers,
    )
    assert compile_response.status_code == 201
    signal_id = compile_response.json()["id"]

    release_response = await client.post(
        "/api/v1/release-decisions/evaluate",
        json={
            "batch_id": batch_id,
            "signal_batch_id": signal_id,
            "control_profile_id": control_id,
            "persist": True,
        },
        headers=scientist_headers,
    )
    assert release_response.status_code == 200

    md_response = await client.get(
        f"/api/v1/audit-packets/batch/{batch_id}/export?format=md",
        headers=scientist_headers,
    )
    assert md_response.status_code == 200
    assert "## Mechanistic Diagnostics" in md_response.text
    assert "- Tau star (min):" in md_response.text
    assert "- C-DI-SER:" in md_response.text

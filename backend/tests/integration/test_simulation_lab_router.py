import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import UTC, datetime

from app.models import Tenant, User
from app.models_bos import (
    ExternalSourceRecord,
    LiteratureExtractionCandidateRecord,
    SimulationAuditEventRecord,
    SimulationCycleRecord,
    SimulationRunRecord,
    SimulationScenarioRecord,
)
from app.schemas.reference_ingestion import ReferenceIngestionStagedItem, ReferenceParserMetadata
from app.services.feature_flags import set_db_override
from app.services.reference_ingestion_service import reference_ingestion_service
from app.services.simulation_lab_service import (
    compare_policies,
    create_scenario,
    export_run,
    get_cycles,
    get_scenario,
    import_scenario_from_reference,
    reset_simulation_lab_store,
)
from app.schemas.simulation_lab import SimulationScenarioCreate, SimulationScenarioImportRequest


async def enable_simulation_lab(db_session: AsyncSession, tenant_id: int) -> None:
    await set_db_override(
        db_session,
        flag_name="bos_simulation_lab",
        tenant_id=tenant_id,
        enabled=True,
    )


@pytest.mark.asyncio
async def test_simulation_lab_requires_feature_flag(client: AsyncClient, operator_headers):
    reset_simulation_lab_store()

    response = await client.post(
        "/api/v1/bos/simulation-lab/scenarios",
        json={"scenario": "moisture_drift", "cycles": 8, "seed": 11},
        headers=operator_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "bos_simulation_lab_disabled"


@pytest.mark.asyncio
async def test_simulation_lab_runs_full_persisted_flow(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
):
    reset_simulation_lab_store()
    await enable_simulation_lab(db_session, test_tenant.id)

    create_response = await client.post(
        "/api/v1/bos/simulation-lab/scenarios",
        json={
            "species": "BSF",
            "feedstock": "mixed_food_waste",
            "scenario": "moisture_drift",
            "cycles": 8,
            "seed": 17,
            "initial_state": {
                "biomass": 0.5,
                "substrate": 10,
                "temperature": 28,
                "moisture": 70,
                "nitrogen": 50,
            },
        },
        headers=operator_headers,
    )
    assert create_response.status_code == 201
    scenario = create_response.json()
    simulation_id = scenario["simulation_id"]
    assert scenario["status"] == "created"

    run_response = await client.post(
        f"/api/v1/bos/simulation-lab/scenarios/{simulation_id}/run",
        headers=operator_headers,
    )
    assert run_response.status_code == 200
    run = run_response.json()
    assert run["summary"]["cycle_count"] == 8
    assert len(run["cycles"]) == 8
    assert run["cycles"][0]["sensor_observation"]["sensor_quality"] == "synthetic"
    assert run["cycles"][0]["visual_observation"]["source"] == "synthetic_visual_mock"
    assert run["cycles"][0]["visual_observation"]["hardware_camera_used"] is False
    assert run["cycles"][0]["actuator_result"]["hardware_execution"] is False

    cycles_response = await client.get(
        f"/api/v1/bos/simulation-lab/scenarios/{simulation_id}/cycles",
        headers=operator_headers,
    )
    assert cycles_response.status_code == 200
    assert len(cycles_response.json()["cycles"]) == 8

    audit_response = await client.get(
        f"/api/v1/bos/simulation-lab/scenarios/{simulation_id}/audit-trace",
        headers=operator_headers,
    )
    assert audit_response.status_code == 200
    audit_trace = audit_response.json()["audit_trace"]
    assert len(audit_trace) == 8
    assert "virtual_actuator" in audit_trace[0]["evidence_chain"]
    assert "synthetic_visual_observation" in audit_trace[0]["evidence_chain"]

    export_response = await client.get(
        f"/api/v1/bos/simulation-lab/scenarios/{simulation_id}/export",
        headers=operator_headers,
    )
    assert export_response.status_code == 200
    exported = export_response.json()
    assert exported["simulation_id"] == simulation_id
    assert exported["summary"]["cycle_count"] == 8
    assert exported["cycles"][0]["risk_prediction"]["source"] in {"chronos", "deterministic_proxy"}
    assert "execution_mode" in exported["cycles"][0]["risk_prediction"]
    assert "confidence_band" in exported["cycles"][0]["risk_prediction"]
    assert exported["cycles"][0]["visual_observation"]["ultralytics_dry_run"] is True
    assert "does not execute hardware actions" in exported["disclaimer"]

    scenarios_response = await client.get(
        "/api/v1/bos/simulation-lab/scenarios?species=BSF&feedstock=mixed_food_waste",
        headers=operator_headers,
    )
    assert scenarios_response.status_code == 200
    assert any(item["simulation_id"] == simulation_id for item in scenarios_response.json())

    runs_response = await client.get(
        f"/api/v1/bos/simulation-lab/scenarios/{simulation_id}/runs",
        headers=operator_headers,
    )
    assert runs_response.status_code == 200
    runs = runs_response.json()
    assert len(runs) == 1
    assert runs[0]["cycle_count"] == 8

    scenario_count = await db_session.scalar(
        select(func.count()).select_from(SimulationScenarioRecord).where(
            SimulationScenarioRecord.simulation_id == simulation_id,
            SimulationScenarioRecord.tenant_id == test_tenant.id,
        )
    )
    run_count = await db_session.scalar(
        select(func.count()).select_from(SimulationRunRecord).where(
            SimulationRunRecord.simulation_id == simulation_id,
            SimulationRunRecord.tenant_id == test_tenant.id,
        )
    )
    cycle_count = await db_session.scalar(
        select(func.count()).select_from(SimulationCycleRecord).where(
            SimulationCycleRecord.simulation_id == simulation_id,
            SimulationCycleRecord.tenant_id == test_tenant.id,
        )
    )
    audit_count = await db_session.scalar(
        select(func.count()).select_from(SimulationAuditEventRecord).where(
            SimulationAuditEventRecord.simulation_id == simulation_id,
            SimulationAuditEventRecord.tenant_id == test_tenant.id,
        )
    )
    assert scenario_count == 1
    assert run_count == 1
    assert cycle_count == 8
    assert audit_count == 8


@pytest.mark.asyncio
async def test_simulation_lab_sludge_route_carries_labsim_governance(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
):
    reset_simulation_lab_store()
    await enable_simulation_lab(db_session, test_tenant.id)

    create_response = await client.post(
        "/api/v1/bos/simulation-lab/scenarios",
        json={
            "species": "BSF",
            "feedstock": "municipal_sludge_heavy_metal_screen",
            "scenario": "temperature_spike",
            "cycles": 6,
            "seed": 82,
            "policy": "risk_minimizing",
        },
        headers=operator_headers,
    )
    assert create_response.status_code == 201
    scenario = create_response.json()
    simulation_id = scenario["simulation_id"]
    scenario_sources = scenario["evidence_sources"]
    assert any(source["field"] == "lab_profile" for source in scenario_sources)
    assert any(
        source["field"] == "heavy_metal_gate" and source["source_kind"] == "official_standard"
        for source in scenario_sources
    )

    run_response = await client.post(
        f"/api/v1/bos/simulation-lab/scenarios/{simulation_id}/run",
        headers=operator_headers,
    )
    assert run_response.status_code == 200
    first_cycle = run_response.json()["cycles"][0]
    assert first_cycle["risk_prediction"]["lab_governance"]["heavy_metal_gate"] == "redline"
    assert first_cycle["risk_prediction"]["lab_assay_comparison"]["source_kind"] == "manuscript_campaign"
    assert first_cycle["risk_prediction"]["lab_assay_comparison"]["calibration_status"] == "review_required"
    assert first_cycle["audit_event"]["lab_governance"]["product_use_lock"] == "research_simulation_only"
    assert first_cycle["audit_event"]["lab_assay_comparison"]["measured_anchor"]["heavy_metal_index"] == 0.82
    assert "lab_governance_gate" in first_cycle["audit_event"]["evidence_chain"]
    assert "lab_assay_calibration" in first_cycle["audit_event"]["evidence_chain"]
    assert any(source["field"] == "cycle_heavy_metal_gate" for source in first_cycle["evidence_sources"])
    assert any(source["field"] == "lab_assay_comparison" for source in first_cycle["evidence_sources"])

    export_response = await client.get(
        f"/api/v1/bos/simulation-lab/scenarios/{simulation_id}/export",
        headers=operator_headers,
    )
    assert export_response.status_code == 200
    assert "heavy-metal and product-use locks" in export_response.json()["disclaimer"]

    appendix_md_response = await client.get(
        f"/api/v1/bos/simulation-lab/scenarios/{simulation_id}/release-appendix?format=md",
        headers=operator_headers,
    )
    assert appendix_md_response.status_code == 200
    assert "LabSim Governance" in appendix_md_response.text
    assert "Lab Assay Calibration Anchors" in appendix_md_response.text
    assert "bsf_sludge_heavy_metal_redline" in appendix_md_response.text
    assert "research_simulation_only" in appendix_md_response.text


@pytest.mark.asyncio
async def test_simulation_lab_uses_operator_entered_lab_assay_measurements(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
):
    reset_simulation_lab_store()
    await enable_simulation_lab(db_session, test_tenant.id)

    create_response = await client.post(
        "/api/v1/bos/simulation-lab/scenarios",
        json={
            "species": "BSF",
            "feedstock": "distillers_grain",
            "scenario": "normal",
            "cycles": 6,
            "seed": 56,
            "policy": "rule_based",
            "lab_assay_measurements": {
                "biomass": 0.91,
                "substrate": 4.45,
                "moisture": 67.2,
                "heavy_metal_index": 0.09,
            },
        },
        headers=operator_headers,
    )
    assert create_response.status_code == 201
    scenario = create_response.json()
    simulation_id = scenario["simulation_id"]
    assert scenario["lab_assay_measurements"]["biomass"] == 0.91
    assert any(source["field"] == "lab_assay_measurements" for source in scenario["evidence_sources"])

    run_response = await client.post(
        f"/api/v1/bos/simulation-lab/scenarios/{simulation_id}/run",
        headers=operator_headers,
    )
    assert run_response.status_code == 200
    assay = run_response.json()["cycles"][0]["risk_prediction"]["lab_assay_comparison"]
    assert assay["measurement_mode"] == "operator_entered"
    assert assay["source_ref"] == "operator_entered_lab_assay_measurements"
    assert assay["measured_anchor"]["heavy_metal_index"] == 0.09

    appendix_md_response = await client.get(
        f"/api/v1/bos/simulation-lab/scenarios/{simulation_id}/release-appendix?format=md",
        headers=operator_headers,
    )
    assert appendix_md_response.status_code == 200
    assert "Measurement source: operator_entered" in appendix_md_response.text
    assert "heavy_metal_index: measured anchor 0.09" in appendix_md_response.text


@pytest.mark.asyncio
async def test_simulation_lab_imports_reference_lab_assay_measurements(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
):
    reset_simulation_lab_store()
    await enable_simulation_lab(db_session, test_tenant.id)

    staged = ReferenceIngestionStagedItem(
        id="reference_assay_measurements",
        tenant_id=test_tenant.id,
        source_title="Reference assay measurements",
        source_anchor="Table 2 measured assay anchors",
        source_type="pdf",
        species_chain=["BSF"],
        feedstocks=["distillers_grain"],
        evidence_level="peer_reviewed_literature",
        campaign_type="adaptability_screen",
        summary="Reference payload includes measured LabSim assay anchors for review-gated calibration.",
        key_parameters={"kernel_temperature_c": 27.0, "total_substrate_g": 10.0},
        observed_outputs={
            "lab_assay_measurements": {
                "biomass": 0.93,
                "substrate": 4.25,
                "moisture": 66.4,
                "heavy_metal_index": 0.12,
            },
        },
        references=["Reference assay fixture"],
        parser_metadata=ReferenceParserMetadata(
            parser_name="test",
            execution_mode="fixture",
            parsed_at=datetime.now(UTC),
            extracted_field_count=10,
        ),
        status="staged",
        human_review_required=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    reference_ingestion_service._write_staged_item(staged)

    try:
        import_response = await client.post(
            "/api/v1/bos/simulation-lab/scenarios/import-reference",
            json={"reference_id": staged.id, "cycles": 6, "seed": 71, "policy": "rule_based"},
            headers=operator_headers,
        )
        assert import_response.status_code == 201
        imported = import_response.json()
        simulation_id = imported["scenario"]["simulation_id"]
        assert imported["scenario"]["lab_assay_measurements"]["biomass"] == 0.93
        assert imported["scenario"]["lab_assay_measurements"]["heavy_metal_index"] == 0.12
        assert imported["import_metadata"]["field_sources"]["lab_assay_measurements.biomass"] == "reference.lab_assay_measurements"

        run_response = await client.post(
            f"/api/v1/bos/simulation-lab/scenarios/{simulation_id}/run",
            headers=operator_headers,
        )
        assert run_response.status_code == 200
        assay = run_response.json()["cycles"][0]["risk_prediction"]["lab_assay_comparison"]
        assert assay["measurement_mode"] == "reference_imported"
        assert assay["source_kind"] == "staged_reference"
        assert assay["source_ref"] == staged.id
        assert assay["review_status"] == "human_review_required"
        assert assay["measured_anchor"]["biomass"] == 0.93
        assert assay["measured_anchor"]["heavy_metal_index"] == 0.12

        appendix_response = await client.get(
            f"/api/v1/bos/simulation-lab/scenarios/{simulation_id}/release-appendix?format=md",
            headers=operator_headers,
        )
        assert appendix_response.status_code == 200
        assert "Measurement source: reference_imported" in appendix_response.text
        assert f"Source ref: {staged.id}" in appendix_response.text
    finally:
        reference_ingestion_service.reset_tenant_storage(test_tenant.id)


@pytest.mark.asyncio
async def test_simulation_lab_imports_literature_candidate_measurement(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
):
    reset_simulation_lab_store()
    await enable_simulation_lab(db_session, test_tenant.id)

    source = ExternalSourceRecord(
        source_id="LABSIM-LIT-SOURCE-001",
        source_name="LabSim literature source",
        source_owner="Fixture publisher",
        source_category="peer_reviewed_literature",
        license_note="Fixture license note",
        bos_module="simulation_lab",
        evidence_source_kind="peer_reviewed_literature",
        ingestion_mode="manual_review_first",
        auto_ingestion_note=None,
        human_review_note="Human review required before use.",
        next_action="Review candidate measurement before release evidence use.",
        raw_payload={},
    )
    db_session.add(source)
    await db_session.flush()
    candidate = LiteratureExtractionCandidateRecord(
        tenant_id=test_tenant.id,
        candidate_id="LIT-LABSIM-BIOMASS-001",
        source_id=source.source_id,
        doi="10.0000/labsim.fixture",
        source_ref="doi:10.0000/labsim.fixture",
        title="Literature candidate biomass assay",
        species="BSF",
        feedstock="distillers_grain",
        treatment="distillers grain candidate assay",
        metric_key="biomass",
        metric_label="Measured biomass",
        raw_value="0.94",
        unit="kg",
        condition_context="candidate measurement context",
        experiment_context="review-gated LabSim import fixture",
        table_or_section_ref="Table 4",
        extraction_note="Candidate raw numeric value for LabSim measured anchor import.",
        license_note="Fixture license note",
        source_kind="peer_reviewed_literature",
        review_status="pending_review",
        human_review_required=True,
        numeric_values_included=True,
        release_evidence_allowed=False,
        runtime_activation_enabled=False,
        validated_default_write_enabled=False,
        promotion_enabled=False,
        guardrails=[
            "literature_extraction_candidates_are_review_gated",
            "candidate_raw_values_are_pending_review_only",
        ],
        raw_payload={},
    )
    db_session.add(candidate)
    await db_session.commit()

    import_response = await client.post(
        "/api/v1/bos/simulation-lab/scenarios/import-reference",
        json={"reference_id": candidate.candidate_id, "cycles": 6, "seed": 72, "policy": "rule_based"},
        headers=operator_headers,
    )
    assert import_response.status_code == 201
    imported = import_response.json()
    simulation_id = imported["scenario"]["simulation_id"]
    assert imported["scenario"]["lab_assay_measurements"]["biomass"] == 0.94
    assert imported["import_metadata"]["reference_source"] == "peer_reviewed_literature"
    assert imported["import_metadata"]["review_status"] == "pending_review"
    assert imported["import_metadata"]["human_review_required"] is True
    assert imported["import_metadata"]["numeric_values_included"] is True
    assert imported["import_metadata"]["release_evidence_allowed"] is False
    assert imported["import_metadata"]["runtime_activation_enabled"] is False
    assert imported["import_metadata"]["validated_default_write_enabled"] is False
    assert imported["import_metadata"]["promotion_enabled"] is False

    run_response = await client.post(
        f"/api/v1/bos/simulation-lab/scenarios/{simulation_id}/run",
        headers=operator_headers,
    )
    assert run_response.status_code == 200
    assay = run_response.json()["cycles"][0]["risk_prediction"]["lab_assay_comparison"]
    assert assay["measurement_mode"] == "reference_imported"
    assert assay["source_kind"] == "peer_reviewed_literature"
    assert assay["source_ref"] == candidate.candidate_id
    assert assay["review_status"] == "pending_review"
    assert assay["human_review_required"] is True
    assert assay["numeric_values_included"] is True
    assert assay["release_evidence_allowed"] is False
    assert assay["runtime_activation_enabled"] is False
    assert assay["validated_default_write_enabled"] is False
    assert assay["measured_anchor"]["biomass"] == 0.94
    assert assay["measured_anchor"]["heavy_metal_index"] == 0.17

    appendix_response = await client.get(
        f"/api/v1/bos/simulation-lab/scenarios/{simulation_id}/release-appendix?format=md",
        headers=operator_headers,
    )
    assert appendix_response.status_code == 200
    assert "Measurement source: reference_imported" in appendix_response.text
    assert "Source kind: peer_reviewed_literature" in appendix_response.text
    assert f"Source ref: {candidate.candidate_id}" in appendix_response.text
    assert "Review status: pending_review" in appendix_response.text
    assert "Human review required: true" in appendix_response.text
    assert "Numeric values included: true" in appendix_response.text
    assert "Release evidence allowed: false" in appendix_response.text
    assert "Runtime activation enabled: false" in appendix_response.text
    assert "Validated default write enabled: false" in appendix_response.text


@pytest.mark.asyncio
async def test_simulation_lab_does_not_import_literature_candidate_without_numeric_values(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
):
    reset_simulation_lab_store()
    await enable_simulation_lab(db_session, test_tenant.id)

    source = ExternalSourceRecord(
        source_id="LABSIM-LIT-SOURCE-002",
        source_name="LabSim metadata-only literature source",
        source_owner="Fixture publisher",
        source_category="peer_reviewed_literature",
        license_note="Fixture license note",
        bos_module="simulation_lab",
        evidence_source_kind="peer_reviewed_literature",
        ingestion_mode="manual_review_first",
        auto_ingestion_note=None,
        human_review_note="Human review required before use.",
        next_action="Review candidate metadata; numeric values are not exposed.",
        raw_payload={},
    )
    db_session.add(source)
    await db_session.flush()
    candidate = LiteratureExtractionCandidateRecord(
        tenant_id=test_tenant.id,
        candidate_id="LIT-LABSIM-METADATA-ONLY-001",
        source_id=source.source_id,
        doi="10.0000/labsim.metadata.fixture",
        source_ref="doi:10.0000/labsim.metadata.fixture",
        title="Literature candidate metadata-only assay",
        species="BSF",
        feedstock="distillers_grain",
        treatment="distillers grain metadata-only assay",
        metric_key="biomass",
        metric_label="Measured biomass",
        raw_value="0.94",
        unit="kg",
        condition_context="metadata-only candidate context",
        experiment_context="metadata-only LabSim import fixture",
        table_or_section_ref="Table 5",
        extraction_note="Metadata-only candidate must not expose numeric measured anchors.",
        license_note="Fixture license note",
        source_kind="peer_reviewed_literature",
        review_status="pending_review",
        human_review_required=True,
        numeric_values_included=False,
        release_evidence_allowed=False,
        runtime_activation_enabled=False,
        validated_default_write_enabled=False,
        promotion_enabled=False,
        guardrails=[
            "literature_extraction_candidates_are_review_gated",
            "numeric_values_not_exposed",
        ],
        raw_payload={},
    )
    db_session.add(candidate)
    await db_session.commit()

    import_response = await client.post(
        "/api/v1/bos/simulation-lab/scenarios/import-reference",
        json={"reference_id": candidate.candidate_id, "cycles": 6, "seed": 73, "policy": "rule_based"},
        headers=operator_headers,
    )
    assert import_response.status_code == 201
    imported = import_response.json()
    simulation_id = imported["scenario"]["simulation_id"]
    assert imported["scenario"]["lab_assay_measurements"] is None
    assert imported["import_metadata"]["reference_source"] == "peer_reviewed_literature"
    assert imported["import_metadata"]["review_status"] == "pending_review"
    assert imported["import_metadata"]["human_review_required"] is True
    assert imported["import_metadata"]["numeric_values_included"] is False
    assert imported["import_metadata"]["release_evidence_allowed"] is False
    assert imported["import_metadata"]["runtime_activation_enabled"] is False
    assert imported["import_metadata"]["validated_default_write_enabled"] is False
    assert imported["import_metadata"]["promotion_enabled"] is False

    run_response = await client.post(
        f"/api/v1/bos/simulation-lab/scenarios/{simulation_id}/run",
        headers=operator_headers,
    )
    assert run_response.status_code == 200
    assay = run_response.json()["cycles"][0]["risk_prediction"]["lab_assay_comparison"]
    assert assay["measurement_mode"] == "profile_anchor"
    assert assay["source_ref"] == "labsim_assay_anchor:bsf_distillers_grain_lane"
    assert assay["measured_anchor"]["biomass"] != 0.94
    assert assay["measured_anchor"]["heavy_metal_index"] == 0.17


@pytest.mark.asyncio
async def test_simulation_lab_compare_policies_persists_runs(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
):
    reset_simulation_lab_store()
    await enable_simulation_lab(db_session, test_tenant.id)

    create_response = await client.post(
        "/api/v1/bos/simulation-lab/scenarios",
        json={
            "species": "BSF",
            "feedstock": "mixed_food_waste",
            "scenario": "temperature_spike",
            "cycles": 6,
            "seed": 31,
        },
        headers=operator_headers,
    )
    assert create_response.status_code == 201
    simulation_id = create_response.json()["simulation_id"]

    compare_response = await client.post(
        f"/api/v1/bos/simulation-lab/scenarios/{simulation_id}/compare",
        json={
            "baseline_policy": "rule_based",
            "policies": ["rule_based", "conservative", "growth_optimized", "risk_minimizing"],
        },
        headers=operator_headers,
    )
    assert compare_response.status_code == 200
    comparison = compare_response.json()
    assert comparison["simulation_id"] == simulation_id
    assert comparison["baseline_policy"] == "rule_based"
    assert {item["policy"] for item in comparison["runs"]} == {
        "rule_based",
        "conservative",
        "growth_optimized",
        "risk_minimizing",
    }
    assert all(item["metrics"]["audit_completeness"] == 1.0 for item in comparison["runs"])
    assert comparison["winner"]["lowest_risk"] in {
        "rule_based",
        "conservative",
        "growth_optimized",
        "risk_minimizing",
    }

    run_count = await db_session.scalar(
        select(func.count()).select_from(SimulationRunRecord).where(
            SimulationRunRecord.simulation_id == simulation_id,
            SimulationRunRecord.tenant_id == test_tenant.id,
        )
    )
    cycle_count = await db_session.scalar(
        select(func.count()).select_from(SimulationCycleRecord).where(
            SimulationCycleRecord.simulation_id == simulation_id,
            SimulationCycleRecord.tenant_id == test_tenant.id,
        )
    )
    audit_count = await db_session.scalar(
        select(func.count()).select_from(SimulationAuditEventRecord).where(
            SimulationAuditEventRecord.simulation_id == simulation_id,
            SimulationAuditEventRecord.tenant_id == test_tenant.id,
        )
    )
    assert run_count == 4
    assert cycle_count == 24
    assert audit_count == 24

    runs_response = await client.get(
        f"/api/v1/bos/simulation-lab/scenarios/{simulation_id}/runs",
        headers=operator_headers,
    )
    assert runs_response.status_code == 200
    assert len(runs_response.json()) == 4

    appendix_response = await client.get(
        f"/api/v1/bos/simulation-lab/scenarios/{simulation_id}/release-appendix",
        headers=operator_headers,
    )
    assert appendix_response.status_code == 200
    appendix = appendix_response.json()
    assert appendix["simulation_id"] == simulation_id
    assert appendix["selected_run"]["run_id"]
    assert len(appendix["comparison_runs"]) == 4
    assert len(appendix["audit_trace_hashes"]) == 6
    assert "does not change release decisions" in appendix["disclaimer"]

    appendix_md_response = await client.get(
        f"/api/v1/bos/simulation-lab/scenarios/{simulation_id}/release-appendix?format=md",
        headers=operator_headers,
    )
    assert appendix_md_response.status_code == 200
    assert "Simulation Release Appendix" in appendix_md_response.text
    assert "Policy Comparison" in appendix_md_response.text
    assert "Audit Trace Hashes" in appendix_md_response.text


@pytest.mark.asyncio
async def test_simulation_lab_imports_scenario_from_reference(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
):
    await enable_simulation_lab(db_session, test_tenant.id)

    import_response = await client.post(
        "/api/v1/bos/simulation-lab/scenarios/import-reference",
        json={
            "reference_id": "beer_lees_moisture_gradient",
            "cycles": 6,
            "seed": 41,
            "policy": "conservative",
        },
        headers=operator_headers,
    )

    assert import_response.status_code == 201
    imported = import_response.json()
    assert imported["scenario"]["feedstock"] == "brewery_spent_grains"
    assert imported["scenario"]["scenario"] == "moisture_drift"
    assert imported["scenario"]["policy"] == "conservative"
    assert imported["import_metadata"]["reference_source"] == "manuscript_campaign"
    assert imported["import_metadata"]["extraction_confidence"] > 0.5
    assert imported["import_metadata"]["expected_risk_constraints"]["visual_observation_source"] == "synthetic_visual_mock"

    run_response = await client.post(
        f"/api/v1/bos/simulation-lab/scenarios/{imported['scenario']['simulation_id']}/run",
        headers=operator_headers,
    )
    assert run_response.status_code == 200
    assert run_response.json()["cycles"][0]["visual_observation"]["frame_id"].startswith(
        imported["scenario"]["simulation_id"]
    )


@pytest.mark.asyncio
async def test_simulation_lab_persistence_is_tenant_isolated(
    db_session: AsyncSession,
    operator_user,
):
    tenant_two = Tenant(name="Other Tenant", slug="other-simlab-tenant")
    db_session.add(tenant_two)
    await db_session.flush()
    other_user = User(
        username="other_simlab_user",
        hashed_password="unused",
        role="operator",
        is_active=True,
        tenant_id=tenant_two.id,
    )
    db_session.add(other_user)
    await db_session.commit()
    await db_session.refresh(tenant_two)

    scenario = await create_scenario(
        db_session,
        tenant_id=operator_user.tenant_id,
        user_id=operator_user.id,
        payload=SimulationScenarioCreate(
            scenario="underfeeding",
            cycles=6,
            seed=23,
        ),
    )

    assert await get_scenario(db_session, tenant_id=tenant_two.id, simulation_id=scenario.simulation_id) is None
    assert await get_cycles(db_session, tenant_id=tenant_two.id, simulation_id=scenario.simulation_id) is None
    assert await export_run(db_session, tenant_id=tenant_two.id, simulation_id=scenario.simulation_id) is None
    assert await compare_policies(
        db_session,
        tenant_id=tenant_two.id,
        user_id=other_user.id,
        simulation_id=scenario.simulation_id,
        policies=["rule_based", "conservative"],
        baseline_policy="rule_based",
    ) is None

    staged = ReferenceIngestionStagedItem(
        id="tenant_one_reference",
        tenant_id=operator_user.tenant_id,
        source_title="Tenant one reference",
        source_anchor="Tenant one methods",
        source_type="pdf",
        species_chain=["BSF"],
        feedstocks=["washed_kitchen_waste"],
        evidence_level="manuscript_campaign",
        campaign_type="adaptability_screen",
        summary="Tenant one staged reference for import isolation.",
        key_parameters={"kernel_temperature_c": 27.0},
        observed_outputs={},
        references=["tenant one only"],
        parser_metadata=ReferenceParserMetadata(
            parser_name="test",
            execution_mode="fixture",
            parsed_at=datetime.now(UTC),
            extracted_field_count=6,
        ),
        status="staged",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    reference_ingestion_service._write_staged_item(staged)
    try:
        assert await import_scenario_from_reference(
            db_session,
            tenant_id=tenant_two.id,
            user_id=other_user.id,
            payload=SimulationScenarioImportRequest(reference_id=staged.id),
        ) is None
    finally:
        reference_ingestion_service.reset_tenant_storage(operator_user.tenant_id)


@pytest.mark.asyncio
async def test_simulation_lab_v24_end_to_end_smoke(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
):
    await enable_simulation_lab(db_session, test_tenant.id)

    create_response = await client.post(
        "/api/v1/bos/simulation-lab/scenarios",
        json={
            "species": "BSF",
            "feedstock": "mixed_food_waste",
            "scenario": "moisture_drift",
            "cycles": 6,
            "seed": 24,
            "policy": "rule_based",
        },
        headers=operator_headers,
    )
    assert create_response.status_code == 201
    simulation_id = create_response.json()["simulation_id"]

    run_response = await client.post(
        f"/api/v1/bos/simulation-lab/scenarios/{simulation_id}/run",
        headers=operator_headers,
    )
    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["summary"]["cycle_count"] == 6
    assert run_payload["cycles"][0]["visual_observation"]["source"] == "synthetic_visual_mock"
    assert run_payload["cycles"][0]["actuator_result"]["hardware_execution"] is False

    compare_response = await client.post(
        f"/api/v1/bos/simulation-lab/scenarios/{simulation_id}/compare",
        json={
            "baseline_policy": "rule_based",
            "policies": ["rule_based", "conservative", "growth_optimized", "risk_minimizing"],
        },
        headers=operator_headers,
    )
    assert compare_response.status_code == 200
    comparison_payload = compare_response.json()
    assert len(comparison_payload["runs"]) == 4
    assert all(item["metrics"]["audit_completeness"] == 1.0 for item in comparison_payload["runs"])

    appendix_response = await client.get(
        f"/api/v1/bos/simulation-lab/scenarios/{simulation_id}/release-appendix?format=md",
        headers=operator_headers,
    )
    assert appendix_response.status_code == 200
    assert "Simulation Release Appendix" in appendix_response.text
    assert "Policy Comparison" in appendix_response.text
    assert "Audit Trace Hashes" in appendix_response.text

    import_response = await client.post(
        "/api/v1/bos/simulation-lab/scenarios/import-reference",
        json={
            "reference_id": "beer_lees_moisture_gradient",
            "scenario_name": "paper-derived moisture drift",
            "cycles": 6,
            "seed": 17,
            "policy": "rule_based",
        },
        headers=operator_headers,
    )
    assert import_response.status_code == 201
    imported_payload = import_response.json()
    assert imported_payload["scenario"]["scenario"] == "moisture_drift"
    assert imported_payload["import_metadata"]["reference_id"] == "beer_lees_moisture_gradient"
    assert imported_payload["import_metadata"]["expected_risk_constraints"]["hardware_execution"] is False

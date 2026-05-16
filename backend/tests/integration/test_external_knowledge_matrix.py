import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import EXTERNAL_RUNTIME_ACTIVATION_APPROVER_ROLE, user_has_resolved_role
from app.models import Batch, UserRoleGrant
from app.models_bos import EvidenceItemRecord, HumanApprovalRequestRecord, KnowledgeRelationRecord


async def _seed_compliance_batch(
    client: AsyncClient,
    headers,
    db_session: AsyncSession,
    test_tenant,
    operator_user,
    *,
    batch_id: str,
) -> Batch:
    batch = Batch(
        batch_id=batch_id,
        species="BSF",
        dm_in=12.0,
        dm_out=8.0,
        user_id=operator_user.id,
        tenant_id=test_tenant.id,
    )
    db_session.add(batch)
    await db_session.commit()
    await db_session.refresh(batch)
    for assay_type, value in {
        "moisture": 10.0,
        "protein": 42.0,
        "heavy_metals": 0.2,
        "microbiology": 0.0,
    }.items():
        assay_response = await client.post(
            f"/api/v1/batches/{batch.id}/assays",
            json={"assay_type": assay_type, "value": value},
            headers=headers,
        )
        assert assay_response.status_code == 201
    return batch


async def _grant_runtime_activation_approver(
    db_session: AsyncSession,
    *,
    test_tenant,
    user,
    granted_by_user,
) -> None:
    grant = await db_session.scalar(
        select(UserRoleGrant).where(
            UserRoleGrant.tenant_id == test_tenant.id,
            UserRoleGrant.user_id == user.id,
            UserRoleGrant.role == EXTERNAL_RUNTIME_ACTIVATION_APPROVER_ROLE,
        )
    )
    if grant is None:
        db_session.add(
            UserRoleGrant(
                tenant_id=test_tenant.id,
                user_id=user.id,
                role=EXTERNAL_RUNTIME_ACTIVATION_APPROVER_ROLE,
                granted_by_user_id=granted_by_user.id,
                reason="Runtime activation approver grant for scoped activation tests.",
                is_active=True,
            )
        )
    else:
        grant.is_active = True
        grant.granted_by_user_id = granted_by_user.id
        grant.reason = "Runtime activation approver grant for scoped activation tests."
    await db_session.commit()
    await db_session.refresh(user)


async def _promote_patch_and_activate_candidate(
    client: AsyncClient,
    *,
    candidate_type: str,
    candidate_key: str,
    registry_version: str,
    operator_headers,
    approver_headers,
    idempotency_prefix: str,
) -> dict:
    request_response = await client.post(
        "/api/v1/external-knowledge/promotion-requests",
        json={
            "candidate_type": candidate_type,
            "candidate_key": candidate_key,
            "reason": "Review candidate before runtime activation.",
        },
        headers=operator_headers,
    )
    assert request_response.status_code == 201
    approval_request_id = request_response.json()["approval_request_id"]

    resolve_response = await client.post(
        f"/api/v1/external-knowledge/promotion-requests/{approval_request_id}/resolve",
        json={"approved": True, "reason": "Approved for manual registry patch only."},
        headers=operator_headers,
    )
    assert resolve_response.status_code == 200

    patch_response = await client.post(
        "/api/v1/external-knowledge/manual-registry-patches",
        json={
            "approval_request_id": approval_request_id,
            "registry_version": registry_version,
            "reason": "Patch validated external registry without runtime mutation.",
        },
        headers=operator_headers,
    )
    assert patch_response.status_code == 201
    registry_patch_id = patch_response.json()["registry_patch_id"]

    draft_response = await client.post(
        "/api/v1/external-knowledge/runtime-activation/drafts",
        json={
            "registry_patch_id": registry_patch_id,
            "operator_attestation": "I reviewed the source evidence and request tenant-scoped runtime activation.",
            "idempotency_key": f"{idempotency_prefix}-draft",
        },
        headers=operator_headers,
    )
    assert draft_response.status_code == 201
    draft = draft_response.json()

    approve_draft_response = await client.post(
        f"/api/v1/external-knowledge/runtime-activation/drafts/{draft['activation_request_id']}/resolve",
        json={"approved": True, "reason": "Approved for tenant-scoped runtime activation."},
        headers=approver_headers,
    )
    assert approve_draft_response.status_code == 200

    activation_response = await client.post(
        "/api/v1/external-knowledge/runtime-activation/executions",
        json={
            "activation_request_id": draft["activation_request_id"],
            "expected_previous_active_registry_patch_id": draft["previous_active_registry_patch_id"],
            "operator_attestation": "Activate only this tenant-scoped read path.",
            "idempotency_key": f"{idempotency_prefix}-execute",
        },
        headers=approver_headers,
    )
    assert activation_response.status_code == 201
    return {
        "approval_request_id": approval_request_id,
        "registry_patch_id": registry_patch_id,
        "activation": activation_response.json(),
    }


@pytest.mark.asyncio
async def test_runtime_activation_approver_legacy_role_string_resolves(
    db_session: AsyncSession,
    operator_user,
):
    operator_user.role = f"operator {EXTERNAL_RUNTIME_ACTIVATION_APPROVER_ROLE}"
    await db_session.commit()
    await db_session.refresh(operator_user)

    assert await user_has_resolved_role(db_session, operator_user, EXTERNAL_RUNTIME_ACTIVATION_APPROVER_ROLE) is True


@pytest.mark.asyncio
async def test_lca_pending_candidate_factor_does_not_replace_default(
    client: AsyncClient,
    scientist_headers,
    db_session: AsyncSession,
):
    response = await client.post(
        "/api/v1/lca/compare",
        json={
            "functional_unit": "tonne_substrate",
            "system_boundary": {"scope": "gate_to_gate"},
            "baseline_scenario": {"kind": "landfill"},
            "alternative_scenario": {"kind": "bsf_route"},
            "activity_data": {"substrate_tonnes": 1.0, "electricity_kwh": 20.0},
            "emission_factors": {},
        },
        headers=scientist_headers,
    )

    assert response.status_code == 200
    lca = response.json()
    assert "emission_factor.electricity_kgco2e_per_kwh defaulted" in lca["uncertainty_warnings"]
    assert lca["emission_factors"]["electricity_kgco2e_per_kwh"] == 0.42
    assert lca["factor_sources"]["electricity_kgco2e_per_kwh"]["source_kind"] == "fallback_default"
    assert lca["factor_sources"]["electricity_kgco2e_per_kwh"]["human_review_required"] is True
    assert lca["review_gate"]["pending_candidates_not_used"] is True
    candidate_context = lca["factor_sources"]["electricity_kgco2e_per_kwh"]["candidate_context"]
    assert candidate_context["pending_review_count"] >= 1
    assert candidate_context["approved_count"] == 0

    evidence_item = await db_session.scalar(
        select(EvidenceItemRecord).where(EvidenceItemRecord.evidence_pack_id == lca["evidence_pack_id"])
    )
    assert evidence_item is not None
    assert evidence_item.source_kind == "fallback_default"
    assert evidence_item.payload["review_gate"]["human_review_required"] is True


@pytest.mark.asyncio
async def test_compliance_rule_candidates_remain_review_gated(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
    operator_user,
):
    batch = await _seed_compliance_batch(
        client,
        operator_headers,
        db_session,
        test_tenant,
        operator_user,
        batch_id="BATCH-COMPLIANCE-CANDIDATE-RULE-001",
    )

    response = await client.post(
        "/api/v1/compliance/evaluate",
        json={"batch_id": batch.id, "jurisdiction": "CN", "product_category": "insect_dry_matter"},
        headers=operator_headers,
    )

    assert response.status_code == 201
    gate = response.json()
    assert gate["status"] == "ready_for_review"
    assert gate["status"] != "compliant"
    assert gate["human_review_required"] is True
    review_gate = gate["payload"]["review_gate"]
    assert review_gate["pending_candidates_not_used"] is True
    assert review_gate["rule_candidates"]["pending_review_count"] >= 1
    assert review_gate["rule_candidates"]["approved_count"] == 0

    evidence_item = await db_session.scalar(
        select(EvidenceItemRecord).where(EvidenceItemRecord.evidence_pack_id == gate["evidence_pack_id"])
    )
    assert evidence_item is not None
    assert evidence_item.source_kind == "fallback_default"
    assert evidence_item.payload["review_gate"]["human_review_required"] is True


@pytest.mark.asyncio
async def test_compliance_runtime_activation_uses_active_registry_and_rolls_back(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
    operator_user,
):
    await _grant_runtime_activation_approver(
        db_session,
        test_tenant=test_tenant,
        user=operator_user,
        granted_by_user=operator_user,
    )
    batch = await _seed_compliance_batch(
        client,
        operator_headers,
        db_session,
        test_tenant,
        operator_user,
        batch_id="BATCH-COMPLIANCE-RUNTIME-ACTIVATION-001",
    )

    before_response = await client.post(
        "/api/v1/compliance/evaluate",
        json={"batch_id": batch.id, "jurisdiction": "CN", "product_category": "insect_dry_matter"},
        headers=operator_headers,
    )
    assert before_response.status_code == 201
    before_gate = before_response.json()
    assert before_gate["payload"]["review_gate"]["pending_candidates_not_used"] is True
    assert before_gate["payload"]["review_gate"]["rule_source"] == "fallback_default"

    activation_bundle = await _promote_patch_and_activate_candidate(
        client,
        candidate_type="compliance_rule_candidate",
        candidate_key="insect_dry_matter.cn",
        registry_version="external-knowledge-registry-compliance-runtime-activation-test",
        operator_headers=operator_headers,
        approver_headers=operator_headers,
        idempotency_prefix="compliance-runtime-activation",
    )

    after_activation_response = await client.post(
        "/api/v1/compliance/evaluate",
        json={"batch_id": batch.id, "jurisdiction": "CN", "product_category": "insect_dry_matter"},
        headers=operator_headers,
    )
    assert after_activation_response.status_code == 201
    after_activation_gate = after_activation_response.json()
    active_review_gate = after_activation_gate["payload"]["review_gate"]
    assert active_review_gate["pending_candidates_not_used"] is False
    assert active_review_gate["rule_source"] == "validated_external_registry_activation"
    assert active_review_gate["active_registry_rule"]["registry_patch_id"] == activation_bundle["registry_patch_id"]
    assert active_review_gate["active_registry_rule"]["activation_id"] == activation_bundle["activation"]["activation_id"]
    assert after_activation_gate["payload"]["required_assays"] == ["moisture", "protein", "heavy_metals", "microbiology"]

    active_evidence_item = await db_session.scalar(
        select(EvidenceItemRecord).where(EvidenceItemRecord.evidence_pack_id == after_activation_gate["evidence_pack_id"])
    )
    assert active_evidence_item is not None
    assert active_evidence_item.source_kind == "official_standard"
    assert active_evidence_item.payload["review_gate"]["rule_source"] == "validated_external_registry_activation"
    assert active_evidence_item.payload["review_gate"]["active_registry_rule"]["registry_patch_id"] == activation_bundle["registry_patch_id"]

    rollback_response = await client.post(
        "/api/v1/external-knowledge/runtime-activation/rollbacks",
        json={
            "activation_id": activation_bundle["activation"]["activation_id"],
            "operator_attestation": "Rollback compliance rule runtime path to fallback defaults.",
            "idempotency_key": "compliance-runtime-activation-rollback",
        },
        headers=operator_headers,
    )
    assert rollback_response.status_code == 201

    after_rollback_response = await client.post(
        "/api/v1/compliance/evaluate",
        json={"batch_id": batch.id, "jurisdiction": "CN", "product_category": "insect_dry_matter"},
        headers=operator_headers,
    )
    assert after_rollback_response.status_code == 201
    after_rollback_gate = after_rollback_response.json()
    assert after_rollback_gate["payload"]["review_gate"]["pending_candidates_not_used"] is True
    assert after_rollback_gate["payload"]["review_gate"]["rule_source"] == "fallback_default"


@pytest.mark.asyncio
async def test_multi_bioexecutor_benchmark_cases_are_seeded(
    client: AsyncClient,
    operator_headers,
):
    response = await client.get("/api/v1/benchmarks/cases", headers=operator_headers)

    assert response.status_code == 200
    cases = response.json()
    case_ids = {case["case_id"] for case in cases}
    assert {
        "CASE-bsf_mixed_food_waste",
        "CASE-tenebrio_brewery_spent_grains",
        "CASE-protaetia_distillers_grains",
        "CASE-vermicompost_food_waste_baseline",
        "CASE-microbial_composting_food_waste_baseline",
        "CASE-anaerobic_digestion_food_waste_baseline",
    }.issubset(case_ids)
    assert all(case["human_review_required"] is True for case in cases)
    assert any(case["scenario_payload"].get("species") == "Tenebrio molitor" for case in cases)


@pytest.mark.asyncio
async def test_provider_capability_matrix_is_metadata_only_and_review_gated(
    client: AsyncClient,
    operator_headers,
):
    response = await client.get("/api/v1/model-providers/capabilities", headers=operator_headers)

    assert response.status_code == 200
    matrix = response.json()
    providers = {item["provider"] for item in matrix["providers"]}
    assert {
        "OpenAI",
        "Anthropic",
        "Google Gemini",
        "Mistral",
        "Meta Llama",
        "Cohere",
        "Qwen/DashScope",
        "DeepSeek",
        "GLM/BigModel",
        "Kimi/Moonshot",
        "ERNIE/Qianfan",
        "MiniMax",
        "SenseNova",
    }.issubset(providers)
    assert matrix["human_review_required"] is True
    assert all(item["checked_date"] for item in matrix["providers"])
    assert all(item["review_status"] == "pending_review" for item in matrix["providers"])
    assert matrix["active_provider_count"] == 0
    assert all(item["runtime_activation_status"] == "inactive" for item in matrix["providers"])


@pytest.mark.asyncio
async def test_provider_capability_runtime_activation_overlays_active_registry_and_rolls_back(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
    operator_user,
):
    await _grant_runtime_activation_approver(
        db_session,
        test_tenant=test_tenant,
        user=operator_user,
        granted_by_user=operator_user,
    )
    before_response = await client.get("/api/v1/model-providers/capabilities", headers=operator_headers)
    assert before_response.status_code == 200
    before_matrix = before_response.json()
    before_openai = next(item for item in before_matrix["providers"] if item["model_id"] == "gpt-5.4")
    assert before_matrix["active_provider_count"] == 0
    assert before_openai["review_status"] == "pending_review"
    assert before_openai["runtime_activation_status"] == "inactive"

    activation_bundle = await _promote_patch_and_activate_candidate(
        client,
        candidate_type="model_provider_capability_candidate",
        candidate_key="gpt-5.4",
        registry_version="external-knowledge-registry-provider-runtime-activation-test",
        operator_headers=operator_headers,
        approver_headers=operator_headers,
        idempotency_prefix="provider-runtime-activation",
    )

    after_activation_response = await client.get("/api/v1/model-providers/capabilities", headers=operator_headers)
    assert after_activation_response.status_code == 200
    after_activation_matrix = after_activation_response.json()
    after_openai = next(item for item in after_activation_matrix["providers"] if item["model_id"] == "gpt-5.4")
    assert after_activation_matrix["active_provider_count"] == 1
    assert after_activation_matrix["runtime_defaults_mutated"] is False
    assert after_openai["review_status"] == "runtime_activated"
    assert after_openai["runtime_activation_status"] == "active"
    assert after_openai["source_kind"] == "validated_external_registry_activation"
    assert after_openai["registry_patch_id"] == activation_bundle["registry_patch_id"]
    assert after_openai["activation_id"] == activation_bundle["activation"]["activation_id"]
    assert after_openai["metadata_policy"] == "active_registry_overlay_recheck_before_runtime_change"

    rollback_response = await client.post(
        "/api/v1/external-knowledge/runtime-activation/rollbacks",
        json={
            "activation_id": activation_bundle["activation"]["activation_id"],
            "operator_attestation": "Rollback provider capability runtime path to metadata-only candidate state.",
            "idempotency_key": "provider-runtime-activation-rollback",
        },
        headers=operator_headers,
    )
    assert rollback_response.status_code == 201

    after_rollback_response = await client.get("/api/v1/model-providers/capabilities", headers=operator_headers)
    assert after_rollback_response.status_code == 200
    after_rollback_matrix = after_rollback_response.json()
    after_rollback_openai = next(item for item in after_rollback_matrix["providers"] if item["model_id"] == "gpt-5.4")
    assert after_rollback_matrix["active_provider_count"] == 0
    assert after_rollback_openai["review_status"] == "pending_review"
    assert after_rollback_openai["runtime_activation_status"] == "inactive"


@pytest.mark.asyncio
async def test_external_knowledge_promotion_is_explicit_review_only(
    client: AsyncClient,
    operator_headers,
    scientist_headers,
    db_session: AsyncSession,
):
    candidates_response = await client.get("/api/v1/external-knowledge/candidates", headers=operator_headers)

    assert candidates_response.status_code == 200
    candidates = candidates_response.json()
    assert candidates["promotion_policy"]["auto_promote"] is False
    assert candidates["promotion_policy"]["validated_defaults_mutated"] is False
    candidate_uids = {item["candidate_uid"] for item in candidates["candidates"]}
    assert "lca_factor_candidate:electricity_kgco2e_per_kwh" in candidate_uids
    assert "model_provider_capability_candidate:gpt-5.4" in candidate_uids
    assert "release_gate_candidate:germination_rate" in candidate_uids
    assert "release_gate_candidate:germination_index" in candidate_uids
    assert "release_gate_candidate:phytotoxicity" in candidate_uids
    assert not any(uid.startswith("literature_extraction_candidate:") for uid in candidate_uids)
    agronomy_candidates = {
        item["key"]: item
        for item in candidates["candidates"]
        if item["key"] in {"germination_rate", "germination_index", "phytotoxicity"}
    }
    assert set(agronomy_candidates) == {"germination_rate", "germination_index", "phytotoxicity"}
    assert all(item["candidate_type"] == "release_gate_candidate" for item in agronomy_candidates.values())
    assert all(item["value"] is None for item in agronomy_candidates.values())
    assert all(item["human_review_required"] is True for item in agronomy_candidates.values())
    assert all(item["approved_for_kernel_use"] is False for item in agronomy_candidates.values())
    assert agronomy_candidates["germination_rate"]["payload"]["review_packet_id"] == "AGR-GERMINATION-RATE-REVIEW-PACKET"
    assert agronomy_candidates["germination_index"]["payload"]["review_packet_id"] == "AGR-GERMINATION-INDEX-REVIEW-PACKET"
    assert agronomy_candidates["phytotoxicity"]["payload"]["review_packet_id"] == "AGR-PHYTOTOXICITY-REVIEW-PACKET"
    assert all(item["payload"]["review_state"] == "pending_review" for item in agronomy_candidates.values())
    assert all(item["payload"]["source_packet_persistence"] == "read_model_only" for item in agronomy_candidates.values())
    assert all(item["payload"]["reviewer_notes_required"] is True for item in agronomy_candidates.values())
    assert all(item["payload"]["release_evidence_allowed"] is False for item in agronomy_candidates.values())
    assert all("numeric_thresholds" in item["payload"]["blocked_use"] for item in agronomy_candidates.values())

    literature_promotion_response = await client.post(
        "/api/v1/external-knowledge/promotion-requests",
        json={
            "candidate_type": "literature_extraction_candidate",
            "candidate_key": "LIT-AGR-GI-001",
            "reason": "Numeric literature extraction candidates must not enter promotion.",
        },
        headers=operator_headers,
    )
    assert literature_promotion_response.status_code == 422

    request_response = await client.post(
        "/api/v1/external-knowledge/promotion-requests",
        json={
            "candidate_type": "lca_factor_candidate",
            "candidate_key": "electricity_kgco2e_per_kwh",
            "reason": "Review grid factor before any manual default patch.",
        },
        headers=operator_headers,
    )

    assert request_response.status_code == 201
    request_payload = request_response.json()
    assert request_payload["status"] == "pending"
    assert request_payload["review_gate"] == "explicit_human_review_required"
    assert request_payload["promoted_to_validated_defaults"] is False
    assert request_payload["side_effects"]["kernel_defaults_mutated"] is False
    assert request_payload["side_effects"]["manual_default_patch_required"] is True

    duplicate_response = await client.post(
        "/api/v1/external-knowledge/promotion-requests",
        json={
            "candidate_type": "lca_factor_candidate",
            "candidate_key": "electricity_kgco2e_per_kwh",
            "reason": "Duplicate request should reuse pending review.",
        },
        headers=operator_headers,
    )
    assert duplicate_response.status_code == 201
    assert duplicate_response.json()["approval_request_id"] == request_payload["approval_request_id"]

    resolve_response = await client.post(
        f"/api/v1/external-knowledge/promotion-requests/{request_payload['approval_request_id']}/resolve",
        json={"approved": True, "reason": "Approved for manual registry patch only."},
        headers=operator_headers,
    )

    assert resolve_response.status_code == 200
    resolved = resolve_response.json()
    assert resolved["status"] == "approved"
    assert resolved["promoted_to_validated_defaults"] is False
    assert resolved["manual_default_patch_required"] is True
    assert resolved["side_effects"]["kernel_defaults_mutated"] is False
    assert resolved["side_effects"]["provider_defaults_mutated"] is False

    approval = await db_session.scalar(
        select(HumanApprovalRequestRecord).where(
            HumanApprovalRequestRecord.approval_request_id == request_payload["approval_request_id"]
        )
    )
    assert approval is not None
    assert approval.status == "approved"
    assert approval.payload["promotion_resolution"]["scope"] == "promotion_review_record_only"

    relation = await db_session.scalar(
        select(KnowledgeRelationRecord).where(KnowledgeRelationRecord.relation_id == resolved["knowledge_relation_id"])
    )
    assert relation is not None
    assert relation.predicate == "promotion_approved_for_manual_default_patch"
    assert relation.object_id == "manual_patch_required"
    assert relation.payload["promotion_side_effects"]["promoted_to_validated_defaults"] is False

    patch_response = await client.post(
        "/api/v1/external-knowledge/manual-registry-patches",
        json={
            "approval_request_id": request_payload["approval_request_id"],
            "registry_version": "external-knowledge-registry-test",
            "reason": "Apply to audited external registry only.",
        },
        headers=operator_headers,
    )
    assert patch_response.status_code == 201
    patch = patch_response.json()
    assert patch["status"] == "applied_to_validated_external_registry"
    assert patch["validated_external_registry_updated"] is True
    assert patch["runtime_defaults_mutated"] is False
    assert patch["side_effects"]["kernel_defaults_mutated"] is False
    assert patch["side_effects"]["requires_separate_runtime_activation"] is True

    duplicate_patch_response = await client.post(
        "/api/v1/external-knowledge/manual-registry-patches",
        json={
            "approval_request_id": request_payload["approval_request_id"],
            "registry_version": "external-knowledge-registry-test",
            "reason": "Duplicate patch should reuse registry relation.",
        },
        headers=operator_headers,
    )
    assert duplicate_patch_response.status_code == 201
    assert duplicate_patch_response.json()["registry_patch_id"] == patch["registry_patch_id"]

    registry_response = await client.get("/api/v1/external-knowledge/validated-defaults", headers=operator_headers)
    assert registry_response.status_code == 200
    registry = registry_response.json()
    assert registry["count"] == 1
    assert registry["runtime_defaults_mutated"] is False
    assert registry["requires_separate_runtime_activation"] is True

    patch_relation = await db_session.scalar(
        select(KnowledgeRelationRecord).where(KnowledgeRelationRecord.relation_id == patch["registry_patch_id"])
    )
    assert patch_relation is not None
    assert patch_relation.predicate == "manual_registry_patch_applied"
    assert patch_relation.object_type == "validated_external_knowledge_registry"
    assert patch_relation.payload["manual_registry_patch_side_effects"]["runtime_defaults_mutated"] is False

    lca_response = await client.post(
        "/api/v1/lca/compare",
        json={
            "functional_unit": "tonne_substrate",
            "system_boundary": {"scope": "gate_to_gate"},
            "baseline_scenario": {"kind": "landfill"},
            "alternative_scenario": {"kind": "bsf_route"},
            "activity_data": {"substrate_tonnes": 1.0, "electricity_kwh": 20.0},
            "emission_factors": {},
        },
        headers=scientist_headers,
    )
    assert lca_response.status_code == 200
    lca = lca_response.json()
    assert lca["emission_factors"]["electricity_kgco2e_per_kwh"] == 0.42
    assert lca["factor_sources"]["electricity_kgco2e_per_kwh"]["source_kind"] == "fallback_default"
    assert lca["review_gate"]["pending_candidates_not_used"] is True


@pytest.mark.asyncio
async def test_external_knowledge_promotion_rejects_unknown_candidate(
    client: AsyncClient,
    operator_headers,
):
    response = await client.post(
        "/api/v1/external-knowledge/promotion-requests",
        json={
            "candidate_type": "lca_factor_candidate",
            "candidate_key": "not_a_real_candidate",
            "reason": "Should not create review request.",
        },
        headers=operator_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_manual_registry_patch_requires_approved_promotion(
    client: AsyncClient,
    operator_headers,
):
    request_response = await client.post(
        "/api/v1/external-knowledge/promotion-requests",
        json={
            "candidate_type": "model_provider_capability_candidate",
            "candidate_key": "gpt-5.4",
            "reason": "Review provider metadata before registry patch.",
        },
        headers=operator_headers,
    )
    assert request_response.status_code == 201

    patch_response = await client.post(
        "/api/v1/external-knowledge/manual-registry-patches",
        json={
            "approval_request_id": request_response.json()["approval_request_id"],
            "reason": "Should be blocked until approved.",
        },
        headers=operator_headers,
    )
    assert patch_response.status_code == 409


@pytest.mark.asyncio
async def test_runtime_activation_gate_is_reviewed_scoped_and_rollbackable(
    client: AsyncClient,
    operator_headers,
    admin_headers,
    scientist_headers,
    db_session: AsyncSession,
    test_tenant,
    operator_user,
):
    before_response = await client.post(
        "/api/v1/lca/compare",
        json={
            "functional_unit": "tonne_substrate",
            "system_boundary": {"scope": "gate_to_gate"},
            "baseline_scenario": {"kind": "landfill"},
            "alternative_scenario": {"kind": "bsf_route"},
            "activity_data": {"substrate_tonnes": 1.0, "electricity_kwh": 20.0},
            "emission_factors": {},
        },
        headers=scientist_headers,
    )
    assert before_response.status_code == 200
    before_lca = before_response.json()
    assert before_lca["emission_factors"]["electricity_kgco2e_per_kwh"] == 0.42
    assert before_lca["factor_sources"]["electricity_kgco2e_per_kwh"]["source_kind"] == "fallback_default"

    request_response = await client.post(
        "/api/v1/external-knowledge/promotion-requests",
        json={
            "candidate_type": "lca_factor_candidate",
            "candidate_key": "electricity_kgco2e_per_kwh",
            "reason": "Review grid factor before runtime activation.",
        },
        headers=operator_headers,
    )
    assert request_response.status_code == 201
    approval_request_id = request_response.json()["approval_request_id"]

    resolve_response = await client.post(
        f"/api/v1/external-knowledge/promotion-requests/{approval_request_id}/resolve",
        json={"approved": True, "reason": "Approved for manual registry patch only."},
        headers=operator_headers,
    )
    assert resolve_response.status_code == 200

    patch_response = await client.post(
        "/api/v1/external-knowledge/manual-registry-patches",
        json={
            "approval_request_id": approval_request_id,
            "registry_version": "external-knowledge-registry-runtime-activation-test",
            "reason": "Patch validated external registry without runtime mutation.",
        },
        headers=operator_headers,
    )
    assert patch_response.status_code == 201
    registry_patch_id = patch_response.json()["registry_patch_id"]

    readiness_response = await client.get(
        f"/api/v1/external-knowledge/runtime-activation/readiness?registry_patch_id={registry_patch_id}",
        headers=operator_headers,
    )
    assert readiness_response.status_code == 200
    readiness = readiness_response.json()
    assert readiness["activation_ready"] is False
    assert readiness["executable"] is False
    assert "approved_activation_draft_required" in readiness["blockers"]
    assert readiness["required_roles"] == [EXTERNAL_RUNTIME_ACTIVATION_APPROVER_ROLE]

    draft_response = await client.post(
        "/api/v1/external-knowledge/runtime-activation/drafts",
        json={
            "registry_patch_id": registry_patch_id,
            "operator_attestation": "I reviewed the source evidence and request tenant-scoped runtime activation.",
            "idempotency_key": "runtime-activation-draft-test",
        },
        headers=operator_headers,
    )
    assert draft_response.status_code == 201
    draft = draft_response.json()
    assert draft["status"] == "pending"
    assert draft["registry_patch_id"] == registry_patch_id
    assert draft["previous_active_registry_patch_id"] is None
    assert draft["rollback_target_registry_patch_id"] is None
    assert draft["side_effects"]["runtime_defaults_mutated"] is False

    blocked_execution_readiness_response = await client.get(
        f"/api/v1/external-knowledge/runtime-activation/drafts/{draft['activation_request_id']}/execution-readiness",
        headers=operator_headers,
    )
    assert blocked_execution_readiness_response.status_code == 200
    blocked_execution_readiness = blocked_execution_readiness_response.json()
    assert blocked_execution_readiness["activation_ready"] is False
    assert "activation_draft_not_approved:pending" in blocked_execution_readiness["blockers"]
    assert blocked_execution_readiness["required_roles"] == [EXTERNAL_RUNTIME_ACTIVATION_APPROVER_ROLE]

    plain_admin_approve_response = await client.post(
        f"/api/v1/external-knowledge/runtime-activation/drafts/{draft['activation_request_id']}/resolve",
        json={"approved": True, "reason": "Plain admin must not approve runtime activation."},
        headers=admin_headers,
    )
    assert plain_admin_approve_response.status_code == 403

    grant_response = await client.put(
        f"/api/v1/users/{operator_user.id}/role-grants",
        json={
            "roles": [EXTERNAL_RUNTIME_ACTIVATION_APPROVER_ROLE],
            "reason": "grant runtime activation authority for scoped activation test",
        },
        headers=admin_headers,
    )
    assert grant_response.status_code == 200
    assert grant_response.json()["manageable_governance_grants"] == [EXTERNAL_RUNTIME_ACTIVATION_APPROVER_ROLE]
    assert await user_has_resolved_role(db_session, operator_user, EXTERNAL_RUNTIME_ACTIVATION_APPROVER_ROLE) is True

    approve_draft_response = await client.post(
        f"/api/v1/external-knowledge/runtime-activation/drafts/{draft['activation_request_id']}/resolve",
        json={"approved": True, "reason": "Approved for tenant-scoped LCA factor activation."},
        headers=operator_headers,
    )
    assert approve_draft_response.status_code == 200
    assert approve_draft_response.json()["status"] == "approved"
    approval_record = await db_session.scalar(
        select(HumanApprovalRequestRecord).where(
            HumanApprovalRequestRecord.approval_request_id == draft["activation_request_id"]
        )
    )
    assert approval_record is not None
    assert approval_record.payload["review_resolution"]["reviewed_by_user_roles"] == [
        EXTERNAL_RUNTIME_ACTIVATION_APPROVER_ROLE,
        "operator",
    ]

    execution_readiness_response = await client.get(
        f"/api/v1/external-knowledge/runtime-activation/drafts/{draft['activation_request_id']}/execution-readiness",
        headers=operator_headers,
    )
    assert execution_readiness_response.status_code == 200
    execution_readiness = execution_readiness_response.json()
    assert execution_readiness["activation_ready"] is True
    assert execution_readiness["executable_now"] is True
    assert execution_readiness["previous_active_registry_patch_id"] is None
    assert execution_readiness["rollback_target_registry_patch_id"] is None
    assert execution_readiness["required_roles"] == [EXTERNAL_RUNTIME_ACTIVATION_APPROVER_ROLE]

    plain_admin_execute_response = await client.post(
        "/api/v1/external-knowledge/runtime-activation/executions",
        json={
            "activation_request_id": draft["activation_request_id"],
            "expected_previous_active_registry_patch_id": None,
            "operator_attestation": "Plain admin must not execute scoped runtime activation.",
            "idempotency_key": "runtime-activation-execute-plain-admin-test",
        },
        headers=admin_headers,
    )
    assert plain_admin_execute_response.status_code == 403

    activation_response = await client.post(
        "/api/v1/external-knowledge/runtime-activation/executions",
        json={
            "activation_request_id": draft["activation_request_id"],
            "expected_previous_active_registry_patch_id": None,
            "operator_attestation": "Activate only this tenant-scoped LCA factor read path.",
            "idempotency_key": "runtime-activation-execute-test",
        },
        headers=operator_headers,
    )
    assert activation_response.status_code == 201
    activation = activation_response.json()
    assert activation["registry_patch_id"] == registry_patch_id
    assert activation["side_effects"]["scoped_runtime_read_path_changed"] is True
    assert activation["side_effects"]["release_decision"] == "unchanged"
    assert activation["side_effects"]["model_activation"] is False
    assert activation["side_effects"]["external_share"] is False
    activation_record = await db_session.scalar(
        select(KnowledgeRelationRecord).where(KnowledgeRelationRecord.relation_id == activation["activation_id"])
    )
    assert activation_record is not None
    assert activation_record.payload["executed_by_user_roles"] == [
        EXTERNAL_RUNTIME_ACTIVATION_APPROVER_ROLE,
        "operator",
    ]

    after_activation_response = await client.post(
        "/api/v1/lca/compare",
        json={
            "functional_unit": "tonne_substrate",
            "system_boundary": {"scope": "gate_to_gate"},
            "baseline_scenario": {"kind": "landfill"},
            "alternative_scenario": {"kind": "bsf_route"},
            "activity_data": {"substrate_tonnes": 1.0, "electricity_kwh": 20.0},
            "emission_factors": {},
        },
        headers=scientist_headers,
    )
    assert after_activation_response.status_code == 200
    after_activation_lca = after_activation_response.json()
    assert after_activation_lca["emission_factors"]["electricity_kgco2e_per_kwh"] == 0.45
    electricity_source = after_activation_lca["factor_sources"]["electricity_kgco2e_per_kwh"]
    assert electricity_source["source_kind"] == "validated_external_registry_activation"
    assert electricity_source["registry_patch_id"] == registry_patch_id
    assert electricity_source["activation_id"] == activation["activation_id"]

    revoke_response = await client.put(
        f"/api/v1/users/{operator_user.id}/role-grants",
        json={"roles": [], "reason": "revoke runtime activation authority after activation"},
        headers=admin_headers,
    )
    assert revoke_response.status_code == 200
    assert revoke_response.json()["manageable_governance_grants"] == []
    assert await user_has_resolved_role(db_session, operator_user, EXTERNAL_RUNTIME_ACTIVATION_APPROVER_ROLE) is False

    revoked_operator_rollback_response = await client.post(
        "/api/v1/external-knowledge/runtime-activation/rollbacks",
        json={
            "activation_id": activation["activation_id"],
            "operator_attestation": "Revoked operator must not rollback scoped runtime activation.",
            "idempotency_key": "runtime-activation-rollback-revoked-operator-test",
        },
        headers=operator_headers,
    )
    assert revoked_operator_rollback_response.status_code == 403

    regrant_response = await client.put(
        f"/api/v1/users/{operator_user.id}/role-grants",
        json={
            "roles": [EXTERNAL_RUNTIME_ACTIVATION_APPROVER_ROLE],
            "reason": "restore runtime activation authority for rollback test",
        },
        headers=admin_headers,
    )
    assert regrant_response.status_code == 200
    assert await user_has_resolved_role(db_session, operator_user, EXTERNAL_RUNTIME_ACTIVATION_APPROVER_ROLE) is True

    plain_admin_rollback_response = await client.post(
        "/api/v1/external-knowledge/runtime-activation/rollbacks",
        json={
            "activation_id": activation["activation_id"],
            "operator_attestation": "Plain admin must not rollback scoped runtime activation.",
            "idempotency_key": "runtime-activation-rollback-plain-admin-test",
        },
        headers=admin_headers,
    )
    assert plain_admin_rollback_response.status_code == 403

    rollback_response = await client.post(
        "/api/v1/external-knowledge/runtime-activation/rollbacks",
        json={
            "activation_id": activation["activation_id"],
            "operator_attestation": "Rollback to the previous fallback-default runtime state.",
            "idempotency_key": "runtime-activation-rollback-test",
        },
        headers=operator_headers,
    )
    assert rollback_response.status_code == 201
    rollback = rollback_response.json()
    assert rollback["predicate"] == "runtime_activation_rolled_back"
    assert rollback["side_effects"]["rollback_event_written"] is True
    rollback_record = await db_session.scalar(
        select(KnowledgeRelationRecord).where(KnowledgeRelationRecord.relation_id == rollback["activation_id"])
    )
    assert rollback_record is not None
    assert rollback_record.payload["rolled_back_by_user_roles"] == [
        EXTERNAL_RUNTIME_ACTIVATION_APPROVER_ROLE,
        "operator",
    ]

    after_rollback_response = await client.post(
        "/api/v1/lca/compare",
        json={
            "functional_unit": "tonne_substrate",
            "system_boundary": {"scope": "gate_to_gate"},
            "baseline_scenario": {"kind": "landfill"},
            "alternative_scenario": {"kind": "bsf_route"},
            "activity_data": {"substrate_tonnes": 1.0, "electricity_kwh": 20.0},
            "emission_factors": {},
        },
        headers=scientist_headers,
    )
    assert after_rollback_response.status_code == 200
    after_rollback_lca = after_rollback_response.json()
    assert after_rollback_lca["emission_factors"]["electricity_kgco2e_per_kwh"] == 0.42
    assert after_rollback_lca["factor_sources"]["electricity_kgco2e_per_kwh"]["source_kind"] == "fallback_default"

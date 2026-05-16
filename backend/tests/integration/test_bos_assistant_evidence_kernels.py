import json
import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Batch, Tenant, User, UserRoleGrant
from app.models_bos import (
    AssistantConfirmationRequestRecord,
    AssistantRunRecord,
    AssistantToolCallRecord,
    EvidenceItemRecord,
    ExternalReleaseShareRecord,
    ExternalSourceExtractionRecord,
    ExternalSourceRecord,
    ExternalSourceReviewCardRecord,
    FinalActionAuditRecord,
    FinalActionRequestDraftRecord,
    FinalActionReviewPacketSnapshot,
    HumanApprovalRequestRecord,
    ModelRegistryRecord,
    ModelVersionRecord,
    ReleaseDecision,
    ReleasePacketAttachmentRecord,
    ReviewedExternalCandidateRecord,
)
from app.routers.auth import create_access_token, pwd_context
from app.routers import governance as governance_router
from app.schemas.final_actions import FinalActionPreflightInput
from app.services.assistant_service import (
    FORBIDDEN_TOOLS,
    REQUIRES_CONFIRMATION,
    SAFE_TOOLS,
    assistant_tool_registry_contract,
    parse_simulation_lab_intent,
)
from app.services.feature_flags import set_db_override
from app.services.final_action_preflight_service import preflight_final_action_request
from app.services.final_action_request_draft_service import create_non_executing_final_action_request_draft
from app.services.final_action_review_packet_service import persist_review_packet_snapshot

FINAL_ACTION_APPROVER_ROLE_GRANTS = ",".join(
    [
        "final_release_approver",
        "model_governance_approver",
        "external_release_share_approver",
        "external_release_delivery_approver",
    ]
)


async def enable_simulation_lab(db_session: AsyncSession, tenant_id: int) -> None:
    await set_db_override(
        db_session,
        flag_name="bos_simulation_lab",
        tenant_id=tenant_id,
        enabled=True,
    )


def _auth_headers_for(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role, user.tenant_id)}"}


async def count_final_action_audit_records(db_session: AsyncSession, tenant_id: int) -> int:
    count = await db_session.scalar(
        select(func.count())
        .select_from(FinalActionAuditRecord)
        .where(FinalActionAuditRecord.tenant_id == tenant_id)
    )
    return int(count or 0)


async def count_final_action_review_packet_snapshots(db_session: AsyncSession, tenant_id: int) -> int:
    count = await db_session.scalar(
        select(func.count())
        .select_from(FinalActionReviewPacketSnapshot)
        .where(FinalActionReviewPacketSnapshot.tenant_id == tenant_id)
    )
    return int(count or 0)


async def count_final_action_request_drafts(db_session: AsyncSession, tenant_id: int) -> int:
    count = await db_session.scalar(
        select(func.count())
        .select_from(FinalActionRequestDraftRecord)
        .where(FinalActionRequestDraftRecord.tenant_id == tenant_id)
    )
    return int(count or 0)


async def count_external_release_share_records(db_session: AsyncSession, tenant_id: int) -> int:
    count = await db_session.scalar(
        select(func.count())
        .select_from(ExternalReleaseShareRecord)
        .where(ExternalReleaseShareRecord.tenant_id == tenant_id)
    )
    return int(count or 0)


def assert_release_governance_envelope_locked(envelope: dict) -> None:
    assert envelope["gate_state"] == "review_required"
    assert envelope["human_review_required"] is True
    assert envelope["validated_default_write_enabled"] is False
    assert envelope["final_action_execution_enabled"] is False
    assert envelope["runtime_activation_enabled"] is False
    assert envelope["hardware_execution_enabled"] is False
    assert envelope["external_share_status"] == "requires_confirmation"
    assert {
        boundary["action"] for boundary in envelope["action_boundaries"]
    } >= {
        "external_share",
        "final_decision",
        "hardware_run",
        "validated_default_write",
        "runtime_activation",
    }


async def create_user_for_tenant(db_session: AsyncSession, *, tenant_id: int, role: str = "operator") -> User:
    suffix = uuid.uuid4().hex[:8]
    role_slug = role.replace(",", "_").replace(";", "_").replace("|", "_").replace(" ", "_")
    user = User(
        username=f"{role_slug}_{suffix}",
        email=f"{role_slug}_{suffix}@bos.io",
        full_name=f"Test {role.title()}",
        hashed_password=pwd_context.hash("TestUser123!"),
        role=role,
        is_active=True,
        tenant_id=tenant_id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def grant_user_role(
    db_session: AsyncSession,
    *,
    user: User,
    role: str,
    tenant_id: int | None = None,
) -> UserRoleGrant:
    grant = UserRoleGrant(
        tenant_id=tenant_id if tenant_id is not None else user.tenant_id,
        user_id=user.id,
        role=role,
        is_active=True,
        reason="integration-test-grant",
    )
    db_session.add(grant)
    await db_session.commit()
    await db_session.refresh(grant)
    return grant


async def create_tenant_with_user(db_session: AsyncSession, *, role: str = "operator") -> tuple[Tenant, User, dict[str, str]]:
    suffix = uuid.uuid4().hex[:8]
    tenant = Tenant(name=f"Other Tenant {suffix}", slug=f"other-tenant-{suffix}")
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    user = await create_user_for_tenant(db_session, tenant_id=tenant.id, role=role)
    return tenant, user, _auth_headers_for(user)


async def create_simulation_run(
    client: AsyncClient,
    operator_headers: dict[str, str],
) -> tuple[str, str]:
    create_response = await client.post(
        "/api/v1/bos/simulation-lab/scenarios",
        json={
            "species": "BSF",
            "feedstock": "mixed_food_waste",
            "scenario": "moisture_drift",
            "cycles": 6,
            "seed": 17,
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

    runs_response = await client.get(
        f"/api/v1/bos/simulation-lab/scenarios/{simulation_id}/runs",
        headers=operator_headers,
    )
    assert runs_response.status_code == 200
    run_id = runs_response.json()[0]["run_id"]
    return simulation_id, run_id


async def create_release_decision(
    db_session: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    batch_public_id: str,
) -> ReleaseDecision:
    batch = Batch(
        batch_id=batch_public_id,
        species="BSF",
        dm_in=10.0,
        dm_out=7.5,
        user_id=user_id,
        tenant_id=tenant_id,
    )
    db_session.add(batch)
    await db_session.flush()
    release_decision = ReleaseDecision(
        batch_id=batch.id,
        user_id=user_id,
        tenant_id=tenant_id,
        decision="review_required",
        reason_codes=["initial_review"],
        trigger_metrics={"risk": 0.42},
    )
    db_session.add(release_decision)
    await db_session.commit()
    await db_session.refresh(release_decision)
    return release_decision


async def create_model_with_version(
    db_session: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    model_id: str,
    model_version_id: str,
    version_status: str = "ready_for_review",
    model_status: str = "review_required",
) -> tuple[ModelRegistryRecord, ModelVersionRecord]:
    model = ModelRegistryRecord(
        model_id=model_id,
        tenant_id=tenant_id,
        user_id=user_id,
        name=f"Model {model_id}",
        task_type="classification",
        status=model_status,
    )
    version = ModelVersionRecord(
        model_version_id=model_version_id,
        model_id=model_id,
        version="1.0.0",
        metadata_payload={"benchmark_run_id": f"BENCH-{model_version_id}", "governance_status": version_status},
        status=version_status,
    )
    db_session.add_all([model, version])
    await db_session.commit()
    await db_session.refresh(model)
    await db_session.refresh(version)
    return model, version


async def create_reviewed_external_metadata_candidate(
    db_session: AsyncSession,
    *,
    tenant_id: int,
) -> dict[str, str]:
    suffix = uuid.uuid4().hex[:8]
    source_id = f"TEST-P4A-{suffix}"
    card_id = f"CARD-P4A-{suffix}"
    extraction_id = f"EXT-P4A-{suffix}"
    candidate_id = f"REC-P4A-{suffix}"

    source = ExternalSourceRecord(
        source_id=source_id,
        source_name="Phase4A metadata-only guard source",
        source_owner="integration-test",
        source_category="lca",
        license_note="metadata-only manual review guard",
        bos_module="release_center_guard",
        evidence_source_kind="peer_reviewed_literature",
        ingestion_mode="manual_review_first",
        auto_ingestion_note="disabled",
        human_review_note="requires human review before any use",
        next_action="Keep out of release evidence until runtime activation.",
        raw_payload={"guard": "release_center_metadata_only"},
    )
    db_session.add(source)
    await db_session.flush()

    card = ExternalSourceReviewCardRecord(
        tenant_id=tenant_id,
        card_id=card_id,
        shortlist_id=f"SHORT-P4A-{suffix}",
        source_id=source_id,
        doi=f"10.0000/phase4a-{suffix}",
        source_url=f"https://example.test/phase4a/{suffix}",
        title="Phase4A metadata-only reviewed candidate guard",
        review_status="approved_for_candidate_use",
        reviewer="integration-test",
        reviewer_user_id=None,
        reviewed_at=datetime.now(UTC),
        license_status="reviewed_metadata_only",
        evidence_source_kind="peer_reviewed_literature",
        ingestion_mode="manual_review_first",
        human_review_required=True,
        extracted_numeric_values_allowed=False,
        boundary_condition_required=True,
        allowed_use="metadata review packet only",
        blocked_use="no release evidence; no runtime activation; no validated defaults",
        next_action="Manual review remains required before release evidence use.",
        boundary_metadata={"domain": "lca", "metadata_only": True},
        raw_payload={"source_id": source_id, "metadata_only": True},
    )
    db_session.add(card)
    await db_session.flush()

    extraction = ExternalSourceExtractionRecord(
        tenant_id=tenant_id,
        extraction_id=extraction_id,
        review_card_id=card.id,
        card_id=card_id,
        source_id=source_id,
        extraction_status="staged_metadata_only",
        extracted_metadata={"title": card.title},
        extracted_numeric_values={},
        numeric_values_included=False,
        boundary_metadata={"domain": "lca", "metadata_only": True},
        human_review_required=True,
    )
    db_session.add(extraction)
    await db_session.flush()

    candidate = ReviewedExternalCandidateRecord(
        tenant_id=tenant_id,
        candidate_id=candidate_id,
        candidate_type="lca_reviewed_metadata_candidate",
        candidate_key=f"phase4a-lca-{suffix}",
        review_card_id=card.id,
        extraction_id=extraction.id,
        card_id=card_id,
        source_id=source_id,
        source_kind="peer_reviewed_literature",
        source_ref=source_id,
        license_status="reviewed_metadata_only",
        license_note="metadata-only manual review guard",
        ingestion_mode="manual_review_first",
        review_status="approved_for_candidate_use",
        reviewer="integration-test",
        reviewed_at=datetime.now(UTC),
        boundary_condition="metadata-only Phase4A domain source",
        allowed_use="reviewed metadata knowledge base only",
        blocked_use="no release evidence; no runtime activation; no validated defaults",
        candidate_payload={
            "source_id": source_id,
            "card_id": card_id,
            "extraction_id": extraction_id,
            "numeric_values_included": False,
            "runtime_activated": False,
            "validated_default_write_enabled": False,
        },
        human_review_required=True,
        promotion_enabled=False,
        runtime_activated=False,
        validated_default_write_enabled=False,
        activation_relation_id=None,
        audit_payload={"manual_review_first": True, "metadata_only": True},
    )
    db_session.add(candidate)
    await db_session.commit()

    return {
        "source_id": source_id,
        "card_id": card_id,
        "extraction_id": extraction_id,
        "candidate_id": candidate_id,
    }


def test_assistant_intent_parser_defaults_and_compare_trigger():
    intent = parse_simulation_lab_intent("please run moisture drift and compare policies")

    assert intent["scenario"] == "moisture_drift"
    assert intent["cycles"] == 8
    assert intent["seed"] == 17
    assert intent["policy"] == "rule_based"
    assert intent["compare_policies"] is True
    assert intent["reference_id"] is None


def test_assistant_tool_policy_never_auto_executes_forbidden_or_confirmation_tools():
    assert FORBIDDEN_TOOLS.isdisjoint(SAFE_TOOLS)
    assert REQUIRES_CONFIRMATION.isdisjoint(SAFE_TOOLS)
    assert {"hardware_execution", "production_batch_mutation", "release_decision_auto_pass"}.issubset(FORBIDDEN_TOOLS)
    assert "release.attach_simulation_appendix" in SAFE_TOOLS
    assert {"compliance.evaluate", "lca.compare", "tea.estimate"}.issubset(SAFE_TOOLS)

    registry = assistant_tool_registry_contract()
    tool_names = {item["name"] for item in registry["tools"]}
    tools_by_name = {item["name"]: item for item in registry["tools"]}
    assert registry["version"] == "assistant-tool-registry-v1"
    assert {
        "simulation_lab.import_reference",
        "simulation_lab.create_run_compare",
        "release.attach_appendix",
        "benchmark.run_suite",
        "model.request_review",
        "model.complete_review",
        "release.request_human_approval",
        "external.share_release_packet",
        "compliance.evaluate",
        "lca.compare",
        "tea.estimate",
    }.issubset(tool_names)
    assert "external.share_release_packet" in REQUIRES_CONFIRMATION
    assert tools_by_name["external.share_release_packet"]["policy"] == "requires_confirmation"
    assert tools_by_name["compliance.evaluate"]["status"] == "available"
    assert tools_by_name["lca.compare"]["status"] == "available"
    assert tools_by_name["tea.estimate"]["status"] == "available"
    assert "release.auto_approve" in registry["confirmation_policy"]["forbidden"]


def test_final_action_audit_record_schema_is_available_without_mutation_routes():
    table = FinalActionAuditRecord.__table__
    assert table.name == "final_action_audit_records"
    assert {
        "final_action_id",
        "tenant_id",
        "action_type",
        "target_type",
        "target_id",
        "requested_by_user_id",
        "reviewed_by_user_id",
        "role_snapshot",
        "source_review_packet_id",
        "source_evidence_pack_ids",
        "precondition_snapshot",
        "before_state",
        "after_state",
        "decision",
        "reason",
        "idempotency_key",
        "status",
        "effect_summary",
        "created_at",
        "resolved_at",
    }.issubset(table.c.keys())
    assert any(
        constraint.name == "uq_final_action_audit_tenant_action_idempotency"
        and {column.name for column in constraint.columns} == {"tenant_id", "action_type", "idempotency_key"}
        for constraint in table.constraints
    )


def test_final_action_review_packet_snapshot_schema_is_available_without_mutation_routes():
    table = FinalActionReviewPacketSnapshot.__table__
    assert table.name == "final_action_review_packet_snapshots"
    assert {
        "source_review_packet_id",
        "tenant_id",
        "packet_type",
        "packet_hash",
        "packet_payload",
        "evidence_pack_ids",
        "generated_by_user_id",
        "created_at",
    }.issubset(table.c.keys())
    assert any(
        constraint.name == "uq_final_action_review_packets_tenant_hash"
        and {column.name for column in constraint.columns} == {"tenant_id", "packet_hash"}
        for constraint in table.constraints
    )


def test_final_action_request_draft_schema_is_available_without_mutation_routes():
    table = FinalActionRequestDraftRecord.__table__
    assert table.name == "final_action_request_drafts"
    assert {
        "final_action_request_id",
        "tenant_id",
        "action_type",
        "target_type",
        "target_id",
        "requested_by_user_id",
        "source_review_packet_id",
        "source_evidence_pack_ids",
        "request_payload",
        "preflight_snapshot",
        "role_snapshot",
        "idempotency_key",
        "status",
        "created_at",
        "updated_at",
    }.issubset(table.c.keys())
    assert any(
        constraint.name == "uq_final_action_request_drafts_tenant_action_idempotency"
        and {column.name for column in constraint.columns} == {"tenant_id", "action_type", "idempotency_key"}
        for constraint in table.constraints
    )


def test_user_role_grant_schema_is_tenant_scoped_and_compatible_with_legacy_user_role():
    table = UserRoleGrant.__table__
    assert table.name == "user_role_grants"
    assert {
        "id",
        "tenant_id",
        "user_id",
        "role",
        "granted_by_user_id",
        "reason",
        "is_active",
        "created_at",
        "updated_at",
    }.issubset(table.c.keys())
    assert any(
        constraint.name == "uq_user_role_grants_tenant_user_role"
        and {column.name for column in constraint.columns} == {"tenant_id", "user_id", "role"}
        for constraint in table.constraints
    )
    assert User.__table__.c.role is not None


@pytest.mark.asyncio
async def test_final_action_preflight_blocks_missing_source_packet_without_writes(
    db_session: AsyncSession,
    test_tenant,
    operator_user,
):
    result = await preflight_final_action_request(
        db_session,
        tenant_id=test_tenant.id,
        request=FinalActionPreflightInput(
            action_type="final_release_approval",
            target_type="release_decision",
            target_id="RD-MISSING-SOURCE",
            source_review_packet_id="FARP-MISSING",
            idempotency_key="idem-missing-source",
            requested_by_user_id=operator_user.id,
        ),
    )

    assert result.schema_version == "final_action_preflight_v1"
    assert result.review_only is True
    assert result.eligible is False
    assert result.executable is False
    assert result.source_review_packet_found is False
    assert result.evidence_pack_ids == []
    assert result.required_roles == ["final_release_approver"]
    assert "source_review_packet_not_found" in result.blockers
    assert "final_action_workflow_unavailable" in result.blockers
    assert "final_release_approval_route_not_executable" in result.blockers
    assert result.would_create_request_draft is False
    assert result.would_write_audit_record is False
    assert result.side_effects_if_executed.release_decision == "not_executed"
    assert result.side_effects_if_executed.model_activation is False
    assert result.side_effects_if_executed.external_share is False
    assert result.side_effects_if_executed.hardware_execution is False
    assert "preflight_only_no_mutation" in result.guardrails
    assert "no_hardware_execution" in result.guardrails
    assert await count_final_action_audit_records(db_session, test_tenant.id) == 0
    assert await count_final_action_request_drafts(db_session, test_tenant.id) == 0


@pytest.mark.asyncio
async def test_final_action_preflight_finds_source_packet_but_stays_non_executable(
    db_session: AsyncSession,
    test_tenant,
    operator_user,
):
    packet = await persist_review_packet_snapshot(
        db_session,
        tenant_id=test_tenant.id,
        generated_by_user_id=operator_user.id,
        packet={
            "packet_type": "assistant_review_workbench_audit_packet",
            "evidence_pack_ids": ["EVP-PREFLIGHT-001"],
            "final_actions": {
                "release_approval": "not_executed",
                "model_activation": "not_executed",
                "external_share": "not_executed",
            },
        },
    )

    result = await preflight_final_action_request(
        db_session,
        tenant_id=test_tenant.id,
        request=FinalActionPreflightInput(
            action_type="model_activation",
            target_type="model_version",
            target_id="MV-PREFLIGHT-001",
            source_review_packet_id=packet.source_review_packet_id,
            idempotency_key="idem-known-source",
            requested_by_user_id=operator_user.id,
        ),
    )

    assert result.eligible is False
    assert result.executable is False
    assert result.source_review_packet_found is True
    assert result.source_review_packet_id == packet.source_review_packet_id
    assert result.evidence_pack_ids == ["EVP-PREFLIGHT-001"]
    assert result.required_roles == ["model_governance_approver"]
    assert "source_review_packet_not_found" not in result.blockers
    assert "final_action_workflow_unavailable" in result.blockers
    assert "model_activation_route_not_executable" in result.blockers
    assert "final_action_request_draft_writer_not_enabled" in result.blockers
    assert "final_action_audit_writer_not_enabled" in result.blockers
    assert result.would_create_request_draft is False
    assert result.would_write_audit_record is False
    assert result.side_effects_if_executed.model_activation is False
    assert "no_model_activation" in result.guardrails
    assert await count_final_action_audit_records(db_session, test_tenant.id) == 0
    assert await count_final_action_request_drafts(db_session, test_tenant.id) == 0


@pytest.mark.asyncio
async def test_non_executing_final_action_request_draft_writer_creates_blocked_draft_only(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
    operator_user,
):
    release_decision = await create_release_decision(
        db_session,
        tenant_id=test_tenant.id,
        user_id=operator_user.id,
        batch_public_id="BATCH-P3-9-DRAFT-001",
    )
    packet = await persist_review_packet_snapshot(
        db_session,
        tenant_id=test_tenant.id,
        generated_by_user_id=operator_user.id,
        packet={
            "packet_type": "assistant_review_workbench_audit_packet",
            "evidence_pack_ids": ["EVP-DRAFT-001", "EVP-DRAFT-002"],
            "final_actions": {
                "release_approval": "not_executed",
                "model_activation": "not_executed",
                "external_share": "not_executed",
            },
        },
    )
    request = FinalActionPreflightInput(
        action_type="final_release_approval",
        target_type="release_decision",
        target_id=str(release_decision.id),
        source_review_packet_id=packet.source_review_packet_id,
        idempotency_key="idem-draft-writer-known-source",
        requested_by_user_id=operator_user.id,
    )

    assert await count_final_action_request_drafts(db_session, test_tenant.id) == 0
    assert await count_final_action_audit_records(db_session, test_tenant.id) == 0

    draft = await create_non_executing_final_action_request_draft(
        db_session,
        tenant_id=test_tenant.id,
        request=request,
    )

    assert draft.final_action_request_id.startswith("FARD-")
    assert draft.status == "draft_blocked"
    assert draft.action_type == "final_release_approval"
    assert draft.target_type == "release_decision"
    assert draft.target_id == str(release_decision.id)
    assert draft.source_review_packet_id == packet.source_review_packet_id
    assert draft.source_evidence_pack_ids == ["EVP-DRAFT-001", "EVP-DRAFT-002"]
    assert draft.request_payload["execution"] == "not_executed"
    assert draft.request_payload["review_only"] is True
    assert draft.preflight_snapshot["eligible"] is False
    assert draft.preflight_snapshot["executable"] is False
    assert draft.preflight_snapshot["would_create_request_draft"] is False
    assert draft.preflight_snapshot["would_write_audit_record"] is False
    assert draft.preflight_snapshot["side_effects_if_executed"] == {
        "release_decision": "not_executed",
        "model_activation": False,
        "external_share": False,
        "hardware_execution": False,
    }
    assert draft.role_snapshot["requested_by_user_id"] == operator_user.id
    assert draft.role_snapshot["requested_by_user_role"] == "operator"
    assert draft.role_snapshot["required_final_action_roles"] == ["final_release_approver"]
    assert draft.role_snapshot["final_action_role_authority_implemented"] is True
    assert await count_final_action_request_drafts(db_session, test_tenant.id) == 1
    assert await count_final_action_audit_records(db_session, test_tenant.id) == 0

    await db_session.refresh(release_decision)
    assert release_decision.decision == "review_required"

    repeated = await create_non_executing_final_action_request_draft(
        db_session,
        tenant_id=test_tenant.id,
        request=request,
    )
    assert repeated.final_action_request_id == draft.final_action_request_id
    assert await count_final_action_request_drafts(db_session, test_tenant.id) == 1

    draft_list_response = await client.get("/api/v1/final-actions/request-drafts", headers=operator_headers)
    assert draft_list_response.status_code == 200
    draft_list = draft_list_response.json()
    assert draft_list["count"] == 1
    assert draft_list["drafts"][0]["final_action_request_id"] == draft.final_action_request_id
    assert draft_list["drafts"][0]["status"] == "draft_blocked"
    assert "final_action_drafts_created_only_by_internal_service" in draft_list["guardrails"]

    with pytest.raises(ValueError, match="final_action_request_draft_idempotency_conflict"):
        await create_non_executing_final_action_request_draft(
            db_session,
            tenant_id=test_tenant.id,
            request=FinalActionPreflightInput(
                action_type="final_release_approval",
                target_type="release_decision",
                target_id="DIFFERENT-TARGET",
                source_review_packet_id=packet.source_review_packet_id,
                idempotency_key="idem-draft-writer-known-source",
                requested_by_user_id=operator_user.id,
            ),
        )
    assert await count_final_action_request_drafts(db_session, test_tenant.id) == 1
    assert await count_final_action_audit_records(db_session, test_tenant.id) == 0


@pytest.mark.asyncio
async def test_final_action_request_draft_post_route_creates_blocked_draft_without_execution(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
    operator_user,
):
    release_decision = await create_release_decision(
        db_session,
        tenant_id=test_tenant.id,
        user_id=operator_user.id,
        batch_public_id="BATCH-P3-10-ROUTE-001",
    )
    packet = await persist_review_packet_snapshot(
        db_session,
        tenant_id=test_tenant.id,
        generated_by_user_id=operator_user.id,
        packet={
            "packet_type": "assistant_review_workbench_audit_packet",
            "evidence_pack_ids": ["EVP-DRAFT-ROUTE-001"],
            "final_actions": {
                "release_approval": "not_executed",
                "model_activation": "not_executed",
                "external_share": "not_executed",
            },
        },
    )

    response = await client.post(
        "/api/v1/final-actions/request-drafts",
        json={
            "action_type": "final_release_approval",
            "target_type": "release_decision",
            "target_id": str(release_decision.id),
            "source_review_packet_id": packet.source_review_packet_id,
            "idempotency_key": "idem-public-draft-route",
            "requested_by_user_id": 999999,
        },
        headers=operator_headers,
    )

    assert response.status_code == 201
    draft = response.json()
    assert draft["final_action_request_id"].startswith("FARD-")
    assert draft["status"] == "draft_blocked"
    assert draft["requested_by_user_id"] == operator_user.id
    assert draft["request_payload"]["requested_by_user_id"] == operator_user.id
    assert draft["request_payload"]["execution"] == "not_executed"
    assert draft["preflight_snapshot"]["eligible"] is False
    assert draft["preflight_snapshot"]["executable"] is False
    assert draft["preflight_snapshot"]["would_write_audit_record"] is False
    assert draft["source_evidence_pack_ids"] == ["EVP-DRAFT-ROUTE-001"]

    repeated_response = await client.post(
        "/api/v1/final-actions/request-drafts",
        json={
            "action_type": "final_release_approval",
            "target_type": "release_decision",
            "target_id": str(release_decision.id),
            "source_review_packet_id": packet.source_review_packet_id,
            "idempotency_key": "idem-public-draft-route",
        },
        headers=operator_headers,
    )
    assert repeated_response.status_code == 201
    assert repeated_response.json()["final_action_request_id"] == draft["final_action_request_id"]

    resolve_response = await client.post(
        f"/api/v1/final-actions/request-drafts/{draft['final_action_request_id']}/resolve",
        json={"approved": True, "reason": "reviewed request draft only"},
        headers=operator_headers,
    )
    assert resolve_response.status_code == 200
    resolved_draft = resolve_response.json()
    assert resolved_draft["status"] == "review_approved_no_execution"
    assert resolved_draft["request_payload"]["execution"] == "not_executed"
    assert resolved_draft["request_payload"]["review_resolution"] == {
        "approved": True,
        "reason": "reviewed request draft only",
        "reviewed_by_user_id": operator_user.id,
        "scope": "request_draft_review_only",
        "side_effects": {
            "release_decision": "unchanged",
            "model_activation": False,
            "external_share": False,
            "hardware_execution": False,
            "final_action_audit_record": False,
        },
    }

    readiness_response = await client.get(
        f"/api/v1/final-actions/request-drafts/{draft['final_action_request_id']}/execution-readiness",
        headers=operator_headers,
    )
    assert readiness_response.status_code == 200
    execution_readiness = readiness_response.json()
    assert execution_readiness["schema_version"] == "final_action_execution_readiness_v1"
    assert execution_readiness["review_only"] is True
    assert execution_readiness["draft_status"] == "review_approved_no_execution"
    assert execution_readiness["target_found"] is True
    assert execution_readiness["target_state"]["decision"] == "review_required"
    assert execution_readiness["source_review_packet_found"] is True
    assert execution_readiness["source_evidence_pack_ids"] == ["EVP-DRAFT-ROUTE-001"]
    assert execution_readiness["ready_for_audited_execution"] is True
    assert execution_readiness["executable_now"] is True
    assert execution_readiness["would_write_audit_record_now"] is True
    assert execution_readiness["side_effects_if_executed"] == {
        "release_decision": "changed",
        "model_activation": False,
        "external_share": False,
        "hardware_execution": False,
    }
    assert execution_readiness["blockers"] == []
    assert "execution_readiness_only" in execution_readiness["guardrails"]

    reject_again_response = await client.post(
        f"/api/v1/final-actions/request-drafts/{draft['final_action_request_id']}/resolve",
        json={"approved": False, "reason": "changed review disposition only"},
        headers=operator_headers,
    )
    assert reject_again_response.status_code == 200
    assert reject_again_response.json()["status"] == "review_rejected_no_execution"

    rejected_readiness_response = await client.get(
        f"/api/v1/final-actions/request-drafts/{draft['final_action_request_id']}/execution-readiness",
        headers=operator_headers,
    )
    assert rejected_readiness_response.status_code == 200
    rejected_readiness = rejected_readiness_response.json()
    assert rejected_readiness["ready_for_audited_execution"] is False
    assert rejected_readiness["executable_now"] is False
    assert "draft_not_review_approved_no_execution:review_rejected_no_execution" in rejected_readiness["blockers"]

    missing_resolve_response = await client.post(
        "/api/v1/final-actions/request-drafts/FARD-NOT-CREATED/resolve",
        json={"approved": True, "reason": "missing draft"},
        headers=operator_headers,
    )
    assert missing_resolve_response.status_code == 404
    assert missing_resolve_response.json()["detail"] == "final_action_request_draft_not_found"

    missing_readiness_response = await client.get(
        "/api/v1/final-actions/request-drafts/FARD-NOT-CREATED/execution-readiness",
        headers=operator_headers,
    )
    assert missing_readiness_response.status_code == 404

    conflict_response = await client.post(
        "/api/v1/final-actions/request-drafts",
        json={
            "action_type": "final_release_approval",
            "target_type": "release_decision",
            "target_id": "DIFFERENT-RELEASE-DECISION",
            "source_review_packet_id": packet.source_review_packet_id,
            "idempotency_key": "idem-public-draft-route",
        },
        headers=operator_headers,
    )
    assert conflict_response.status_code == 409
    assert conflict_response.json()["detail"] == "final_action_request_draft_idempotency_conflict"

    missing_packet_response = await client.post(
        "/api/v1/final-actions/request-drafts",
        json={
            "action_type": "final_release_approval",
            "target_type": "release_decision",
            "target_id": str(release_decision.id),
            "source_review_packet_id": "FARP-NOT-FOUND-FOR-POST",
            "idempotency_key": "idem-public-missing-source",
        },
        headers=operator_headers,
    )
    assert missing_packet_response.status_code == 404
    assert missing_packet_response.json()["detail"] == "source_review_packet_not_found"

    await db_session.refresh(release_decision)
    assert release_decision.decision == "review_required"
    assert await count_final_action_request_drafts(db_session, test_tenant.id) == 1
    assert await count_final_action_audit_records(db_session, test_tenant.id) == 0


@pytest.mark.asyncio
async def test_final_release_approval_executes_only_through_audited_final_action_workflow(
    client: AsyncClient,
    operator_headers,
    admin_headers,
    db_session: AsyncSession,
    test_tenant,
    operator_user,
):
    final_action_approver = await create_user_for_tenant(
        db_session,
        tenant_id=test_tenant.id,
        role=FINAL_ACTION_APPROVER_ROLE_GRANTS,
    )
    final_action_approver_headers = _auth_headers_for(final_action_approver)
    release_decision = await create_release_decision(
        db_session,
        tenant_id=test_tenant.id,
        user_id=operator_user.id,
        batch_public_id="BATCH-P3-13-RELEASE-001",
    )
    packet = await persist_review_packet_snapshot(
        db_session,
        tenant_id=test_tenant.id,
        generated_by_user_id=operator_user.id,
        packet={
            "packet_type": "assistant_review_workbench_audit_packet",
            "evidence_pack_ids": ["EVP-FINAL-RELEASE-001"],
            "final_actions": {
                "release_approval": "not_executed",
                "model_activation": "not_executed",
                "external_share": "not_executed",
            },
        },
    )
    draft_response = await client.post(
        "/api/v1/final-actions/request-drafts",
        json={
            "action_type": "final_release_approval",
            "target_type": "release_decision",
            "target_id": str(release_decision.id),
            "source_review_packet_id": packet.source_review_packet_id,
            "idempotency_key": "idem-final-release-draft",
        },
        headers=operator_headers,
    )
    assert draft_response.status_code == 201
    draft_id = draft_response.json()["final_action_request_id"]

    unapproved_execute_response = await client.post(
        "/api/v1/final-actions/release-approvals",
        json={
            "final_action_request_id": draft_id,
            "expected_current_decision": "review_required",
            "operator_attestation": "I reviewed the immutable source packet and approve release.",
            "idempotency_key": "idem-final-release-execution",
        },
        headers=final_action_approver_headers,
    )
    assert unapproved_execute_response.status_code == 409
    assert unapproved_execute_response.json()["detail"] == "final_action_request_draft_not_approved_for_execution"
    assert await count_final_action_audit_records(db_session, test_tenant.id) == 0

    resolve_response = await client.post(
        f"/api/v1/final-actions/request-drafts/{draft_id}/resolve",
        json={"approved": True, "reason": "approved for audited release workflow"},
        headers=operator_headers,
    )
    assert resolve_response.status_code == 200

    operator_execute_response = await client.post(
        "/api/v1/final-actions/release-approvals",
        json={
            "final_action_request_id": draft_id,
            "expected_current_decision": "review_required",
            "operator_attestation": "Operator cannot execute final release approval.",
            "idempotency_key": "idem-final-release-operator-denied",
        },
        headers=operator_headers,
    )
    assert operator_execute_response.status_code == 403
    assert await count_final_action_audit_records(db_session, test_tenant.id) == 0

    admin_execute_response = await client.post(
        "/api/v1/final-actions/release-approvals",
        json={
            "final_action_request_id": draft_id,
            "expected_current_decision": "review_required",
            "operator_attestation": "Administrator without final release approver role cannot execute.",
            "idempotency_key": "idem-final-release-admin-denied",
        },
        headers=admin_headers,
    )
    assert admin_execute_response.status_code == 403
    assert await count_final_action_audit_records(db_session, test_tenant.id) == 0

    execute_response = await client.post(
        "/api/v1/final-actions/release-approvals",
        json={
            "final_action_request_id": draft_id,
            "expected_current_decision": "review_required",
            "operator_attestation": "I reviewed the immutable source packet and approve release.",
            "idempotency_key": "idem-final-release-execution",
        },
        headers=final_action_approver_headers,
    )
    assert execute_response.status_code == 201
    audit_record = execute_response.json()
    assert audit_record["final_action_id"].startswith("FA-")
    assert audit_record["action_type"] == "final_release_approval"
    assert audit_record["target_id"] == str(release_decision.id)
    assert audit_record["source_review_packet_id"] == packet.source_review_packet_id
    assert audit_record["source_evidence_pack_ids"] == ["EVP-FINAL-RELEASE-001"]
    assert audit_record["precondition_snapshot"]["final_action_request_id"] == draft_id
    assert audit_record["before_state"]["decision"] == "review_required"
    assert audit_record["after_state"]["decision"] == "approved"
    assert audit_record["decision"] == "approved"
    assert audit_record["status"] == "executed"
    assert audit_record["role_snapshot"]["required_role"] == "final_release_approver"
    assert "final_release_approver" in audit_record["role_snapshot"]["reviewed_by_user_roles"]
    assert audit_record["role_snapshot"]["admin_override"] is False
    assert audit_record["effect_summary"] == {
        "release_decision": "changed",
        "model_activation": False,
        "external_share": False,
        "hardware_execution": False,
    }

    await db_session.refresh(release_decision)
    assert release_decision.decision == "approved"
    assert "final_action_release_approved" in release_decision.reason_codes
    assert release_decision.trigger_metrics["final_action_id"] == audit_record["final_action_id"]
    assert release_decision.trigger_metrics["final_action_request_id"] == draft_id
    assert await count_final_action_audit_records(db_session, test_tenant.id) == 1

    repeat_response = await client.post(
        "/api/v1/final-actions/release-approvals",
        json={
            "final_action_request_id": draft_id,
            "expected_current_decision": "review_required",
            "operator_attestation": "Idempotent repeat returns existing audit record.",
            "idempotency_key": "idem-final-release-execution",
        },
        headers=final_action_approver_headers,
    )
    assert repeat_response.status_code == 201
    assert repeat_response.json()["final_action_id"] == audit_record["final_action_id"]
    assert await count_final_action_audit_records(db_session, test_tenant.id) == 1

    second_execute_response = await client.post(
        "/api/v1/final-actions/release-approvals",
        json={
            "final_action_request_id": draft_id,
            "expected_current_decision": "review_required",
            "operator_attestation": "Cannot approve after state has moved.",
            "idempotency_key": "idem-final-release-second-execution",
        },
        headers=final_action_approver_headers,
    )
    assert second_execute_response.status_code == 409
    assert second_execute_response.json()["detail"] == "release_decision_state_mismatch:approved"

    audit_records_response = await client.get("/api/v1/final-actions/audit-records", headers=operator_headers)
    assert audit_records_response.status_code == 200
    audit_records = audit_records_response.json()
    assert audit_records["count"] == 1
    assert audit_records["records"][0]["final_action_id"] == audit_record["final_action_id"]
    assert "audit_records_may_include_executed_final_actions" in audit_records["guardrails"]
    assert "no_model_activation" in audit_records["guardrails"]
    assert "no_external_share_record" in audit_records["guardrails"]
    assert "no_hardware_execution" in audit_records["guardrails"]


@pytest.mark.asyncio
async def test_db_backed_final_action_role_grant_executes_and_remains_tenant_scoped(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
    operator_user,
):
    final_action_approver = await create_user_for_tenant(
        db_session,
        tenant_id=test_tenant.id,
        role="viewer",
    )
    await grant_user_role(
        db_session,
        user=final_action_approver,
        role="final_release_approver",
    )
    final_action_approver_headers = _auth_headers_for(final_action_approver)
    release_decision = await create_release_decision(
        db_session,
        tenant_id=test_tenant.id,
        user_id=operator_user.id,
        batch_public_id="BATCH-DB-RBAC-RELEASE-001",
    )
    packet = await persist_review_packet_snapshot(
        db_session,
        tenant_id=test_tenant.id,
        generated_by_user_id=operator_user.id,
        packet={
            "packet_type": "assistant_review_workbench_audit_packet",
            "evidence_pack_ids": ["EVP-DB-RBAC-RELEASE-001"],
            "final_actions": {
                "release_approval": "not_executed",
                "model_activation": "not_executed",
                "external_share": "not_executed",
            },
        },
    )
    draft_response = await client.post(
        "/api/v1/final-actions/request-drafts",
        json={
            "action_type": "final_release_approval",
            "target_type": "release_decision",
            "target_id": str(release_decision.id),
            "source_review_packet_id": packet.source_review_packet_id,
            "idempotency_key": "idem-db-rbac-final-release-draft",
        },
        headers=operator_headers,
    )
    assert draft_response.status_code == 201
    draft_id = draft_response.json()["final_action_request_id"]
    resolve_response = await client.post(
        f"/api/v1/final-actions/request-drafts/{draft_id}/resolve",
        json={"approved": True, "reason": "approved for db-backed role grant execution"},
        headers=operator_headers,
    )
    assert resolve_response.status_code == 200

    other_tenant, _, _ = await create_tenant_with_user(db_session)
    cross_tenant_grant_user = await create_user_for_tenant(
        db_session,
        tenant_id=test_tenant.id,
        role="viewer",
    )
    await grant_user_role(
        db_session,
        user=cross_tenant_grant_user,
        role="final_release_approver",
        tenant_id=other_tenant.id,
    )
    cross_tenant_response = await client.post(
        "/api/v1/final-actions/release-approvals",
        json={
            "final_action_request_id": draft_id,
            "expected_current_decision": "review_required",
            "operator_attestation": "Cross-tenant role grant must not authorize this user.",
            "idempotency_key": "idem-db-rbac-cross-tenant-denied",
        },
        headers=_auth_headers_for(cross_tenant_grant_user),
    )
    assert cross_tenant_response.status_code == 403
    assert await count_final_action_audit_records(db_session, test_tenant.id) == 0

    execute_response = await client.post(
        "/api/v1/final-actions/release-approvals",
        json={
            "final_action_request_id": draft_id,
            "expected_current_decision": "review_required",
            "operator_attestation": "I approve with a DB-backed final_release_approver grant.",
            "idempotency_key": "idem-db-rbac-final-release-execution",
        },
        headers=final_action_approver_headers,
    )
    assert execute_response.status_code == 201
    audit_record = execute_response.json()
    assert audit_record["action_type"] == "final_release_approval"
    assert audit_record["after_state"]["decision"] == "approved"
    assert audit_record["role_snapshot"]["reviewed_by_user_role"] == "viewer"
    assert audit_record["role_snapshot"]["required_role"] == "final_release_approver"
    assert "final_release_approver" in audit_record["role_snapshot"]["reviewed_by_user_roles"]
    assert audit_record["role_snapshot"]["admin_override"] is False
    assert await count_final_action_audit_records(db_session, test_tenant.id) == 1


@pytest.mark.asyncio
async def test_final_model_activation_executes_only_through_audited_final_action_workflow(
    client: AsyncClient,
    operator_headers,
    admin_headers,
    db_session: AsyncSession,
    test_tenant,
    operator_user,
):
    final_action_approver = await create_user_for_tenant(
        db_session,
        tenant_id=test_tenant.id,
        role=FINAL_ACTION_APPROVER_ROLE_GRANTS,
    )
    final_action_approver_headers = _auth_headers_for(final_action_approver)
    model, version = await create_model_with_version(
        db_session,
        tenant_id=test_tenant.id,
        user_id=operator_user.id,
        model_id="MOD-P3-14-ACTIVATE",
        model_version_id="MVN-P3-14-ACTIVATE",
    )
    _, previous_active = await create_model_with_version(
        db_session,
        tenant_id=test_tenant.id,
        user_id=operator_user.id,
        model_id="MOD-P3-14-PREVIOUS",
        model_version_id="MVN-P3-14-OTHER-ACTIVE",
        version_status="active",
        model_status="active",
    )
    previous_active.model_id = model.model_id
    await db_session.commit()
    packet = await persist_review_packet_snapshot(
        db_session,
        tenant_id=test_tenant.id,
        generated_by_user_id=operator_user.id,
        packet={
            "packet_type": "assistant_review_workbench_audit_packet",
            "evidence_pack_ids": ["EVP-FINAL-MODEL-001"],
            "final_actions": {
                "release_approval": "not_executed",
                "model_activation": "not_executed",
                "external_share": "not_executed",
            },
        },
    )
    draft_response = await client.post(
        "/api/v1/final-actions/request-drafts",
        json={
            "action_type": "model_activation",
            "target_type": "model_version",
            "target_id": version.model_version_id,
            "source_review_packet_id": packet.source_review_packet_id,
            "idempotency_key": "idem-final-model-draft",
        },
        headers=operator_headers,
    )
    assert draft_response.status_code == 201
    draft_id = draft_response.json()["final_action_request_id"]

    resolve_response = await client.post(
        f"/api/v1/final-actions/request-drafts/{draft_id}/resolve",
        json={"approved": True, "reason": "approved for audited model activation"},
        headers=operator_headers,
    )
    assert resolve_response.status_code == 200

    readiness_response = await client.get(
        f"/api/v1/final-actions/request-drafts/{draft_id}/execution-readiness",
        headers=operator_headers,
    )
    assert readiness_response.status_code == 200
    readiness = readiness_response.json()
    assert readiness["ready_for_audited_execution"] is True
    assert readiness["executable_now"] is True
    assert readiness["would_write_audit_record_now"] is True
    assert readiness["side_effects_if_executed"]["model_activation"] is True

    operator_execute_response = await client.post(
        "/api/v1/final-actions/model-activations",
        json={
            "final_action_request_id": draft_id,
            "expected_current_version_status": "ready_for_review",
            "operator_attestation": "Operator cannot activate model.",
            "idempotency_key": "idem-final-model-operator-denied",
        },
        headers=operator_headers,
    )
    assert operator_execute_response.status_code == 403
    assert await count_final_action_audit_records(db_session, test_tenant.id) == 0

    admin_execute_response = await client.post(
        "/api/v1/final-actions/model-activations",
        json={
            "final_action_request_id": draft_id,
            "expected_current_version_status": "ready_for_review",
            "operator_attestation": "Administrator without model governance role cannot activate model.",
            "idempotency_key": "idem-final-model-admin-denied",
        },
        headers=admin_headers,
    )
    assert admin_execute_response.status_code == 403
    assert await count_final_action_audit_records(db_session, test_tenant.id) == 0

    execute_response = await client.post(
        "/api/v1/final-actions/model-activations",
        json={
            "final_action_request_id": draft_id,
            "expected_current_version_status": "ready_for_review",
            "operator_attestation": "I reviewed the benchmark evidence and activate this model version.",
            "idempotency_key": "idem-final-model-execution",
        },
        headers=final_action_approver_headers,
    )
    assert execute_response.status_code == 201
    audit_record = execute_response.json()
    assert audit_record["action_type"] == "model_activation"
    assert audit_record["target_id"] == version.model_version_id
    assert audit_record["source_evidence_pack_ids"] == ["EVP-FINAL-MODEL-001"]
    assert audit_record["before_state"]["version_status"] == "ready_for_review"
    assert audit_record["after_state"]["version_status"] == "active"
    assert previous_active.model_version_id in audit_record["before_state"]["previous_active_version_ids"]
    assert audit_record["role_snapshot"]["required_role"] == "model_governance_approver"
    assert "model_governance_approver" in audit_record["role_snapshot"]["reviewed_by_user_roles"]
    assert audit_record["role_snapshot"]["admin_override"] is False
    assert audit_record["effect_summary"] == {
        "release_decision": "unchanged",
        "model_activation": True,
        "external_share": False,
        "hardware_execution": False,
    }

    await db_session.refresh(model)
    await db_session.refresh(version)
    await db_session.refresh(previous_active)
    assert model.status == "active"
    assert version.status == "active"
    assert version.metadata_payload["activated_by_final_action_id"] == audit_record["final_action_id"]
    assert previous_active.status == "superseded"
    assert previous_active.metadata_payload["superseded_by_model_version_id"] == version.model_version_id

    repeat_response = await client.post(
        "/api/v1/final-actions/model-activations",
        json={
            "final_action_request_id": draft_id,
            "expected_current_version_status": "ready_for_review",
            "operator_attestation": "Idempotent repeat returns existing audit record.",
            "idempotency_key": "idem-final-model-execution",
        },
        headers=final_action_approver_headers,
    )
    assert repeat_response.status_code == 201
    assert repeat_response.json()["final_action_id"] == audit_record["final_action_id"]
    assert await count_final_action_audit_records(db_session, test_tenant.id) == 1

    second_execute_response = await client.post(
        "/api/v1/final-actions/model-activations",
        json={
            "final_action_request_id": draft_id,
            "expected_current_version_status": "ready_for_review",
            "operator_attestation": "Cannot activate after state has moved.",
            "idempotency_key": "idem-final-model-second-execution",
        },
        headers=final_action_approver_headers,
    )
    assert second_execute_response.status_code == 409
    assert second_execute_response.json()["detail"] == "model_version_state_mismatch:active"


@pytest.mark.asyncio
async def test_final_external_release_share_creates_internal_share_record_without_sending(
    client: AsyncClient,
    operator_headers,
    admin_headers,
    db_session: AsyncSession,
    test_tenant,
    operator_user,
    monkeypatch,
):
    final_action_approver = await create_user_for_tenant(
        db_session,
        tenant_id=test_tenant.id,
        role=FINAL_ACTION_APPROVER_ROLE_GRANTS,
    )
    final_action_approver_headers = _auth_headers_for(final_action_approver)
    release_decision = await create_release_decision(
        db_session,
        tenant_id=test_tenant.id,
        user_id=operator_user.id,
        batch_public_id="BATCH-P3-15-SHARE-001",
    )
    release_packet = ReleasePacketAttachmentRecord(
        attachment_id="RPA-P3-15-SHARE-001",
        release_decision_id=release_decision.id,
        tenant_id=test_tenant.id,
        user_id=operator_user.id,
        attachment_type="appendix",
        evidence_pack_id="EVP-FINAL-SHARE-001",
        appendix_hash="a" * 64,
        payload={"packet": "redacted release packet"},
    )
    db_session.add(release_packet)
    await db_session.commit()
    packet = await persist_review_packet_snapshot(
        db_session,
        tenant_id=test_tenant.id,
        generated_by_user_id=operator_user.id,
        packet={
            "packet_type": "assistant_review_workbench_audit_packet",
            "evidence_pack_ids": ["EVP-FINAL-SHARE-001"],
            "final_actions": {
                "release_approval": "not_executed",
                "model_activation": "not_executed",
                "external_share": "not_executed",
            },
        },
    )
    draft_response = await client.post(
        "/api/v1/final-actions/request-drafts",
        json={
            "action_type": "external_release_share",
            "target_type": "release_decision",
            "target_id": str(release_decision.id),
            "source_review_packet_id": packet.source_review_packet_id,
            "idempotency_key": "idem-final-share-draft",
        },
        headers=operator_headers,
    )
    assert draft_response.status_code == 201
    draft_id = draft_response.json()["final_action_request_id"]
    resolve_response = await client.post(
        f"/api/v1/final-actions/request-drafts/{draft_id}/resolve",
        json={"approved": True, "reason": "approved for internal external-share preparation"},
        headers=operator_headers,
    )
    assert resolve_response.status_code == 200

    blocked_response = await client.post(
        "/api/v1/final-actions/external-release-shares",
        json={
            "final_action_request_id": draft_id,
            "release_packet_attachment_id": release_packet.attachment_id,
            "recipient_scope": "allowlisted:regulator",
            "redaction_policy_id": "redaction-policy-v1",
            "operator_attestation": "Cannot share before release approval.",
            "idempotency_key": "idem-final-share-before-release",
        },
        headers=final_action_approver_headers,
    )
    assert blocked_response.status_code == 409
    assert blocked_response.json()["detail"] == "release_decision_not_approved:review_required"
    assert await count_external_release_share_records(db_session, test_tenant.id) == 0

    release_decision.decision = "approved"
    await db_session.commit()
    readiness_response = await client.get(
        f"/api/v1/final-actions/request-drafts/{draft_id}/execution-readiness",
        headers=operator_headers,
    )
    assert readiness_response.status_code == 200
    readiness = readiness_response.json()
    assert readiness["ready_for_audited_execution"] is True
    assert readiness["side_effects_if_executed"]["external_share"] is True
    assert readiness["target_state"]["external_network_send"] is False

    not_allowlisted_response = await client.post(
        "/api/v1/final-actions/external-release-shares",
        json={
            "final_action_request_id": draft_id,
            "release_packet_attachment_id": release_packet.attachment_id,
            "recipient_scope": "public:web",
            "redaction_policy_id": "redaction-policy-v1",
            "operator_attestation": "Recipient is not allowlisted.",
            "idempotency_key": "idem-final-share-not-allowlisted",
        },
        headers=final_action_approver_headers,
    )
    assert not_allowlisted_response.status_code == 409
    assert not_allowlisted_response.json()["detail"] == "recipient_scope_not_allowlisted"

    admin_share_response = await client.post(
        "/api/v1/final-actions/external-release-shares",
        json={
            "final_action_request_id": draft_id,
            "release_packet_attachment_id": release_packet.attachment_id,
            "recipient_scope": "allowlisted:regulator",
            "redaction_policy_id": "redaction-policy-v1",
            "operator_attestation": "Administrator without external share approver role cannot prepare share.",
            "idempotency_key": "idem-final-share-admin-denied",
        },
        headers=admin_headers,
    )
    assert admin_share_response.status_code == 403
    assert await count_external_release_share_records(db_session, test_tenant.id) == 0

    execute_response = await client.post(
        "/api/v1/final-actions/external-release-shares",
        json={
            "final_action_request_id": draft_id,
            "release_packet_attachment_id": release_packet.attachment_id,
            "recipient_scope": "allowlisted:regulator",
            "redaction_policy_id": "redaction-policy-v1",
            "operator_attestation": "I reviewed the redacted packet and prepare the external-share record.",
            "idempotency_key": "idem-final-share-execution",
        },
        headers=final_action_approver_headers,
    )
    assert execute_response.status_code == 201
    audit_record = execute_response.json()
    assert audit_record["action_type"] == "external_release_share"
    assert audit_record["target_id"] == str(release_decision.id)
    assert audit_record["decision"] == "prepared_internal_share"
    assert audit_record["after_state"]["delivery_status"] == "not_sent"
    assert audit_record["after_state"]["external_network_send"] is False
    assert audit_record["role_snapshot"]["required_role"] == "external_release_share_approver"
    assert "external_release_share_approver" in audit_record["role_snapshot"]["reviewed_by_user_roles"]
    assert audit_record["role_snapshot"]["admin_override"] is False
    assert audit_record["effect_summary"] == {
        "release_decision": "unchanged",
        "model_activation": False,
        "external_share": True,
        "hardware_execution": False,
        "external_network_send": False,
    }
    assert await count_external_release_share_records(db_session, test_tenant.id) == 1
    share = await db_session.scalar(
        select(ExternalReleaseShareRecord).where(
            ExternalReleaseShareRecord.final_action_id == audit_record["final_action_id"]
        )
    )
    assert share is not None
    assert share.delivery_status == "not_sent"
    assert share.payload["outbound_delivery_gate"] == "separate_approval_required"

    delivery_attempt_without_send_attestation = await client.post(
        "/api/v1/final-actions/external-release-deliveries",
        json={
            "share_id": share.share_id,
            "expected_delivery_status": "not_sent",
            "delivery_channel": "webhook",
            "delivery_endpoint": "http://127.0.0.1:8999/external-share-receiver",
            "external_network_send": False,
            "operator_attestation": "Missing explicit network send attestation.",
            "idempotency_key": "idem-final-share-delivery-no-send",
        },
        headers=final_action_approver_headers,
    )
    assert delivery_attempt_without_send_attestation.status_code == 409
    assert delivery_attempt_without_send_attestation.json()["detail"] == "external_network_send_attestation_required"
    await db_session.refresh(share)
    assert share.delivery_status == "not_sent"

    delivery_attempt_not_allowlisted = await client.post(
        "/api/v1/final-actions/external-release-deliveries",
        json={
            "share_id": share.share_id,
            "expected_delivery_status": "not_sent",
            "delivery_channel": "webhook",
            "delivery_endpoint": "https://unapproved.example.com/external-share-receiver",
            "external_network_send": True,
            "operator_attestation": "Endpoint must be allowlisted.",
            "idempotency_key": "idem-final-share-delivery-unapproved-endpoint",
        },
        headers=final_action_approver_headers,
    )
    assert delivery_attempt_not_allowlisted.status_code == 409
    assert delivery_attempt_not_allowlisted.json()["detail"] == "delivery_endpoint_not_allowlisted"
    await db_session.refresh(share)
    assert share.delivery_status == "not_sent"

    delivered_payloads = []

    class FakeDeliveryResponse:
        status_code = 202
        text = "accepted"

    class FakeDeliveryClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json):
            delivered_payloads.append({"url": url, "json": json})
            return FakeDeliveryResponse()

    monkeypatch.setattr(
        "app.services.final_action_audit_record_service.httpx.AsyncClient",
        FakeDeliveryClient,
    )

    admin_delivery_response = await client.post(
        "/api/v1/final-actions/external-release-deliveries",
        json={
            "share_id": share.share_id,
            "expected_delivery_status": "not_sent",
            "delivery_channel": "webhook",
            "delivery_endpoint": "http://127.0.0.1:8999/external-share-receiver",
            "external_network_send": True,
            "operator_attestation": "Administrator without external delivery approver role cannot deliver.",
            "idempotency_key": "idem-final-share-delivery-admin-denied",
        },
        headers=admin_headers,
    )
    assert admin_delivery_response.status_code == 403
    assert len(delivered_payloads) == 0

    delivery_response = await client.post(
        "/api/v1/final-actions/external-release-deliveries",
        json={
            "share_id": share.share_id,
            "expected_delivery_status": "not_sent",
            "delivery_channel": "webhook",
            "delivery_endpoint": "http://127.0.0.1:8999/external-share-receiver",
            "external_network_send": True,
            "operator_attestation": "I approve the outbound external share delivery.",
            "idempotency_key": "idem-final-share-delivery",
        },
        headers=final_action_approver_headers,
    )
    assert delivery_response.status_code == 201
    delivery_audit_record = delivery_response.json()
    assert delivery_audit_record["action_type"] == "external_release_delivery"
    assert delivery_audit_record["target_type"] == "external_release_share_record"
    assert delivery_audit_record["target_id"] == share.share_id
    assert delivery_audit_record["decision"] == "sent"
    assert delivery_audit_record["before_state"]["delivery_status"] == "not_sent"
    assert delivery_audit_record["before_state"]["external_network_send"] is False
    assert delivery_audit_record["after_state"]["delivery_status"] == "sent"
    assert delivery_audit_record["after_state"]["external_network_send"] is True
    assert delivery_audit_record["role_snapshot"]["required_role"] == "external_release_delivery_approver"
    assert "external_release_delivery_approver" in delivery_audit_record["role_snapshot"]["reviewed_by_user_roles"]
    assert delivery_audit_record["role_snapshot"]["admin_override"] is False
    assert delivery_audit_record["effect_summary"]["external_network_send"] is True
    assert delivered_payloads == [
        {
            "url": "http://127.0.0.1:8999/external-share-receiver",
            "json": {
                "schema_version": "bos_external_release_delivery_v1",
                "share_id": share.share_id,
                "release_decision_id": release_decision.id,
                "release_packet_attachment_id": release_packet.attachment_id,
                "release_packet_appendix_hash": release_packet.appendix_hash,
                "recipient_scope": "allowlisted:regulator",
                "redaction_policy_id": "redaction-policy-v1",
                "source_review_packet_id": packet.source_review_packet_id,
                "preparation_final_action_id": audit_record["final_action_id"],
                "delivery_final_action_id": delivery_audit_record["final_action_id"],
                "release_packet_payload": {"packet": "redacted release packet"},
            },
        }
    ]
    await db_session.refresh(share)
    assert share.delivery_status == "sent"
    assert share.status == "delivered_external_share"
    assert share.payload["external_network_send"] is True
    assert share.payload["outbound_delivery_gate"] == "executed"
    assert share.payload["delivery_response_status_code"] == 202

    delivery_repeat_response = await client.post(
        "/api/v1/final-actions/external-release-deliveries",
        json={
            "share_id": share.share_id,
            "expected_delivery_status": "not_sent",
            "delivery_channel": "webhook",
            "delivery_endpoint": "http://127.0.0.1:8999/external-share-receiver",
            "external_network_send": True,
            "operator_attestation": "Idempotent repeat returns delivery audit record.",
            "idempotency_key": "idem-final-share-delivery",
        },
        headers=final_action_approver_headers,
    )
    assert delivery_repeat_response.status_code == 201
    assert delivery_repeat_response.json()["final_action_id"] == delivery_audit_record["final_action_id"]
    assert len(delivered_payloads) == 1

    second_delivery_response = await client.post(
        "/api/v1/final-actions/external-release-deliveries",
        json={
            "share_id": share.share_id,
            "expected_delivery_status": "not_sent",
            "delivery_channel": "webhook",
            "delivery_endpoint": "http://127.0.0.1:8999/external-share-receiver",
            "external_network_send": True,
            "operator_attestation": "Second delivery must not resend already sent share.",
            "idempotency_key": "idem-final-share-delivery-second",
        },
        headers=final_action_approver_headers,
    )
    assert second_delivery_response.status_code == 409
    assert second_delivery_response.json()["detail"] == "external_release_share_delivery_status_mismatch:sent"
    assert len(delivered_payloads) == 1

    repeat_response = await client.post(
        "/api/v1/final-actions/external-release-shares",
        json={
            "final_action_request_id": draft_id,
            "release_packet_attachment_id": release_packet.attachment_id,
            "recipient_scope": "allowlisted:regulator",
            "redaction_policy_id": "redaction-policy-v1",
            "operator_attestation": "Idempotent repeat returns existing audit record.",
            "idempotency_key": "idem-final-share-execution",
        },
        headers=final_action_approver_headers,
    )
    assert repeat_response.status_code == 201
    assert repeat_response.json()["final_action_id"] == audit_record["final_action_id"]
    assert await count_external_release_share_records(db_session, test_tenant.id) == 1

    audit_records_response = await client.get("/api/v1/final-actions/audit-records", headers=operator_headers)
    assert audit_records_response.status_code == 200
    assert "external_share_records_may_include_delivered_external_shares" in audit_records_response.json()["guardrails"]
    assert "external_network_send_executed_by_delivery_gate" in audit_records_response.json()["guardrails"]


@pytest.mark.asyncio
async def test_non_executing_final_action_request_draft_writer_blocks_invalid_inputs_without_writes(
    db_session: AsyncSession,
    test_tenant,
    operator_user,
):
    other_tenant, other_operator, _ = await create_tenant_with_user(db_session)
    viewer_user = await create_user_for_tenant(db_session, tenant_id=test_tenant.id, role="viewer")
    other_packet = await persist_review_packet_snapshot(
        db_session,
        tenant_id=other_tenant.id,
        generated_by_user_id=other_operator.id,
        packet={
            "packet_type": "assistant_review_workbench_audit_packet",
            "evidence_pack_ids": ["EVP-OTHER-DRAFT"],
            "final_actions": {
                "release_approval": "not_executed",
                "model_activation": "not_executed",
                "external_share": "not_executed",
            },
        },
    )

    with pytest.raises(ValueError, match="source_review_packet_not_found"):
        await create_non_executing_final_action_request_draft(
            db_session,
            tenant_id=test_tenant.id,
            request=FinalActionPreflightInput(
                action_type="external_release_share",
                target_type="release_packet",
                target_id="RPACK-MISSING-SOURCE",
                source_review_packet_id="FARP-MISSING-DRAFT",
                idempotency_key="idem-missing-draft-source",
                requested_by_user_id=operator_user.id,
            ),
        )

    with pytest.raises(ValueError, match="source_review_packet_not_found"):
        await create_non_executing_final_action_request_draft(
            db_session,
            tenant_id=test_tenant.id,
            request=FinalActionPreflightInput(
                action_type="external_release_share",
                target_type="release_packet",
                target_id="RPACK-CROSS-TENANT-SOURCE",
                source_review_packet_id=other_packet.source_review_packet_id,
                idempotency_key="idem-cross-tenant-source",
                requested_by_user_id=operator_user.id,
            ),
        )

    with pytest.raises(ValueError, match="requested_by_user_tenant_mismatch"):
        await create_non_executing_final_action_request_draft(
            db_session,
            tenant_id=test_tenant.id,
            request=FinalActionPreflightInput(
                action_type="model_activation",
                target_type="model_version",
                target_id="MV-CROSS-TENANT-REQUESTER",
                source_review_packet_id=other_packet.source_review_packet_id,
                idempotency_key="idem-cross-tenant-requester",
                requested_by_user_id=other_operator.id,
            ),
        )

    with pytest.raises(ValueError, match="requested_by_user_role_not_allowed_for_final_action_draft"):
        await create_non_executing_final_action_request_draft(
            db_session,
            tenant_id=test_tenant.id,
            request=FinalActionPreflightInput(
                action_type="model_activation",
                target_type="model_version",
                target_id="MV-VIEWER-REQUESTER",
                source_review_packet_id=other_packet.source_review_packet_id,
                idempotency_key="idem-viewer-requester",
                requested_by_user_id=viewer_user.id,
            ),
        )

    assert await count_final_action_request_drafts(db_session, test_tenant.id) == 0
    assert await count_final_action_audit_records(db_session, test_tenant.id) == 0


@pytest.mark.asyncio
async def test_assistant_feature_flag_off_does_not_create_runs_or_tool_calls(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
):
    await set_db_override(
        db_session,
        flag_name="bos_simulation_lab",
        tenant_id=test_tenant.id,
        enabled=False,
    )

    response = await client.post(
        "/api/v1/assistant/runs",
        json={"message": "create a moisture drift scenario, run 8 cycles", "mode": "simulation_lab"},
        headers=operator_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "bos_simulation_lab_disabled"

    run_count = (
        await db_session.execute(
            select(func.count()).select_from(AssistantRunRecord).where(AssistantRunRecord.tenant_id == test_tenant.id)
        )
    ).scalar_one()
    tool_call_count = (
        await db_session.execute(
            select(func.count())
            .select_from(AssistantToolCallRecord)
            .where(AssistantToolCallRecord.tenant_id == test_tenant.id)
        )
    ).scalar_one()
    assert run_count == 0
    assert tool_call_count == 0


@pytest.mark.asyncio
async def test_research_review_run_creates_fixed_team_evidence_packet_and_review_queue(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
):
    snapshot_count_before = await count_final_action_review_packet_snapshots(db_session, test_tenant.id)
    audit_count_before = await count_final_action_audit_records(db_session, test_tenant.id)

    response = await client.post(
        "/api/v1/assistant/runs",
        json={
            "message": (
                "Research review: evaluate a BSF solid waste protocol with literature context, "
                "existing data, mechanism risks, and simulation suggestions."
            ),
            "mode": "research_review",
        },
        headers=operator_headers,
    )

    assert response.status_code == 201
    assistant_run = response.json()
    assert assistant_run["status"] == "completed"
    assert assistant_run["parsed_intent"]["mode"] == "research_review"
    assert assistant_run["parsed_intent"]["review_type"] == "research_protocol_review"
    assert assistant_run["evidence_pack_id"]
    assert assistant_run["tool_calls"] == []
    assert assistant_run["team_plan"] == assistant_run["result_summary"]["team_plan"]
    assert len(assistant_run["team_plan"]) == 9
    assert [step["title"] for step in assistant_run["team_plan"]] == [
        "Chief Scientist",
        "Protocol Designer",
        "Mechanistic Analyst",
        "Reference Evidence Curator",
        "Digital Twin Analyst",
        "Data Integrity Reviewer",
        "Scientific Reviewer",
        "Evidence Auditor",
        "Chief Scientist",
    ]
    assert len(assistant_run["specialist_cards"]) == 9
    assert all(card["review_required"] is True for card in assistant_run["specialist_cards"])
    assert assistant_run["final_synthesis"]["approval_state"] == "review_required"
    assert assistant_run["result_summary"]["human_review_queue"]["status"] == "pending"
    assert assistant_run["result_summary"]["human_review_queue"]["source_review_packet_id"].startswith("FARP-")
    assert {item["action_policy"] for item in assistant_run["action_ledger"]} >= {
        "auto_allowed",
        "requires_confirmation",
        "forbidden",
    }
    assert any(item["status"] == "forbidden" for item in assistant_run["action_ledger"])
    assert any(item["requires_confirmation"] is True for item in assistant_run["action_ledger"])

    forbidden_statuses = {"approved", "executable", "auto_approved"}
    encoded_summary = json.dumps(assistant_run["result_summary"], sort_keys=True)
    assert not any(status in encoded_summary for status in forbidden_statuses)

    evidence_response = await client.get(
        f"/api/v1/evidence-packs/{assistant_run['evidence_pack_id']}",
        headers=operator_headers,
    )
    assert evidence_response.status_code == 200
    evidence_pack = evidence_response.json()
    assert evidence_pack["subject_type"] == "assistant_run"
    assert evidence_pack["verification_status"] == "review_required"
    assert evidence_pack["human_review_required"] is True
    assert {item["kind"] for item in evidence_pack["items"]} == {
        "research_review_intent",
        "research_review_team_trace",
    }

    approval = await db_session.scalar(
        select(HumanApprovalRequestRecord).where(
            HumanApprovalRequestRecord.tenant_id == test_tenant.id,
            HumanApprovalRequestRecord.subject_type == "research_review",
            HumanApprovalRequestRecord.subject_id == assistant_run["run_id"],
        )
    )
    assert approval is not None
    assert approval.status == "pending"
    assert approval.payload["assistant_evidence_pack_id"] == assistant_run["evidence_pack_id"]

    assert await count_final_action_review_packet_snapshots(db_session, test_tenant.id) == snapshot_count_before + 1
    assert await count_final_action_audit_records(db_session, test_tenant.id) == audit_count_before


@pytest.mark.asyncio
async def test_research_review_chinese_mealworm_grub_distillers_grain_keeps_review_gate(
    client: AsyncClient,
    operator_headers,
):
    response = await client.post(
        "/api/v1/assistant/runs",
        json={
            "message": "你觉得黄粉虫和蛴螬 哪个更适合处理酒糟",
            "mode": "research_review",
        },
        headers=operator_headers,
    )

    assert response.status_code == 201
    assistant_run = response.json()
    final_synthesis = assistant_run["final_synthesis"]

    assert assistant_run["parsed_intent"]["language"] == "zh-CN"
    assert assistant_run["result_summary"]["language"] == "zh-CN"
    assert final_synthesis["language"] == "zh-CN"
    assert final_synthesis["reasoning_stages"]
    assert final_synthesis["debate_turns"]
    assert final_synthesis["evidence_status"]
    assert final_synthesis["experiment_plan"]
    assert "黄粉虫" in final_synthesis["unified_answer"]
    assert "蛴螬" in final_synthesis["unified_answer"]
    assert any(stage["stage"] == "问题重构" for stage in final_synthesis["reasoning_stages"])
    assert any(item["status"] == "candidate_evidence" for item in final_synthesis["evidence_status"])
    assert any("黄粉虫" in item["step"] for item in final_synthesis["experiment_plan"])
    assert any(turn.get("reply") for turn in final_synthesis["debate_turns"])
    assert final_synthesis["approval_state"] == "review_required"
    assert all(card["review_required"] is True for card in assistant_run["specialist_cards"])


def assert_research_review_contract(assistant_run: dict):
    assert assistant_run["status"] == "completed"
    assert assistant_run["parsed_intent"]["mode"] == "research_review"
    assert len(assistant_run["team_plan"]) == 9
    assert len(assistant_run["specialist_cards"]) == 9
    assert all(card["review_required"] is True for card in assistant_run["specialist_cards"])
    assert assistant_run["evidence_pack_id"]
    assert assistant_run["final_synthesis"]["approval_state"] == "review_required"
    assert assistant_run["final_synthesis"]["review_packet_snapshot_id"].startswith("FARP-")
    actions_by_name = {item["action_name"]: item for item in assistant_run["action_ledger"]}
    assert actions_by_name["external.share"]["status"] == "requires_confirmation"
    assert actions_by_name["release.final_decision"]["status"] == "forbidden"
    assert actions_by_name["hardware.run"]["status"] == "forbidden"
    disallowed_states = {"approved", "executable", "auto_approved"}
    assert assistant_run["final_synthesis"]["approval_state"] not in disallowed_states
    assert not any(item.get("status") in disallowed_states for item in assistant_run["action_ledger"])


@pytest.mark.asyncio
async def test_research_review_multisample_golden_suite_keeps_review_gates(
    client: AsyncClient,
    operator_headers,
):
    samples = [
        "Research review: BSF larvae food waste moisture control for SER improvement and ammonia odor reduction.",
        "Research review: feedstock substitution with contamination risk, source provenance, and review gates.",
        "Scientific review: digital twin scenario validation for moisture drift and sensitivity checks.",
        "Protocol review: ammonia odor reduction with mechanism counterexamples and failure modes.",
        "Research protocol review: literature-heavy evidence map with external source audit gaps.",
        "请做课题方案评审：餐厨垃圾替代饲料基质的污染风险控制，检查证据、数据完整性和安全门。",
    ]

    for index, message in enumerate(samples):
        response = await client.post(
            "/api/v1/assistant/runs",
            json={
                "message": message,
                "mode": "research_review",
                "thread_id": f"research-review-golden-suite-{index}",
            },
            headers=operator_headers,
        )
        assert response.status_code == 201
        assistant_run = response.json()
        assert_research_review_contract(assistant_run)

        evidence_response = await client.get(
            f"/api/v1/evidence-packs/{assistant_run['evidence_pack_id']}",
            headers=operator_headers,
        )
        assert evidence_response.status_code == 200
        evidence_pack = evidence_response.json()
        assert evidence_pack["verification_status"] == "review_required"
        assert evidence_pack["human_review_required"] is True


@pytest.mark.asyncio
async def test_research_review_follow_up_recalls_parent_team_and_focuses_specialist(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
):
    audit_count_before = await count_final_action_audit_records(db_session, test_tenant.id)

    first_response = await client.post(
        "/api/v1/assistant/runs",
        json={
            "message": "Research review: evaluate a BSF solid waste protocol with mechanism risks.",
            "mode": "research_review",
            "thread_id": "assistant-thread-42",
        },
        headers=operator_headers,
    )
    assert first_response.status_code == 201
    first_run = first_response.json()

    follow_up_response = await client.post(
        "/api/v1/assistant/runs",
        json={
            "message": "让 Mechanistic Analyst 继续深挖反证和失效模式",
            "mode": "research_review",
            "thread_id": "assistant-thread-42",
            "parent_run_id": first_run["run_id"],
        },
        headers=operator_headers,
    )

    assert follow_up_response.status_code == 201
    follow_up = follow_up_response.json()
    assert follow_up["status"] == "completed"
    assert follow_up["parsed_intent"]["parent_run_id"] == first_run["run_id"]
    assert follow_up["parsed_intent"]["continuity_scope"] == "tenant_scoped_parent_run"
    assert follow_up["parsed_intent"]["requested_specialist"] == "mechanistic_analyst"
    assert follow_up["result_summary"]["result_ids"]["parent_run_id"] == first_run["run_id"]
    assert follow_up["result_summary"]["continuity_context"]["parent_run_id"] == first_run["run_id"]
    assert follow_up["team_plan"] == first_run["team_plan"]
    assert follow_up["final_synthesis"]["approval_state"] == "review_required"
    assert follow_up["final_synthesis"]["continuity"]["team_context_reused"] is True
    mechanistic_card = next(card for card in follow_up["specialist_cards"] if card["specialist_id"] == "mechanistic_analyst")
    assert any(item == f"parent_run:{first_run['run_id']}" for item in mechanistic_card["inputs_used"])
    assert "counterexamples" in mechanistic_card["deliverable"] or "反例" in mechanistic_card["deliverable"]
    assert all(card["review_required"] is True for card in follow_up["specialist_cards"])

    encoded_summary = json.dumps(follow_up["result_summary"], sort_keys=True)
    assert "executable" not in encoded_summary
    assert "auto_approved" not in encoded_summary
    assert await count_final_action_audit_records(db_session, test_tenant.id) == audit_count_before


@pytest.mark.asyncio
async def test_research_review_parent_run_recall_is_tenant_scoped(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
):
    other_tenant, _other_user, other_headers = await create_tenant_with_user(db_session)

    other_response = await client.post(
        "/api/v1/assistant/runs",
        json={
            "message": "Research review: other tenant protocol",
            "mode": "research_review",
            "thread_id": "other-thread",
        },
        headers=other_headers,
    )
    assert other_response.status_code == 201
    other_run = other_response.json()

    response = await client.post(
        "/api/v1/assistant/runs",
        json={
            "message": "continue with mechanistic analyst",
            "mode": "research_review",
            "thread_id": "operator-thread",
            "parent_run_id": other_run["run_id"],
        },
        headers=operator_headers,
    )
    assert response.status_code == 201
    assistant_run = response.json()

    assert other_tenant.id != test_tenant.id
    assert assistant_run["tenant_id"] == test_tenant.id
    assert assistant_run["parsed_intent"]["parent_run_id_requested"] == other_run["run_id"]
    assert assistant_run["parsed_intent"]["continuity_scope"] == "not_recalled_missing_or_tenant_boundary"
    assert assistant_run["result_summary"]["continuity_context"] is None
    assert assistant_run["result_summary"]["result_ids"]["parent_run_id"] is None
    assert assistant_run["final_synthesis"]["approval_state"] == "review_required"


@pytest.mark.asyncio
async def test_assistant_run_creates_simulation_tool_log_and_evidence_pack(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
):
    await enable_simulation_lab(db_session, test_tenant.id)

    response = await client.post(
        "/api/v1/assistant/runs",
        json={"message": "create a moisture drift scenario, run 6 cycles, compare policies", "mode": "simulation_lab"},
        headers=operator_headers,
    )

    assert response.status_code == 201
    assistant_run = response.json()
    assert assistant_run["status"] == "completed"
    assert assistant_run["parsed_intent"]["scenario"] == "moisture_drift"
    assert assistant_run["parsed_intent"]["cycles"] == 6
    assert assistant_run["evidence_pack_id"]
    assert assistant_run["result_summary"]["simulation_id"].startswith("SIM-")
    assert assistant_run["result_summary"]["comparison"]["winner"]["lowest_risk"]
    assert assistant_run["tool_registry"]["version"] == "assistant-tool-registry-v1"
    assert assistant_run["result_summary"]["tool_registry_version"] == "assistant-tool-registry-v1"
    assert assistant_run["result_summary"]["input_snapshot"]["scenario"] == "moisture_drift"
    assert assistant_run["result_summary"]["input_snapshot"]["requested_outputs"]["compare_policies"] is True
    assert assistant_run["result_summary"]["human_review_requirement"]["state"] == "review_required"
    assert assistant_run["result_summary"]["next_safe_actions"]
    assert [step["status"] for step in assistant_run["result_summary"]["execution_plan"]].count("completed") >= 3

    tool_names = [call["tool_name"] for call in assistant_run["tool_calls"]]
    assert tool_names == [
        "simulation_lab.create_scenario",
        "simulation_lab.run_scenario",
        "simulation_lab.compare_policies",
        "simulation_lab.get_cycles",
        "simulation_lab.get_audit_trace",
        "simulation_lab.export_release_appendix",
    ]
    assert all(call["status"] == "completed" for call in assistant_run["tool_calls"])

    tool_response = await client.get(
        f"/api/v1/assistant/runs/{assistant_run['run_id']}/tool-calls",
        headers=operator_headers,
    )
    assert tool_response.status_code == 200
    assert len(tool_response.json()) == 6

    evidence_response = await client.get(
        f"/api/v1/evidence-packs/{assistant_run['evidence_pack_id']}",
        headers=operator_headers,
    )
    assert evidence_response.status_code == 200
    evidence_pack = evidence_response.json()
    assert evidence_pack["subject_type"] == "assistant_run"
    assert evidence_pack["human_review_required"] is True
    assert {item["kind"] for item in evidence_pack["items"]} == {"assistant_intent", "tool_call_log"}
    tool_log = next(item for item in evidence_pack["items"] if item["kind"] == "tool_call_log")
    assert tool_log["uncertainty_level"] == "medium"
    assert "release.attach_simulation_appendix" in tool_log["payload"]["safe_tools"]
    assert "release.request_human_approval" in tool_log["payload"]["requires_confirmation"]
    assert tool_log["payload"]["tool_registry"]["version"] == "assistant-tool-registry-v1"
    assert tool_log["payload"]["execution_plan"]
    assert tool_log["payload"]["input_snapshot"]["scenario"] == "moisture_drift"


@pytest.mark.asyncio
async def test_assistant_run_wires_compliance_lca_and_tea_value_proofs_without_release_approval(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
    operator_user,
):
    await enable_simulation_lab(db_session, test_tenant.id)
    release_decision = await create_release_decision(
        db_session,
        tenant_id=test_tenant.id,
        user_id=operator_user.id,
        batch_public_id="BATCH-ASSISTANT-P12-001",
    )

    response = await client.post(
        "/api/v1/assistant/runs",
        json={
            "message": (
                f"create a moisture drift scenario, compare policies, run compliance for batch: {release_decision.batch_id}, "
                "then add LCA and TEA value proof"
            ),
            "mode": "simulation_lab",
        },
        headers=operator_headers,
    )

    assert response.status_code == 201
    assistant_run = response.json()
    assert assistant_run["status"] == "completed"
    assert assistant_run["parsed_intent"]["request_compliance"] is True
    assert assistant_run["parsed_intent"]["request_lca"] is True
    assert assistant_run["parsed_intent"]["request_tea"] is True

    tool_names = [call["tool_name"] for call in assistant_run["tool_calls"]]
    assert "compliance.evaluate" in tool_names
    assert "lca.compare" in tool_names
    assert "tea.estimate" in tool_names
    assert all(call["status"] == "completed" for call in assistant_run["tool_calls"])

    summary = assistant_run["result_summary"]
    assert summary["compliance_gate"]["status"] == "blocked"
    assert summary["compliance_gate"]["human_review_required"] is True
    assert all(reason.startswith("missing_assay:") for reason in summary["compliance_gate"]["blocked_reasons"])
    assert summary["lca_value_proof"]["result"]["co2e_abatement_kg"] > 0
    assert "emission_factor.electricity_kgco2e_per_kwh defaulted" in summary["lca_value_proof"]["uncertainty_warnings"]
    assert "gross_margin_usd" in summary["tea_value_proof"]["result"]
    assert "cost_factor.energy_usd_per_kwh defaulted" in summary["tea_value_proof"]["uncertainty_warnings"]
    assert "emission_factor.electricity_kgco2e_per_kwh defaulted" in summary["uncertainty_warnings"]
    assert "cost_factor.energy_usd_per_kwh defaulted" in summary["uncertainty_warnings"]
    assert summary["result_ids"]["compliance_evidence_pack_id"]
    assert summary["result_ids"]["lca_evidence_pack_id"]
    assert summary["result_ids"]["tea_evidence_pack_id"]
    assert summary["human_review_requirement"]["state"] == "review_required"
    assert "compliance blocker resolution" in summary["human_review_requirement"]["required_for"]
    assert "LCA/TEA uncertainty review" in summary["human_review_requirement"]["required_for"]
    assert "Release decision remains unchanged until human review." in summary["risk_value_drivers"]["risk_drivers"]
    assert any(action["label"] == "Review compliance evidence" for action in summary["next_safe_actions"])

    await db_session.refresh(release_decision)
    assert release_decision.decision == "review_required"

    runs_response = await client.get("/api/v1/assistant/runs", params={"limit": 3}, headers=operator_headers)
    assert runs_response.status_code == 200
    listed_runs = runs_response.json()
    assert listed_runs[0]["run_id"] == assistant_run["run_id"]
    assert listed_runs[0]["result_summary"]["result_ids"]["lca_evidence_pack_id"]


@pytest.mark.asyncio
async def test_assistant_reference_id_uses_import_tool_and_evidence_contract(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
):
    await enable_simulation_lab(db_session, test_tenant.id)

    response = await client.post(
        "/api/v1/assistant/runs",
        json={
            "message": "reference_id:beer_lees_moisture_gradient run 6 cycles",
            "mode": "simulation_lab",
        },
        headers=operator_headers,
    )

    assert response.status_code == 201
    assistant_run = response.json()
    assert assistant_run["status"] == "completed"
    assert assistant_run["parsed_intent"]["reference_id"] == "beer_lees_moisture_gradient"
    tool_names = [call["tool_name"] for call in assistant_run["tool_calls"]]
    assert tool_names[0] == "simulation_lab.import_scenario_from_reference"
    assert "simulation_lab.create_scenario" not in tool_names
    assert assistant_run["evidence_pack_id"]

    evidence_response = await client.get(
        f"/api/v1/evidence-packs/{assistant_run['evidence_pack_id']}",
        headers=operator_headers,
    )
    assert evidence_response.status_code == 200
    evidence_pack = evidence_response.json()
    assert evidence_pack["subject_type"] == "assistant_run"
    assert evidence_pack["verification_status"] == "review_required"
    assert evidence_pack["human_review_required"] is True
    assert {item["kind"] for item in evidence_pack["items"]} == {"assistant_intent", "tool_call_log"}


@pytest.mark.asyncio
async def test_assistant_tool_calls_and_evidence_pack_are_tenant_isolated(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
):
    await enable_simulation_lab(db_session, test_tenant.id)
    _other_tenant, _other_user, other_headers = await create_tenant_with_user(db_session)

    response = await client.post(
        "/api/v1/assistant/runs",
        json={"message": "create a moisture drift scenario, run 6 cycles, compare policies", "mode": "simulation_lab"},
        headers=operator_headers,
    )

    assert response.status_code == 201
    assistant_run = response.json()
    run_id = assistant_run["run_id"]
    evidence_pack_id = assistant_run["evidence_pack_id"]

    assert (
        await client.get(
            f"/api/v1/assistant/runs/{run_id}",
            headers=other_headers,
        )
    ).status_code == 404
    assert (
        await client.get(
            f"/api/v1/assistant/runs/{run_id}/tool-calls",
            headers=other_headers,
        )
    ).status_code == 404
    assert (
        await client.get(
            f"/api/v1/evidence-packs/{evidence_pack_id}",
            headers=other_headers,
        )
    ).status_code == 404
    assert (
        await client.get(
            f"/api/v1/evidence-packs/{evidence_pack_id}/items",
            headers=other_headers,
        )
    ).status_code == 404


@pytest.mark.asyncio
async def test_evidence_pack_create_and_fetch_round_trip(client: AsyncClient, operator_headers):
    response = await client.post(
        "/api/v1/evidence-packs",
        json={
            "subject_type": "recommendation",
            "subject_id": "REC-001",
            "title": "Recommendation evidence",
            "summary": "Minimal evidence pack smoke test.",
            "verification_status": "review_required",
            "human_review_required": True,
            "items": [
                {
                    "kind": "assumption",
                    "source_kind": "operator_input",
                    "source_ref": "pytest",
                    "payload": {"risk": "moisture"},
                    "confidence": 0.8,
                    "uncertainty_level": "medium",
                }
            ],
        },
        headers=operator_headers,
    )

    assert response.status_code == 201
    pack = response.json()
    assert pack["evidence_pack_id"].startswith("EVP-")
    assert pack["items"][0]["uncertainty_level"] == "medium"

    items_response = await client.get(
        f"/api/v1/evidence-packs/{pack['evidence_pack_id']}/items",
        headers=operator_headers,
    )
    assert items_response.status_code == 200
    assert items_response.json()[0]["source_kind"] == "operator_input"


@pytest.mark.asyncio
async def test_evidence_sources_and_replay_are_deterministic_for_core_fields(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
):
    await enable_simulation_lab(db_session, test_tenant.id)
    simulation_id, run_id = await create_simulation_run(client, operator_headers)

    sources_response = await client.get(
        f"/api/v1/bos/simulation-lab/scenarios/{simulation_id}/evidence-sources",
        headers=operator_headers,
    )
    assert sources_response.status_code == 200
    sources = sources_response.json()
    scenario_sources = {item["field"]: item for item in sources["scenario_sources"]}
    assert scenario_sources["species"]["source_kind"] == "operator_input"
    assert scenario_sources["feedstock"]["source_kind"] == "operator_input"
    assert scenario_sources["scenario"]["source_kind"] == "operator_input"
    assert scenario_sources["initial_state"]["source_kind"] == "operator_input"
    assert scenario_sources["policy"]["source_kind"] == "operator_input"

    latest_run_sources = {item["field"]: item for item in sources["latest_run_sources"]}
    assert latest_run_sources["risk_prediction"]["source_kind"] in {
        "deterministic_model",
        "chronos_model",
        "fallback_default",
    }
    assert latest_run_sources["visual_observation"]["source_kind"] == "synthetic"
    assert latest_run_sources["agent_action"]["source_kind"] == "deterministic_model"
    assert sources["cycle_sources"]
    first_cycle_sources = {item["field"]: item for item in sources["cycle_sources"][0]["evidence_sources"]}
    assert first_cycle_sources["sensor_observation"]["source_kind"] == "synthetic"
    assert first_cycle_sources["visual_observation"]["source_kind"] == "synthetic"
    assert first_cycle_sources["risk_prediction"]["source_kind"] in {
        "deterministic_model",
        "chronos_model",
        "fallback_default",
    }

    export_response = await client.get(
        f"/api/v1/bos/simulation-lab/scenarios/{simulation_id}/export",
        headers=operator_headers,
    )
    assert export_response.status_code == 200
    exported = export_response.json()
    exported_sources = {item["field"]: item for item in exported["evidence_sources"]}
    assert exported_sources["scenario"]["source_kind"] == "operator_input"
    assert exported["cycles"][0]["evidence_sources"]

    appendix_response = await client.get(
        f"/api/v1/bos/simulation-lab/scenarios/{simulation_id}/release-appendix",
        headers=operator_headers,
    )
    assert appendix_response.status_code == 200
    appendix = appendix_response.json()
    appendix_sources = {item["field"]: item for item in appendix["scenario"]["evidence_sources"]}
    assert appendix_sources["initial_state"]["source_kind"] == "operator_input"

    replay_response = await client.post(
        f"/api/v1/bos/simulation-lab/runs/{run_id}/replay",
        headers=operator_headers,
    )
    assert replay_response.status_code == 200
    replay = replay_response.json()
    assert replay["source_run_id"] == run_id
    assert replay["deterministic_core_match"] is True
    assert replay["replay_run"]["replay_of_run_id"] == run_id
    assert replay["replay_run"]["input_snapshot_hash"]

    diff_response = await client.get(
        f"/api/v1/bos/simulation-lab/runs/{run_id}/diff",
        params={"against_run_id": replay["replay_run"]["run_id"]},
        headers=operator_headers,
    )
    assert diff_response.status_code == 200
    assert diff_response.json()["deterministic_core_match"] is True


@pytest.mark.asyncio
async def test_reference_import_run_and_export_preserve_source_attribution(
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
    simulation_id = imported["scenario"]["simulation_id"]
    metadata = imported["import_metadata"]
    assert metadata["reference_source"] == "manuscript_campaign"

    scenario_sources = {item["field"]: item for item in imported["scenario"]["evidence_sources"]}
    assert scenario_sources["scenario"]["source_kind"] == "manuscript_campaign"
    assert scenario_sources["policy"]["source_kind"] == "operator_input"
    assert any(source["source_kind"] == "manuscript_campaign" for source in scenario_sources.values())

    run_response = await client.post(
        f"/api/v1/bos/simulation-lab/scenarios/{simulation_id}/run",
        headers=operator_headers,
    )
    assert run_response.status_code == 200

    sources_response = await client.get(
        f"/api/v1/bos/simulation-lab/scenarios/{simulation_id}/evidence-sources",
        headers=operator_headers,
    )
    assert sources_response.status_code == 200
    sources = sources_response.json()
    assert any(item["source_kind"] == "manuscript_campaign" for item in sources["scenario_sources"])
    assert sources["cycle_sources"][0]["evidence_sources"]

    export_response = await client.get(
        f"/api/v1/bos/simulation-lab/scenarios/{simulation_id}/export",
        headers=operator_headers,
    )
    assert export_response.status_code == 200
    exported = export_response.json()
    exported_scenario_sources = {item["field"]: item for item in exported["scenario"]["evidence_sources"]}
    assert exported_scenario_sources["scenario"]["source_kind"] == "manuscript_campaign"
    assert exported["cycles"][0]["evidence_sources"]


@pytest.mark.asyncio
async def test_release_appendix_attachment_does_not_change_release_decision(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
    operator_user,
):
    await enable_simulation_lab(db_session, test_tenant.id)
    simulation_id, run_id = await create_simulation_run(client, operator_headers)

    release_decision = await create_release_decision(
        db_session,
        tenant_id=test_tenant.id,
        user_id=operator_user.id,
        batch_public_id="BATCH-RELEASE-001",
    )

    response = await client.post(
        f"/api/v1/release-packets/{release_decision.id}/appendices/simulation",
        json={"simulation_id": simulation_id, "run_id": run_id},
        headers=operator_headers,
    )

    assert response.status_code == 201
    attachment = response.json()
    assert attachment["simulation_id"] == simulation_id
    assert attachment["run_id"] == run_id
    assert attachment["appendix_hash"]

    await db_session.refresh(release_decision)
    assert release_decision.decision == "review_required"
    assert release_decision.reason_codes == ["initial_review"]

    attachment_count = len(
        (
            await db_session.execute(
                select(ReleasePacketAttachmentRecord).where(
                    ReleasePacketAttachmentRecord.release_decision_id == release_decision.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert attachment_count == 1


@pytest.mark.asyncio
async def test_assistant_dispatcher_attaches_packet_benchmarks_and_requests_model_review_without_auto_approval(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
    operator_user,
):
    await enable_simulation_lab(db_session, test_tenant.id)
    release_decision = await create_release_decision(
        db_session,
        tenant_id=test_tenant.id,
        user_id=operator_user.id,
        batch_public_id="BATCH-ASSISTANT-DISPATCH-001",
    )

    response = await client.post(
        "/api/v1/assistant/runs",
        json={
            "message": (
                f"create a moisture drift scenario, run 6 cycles, compare policies, export appendix, "
                f"attach release packet release_decision_id:{release_decision.id}, run benchmark, request model review"
            ),
            "mode": "simulation_lab",
        },
        headers=operator_headers,
    )

    assert response.status_code == 201
    assistant_run = response.json()
    assert assistant_run["status"] == "completed"
    result_ids = assistant_run["result_summary"]["result_ids"]
    assert result_ids["simulation_id"].startswith("SIM-")
    assert result_ids["run_id"].startswith("RUN-")
    assert result_ids["evidence_pack_id"].startswith("EVP-")
    assert result_ids["release_attachment_id"].startswith("RPA-")
    assert result_ids["benchmark_run_id"].startswith("BMR-")
    assert result_ids["model_approval_request_id"].startswith("HAR-")
    assert assistant_run["result_summary"]["safety"] == {
        "hardware_execution": False,
        "production_batch_mutation": False,
        "release_decision_auto_pass": False,
        "release_decision_impact": "unchanged",
        "human_review_required": True,
    }
    assert assistant_run["result_summary"]["human_review_requirement"]["required"] is True
    assert "model governance review completion" in assistant_run["result_summary"]["human_review_requirement"]["required_for"]
    assert "Release decision remains unchanged until human review." in assistant_run["result_summary"]["risk_value_drivers"]["risk_drivers"]
    assert any(
        action["requires_confirmation"] == "true"
        for action in assistant_run["result_summary"]["next_safe_actions"]
    )
    assert assistant_run["result_summary"]["confirmation_queue"]["status"] == "pending_human_confirmation"
    assert assistant_run["result_summary"]["confirmation_queue"]["guardrails"] == {
        "release_decision_auto_pass": False,
        "model_auto_activation": False,
        "external_share_auto_send": False,
    }
    assert set(assistant_run["result_summary"]["confirmation_queue"]["confirmation_ids"]) == {
        item["confirmation_id"] for item in assistant_run["confirmation_requests"]
    }
    confirmation_by_action = {item["action_name"]: item for item in assistant_run["confirmation_requests"]}
    assert set(confirmation_by_action) == {
        "release.request_human_approval",
        "external.share_release_packet",
        "model.complete_review",
    }
    assert all(item["status"] == "pending" for item in assistant_run["confirmation_requests"])
    assert confirmation_by_action["release.request_human_approval"]["action_payload"]["release_decision_impact"] == (
        "unchanged_until_separate_human_release_workflow"
    )
    assert confirmation_by_action["external.share_release_packet"]["action_payload"]["execution"] == (
        "forbidden_until_explicit_external_share_workflow"
    )
    assert confirmation_by_action["model.complete_review"]["action_payload"]["execution"] == "queue_only_no_model_activation"

    tool_names = [call["tool_name"] for call in assistant_run["tool_calls"]]
    assert "release.attach_simulation_appendix" in tool_names
    assert "benchmark.run_suite" in tool_names
    assert "model.register_candidate" in tool_names
    assert "model.request_governance_review" in tool_names
    assert all(call["status"] == "completed" for call in assistant_run["tool_calls"])
    governance_call = next(call for call in assistant_run["tool_calls"] if call["tool_name"] == "model.request_governance_review")
    assert governance_call["input_payload"]["decision"] == "request_review"
    assert "approved" not in json.dumps(governance_call, ensure_ascii=False).lower()

    await db_session.refresh(release_decision)
    assert release_decision.decision == "review_required"
    assert release_decision.reason_codes == ["initial_review"]

    attachment = await db_session.scalar(
        select(ReleasePacketAttachmentRecord).where(
            ReleasePacketAttachmentRecord.attachment_id == result_ids["release_attachment_id"]
        )
    )
    assert attachment is not None
    assert attachment.release_decision_id == release_decision.id
    assert attachment.simulation_id == result_ids["simulation_id"]

    approval_request = await db_session.scalar(
        select(HumanApprovalRequestRecord).where(
            HumanApprovalRequestRecord.approval_request_id == result_ids["model_approval_request_id"]
        )
    )
    assert approval_request is not None
    assert approval_request.status == "pending"
    assert approval_request.subject_type == "model_version"
    assert approval_request.payload["benchmark_run_id"] == result_ids["benchmark_run_id"]
    assert approval_request.payload["governance_decision"] == "request_review"

    model_confirmation = confirmation_by_action["model.complete_review"]
    confirm_response = await client.post(
        f"/api/v1/assistant/runs/{assistant_run['run_id']}/confirm",
        json={
            "confirmation_id": model_confirmation["confirmation_id"],
            "approved": True,
            "reason": "reviewed by human; queue item only",
        },
        headers=operator_headers,
    )
    assert confirm_response.status_code == 200
    confirmed_run = confirm_response.json()
    confirmed_item = next(
        item for item in confirmed_run["confirmation_requests"] if item["confirmation_id"] == model_confirmation["confirmation_id"]
    )
    assert confirmed_item["status"] == "approved"
    assert confirmed_item["reason"] == "reviewed by human; queue item only"

    await db_session.refresh(release_decision)
    await db_session.refresh(approval_request)
    assert release_decision.decision == "review_required"
    assert approval_request.status == "pending"

    persisted_confirmations = (
        await db_session.execute(
            select(AssistantConfirmationRequestRecord).where(
                AssistantConfirmationRequestRecord.assistant_run_id == (
                    await db_session.scalar(
                        select(AssistantRunRecord.id).where(AssistantRunRecord.run_id == assistant_run["run_id"])
                    )
                )
            )
        )
    ).scalars().all()
    assert len(persisted_confirmations) == 3


@pytest.mark.asyncio
async def test_assistant_review_workbench_lists_pending_queue_and_keeps_side_effects_gated(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
    operator_user,
):
    await enable_simulation_lab(db_session, test_tenant.id)
    release_decision = await create_release_decision(
        db_session,
        tenant_id=test_tenant.id,
        user_id=operator_user.id,
        batch_public_id="BATCH-ASSISTANT-WORKBENCH-001",
    )
    other_tenant, other_user, other_headers = await create_tenant_with_user(db_session)
    db_session.add(
        HumanApprovalRequestRecord(
            approval_request_id="HAR-OTHER-TENANT",
            release_decision_id=None,
            tenant_id=other_tenant.id,
            user_id=other_user.id,
            subject_type="model_version",
            subject_id="MV-OTHER",
            status="pending",
            reason="must not leak across tenant",
            payload={"evidence_pack_id": "EVP-OTHER"},
        )
    )
    await db_session.commit()
    assert await count_final_action_audit_records(db_session, test_tenant.id) == 0
    assert await count_final_action_request_drafts(db_session, test_tenant.id) == 0

    response = await client.post(
        "/api/v1/assistant/runs",
        json={
            "message": (
                f"create a moisture drift scenario, compare policies, export appendix, "
                f"attach release packet release_decision_id:{release_decision.id}, run benchmark, request model review"
            ),
            "mode": "simulation_lab",
        },
        headers=operator_headers,
    )
    assert response.status_code == 201
    assistant_run = response.json()
    result_ids = assistant_run["result_summary"]["result_ids"]

    workbench_response = await client.get("/api/v1/assistant/review-workbench", headers=operator_headers)
    assert workbench_response.status_code == 200
    workbench = workbench_response.json()
    assert "tenant_scoped_read_model" in workbench["guardrails"]
    assert "release_decision_remains_review_required" in workbench["guardrails"]
    assert {item["action_name"] for item in workbench["assistant_confirmations"]} == {
        "release.request_human_approval",
        "external.share_release_packet",
        "model.complete_review",
    }
    assert all(item["status"] == "pending" for item in workbench["assistant_confirmations"])
    assert {item["source_assistant_run_id"] for item in workbench["assistant_confirmations"]} == {
        assistant_run["run_id"]
    }
    assert any(
        "queue_only_no_auto_approval" in item["risk_guardrails"]
        for item in workbench["assistant_confirmations"]
        if item["action_name"] == "release.request_human_approval"
    )
    assert any(
        "queue_only_no_external_sharing" in item["risk_guardrails"]
        for item in workbench["assistant_confirmations"]
        if item["action_name"] == "external.share_release_packet"
    )
    assert any(
        "queue_only_no_model_activation" in item["risk_guardrails"]
        for item in workbench["assistant_confirmations"]
        if item["action_name"] == "model.complete_review"
    )

    approval_requests = workbench["human_approval_requests"]
    assert [item["approval_request_id"] for item in approval_requests] == [result_ids["model_approval_request_id"]]
    assert approval_requests[0]["subject_type"] == "model_version"
    assert approval_requests[0]["status"] == "pending"
    assert approval_requests[0]["source_assistant_run_id"] == assistant_run["run_id"]
    assert result_ids["benchmark_run_id"] in json.dumps(approval_requests[0]["payload"])
    assert "HAR-OTHER-TENANT" not in json.dumps(workbench)

    model_confirmation = next(
        item for item in workbench["assistant_confirmations"] if item["action_name"] == "model.complete_review"
    )
    confirm_response = await client.post(
        f"/api/v1/assistant/runs/{assistant_run['run_id']}/confirm",
        json={
            "confirmation_id": model_confirmation["confirmation_id"],
            "approved": False,
            "reason": "queue-only rejection for workbench test",
        },
        headers=operator_headers,
    )
    assert confirm_response.status_code == 200
    assert await count_final_action_audit_records(db_session, test_tenant.id) == 0
    assert await count_final_action_request_drafts(db_session, test_tenant.id) == 0

    after_response = await client.get("/api/v1/assistant/review-workbench", headers=operator_headers)
    assert after_response.status_code == 200
    after_workbench = after_response.json()
    assert "model.complete_review" not in {item["action_name"] for item in after_workbench["assistant_confirmations"]}
    assert [item["approval_request_id"] for item in after_workbench["human_approval_requests"]] == [
        result_ids["model_approval_request_id"]
    ]
    rejected_history_response = await client.get(
        "/api/v1/assistant/review-workbench?status=rejected",
        headers=operator_headers,
    )
    assert rejected_history_response.status_code == 200
    rejected_history = rejected_history_response.json()
    assert rejected_history["human_approval_requests"] == []
    rejected_confirmation = next(
        item for item in rejected_history["assistant_confirmations"] if item["action_name"] == "model.complete_review"
    )
    assert rejected_confirmation["confirmation_id"] == model_confirmation["confirmation_id"]
    assert rejected_confirmation["status"] == "rejected"
    assert rejected_confirmation["reason"] == "queue-only rejection for workbench test"
    assert rejected_confirmation["resolved_at"] is not None
    assert rejected_confirmation["source_assistant_run_id"] == assistant_run["run_id"]
    assert result_ids["evidence_pack_id"] in rejected_confirmation["evidence_pack_ids"]
    approval_request = await db_session.scalar(
        select(HumanApprovalRequestRecord).where(
            HumanApprovalRequestRecord.approval_request_id == result_ids["model_approval_request_id"]
        )
    )
    model_version = await db_session.scalar(
        select(ModelVersionRecord).where(
            ModelVersionRecord.model_version_id == approval_requests[0]["subject_id"]
        )
    )
    await db_session.refresh(release_decision)
    assert approval_request is not None
    assert approval_request.status == "pending"
    assert release_decision.decision == "review_required"
    assert model_version is not None
    assert model_version.status == "ready_for_review"

    resolve_response = await client.post(
        f"/api/v1/assistant/review-workbench/human-approval-requests/{result_ids['model_approval_request_id']}/resolve",
        json={
            "approved": True,
            "reason": "review request disposition only; no model activation",
        },
        headers=operator_headers,
    )
    assert resolve_response.status_code == 200
    assert await count_final_action_audit_records(db_session, test_tenant.id) == 0
    assert await count_final_action_request_drafts(db_session, test_tenant.id) == 0
    resolved_item = resolve_response.json()
    assert resolved_item["approval_request_id"] == result_ids["model_approval_request_id"]
    assert resolved_item["status"] == "approved"
    assert "resolved_review_request_only" in resolved_item["risk_guardrails"]
    assert resolved_item["payload"]["workbench_resolution"]["scope"] == "human_approval_request_only"
    assert resolved_item["payload"]["workbench_resolution"]["side_effects"] == {
        "release_decision": "unchanged",
        "model_activation": False,
        "external_share": False,
    }
    after_resolve_response = await client.get("/api/v1/assistant/review-workbench", headers=operator_headers)
    assert after_resolve_response.status_code == 200
    after_resolve_workbench = after_resolve_response.json()
    assert result_ids["model_approval_request_id"] not in {
        item["approval_request_id"] for item in after_resolve_workbench["human_approval_requests"]
    }
    approved_history_response = await client.get(
        "/api/v1/assistant/review-workbench?status=approved",
        headers=operator_headers,
    )
    assert approved_history_response.status_code == 200
    approved_history = approved_history_response.json()
    assert approved_history["assistant_confirmations"] == []
    approved_request = next(
        item
        for item in approved_history["human_approval_requests"]
        if item["approval_request_id"] == result_ids["model_approval_request_id"]
    )
    assert approved_request["status"] == "approved"
    assert approved_request["reason"] == "review request disposition only; no model activation"
    assert approved_request["resolved_at"] is not None
    assert approved_request["source_assistant_run_id"] == assistant_run["run_id"]
    assert approved_request["evidence_pack_ids"] == [approved_request["payload"]["evidence_pack_id"]]
    assert approved_request["payload"]["workbench_resolution"]["side_effects"] == {
        "release_decision": "unchanged",
        "model_activation": False,
        "external_share": False,
    }
    snapshot_response = await client.post(
        "/api/v1/assistant/review-workbench/audit-packet/snapshot",
        headers=operator_headers,
    )
    assert snapshot_response.status_code == 201
    assert await count_final_action_audit_records(db_session, test_tenant.id) == 0
    assert await count_final_action_request_drafts(db_session, test_tenant.id) == 0
    assert await count_final_action_review_packet_snapshots(db_session, test_tenant.id) == 1
    snapshot = snapshot_response.json()
    assert snapshot["schema_version"] == "final_action_review_packet_snapshot_v1"
    assert snapshot["review_only"] is True
    assert snapshot["source_review_packet_id"].startswith("FARP-")
    assert snapshot["packet_hash"]
    assert result_ids["evidence_pack_id"] in snapshot["evidence_pack_ids"]
    assert "immutable_packet_snapshot" in snapshot["guardrails"]
    assert "final_actions_not_executed" in snapshot["guardrails"]
    assert snapshot["packet_payload"]["source_review_packet_id"] == snapshot["source_review_packet_id"]
    snapshot_repeat_response = await client.post(
        "/api/v1/assistant/review-workbench/audit-packet/snapshot",
        headers=operator_headers,
    )
    assert snapshot_repeat_response.status_code == 201
    assert snapshot_repeat_response.json()["source_review_packet_id"] == snapshot["source_review_packet_id"]
    assert snapshot_repeat_response.json()["packet_hash"] == snapshot["packet_hash"]
    assert await count_final_action_review_packet_snapshots(db_session, test_tenant.id) == 1

    audit_packet_response = await client.get(
        "/api/v1/assistant/review-workbench/audit-packet?format=json",
        headers=operator_headers,
    )
    assert audit_packet_response.status_code == 200
    assert await count_final_action_audit_records(db_session, test_tenant.id) == 0
    assert await count_final_action_request_drafts(db_session, test_tenant.id) == 0
    assert await count_final_action_review_packet_snapshots(db_session, test_tenant.id) == 1
    audit_packet = audit_packet_response.json()
    assert audit_packet["packet_type"] == "assistant_review_workbench_audit_packet"
    assert audit_packet["source_review_packet_id"] == snapshot["source_review_packet_id"]
    assert audit_packet["packet_hash"] == snapshot["packet_hash"]
    assert audit_packet["review_only"] is True
    assert audit_packet["summary"]["pending_queue_count"] == 2
    assert audit_packet["summary"]["resolved_approval_count"] == 1
    assert audit_packet["summary"]["resolved_rejection_count"] == 1
    assert audit_packet["summary"]["final_actions"] == "not_executed"
    assert audit_packet["final_actions"] == {
        "release_approval": "not_executed",
        "model_activation": "not_executed",
        "external_share": "not_executed",
    }
    assert "review_only_export" in audit_packet["guardrails"]
    assert "release_decision_remains_review_required" in audit_packet["guardrails"]
    assert result_ids["model_approval_request_id"] in json.dumps(audit_packet)
    assert result_ids["evidence_pack_id"] in audit_packet["evidence_pack_ids"]
    assert result_ids["model_approval_request_id"] not in {
        item["approval_request_id"]
        for item in audit_packet["statuses"]["pending"]["human_approval_requests"]
    }
    assert "HAR-OTHER-TENANT" not in json.dumps(audit_packet)
    persisted_review_packet = await db_session.scalar(
        select(FinalActionReviewPacketSnapshot).where(
            FinalActionReviewPacketSnapshot.source_review_packet_id == audit_packet["source_review_packet_id"]
        )
    )
    assert persisted_review_packet is not None
    assert persisted_review_packet.tenant_id == test_tenant.id
    assert persisted_review_packet.packet_hash == audit_packet["packet_hash"]
    assert persisted_review_packet.packet_payload["source_review_packet_id"] == audit_packet["source_review_packet_id"]
    assert result_ids["evidence_pack_id"] in persisted_review_packet.evidence_pack_ids

    audit_packet_reexport_response = await client.get(
        "/api/v1/assistant/review-workbench/audit-packet?format=json",
        headers=operator_headers,
    )
    assert audit_packet_reexport_response.status_code == 200
    audit_packet_reexport = audit_packet_reexport_response.json()
    assert audit_packet_reexport["source_review_packet_id"] == audit_packet["source_review_packet_id"]
    assert audit_packet_reexport["packet_hash"] == audit_packet["packet_hash"]
    assert await count_final_action_review_packet_snapshots(db_session, test_tenant.id) == 1

    source_packet_response = await client.get(
        f"/api/v1/final-actions/source-review-packets/{audit_packet['source_review_packet_id']}",
        headers=operator_headers,
    )
    assert source_packet_response.status_code == 200
    source_packet = source_packet_response.json()
    assert source_packet["schema_version"] == "final_action_review_packet_snapshot_v1"
    assert source_packet["review_only"] is True
    assert source_packet["source_review_packet_id"] == audit_packet["source_review_packet_id"]
    assert source_packet["packet_hash"] == audit_packet["packet_hash"]
    assert source_packet["packet_payload"]["final_actions"] == audit_packet["final_actions"]
    assert result_ids["evidence_pack_id"] in source_packet["evidence_pack_ids"]
    assert {
        "read_only_source_review_packet",
        "immutable_packet_snapshot",
        "tenant_scoped_read_model",
        "final_actions_not_executed",
        "no_release_decision_mutation",
        "no_model_activation",
        "no_external_share_record",
    }.issubset(set(source_packet["guardrails"]))

    latest_source_packet_response = await client.get(
        "/api/v1/final-actions/source-review-packets/latest",
        headers=operator_headers,
    )
    assert latest_source_packet_response.status_code == 200
    latest_source_packet = latest_source_packet_response.json()
    assert latest_source_packet["source_review_packet_id"] == audit_packet["source_review_packet_id"]
    assert latest_source_packet["packet_hash"] == audit_packet["packet_hash"]

    audit_markdown_response = await client.get(
        "/api/v1/assistant/review-workbench/audit-packet?format=md",
        headers=operator_headers,
    )
    assert audit_markdown_response.status_code == 200
    audit_markdown = audit_markdown_response.text
    assert "# BOS Assistant Review Workbench Audit Packet" in audit_markdown
    assert f"Source review packet ID: {audit_packet['source_review_packet_id']}" in audit_markdown
    assert "Release approval: not_executed" in audit_markdown
    assert "Model activation: not_executed" in audit_markdown
    assert "External share: not_executed" in audit_markdown
    assert result_ids["model_approval_request_id"] in audit_markdown
    assert result_ids["evidence_pack_id"] in audit_markdown
    assert "HAR-OTHER-TENANT" not in audit_markdown

    readiness_response = await client.get("/api/v1/final-actions/readiness", headers=operator_headers)
    assert readiness_response.status_code == 200
    readiness = readiness_response.json()
    assert readiness["schema_version"] == "final_action_readiness_v1"
    assert readiness["tenant_id"] == test_tenant.id
    assert readiness["review_only"] is True
    assert readiness["audit_schema_available"] is True
    assert readiness["request_draft_schema_available"] is True
    assert readiness["source_review_packet_id"] == audit_packet["source_review_packet_id"]
    assert readiness["current_state"]["latest_release_decision_id"] == release_decision.id
    assert readiness["current_state"]["latest_release_decision"] == "review_required"
    assert readiness["current_state"]["latest_model_version_status"] == "ready_for_review"
    assert readiness["current_state"]["pending_review_items"] == 2
    assert readiness["current_state"]["resolved_review_items"] == 2
    assert readiness["current_state"]["external_share_record_created"] is False
    assert readiness["current_state"]["final_action_request_drafts_created"] is False
    assert result_ids["evidence_pack_id"] in readiness["current_state"]["evidence_pack_ids"]
    assert {
        "readiness_only",
        "readiness_query_does_not_execute_final_actions",
        "no_assistant_confirmation_authority",
        "no_human_approval_disposition_authority",
        "tenant_scoped_read_model",
        "final_action_routes_require_approved_request_draft",
        "external_network_send_requires_separate_gate",
        "no_hardware_execution",
    }.issubset(set(readiness["guardrails"]))
    actions_by_name = {item["action"]: item for item in readiness["actions"]}
    assert set(actions_by_name) == {
        "final_release_approval",
        "model_activation",
        "external_release_share",
    }
    for action in actions_by_name.values():
        assert action["executable"] is False
        assert action["source_review_packet_required"] is True
        assert action["source_review_packet_id"] == audit_packet["source_review_packet_id"]
        assert action["side_effects_if_executed"] == {
            "release_decision": "not_executed",
            "model_activation": False,
            "external_share": False,
            "hardware_execution": False,
        }
        assert "request_draft_required" in action["blockers"]
        assert "approved_request_draft_required" in action["blockers"]
        assert "specific_final_action_approver_role_required" in action["blockers"]
        assert "immutable_source_review_packet_not_persisted" not in action["blockers"]
    assert "release_packet_attachment_required" in actions_by_name["external_release_share"]["blockers"]
    assert "allowlisted_recipient_scope_required" in actions_by_name["external_release_share"]["blockers"]
    assert "redaction_policy_attestation_required" in actions_by_name["external_release_share"]["blockers"]
    assert await count_final_action_audit_records(db_session, test_tenant.id) == 0
    assert await count_final_action_request_drafts(db_session, test_tenant.id) == 0

    audit_records_response = await client.get("/api/v1/final-actions/audit-records", headers=operator_headers)
    assert audit_records_response.status_code == 200
    audit_records = audit_records_response.json()
    assert audit_records["schema_version"] == "final_action_audit_records_read_model_v1"
    assert audit_records["tenant_id"] == test_tenant.id
    assert audit_records["review_only"] is True
    assert audit_records["count"] == 0
    assert audit_records["records"] == []
    assert {
        "read_only_final_action_audit_records",
        "final_actions_not_executed",
        "tenant_scoped_read_model",
        "no_release_decision_mutation",
        "no_model_activation",
        "no_external_share_record",
    }.issubset(set(audit_records["guardrails"]))

    missing_audit_record_response = await client.get(
        "/api/v1/final-actions/audit-records/FA-NOT-CREATED",
        headers=operator_headers,
    )
    assert missing_audit_record_response.status_code == 404

    request_drafts_response = await client.get("/api/v1/final-actions/request-drafts", headers=operator_headers)
    assert request_drafts_response.status_code == 200
    request_drafts = request_drafts_response.json()
    assert request_drafts["schema_version"] == "final_action_request_drafts_read_model_v1"
    assert request_drafts["tenant_id"] == test_tenant.id
    assert request_drafts["review_only"] is True
    assert request_drafts["count"] == 0
    assert request_drafts["drafts"] == []
    assert {
        "read_only_final_action_request_drafts",
        "final_action_drafts_not_created_by_assistant",
        "tenant_scoped_read_model",
        "no_release_decision_mutation",
        "no_model_activation",
        "no_external_share_record",
    }.issubset(set(request_drafts["guardrails"]))

    missing_request_draft_response = await client.get(
        "/api/v1/final-actions/request-drafts/FARD-NOT-CREATED",
        headers=operator_headers,
    )
    assert missing_request_draft_response.status_code == 404

    post_readiness_response = await client.post("/api/v1/final-actions/readiness", headers=operator_headers)
    assert post_readiness_response.status_code == 405
    post_audit_records_response = await client.post("/api/v1/final-actions/audit-records", headers=operator_headers)
    assert post_audit_records_response.status_code == 405
    post_request_drafts_response = await client.post("/api/v1/final-actions/request-drafts", headers=operator_headers)
    assert post_request_drafts_response.status_code == 422
    assert await count_final_action_request_drafts(db_session, test_tenant.id) == 0
    post_source_packet_response = await client.post(
        "/api/v1/final-actions/source-review-packets/latest",
        headers=operator_headers,
    )
    assert post_source_packet_response.status_code == 405
    release_approval_route_response = await client.post(
        "/api/v1/final-actions/release-approvals",
        json={},
        headers=operator_headers,
    )
    assert release_approval_route_response.status_code == 403
    assert await count_final_action_audit_records(db_session, test_tenant.id) == 0
    model_activation_route_response = await client.post(
        "/api/v1/final-actions/model-activations",
        json={},
        headers=operator_headers,
    )
    assert model_activation_route_response.status_code == 403
    external_share_route_response = await client.post(
        "/api/v1/final-actions/external-release-shares",
        json={},
        headers=operator_headers,
    )
    assert external_share_route_response.status_code == 403
    assert await count_external_release_share_records(db_session, test_tenant.id) == 0

    approval_request = await db_session.scalar(
        select(HumanApprovalRequestRecord).where(
            HumanApprovalRequestRecord.approval_request_id == result_ids["model_approval_request_id"]
        )
    )
    model_version = await db_session.scalar(
        select(ModelVersionRecord).where(
            ModelVersionRecord.model_version_id == approval_requests[0]["subject_id"]
        )
    )
    await db_session.refresh(release_decision)
    assert approval_request is not None
    assert approval_request.status == "approved"
    assert release_decision.decision == "review_required"
    assert model_version is not None
    assert model_version.status == "ready_for_review"
    assert await count_final_action_request_drafts(db_session, test_tenant.id) == 0

    cross_tenant_resolve = await client.post(
        f"/api/v1/assistant/review-workbench/human-approval-requests/{result_ids['model_approval_request_id']}/resolve",
        json={"approved": False, "reason": "cross tenant must not resolve"},
        headers=other_headers,
    )
    assert cross_tenant_resolve.status_code == 404

    other_workbench_response = await client.get("/api/v1/assistant/review-workbench", headers=other_headers)
    assert other_workbench_response.status_code == 200
    other_workbench = other_workbench_response.json()
    assert other_workbench["assistant_confirmations"] == []
    assert [item["approval_request_id"] for item in other_workbench["human_approval_requests"]] == [
        "HAR-OTHER-TENANT"
    ]
    other_approved_history_response = await client.get(
        "/api/v1/assistant/review-workbench?status=approved",
        headers=other_headers,
    )
    assert other_approved_history_response.status_code == 200
    assert "HAR-OTHER-TENANT" not in json.dumps(other_approved_history_response.json())

    other_audit_packet_response = await client.get(
        "/api/v1/assistant/review-workbench/audit-packet?format=json",
        headers=other_headers,
    )
    assert other_audit_packet_response.status_code == 200
    other_audit_packet = other_audit_packet_response.json()
    assert "HAR-OTHER-TENANT" in json.dumps(other_audit_packet)
    assert result_ids["model_approval_request_id"] not in json.dumps(other_audit_packet)
    cross_tenant_source_packet_response = await client.get(
        f"/api/v1/final-actions/source-review-packets/{audit_packet['source_review_packet_id']}",
        headers=other_headers,
    )
    assert cross_tenant_source_packet_response.status_code == 404
    other_latest_source_packet_response = await client.get(
        "/api/v1/final-actions/source-review-packets/latest",
        headers=other_headers,
    )
    assert other_latest_source_packet_response.status_code == 200
    assert other_latest_source_packet_response.json()["source_review_packet_id"] != audit_packet["source_review_packet_id"]

    other_readiness_response = await client.get("/api/v1/final-actions/readiness", headers=other_headers)
    assert other_readiness_response.status_code == 200
    other_readiness = other_readiness_response.json()
    assert other_readiness["tenant_id"] == other_tenant.id
    assert other_readiness["current_state"]["latest_release_decision_id"] is None
    assert other_readiness["current_state"]["latest_model_version_id"] is None
    assert other_readiness["current_state"]["pending_review_items"] == 1
    assert other_readiness["current_state"]["final_action_request_drafts_created"] is False
    assert "HAR-OTHER-TENANT" not in json.dumps(readiness)
    assert result_ids["model_approval_request_id"] not in json.dumps(other_readiness)
    other_audit_records_response = await client.get("/api/v1/final-actions/audit-records", headers=other_headers)
    assert other_audit_records_response.status_code == 200
    other_audit_records = other_audit_records_response.json()
    assert other_audit_records["tenant_id"] == other_tenant.id
    assert other_audit_records["count"] == 0
    assert other_audit_records["records"] == []
    other_request_drafts_response = await client.get("/api/v1/final-actions/request-drafts", headers=other_headers)
    assert other_request_drafts_response.status_code == 200
    other_request_drafts = other_request_drafts_response.json()
    assert other_request_drafts["tenant_id"] == other_tenant.id
    assert other_request_drafts["count"] == 0
    assert other_request_drafts["drafts"] == []
    assert await count_final_action_request_drafts(db_session, other_tenant.id) == 0


@pytest.mark.asyncio
async def test_release_governance_envelope_endpoint_stays_review_locked(
    client: AsyncClient,
    operator_headers,
):
    response = await client.get(
        "/api/v1/governance/release-envelope"
        "?evidence_chain_id=CHAIN-GOV-LOCK-001&source_boundary=integration_test_surface",
        headers=operator_headers,
    )

    assert response.status_code == 200
    envelope = response.json()
    assert envelope["schema_version"] == "release_governance_envelope_v1"
    assert envelope["evidence_chain_id"] == "CHAIN-GOV-LOCK-001"
    assert envelope["source_boundary"] == "integration_test_surface"
    assert envelope["review_required_reason"] == "operator_requested_release_surface_requires_human_review"
    assert_release_governance_envelope_locked(envelope)


@pytest.mark.asyncio
async def test_rc_manifest_endpoint_is_read_only_and_keeps_candidate_state_separate(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
    tmp_path,
    monkeypatch,
):
    manifest_path = tmp_path / "BOS_V9_RC_MANIFEST.json"
    manifest_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-04-28T10:33:40Z",
                "release_state": "review_required",
                "candidate_evidence_state": "ready_for_review",
                "preflight_pass_count": 21,
                "preflight_warn_count": 0,
                "preflight_fail_count": 0,
                "review_required_items": [],
                "local_validation_notes": [],
                "recommended_next_action": "Move this candidate to human approval required review and circulate the dossier.",
                "bos_v9_target_progress_percent": 91,
                "bos_v9_target_scorecard": [
                    {
                        "dimension": "reproducible_p0_baseline",
                        "score": 9,
                        "target": 9,
                        "evidence": "P0 has zero failures and zero warnings with the default stack online.",
                    }
                ],
                "safety_boundary": {
                    "release_decision": "review_required",
                    "model_version": "ready_for_review",
                    "final_action_draft_count": 0,
                    "final_action_audit_record_count": 0,
                    "external_share_record_created": False,
                    "final_action_execute_call_count": 0,
                    "validated_default_write_enabled": False,
                    "runtime_activation_enabled": False,
                    "hardware_execution_enabled": False,
                    "final_action_execution_enabled": False,
                },
                "release_reference_smoke_passed": True,
                "checks": [
                    {"status": "ready_for_review", "raw_status": "PASS", "name": "backend integration", "summary": "completed"}
                ],
                "artifacts": {
                    "bos_v9_rc_manifest": "reports/stabilize-v9/BOS_V9_RC_MANIFEST.json",
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(governance_router, "RC_MANIFEST_PATH", manifest_path)
    audit_count_before = await count_final_action_audit_records(db_session, test_tenant.id)
    draft_count_before = await count_final_action_request_drafts(db_session, test_tenant.id)

    response = await client.get("/api/v1/governance/rc-manifest", headers=operator_headers)

    assert response.status_code == 200
    manifest = response.json()
    assert manifest["candidate_evidence_state"] == "ready_for_review"
    assert manifest["release_state"] == "review_required"
    assert manifest["safety_boundary"]["release_decision"] == "review_required"
    assert manifest["safety_boundary"]["final_action_execute_call_count"] == 0
    assert "approved" not in json.dumps(
        {
            "release_state": manifest["release_state"],
            "candidate_evidence_state": manifest["candidate_evidence_state"],
            "safety_boundary": manifest["safety_boundary"],
        },
        sort_keys=True,
    )
    assert await count_final_action_audit_records(db_session, test_tenant.id) == audit_count_before
    assert await count_final_action_request_drafts(db_session, test_tenant.id) == draft_count_before


@pytest.mark.asyncio
async def test_final_action_readiness_does_not_treat_unactivated_reviewed_metadata_as_release_evidence(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
    operator_user,
):
    release_decision = await create_release_decision(
        db_session,
        tenant_id=test_tenant.id,
        user_id=operator_user.id,
        batch_public_id="BATCH-P4A-METADATA-GUARD-001",
    )
    external_ids = await create_reviewed_external_metadata_candidate(
        db_session,
        tenant_id=test_tenant.id,
    )

    response = await client.get("/api/v1/final-actions/readiness", headers=operator_headers)

    assert response.status_code == 200
    readiness = response.json()
    readiness_blob = json.dumps(readiness)
    assert readiness["tenant_id"] == test_tenant.id
    assert readiness["review_only"] is True
    assert readiness["current_state"]["latest_release_decision_id"] == release_decision.id
    assert readiness["current_state"]["latest_release_decision"] == "review_required"
    assert readiness["current_state"]["evidence_pack_ids"] == []
    assert readiness["current_state"]["external_share_record_created"] is False
    assert readiness["current_state"]["final_action_request_drafts_created"] is False
    assert readiness["governance_envelope"]["source_boundary"] == "final_action_readiness_read_model"
    assert (
        readiness["governance_envelope"]["review_required_reason"]
        == "final_actions_require_immutable_source_packet_and_human_review"
    )
    assert_release_governance_envelope_locked(readiness["governance_envelope"])

    for external_id in external_ids.values():
        assert external_id not in readiness_blob

    actions_by_name = {item["action"]: item for item in readiness["actions"]}
    assert set(actions_by_name) == {
        "final_release_approval",
        "model_activation",
        "external_release_share",
    }
    for action in actions_by_name.values():
        assert action["executable"] is False
        assert action["required_evidence_ids"] == []
        assert "immutable_source_review_packet_not_persisted" in action["blockers"]
    assert actions_by_name["final_release_approval"]["missing_evidence_ids"] == [
        "review_workbench_evidence_pack"
    ]
    assert await count_final_action_audit_records(db_session, test_tenant.id) == 0
    assert await count_final_action_request_drafts(db_session, test_tenant.id) == 0
    assert await count_external_release_share_records(db_session, test_tenant.id) == 0

    candidate = await db_session.scalar(
        select(ReviewedExternalCandidateRecord).where(
            ReviewedExternalCandidateRecord.tenant_id == test_tenant.id,
            ReviewedExternalCandidateRecord.candidate_id == external_ids["candidate_id"],
        )
    )
    assert candidate is not None
    assert candidate.runtime_activated is False
    assert candidate.validated_default_write_enabled is False
    assert candidate.promotion_enabled is False
    assert candidate.candidate_payload["numeric_values_included"] is False
    await db_session.refresh(release_decision)
    assert release_decision.decision == "review_required"


@pytest.mark.asyncio
async def test_release_appendix_attachment_enforces_role_and_tenant_isolation(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
    operator_user,
):
    await enable_simulation_lab(db_session, test_tenant.id)
    simulation_id, run_id = await create_simulation_run(client, operator_headers)
    release_decision = await create_release_decision(
        db_session,
        tenant_id=test_tenant.id,
        user_id=operator_user.id,
        batch_public_id="BATCH-RELEASE-ISOLATION-001",
    )
    viewer = await create_user_for_tenant(db_session, tenant_id=test_tenant.id, role="viewer")
    viewer_headers = _auth_headers_for(viewer)
    _other_tenant, _other_user, other_headers = await create_tenant_with_user(db_session)

    viewer_response = await client.post(
        f"/api/v1/release-packets/{release_decision.id}/appendices/simulation",
        json={"simulation_id": simulation_id, "run_id": run_id},
        headers=viewer_headers,
    )
    assert viewer_response.status_code == 403

    cross_tenant_attach = await client.post(
        f"/api/v1/release-packets/{release_decision.id}/appendices/simulation",
        json={"simulation_id": simulation_id, "run_id": run_id},
        headers=other_headers,
    )
    assert cross_tenant_attach.status_code == 404

    cross_tenant_list = await client.get(
        f"/api/v1/release-packets/{release_decision.id}/appendices",
        headers=other_headers,
    )
    assert cross_tenant_list.status_code == 404

    attachment_count = (
        await db_session.execute(
            select(func.count())
            .select_from(ReleasePacketAttachmentRecord)
            .where(ReleasePacketAttachmentRecord.release_decision_id == release_decision.id)
        )
    ).scalar_one()
    assert attachment_count == 0


@pytest.mark.asyncio
async def test_release_approval_request_enforces_role_tenant_and_decision_immutability(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
    operator_user,
):
    release_decision = await create_release_decision(
        db_session,
        tenant_id=test_tenant.id,
        user_id=operator_user.id,
        batch_public_id="BATCH-APPROVAL-001",
    )
    viewer = await create_user_for_tenant(db_session, tenant_id=test_tenant.id, role="viewer")
    viewer_headers = _auth_headers_for(viewer)
    _other_tenant, _other_user, other_headers = await create_tenant_with_user(db_session)

    viewer_response = await client.post(
        f"/api/v1/release-packets/{release_decision.id}/approval-requests",
        json={"reason": "review simulation appendix"},
        headers=viewer_headers,
    )
    assert viewer_response.status_code == 403

    cross_tenant_response = await client.post(
        f"/api/v1/release-packets/{release_decision.id}/approval-requests",
        json={"reason": "cross tenant should not see release decision"},
        headers=other_headers,
    )
    assert cross_tenant_response.status_code == 404

    response = await client.post(
        f"/api/v1/release-packets/{release_decision.id}/approval-requests",
        json={"reason": "operator requests release review", "payload": {"source": "pytest"}},
        headers=operator_headers,
    )
    assert response.status_code == 201
    approval = response.json()
    assert approval["status"] == "pending"
    assert approval["release_decision_id"] == release_decision.id

    await db_session.refresh(release_decision)
    assert release_decision.decision == "review_required"
    assert release_decision.reason_codes == ["initial_review"]

    approval_count = (
        await db_session.execute(
            select(func.count())
            .select_from(HumanApprovalRequestRecord)
            .where(HumanApprovalRequestRecord.release_decision_id == release_decision.id)
        )
    ).scalar_one()
    assert approval_count == 1


@pytest.mark.asyncio
async def test_input_snapshot_is_fetchable_and_tenant_isolated(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
):
    await enable_simulation_lab(db_session, test_tenant.id)
    _other_tenant, _other_user, other_headers = await create_tenant_with_user(db_session)
    simulation_id, _run_id = await create_simulation_run(client, operator_headers)

    runs_response = await client.get(
        f"/api/v1/bos/simulation-lab/scenarios/{simulation_id}/runs",
        headers=operator_headers,
    )
    assert runs_response.status_code == 200
    run_history = runs_response.json()[0]
    input_snapshot_id = run_history["input_snapshot_id"]
    assert input_snapshot_id

    snapshot_response = await client.get(
        f"/api/v1/input-snapshots/{input_snapshot_id}",
        headers=operator_headers,
    )
    assert snapshot_response.status_code == 200
    snapshot = snapshot_response.json()
    assert snapshot["payload_hash"] == run_history["input_snapshot_hash"]
    assert snapshot["subject_id"] == simulation_id

    cross_tenant_response = await client.get(
        f"/api/v1/input-snapshots/{input_snapshot_id}",
        headers=other_headers,
    )
    assert cross_tenant_response.status_code == 404


@pytest.mark.asyncio
async def test_replay_and_diff_are_tenant_isolated(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
):
    await enable_simulation_lab(db_session, test_tenant.id)
    other_tenant, _other_user, other_headers = await create_tenant_with_user(db_session)
    await enable_simulation_lab(db_session, other_tenant.id)
    _simulation_id, run_id = await create_simulation_run(client, operator_headers)

    replay_response = await client.post(
        f"/api/v1/bos/simulation-lab/runs/{run_id}/replay",
        headers=operator_headers,
    )
    assert replay_response.status_code == 200
    replay_run_id = replay_response.json()["replay_run"]["run_id"]

    cross_tenant_replay = await client.post(
        f"/api/v1/bos/simulation-lab/runs/{run_id}/replay",
        headers=other_headers,
    )
    assert cross_tenant_replay.status_code == 404

    cross_tenant_diff = await client.get(
        f"/api/v1/bos/simulation-lab/runs/{run_id}/diff",
        params={"against_run_id": replay_run_id},
        headers=other_headers,
    )
    assert cross_tenant_diff.status_code == 404


@pytest.mark.asyncio
async def test_lca_compare_and_tea_estimate_smoke(client: AsyncClient, scientist_headers):
    invalid_lca_response = await client.post(
        "/api/v1/lca/compare",
        json={
            "system_boundary": {"scope": "gate_to_gate"},
            "baseline_scenario": {"kind": "landfill"},
            "alternative_scenario": {"kind": "bsf_route"},
        },
        headers=scientist_headers,
    )
    assert invalid_lca_response.status_code == 422

    invalid_lca_baseline_response = await client.post(
        "/api/v1/lca/compare",
        json={
            "functional_unit": "tonne_substrate",
            "system_boundary": {"scope": "gate_to_gate"},
            "alternative_scenario": {"kind": "bsf_route"},
        },
        headers=scientist_headers,
    )
    assert invalid_lca_baseline_response.status_code == 422

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
    assert lca["result_type"] == "lca"
    assert lca["evidence_pack_id"]
    assert lca["result"]["co2e_abatement_kg"] > 0
    assert "emission_factor.electricity_kgco2e_per_kwh defaulted" in lca["uncertainty_warnings"]

    invalid_tea_response = await client.post(
        "/api/v1/tea/estimate",
        json={
            "functional_unit": "kg_biomass",
            "system_boundary": {"scope": "pilot"},
            "alternative_scenario": {"kind": "bsf_route"},
        },
        headers=scientist_headers,
    )
    assert invalid_tea_response.status_code == 422

    tea_response = await client.post(
        "/api/v1/tea/estimate",
        json={
            "functional_unit": "kg_biomass",
            "system_boundary": {"scope": "pilot"},
            "baseline_scenario": {"kind": "composting"},
            "alternative_scenario": {"kind": "bsf_route"},
            "activity_data": {"biomass_kg": 50.0, "energy_kwh": 20.0, "labor_hours": 1.0},
            "cost_factors": {},
        },
        headers=scientist_headers,
    )
    assert tea_response.status_code == 200
    tea = tea_response.json()
    assert tea["result_type"] == "tea"
    assert tea["evidence_pack_id"]
    assert "gross_margin_usd" in tea["result"]
    assert "cost_factor.energy_usd_per_kwh defaulted" in tea["uncertainty_warnings"]

    lookup_response = await client.get(
        f"/api/v1/sustainability/results/{tea['result_id']}",
        headers=scientist_headers,
    )
    assert lookup_response.status_code == 200
    assert lookup_response.json()["result_id"] == tea["result_id"]


@pytest.mark.asyncio
async def test_compliance_missing_assays_blocks_release_gate(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
    operator_user,
):
    batch = Batch(
        batch_id="BATCH-COMPLIANCE-001",
        species="BSF",
        dm_in=12.0,
        dm_out=8.0,
        user_id=operator_user.id,
        tenant_id=test_tenant.id,
    )
    db_session.add(batch)
    await db_session.commit()
    await db_session.refresh(batch)

    response = await client.post(
        "/api/v1/compliance/evaluate",
        json={"batch_id": batch.id, "jurisdiction": "CN", "product_category": "insect_dry_matter"},
        headers=operator_headers,
    )

    assert response.status_code == 201
    gate = response.json()
    assert gate["status"] == "blocked"
    assert set(gate["missing_assays"]) == {"moisture", "protein", "heavy_metals", "microbiology"}
    assert all(reason.startswith("missing_assay:") for reason in gate["blocked_reasons"])
    assert gate["human_review_required"] is True
    assert gate["evidence_pack_id"]

    gates_response = await client.get(
        f"/api/v1/batches/{batch.id}/release-gates",
        headers=operator_headers,
    )
    assert gates_response.status_code == 200
    assert gates_response.json()[0]["gate_id"] == gate["gate_id"]


@pytest.mark.asyncio
async def test_compliance_threshold_breach_blocks_without_saying_compliant(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
    operator_user,
):
    batch = Batch(
        batch_id="BATCH-COMPLIANCE-THRESHOLD-001",
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
        "moisture": 15.0,
        "protein": 42.0,
        "heavy_metals": 0.2,
        "microbiology": 0.0,
    }.items():
        assay_response = await client.post(
            f"/api/v1/batches/{batch.id}/assays",
            json={"assay_type": assay_type, "value": value},
            headers=operator_headers,
        )
        assert assay_response.status_code == 201

    response = await client.post(
        "/api/v1/compliance/evaluate",
        json={"batch_id": batch.id, "jurisdiction": "CN", "product_category": "insect_dry_matter"},
        headers=operator_headers,
    )

    assert response.status_code == 201
    gate = response.json()
    assert gate["status"] == "blocked"
    assert gate["missing_assays"] == []
    assert "threshold_breach:moisture" in gate["blocked_reasons"]
    assert gate["human_review_required"] is True
    assert gate["evidence_pack_id"]
    assert gate["status"] != "compliant"


@pytest.mark.asyncio
async def test_compliance_ambiguous_category_requires_human_review(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
    operator_user,
):
    batch = Batch(
        batch_id="BATCH-COMPLIANCE-AMBIGUOUS-001",
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
        "moisture": 25.0,
        "pathogens": 0.0,
        "heavy_metals": 0.2,
    }.items():
        assay_response = await client.post(
            f"/api/v1/batches/{batch.id}/assays",
            json={"assay_type": assay_type, "value": value},
            headers=operator_headers,
        )
        assert assay_response.status_code == 201

    response = await client.post(
        "/api/v1/compliance/evaluate",
        json={"batch_id": batch.id, "jurisdiction": "CN", "product_category": "residue_handling"},
        headers=operator_headers,
    )

    assert response.status_code == 201
    gate = response.json()
    assert gate["status"] == "insufficient_evidence"
    assert gate["missing_assays"] == []
    assert gate["blocked_reasons"] == []
    assert gate["human_review_required"] is True
    assert gate["status"] != "compliant"


@pytest.mark.asyncio
async def test_historical_replay_creates_immutable_snapshot_evidence_and_is_tenant_isolated(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
    test_tenant,
    operator_user,
):
    batch = Batch(
        batch_id="BATCH-HISTORICAL-REPLAY-001",
        species="BSF",
        substrate="mixed_food_waste",
        dm_in=14.0,
        dm_out=9.0,
        status="logged",
        user_id=operator_user.id,
        tenant_id=test_tenant.id,
    )
    db_session.add(batch)
    await db_session.commit()
    await db_session.refresh(batch)
    _other_tenant, _other_user, other_headers = await create_tenant_with_user(db_session)

    response = await client.post(
        f"/api/v1/replay/batches/{batch.id}",
        json={"counterfactual_actions": [{"cycle": 2, "action": "reduce_moisture"}]},
        headers=operator_headers,
    )

    assert response.status_code == 201
    replay = response.json()
    assert replay["replay_id"].startswith("HRP-")
    assert replay["immutable_snapshot"]["batch_id"] == "BATCH-HISTORICAL-REPLAY-001"
    assert replay["immutable_snapshot"]["dm_in"] == 14.0
    assert replay["outcome"]["original_batch_mutated"] is False
    assert replay["evidence_pack_id"]

    await db_session.refresh(batch)
    assert batch.status == "logged"
    assert batch.dm_in == 14.0

    evidence_response = await client.get(
        f"/api/v1/evidence-packs/{replay['evidence_pack_id']}",
        headers=operator_headers,
    )
    assert evidence_response.status_code == 200
    evidence_pack = evidence_response.json()
    assert evidence_pack["subject_type"] == "historical_replay"
    assert {item["kind"] for item in evidence_pack["items"]} == {"historical_replay_snapshot"}

    lookup_response = await client.get(
        f"/api/v1/replay/runs/{replay['replay_id']}",
        headers=operator_headers,
    )
    assert lookup_response.status_code == 200
    assert lookup_response.json()["evidence_pack_id"] == replay["evidence_pack_id"]

    cross_tenant_response = await client.get(
        f"/api/v1/replay/runs/{replay['replay_id']}",
        headers=other_headers,
    )
    assert cross_tenant_response.status_code == 404


@pytest.mark.asyncio
async def test_benchmark_model_governance_and_knowledge_relation_close_v35_loop(
    client: AsyncClient,
    operator_headers,
    db_session: AsyncSession,
):
    _other_tenant, _other_user, other_headers = await create_tenant_with_user(db_session)
    cases_response = await client.get("/api/v1/benchmarks/cases", headers=operator_headers)
    assert cases_response.status_code == 200
    cases = cases_response.json()
    assert {case["case_id"] for case in cases} >= {
        "CASE-moisture_drift",
        "CASE-temperature_spike",
        "CASE-underfeeding",
        "CASE-sensor_missingness",
    }

    benchmark_response = await client.post(
        "/api/v1/benchmarks/runs",
        json={"suite_name": "simulation_lab_regression"},
        headers=operator_headers,
    )
    assert benchmark_response.status_code == 201
    benchmark = benchmark_response.json()
    assert benchmark["benchmark_run_id"].startswith("BMR-")
    assert benchmark["evidence_pack_id"]
    assert benchmark["scorecard"]["suite_gate"] == "human_review_required"
    assert benchmark["scorecard"]["case_count"] >= 10
    assert benchmark["scorecard"]["passed_count"] >= 1
    assert {case["status"] for case in benchmark["scorecard"]["cases"]}.issubset({"passed", "failed"})
    assert all(case["simulation_id"].startswith("SIM-") for case in benchmark["scorecard"]["cases"])
    assert all(case["run_id"].startswith("RUN-") for case in benchmark["scorecard"]["cases"])
    assert all(case["evidence_pack_id"] for case in benchmark["scorecard"]["cases"])
    assert all(case["assertions"] for case in benchmark["scorecard"]["cases"])

    benchmark_lookup = await client.get(
        f"/api/v1/benchmarks/runs/{benchmark['benchmark_run_id']}",
        headers=operator_headers,
    )
    assert benchmark_lookup.status_code == 200
    benchmark_list_response = await client.get("/api/v1/benchmarks/runs", headers=operator_headers)
    assert benchmark_list_response.status_code == 200
    assert benchmark_list_response.json()[0]["benchmark_run_id"] == benchmark["benchmark_run_id"]
    cross_tenant_benchmark_lookup = await client.get(
        f"/api/v1/benchmarks/runs/{benchmark['benchmark_run_id']}",
        headers=other_headers,
    )
    assert cross_tenant_benchmark_lookup.status_code == 404
    other_benchmark_list_response = await client.get("/api/v1/benchmarks/runs", headers=other_headers)
    assert other_benchmark_list_response.status_code == 200
    assert all(item["benchmark_run_id"] != benchmark["benchmark_run_id"] for item in other_benchmark_list_response.json())
    evidence_item = await db_session.scalar(
        select(EvidenceItemRecord).where(EvidenceItemRecord.evidence_pack_id == benchmark["evidence_pack_id"])
    )
    assert evidence_item is not None
    assert evidence_item.payload["scorecard"]["case_count"] >= 10

    blocked_benchmark_response = await client.post(
        "/api/v1/benchmarks/runs",
        json={
            "suite_name": "simulation_lab_regression",
            "threshold_overrides": {"CASE-moisture_drift": {"max_ending_risk": 0.01}},
        },
        headers=operator_headers,
    )
    assert blocked_benchmark_response.status_code == 201
    blocked_benchmark = blocked_benchmark_response.json()
    moisture_case = next(
        item for item in blocked_benchmark["scorecard"]["cases"] if item["case_id"] == "CASE-moisture_drift"
    )
    assert moisture_case["status"] == "failed"
    assert moisture_case["expected_metrics"]["max_ending_risk"] == 0.01
    assert blocked_benchmark["scorecard"]["status"] == "blocked"

    model_response = await client.post(
        "/api/v1/models",
        json={
            "name": "chronos-risk-candidate",
            "task_type": "risk_forecast",
            "version": "2026.04",
            "benchmark_run_id": benchmark["benchmark_run_id"],
            "metadata_payload": {"engine": "chronos"},
        },
        headers=operator_headers,
    )
    assert model_response.status_code == 201
    model = model_response.json()
    assert model["status"] == "candidate"
    assert model["version_status"] == "candidate"
    assert model["metadata_payload"]["evidence_pack_id"] == benchmark["evidence_pack_id"]
    assert (
        await client.post(
            "/api/v1/models",
            json={
                "name": "cross-tenant-should-not-bind",
                "task_type": "risk_forecast",
                "version": "2026.04",
                "benchmark_run_id": benchmark["benchmark_run_id"],
            },
            headers=other_headers,
        )
    ).status_code == 404
    models_response = await client.get("/api/v1/models", headers=operator_headers)
    assert models_response.status_code == 200
    assert [item["model_id"] for item in models_response.json()] == [model["model_id"]]
    other_models_response = await client.get("/api/v1/models", headers=other_headers)
    assert other_models_response.status_code == 200
    assert other_models_response.json() == []

    governance_response = await client.post(
        f"/api/v1/models/{model['model_id']}/versions/{model['model_version_id']}/governance",
        json={
            "benchmark_run_id": benchmark["benchmark_run_id"],
            "decision": "approve_for_review",
            "reason": "Benchmark evidence is ready for human review.",
        },
        headers=operator_headers,
    )
    assert governance_response.status_code == 201
    governance = governance_response.json()
    assert governance["model_status"] == "review_required"
    assert governance["version_status"] == "ready_for_review"
    assert governance["evidence_pack_id"] == benchmark["evidence_pack_id"]
    assert governance["approval_request_id"].startswith("HAR-")
    approval_request = await db_session.scalar(
        select(HumanApprovalRequestRecord).where(
            HumanApprovalRequestRecord.approval_request_id == governance["approval_request_id"]
        )
    )
    assert approval_request is not None
    assert approval_request.status == "pending"
    assert approval_request.subject_type == "model_version"
    assert approval_request.subject_id == model["model_version_id"]
    assert approval_request.payload["benchmark_run_id"] == benchmark["benchmark_run_id"]
    assert approval_request.payload["evidence_pack_id"] == benchmark["evidence_pack_id"]
    assert (
        await client.post(
            f"/api/v1/models/{model['model_id']}/versions/{model['model_version_id']}/governance",
            json={
                "benchmark_run_id": benchmark["benchmark_run_id"],
                "decision": "approve_for_review",
                "reason": "cross tenant should not govern this candidate",
            },
            headers=other_headers,
        )
    ).status_code == 404

    versions_response = await client.get(
        f"/api/v1/models/{model['model_id']}/versions",
        headers=operator_headers,
    )
    assert versions_response.status_code == 200
    assert versions_response.json()[0]["metadata_payload"]["governance_status"] == "ready_for_review"
    assert (
        await client.get(
            f"/api/v1/models/{model['model_id']}/versions",
            headers=other_headers,
        )
    ).status_code == 404

    relations_response = await client.get(
        "/api/v1/knowledge/relations",
        params={"subject_type": "model_version", "subject_id": model["model_version_id"]},
        headers=operator_headers,
    )
    assert relations_response.status_code == 200
    relations = relations_response.json()
    assert relations[0]["predicate"] == "evaluated_by"
    assert relations[0]["object_id"] == benchmark["benchmark_run_id"]
    assert relations[0]["evidence_pack_id"] == benchmark["evidence_pack_id"]

    manual_relation_response = await client.post(
        "/api/v1/knowledge/relations",
        json={
            "subject_type": "benchmark_run",
            "subject_id": benchmark["benchmark_run_id"],
            "predicate": "supports",
            "object_type": "evidence_pack",
            "object_id": benchmark["evidence_pack_id"],
            "evidence_pack_id": benchmark["evidence_pack_id"],
            "payload": {"scope": "v3.5"},
        },
        headers=operator_headers,
    )
    assert manual_relation_response.status_code == 201
    manual_relation = manual_relation_response.json()
    assert manual_relation["evidence_pack_id"] == benchmark["evidence_pack_id"]
    assert manual_relation["created_at"]
    relation_lookup_response = await client.get(
        f"/api/v1/knowledge/relations/{manual_relation['relation_id']}",
        headers=operator_headers,
    )
    assert relation_lookup_response.status_code == 200
    assert relation_lookup_response.json()["relation_id"] == manual_relation["relation_id"]
    cross_tenant_relation_lookup_response = await client.get(
        f"/api/v1/knowledge/relations/{manual_relation['relation_id']}",
        headers=other_headers,
    )
    assert cross_tenant_relation_lookup_response.status_code == 404
    relation_by_evidence_response = await client.get(
        "/api/v1/knowledge/relations",
        params={"evidence_pack_id": benchmark["evidence_pack_id"]},
        headers=operator_headers,
    )
    assert relation_by_evidence_response.status_code == 200
    assert manual_relation["relation_id"] in {
        item["relation_id"] for item in relation_by_evidence_response.json()
    }
    relation_by_object_response = await client.get(
        "/api/v1/knowledge/relations",
        params={"object_type": "evidence_pack", "object_id": benchmark["evidence_pack_id"]},
        headers=operator_headers,
    )
    assert relation_by_object_response.status_code == 200
    assert [item["relation_id"] for item in relation_by_object_response.json()] == [manual_relation["relation_id"]]
    other_relations_response = await client.get(
        "/api/v1/knowledge/relations",
        params={"evidence_pack_id": benchmark["evidence_pack_id"]},
        headers=other_headers,
    )
    assert other_relations_response.status_code == 200
    assert all(item["relation_id"] != manual_relation["relation_id"] for item in other_relations_response.json())

    rejected_model_response = await client.post(
        "/api/v1/models",
        json={
            "name": "chronos-risk-reject-candidate",
            "task_type": "risk_forecast",
            "version": "2026.04-reject",
            "benchmark_run_id": benchmark["benchmark_run_id"],
        },
        headers=operator_headers,
    )
    assert rejected_model_response.status_code == 201
    rejected_model = rejected_model_response.json()
    reject_response = await client.post(
        f"/api/v1/models/{rejected_model['model_id']}/versions/{rejected_model['model_version_id']}/governance",
        json={
            "benchmark_run_id": benchmark["benchmark_run_id"],
            "decision": "reject",
            "reason": "Benchmark evidence is not acceptable for review.",
        },
        headers=operator_headers,
    )
    assert reject_response.status_code == 201
    rejected = reject_response.json()
    assert rejected["model_status"] == "rejected"
    assert rejected["version_status"] == "rejected"
    assert rejected["approval_request_id"] is None
    rejected_relations_response = await client.get(
        "/api/v1/knowledge/relations",
        params={
            "subject_type": "model_version",
            "subject_id": rejected_model["model_version_id"],
            "predicate": "rejected_by",
        },
        headers=operator_headers,
    )
    assert rejected_relations_response.status_code == 200
    assert rejected_relations_response.json()[0]["predicate"] == "rejected_by"
    rejected_versions_response = await client.get(
        f"/api/v1/models/{rejected_model['model_id']}/versions",
        headers=operator_headers,
    )
    assert rejected_versions_response.status_code == 200
    assert rejected_versions_response.json()[0]["status"] == "rejected"

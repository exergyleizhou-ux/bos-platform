from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.models import Batch, User
from app.models_bos import ReleaseDecision
from app.routers.auth import create_access_token


@pytest.mark.asyncio
async def test_external_sources_seed_resolve_and_list_flow(
    client: AsyncClient,
    db_session,
    test_tenant,
    scientist_user,
    scientist_headers,
    operator_headers,
):
    seed_response = await client.post("/api/v1/external-sources/p0/seed", headers=scientist_headers)
    assert seed_response.status_code == 201
    seed_payload = seed_response.json()
    assert seed_payload["source_count"] == 94
    assert seed_payload["review_card_count"] == 8
    assert seed_payload["reviewed_candidate_count"] == 0
    assert "runtime_activated_false" in seed_payload["guardrails"]

    phase4a_seed_response = await client.post(
        "/api/v1/external-sources/phase4a/domain-metadata/seed",
        headers=scientist_headers,
    )
    assert phase4a_seed_response.status_code == 201
    phase4a_seed_payload = phase4a_seed_response.json()
    assert phase4a_seed_payload["source_count"] == 24
    assert phase4a_seed_payload["phase4a_domain_metadata_ready"] is True
    assert phase4a_seed_payload["phase4a_domain_missing_counts"] == {
        "lca": 0,
        "tea": 0,
        "compliance": 0,
        "model_provider": 0,
        "github_reference": 0,
    }
    assert phase4a_seed_payload["runtime_activated_count"] == 0
    assert phase4a_seed_payload["validated_default_write_enabled_count"] == 0
    assert phase4a_seed_payload["numeric_value_candidate_count"] == 0
    assert "source_records_only" in phase4a_seed_payload["guardrails"]

    readiness_response = await client.get("/api/v1/external-sources/schema-readiness", headers=operator_headers)
    assert readiness_response.status_code == 200
    readiness_payload = readiness_response.json()
    assert readiness_payload["status"] == "ready"
    assert readiness_payload["schema_ready"] is True
    assert readiness_payload["source_catalog_ready"] is True
    assert readiness_payload["knowledge_coverage_ready"] is True
    assert readiness_payload["knowledge_coverage_percent"] == 100
    assert readiness_payload["source_metadata_coverage_percent"] == 100
    assert readiness_payload["business_knowledge_coverage_percent"] == 84.17
    assert readiness_payload["business_knowledge_coverage_percent"] < readiness_payload["source_metadata_coverage_percent"]
    business_groups = {
        group["group_key"]: group
        for group in readiness_payload["business_knowledge_coverage_groups"]
    }
    assert business_groups["bioexecutor_species"]["coverage_percent"] == 100
    assert business_groups["product_agronomy_outputs"]["status"] == "partial"
    product_items = {
        item["item_key"]: item
        for item in business_groups["product_agronomy_outputs"]["items"]
    }
    assert business_groups["product_agronomy_outputs"]["coverage_percent"] == 70
    assert product_items["germination_rate"]["status"] == "candidate_read_model"
    assert product_items["germination_rate"]["coverage_basis"] == "candidate_read_model"
    assert product_items["germination_rate"]["numeric_values_included"] is False
    assert product_items["germination_index"]["status"] == "candidate_read_model"
    assert product_items["germination_index"]["runtime_activation_enabled"] is False
    assert product_items["phytotoxicity"]["status"] == "candidate_read_model"
    assert product_items["phytotoxicity"]["validated_default_write_enabled"] is False
    assert {domain["domain_key"] for domain in readiness_payload["knowledge_coverage_domains"]} == {
        "bsf_metadata",
        "feedstock_metadata",
        "lca",
        "tea",
        "compliance",
        "model_provider",
        "github_reference",
    }
    assert all(domain["status"] == "covered" for domain in readiness_payload["knowledge_coverage_domains"])
    assert all(domain["runtime_activation_enabled"] is False for domain in readiness_payload["knowledge_coverage_domains"])
    assert all(domain["validated_default_write_enabled"] is False for domain in readiness_payload["knowledge_coverage_domains"])
    assert all(domain["numeric_values_included"] is False for domain in readiness_payload["knowledge_coverage_domains"])
    assert readiness_payload["feedstock_dataset_candidate_count"] >= 9
    assert readiness_payload["literature_extraction_candidate_count"] >= 5
    assert readiness_payload["phase4a_domain_metadata_ready"] is True
    assert readiness_payload["phase4a_domain_candidate_counts"] == {
        "lca": 6,
        "tea": 6,
        "compliance": 5,
        "model_provider": 4,
        "github_reference": 3,
    }
    assert readiness_payload["phase4a_domain_expected_counts"] == {
        "lca": 6,
        "tea": 6,
        "compliance": 5,
        "model_provider": 4,
        "github_reference": 3,
    }
    assert readiness_payload["phase4a_domain_missing_counts"] == {
        "lca": 0,
        "tea": 0,
        "compliance": 0,
        "model_provider": 0,
        "github_reference": 0,
    }
    assert readiness_payload["missing_required_tables"] == []
    assert "no_table_creation" in readiness_payload["guardrails"]
    assert "no_seed_mutation" in readiness_payload["guardrails"]
    assert "phase4a_domain_coverage_is_read_only" in readiness_payload["guardrails"]
    assert {
        "external_source_records",
        "external_source_review_cards",
        "external_source_extraction_records",
        "literature_extraction_candidate_records",
        "literature_extraction_review_draft_records",
        "literature_value_overlay_records",
        "literature_value_promotion_requests",
        "literature_value_promotion_approval_records",
        "literature_value_runtime_activation_records",
        "literature_value_release_evidence_links",
        "literature_value_rollback_records",
        "reviewed_external_candidate_records",
    }.issubset({item["table_name"] for item in readiness_payload["required_tables"]})

    catalog_response = await client.get("/api/v1/external-sources/catalog", headers=operator_headers)
    assert catalog_response.status_code == 200
    assert catalog_response.json()["count"] == 94

    literature_seed_response = await client.post(
        "/api/v1/external-sources/literature-extraction-candidates/seed",
        headers=scientist_headers,
    )
    assert literature_seed_response.status_code == 201
    literature_seed_payload = literature_seed_response.json()
    assert literature_seed_payload["schema_version"] == "literature_extraction_candidate_seed_v1"
    assert literature_seed_payload["source_count"] == 1
    assert literature_seed_payload["candidate_count"] >= 5
    assert literature_seed_payload["review_status"] == "pending_review"
    assert literature_seed_payload["numeric_values_included"] is True
    assert literature_seed_payload["release_evidence_allowed"] is False
    assert literature_seed_payload["runtime_activation_enabled"] is False
    assert literature_seed_payload["validated_default_write_enabled"] is False
    assert literature_seed_payload["promotion_enabled"] is False
    assert all(value is False for value in literature_seed_payload["side_effects"].values())
    assert "literature_extraction_candidate_records_only" in literature_seed_payload["guardrails"]

    literature_response = await client.get(
        "/api/v1/external-sources/literature-extraction-candidates",
        headers=operator_headers,
    )
    assert literature_response.status_code == 200
    literature_payload = literature_response.json()
    assert literature_payload["schema_version"] == "literature_extraction_candidate_list_v1"
    assert literature_payload["count"] >= 5
    assert literature_payload["metric_counts"]["germination_index"] >= 1
    assert literature_payload["metric_counts"]["phytotoxicity"] >= 1
    assert literature_payload["side_effects"] == {
        "runtime_activation": False,
        "validated_default_write": False,
        "species_db_write": False,
        "feedstock_db_write": False,
        "release_evidence_use": False,
        "promotion": False,
        "final_action_execution": False,
    }
    assert all(item["candidate_type"] == "literature_extraction_candidate" for item in literature_payload["items"])
    assert all(item["review_status"] == "pending_review" for item in literature_payload["items"])
    assert all(item["numeric_values_included"] is True for item in literature_payload["items"])
    assert all(item["release_evidence_allowed"] is False for item in literature_payload["items"])
    assert all(item["runtime_activation_enabled"] is False for item in literature_payload["items"])
    assert all(item["validated_default_write_enabled"] is False for item in literature_payload["items"])
    assert all(item["promotion_enabled"] is False for item in literature_payload["items"])

    filtered_literature_response = await client.get(
        "/api/v1/external-sources/literature-extraction-candidates",
        params={"metric_key": "phytotoxicity"},
        headers=operator_headers,
    )
    assert filtered_literature_response.status_code == 200
    filtered_literature_payload = filtered_literature_response.json()
    assert filtered_literature_payload["count"] == literature_payload["metric_counts"]["phytotoxicity"]
    assert {item["metric_key"] for item in filtered_literature_payload["items"]} == {"phytotoxicity"}

    literature_candidate_id = literature_payload["items"][0]["candidate_id"]
    literature_export_response = await client.get(
        f"/api/v1/external-sources/literature-extraction-candidates/{literature_candidate_id}/review-packet/export",
        headers=operator_headers,
    )
    assert literature_export_response.status_code == 200
    literature_export = literature_export_response.json()
    assert literature_export["schema_version"] == "literature_extraction_candidate_review_packet_export_v1"
    assert literature_export["export_format"] == "json"
    assert literature_export["export_filename"] == f"{literature_candidate_id}-literature-extraction-review-packet.json"
    assert len(literature_export["content_hash"]) == 64
    assert literature_export["export_manifest"]["candidate_id"] == literature_candidate_id
    assert literature_export["export_manifest"]["content_hash"] == literature_export["content_hash"]
    assert literature_export["export_manifest"]["export_policy"] == "response_only_no_file_write"
    assert literature_export["export_manifest"]["release_evidence_allowed"] is False
    assert literature_export["export_manifest"]["runtime_activation_enabled"] is False
    assert literature_export["export_manifest"]["validated_default_write_enabled"] is False
    assert literature_export["export_manifest"]["promotion_enabled"] is False
    assert literature_export["export_manifest"]["final_action_execution"] is False
    assert literature_export["review_packet"]["candidate"]["candidate_id"] == literature_candidate_id
    assert literature_export["review_packet"]["candidate_payload"]["raw_value"] == literature_payload["items"][0]["raw_value"]
    assert literature_export["review_packet"]["raw_value"] == literature_payload["items"][0]["raw_value"]
    assert literature_export["review_packet"]["unit"] == literature_payload["items"][0]["unit"]
    assert literature_export["review_packet"]["conditions"]["condition_context"] == literature_payload["items"][0]["condition_context"]
    assert literature_export["review_packet"]["license_note"] == literature_payload["items"][0]["license_note"]
    assert literature_export["review_packet"]["source_trace"]["source_ref"] == literature_payload["items"][0]["source_ref"]
    assert literature_export["review_packet"]["release_evidence_allowed"] is False
    assert literature_export["review_packet"]["runtime_activation_enabled"] is False
    assert literature_export["review_packet"]["validated_default_write_enabled"] is False
    assert literature_export["review_packet"]["promotion_enabled"] is False
    assert literature_export["review_packet"]["final_action_execution"] is False
    assert literature_export["side_effects"] == {
        "file_written": False,
        "runtime_activation": False,
        "validated_default_write": False,
        "species_db_write": False,
        "feedstock_db_write": False,
        "release_evidence_use": False,
        "promotion": False,
        "final_action_execution": False,
    }
    assert "literature_extraction_review_packet_export_is_read_only" in literature_export["guardrails"]
    assert "export_response_only_no_file_write" in literature_export["guardrails"]
    assert "no_final_action_execution" in literature_export["guardrails"]

    literature_bulk_export_response = await client.get(
        "/api/v1/external-sources/literature-extraction-candidates/review-packets/export",
        headers=operator_headers,
    )
    assert literature_bulk_export_response.status_code == 200
    literature_bulk_export = literature_bulk_export_response.json()
    assert literature_bulk_export["schema_version"] == "literature_extraction_candidate_review_packet_bulk_export_v1"
    assert literature_bulk_export["export_format"] == "json"
    assert literature_bulk_export["export_filename"] == "literature-extraction-review-packets.json"
    assert len(literature_bulk_export["content_hash"]) == 64
    assert literature_bulk_export["count"] == literature_payload["count"]
    assert len(literature_bulk_export["packet_exports"]) == literature_payload["count"]
    assert literature_bulk_export["export_manifest"]["candidate_count"] == literature_payload["count"]
    assert literature_bulk_export["export_manifest"]["candidate_ids"][0] == literature_candidate_id
    assert literature_bulk_export["export_manifest"]["content_hash"] == literature_bulk_export["content_hash"]
    assert literature_bulk_export["export_manifest"]["export_policy"] == "response_only_no_file_write"
    assert literature_bulk_export["export_manifest"]["source_packet_persistence"] == "persisted_candidate_records_only"
    assert literature_bulk_export["export_manifest"]["release_evidence_allowed"] is False
    assert literature_bulk_export["export_manifest"]["runtime_activation_enabled"] is False
    assert literature_bulk_export["export_manifest"]["validated_default_write_enabled"] is False
    assert literature_bulk_export["export_manifest"]["promotion_enabled"] is False
    assert literature_bulk_export["export_manifest"]["final_action_execution"] is False
    assert all(value is False for value in literature_bulk_export["side_effects"].values())
    assert all(all(value is False for value in item["side_effects"].values()) for item in literature_bulk_export["packet_exports"])
    assert "literature_extraction_bulk_export_is_read_only" in literature_bulk_export["guardrails"]
    assert "tenant_scoped_persisted_candidates_only" in literature_bulk_export["guardrails"]

    literature_filtered_bulk_export_response = await client.get(
        "/api/v1/external-sources/literature-extraction-candidates/review-packets/export",
        params={"metric_key": "phytotoxicity"},
        headers=operator_headers,
    )
    assert literature_filtered_bulk_export_response.status_code == 200
    literature_filtered_bulk_export = literature_filtered_bulk_export_response.json()
    assert literature_filtered_bulk_export["count"] == literature_payload["metric_counts"]["phytotoxicity"]
    assert literature_filtered_bulk_export["export_filename"] == "literature-extraction-review-packets-phytotoxicity.json"
    assert literature_filtered_bulk_export["export_manifest"]["metric_key_filter"] == "phytotoxicity"
    assert set(literature_filtered_bulk_export["metric_counts"]) == {"phytotoxicity"}

    literature_review_draft_response = await client.post(
        f"/api/v1/external-sources/literature-extraction-candidates/{literature_candidate_id}/review-drafts",
        json={
            "review_intent": "approve_candidate_use_intent",
            "reviewer_notes": "Reviewer intent only; candidate raw value remains pending review.",
            "idempotency_key": "idem-literature-review-draft-router",
        },
        headers=operator_headers,
    )
    assert literature_review_draft_response.status_code == 201
    literature_review_draft = literature_review_draft_response.json()
    assert literature_review_draft["schema_version"] == "literature_extraction_review_draft_v1"
    assert literature_review_draft["review_draft_id"].startswith("LERD-")
    assert literature_review_draft["candidate_id"] == literature_candidate_id
    assert literature_review_draft["review_intent"] == "approve_candidate_use_intent"
    assert literature_review_draft["status"] == "draft_intent_recorded"
    assert literature_review_draft["candidate_snapshot"]["review_status"] == "pending_review"
    assert literature_review_draft["source_review_packet_export_id"] == literature_export["export_manifest"]["export_id"]
    assert literature_review_draft["source_review_packet_hash"] == literature_export["content_hash"]
    assert literature_review_draft["export_manifest"]["export_policy"] == "response_only_no_file_write"
    assert literature_review_draft["release_evidence_allowed"] is False
    assert literature_review_draft["runtime_activation_enabled"] is False
    assert literature_review_draft["validated_default_write_enabled"] is False
    assert literature_review_draft["promotion_enabled"] is False
    assert literature_review_draft["final_action_execution"] is False
    assert all(value is False for value in literature_review_draft["side_effects"].values())
    assert "candidate_status_remains_pending_review" in literature_review_draft["guardrails"]

    repeated_literature_review_draft_response = await client.post(
        f"/api/v1/external-sources/literature-extraction-candidates/{literature_candidate_id}/review-drafts",
        json={
            "review_intent": "approve_candidate_use_intent",
            "reviewer_notes": "Repeated request returns existing draft.",
            "idempotency_key": "idem-literature-review-draft-router",
        },
        headers=operator_headers,
    )
    assert repeated_literature_review_draft_response.status_code == 201
    assert repeated_literature_review_draft_response.json()["review_draft_id"] == literature_review_draft["review_draft_id"]

    literature_review_drafts_response = await client.get(
        "/api/v1/external-sources/literature-extraction-candidates/review-drafts",
        headers=operator_headers,
    )
    assert literature_review_drafts_response.status_code == 200
    literature_review_drafts = literature_review_drafts_response.json()
    assert literature_review_drafts["schema_version"] == "literature_extraction_review_draft_list_v1"
    assert literature_review_drafts["count"] == 1
    assert literature_review_drafts["drafts"][0]["review_draft_id"] == literature_review_draft["review_draft_id"]
    assert literature_review_drafts["side_effects"]["candidate_status_update"] is False
    assert "literature_extraction_review_draft_list_is_read_only" in literature_review_drafts["guardrails"]

    literature_review_draft_comparison_response = await client.get(
        f"/api/v1/external-sources/literature-extraction-candidates/{literature_candidate_id}/review-drafts/comparison",
        headers=operator_headers,
    )
    assert literature_review_draft_comparison_response.status_code == 200
    literature_review_draft_comparison = literature_review_draft_comparison_response.json()
    assert literature_review_draft_comparison["schema_version"] == "literature_extraction_review_draft_comparison_v1"
    assert literature_review_draft_comparison["current_review_draft_id"] == literature_review_draft["review_draft_id"]
    assert literature_review_draft_comparison["current_revision_hash"]
    assert literature_review_draft_comparison["source_review_packet_hash"] == literature_export["content_hash"]
    assert literature_review_draft_comparison["current_response_packet_hash"] == literature_export["content_hash"]
    assert literature_review_draft_comparison["comparison_manifest"]["comparison_policy"] == "response_only_no_file_write"
    assert literature_review_draft_comparison["report_manifest"]["report_policy"] == "response_only_no_file_write"
    assert literature_review_draft_comparison["report_manifest"]["file_written"] is False
    assert literature_review_draft_comparison["report_payload"]["summary"]["packet_hash_matches"] is True
    assert literature_review_draft_comparison["comparison_manifest"]["candidate_status"] == "pending_review"
    assert literature_review_draft_comparison["comparison_summary"]["current_response_packet_hash_matches_draft"] is True
    assert literature_review_draft_comparison["audit_trail"][0]["review_draft_id"] == literature_review_draft["review_draft_id"]
    assert all(value is False for value in literature_review_draft_comparison["side_effects"].values())
    assert "literature_extraction_review_draft_comparison_is_read_only" in literature_review_draft_comparison["guardrails"]

    filtered_literature_review_draft_comparison_response = await client.get(
        f"/api/v1/external-sources/literature-extraction-candidates/{literature_candidate_id}/review-drafts/comparison?changed_field=review_intent",
        headers=operator_headers,
    )
    assert filtered_literature_review_draft_comparison_response.status_code == 200
    filtered_literature_review_draft_comparison = filtered_literature_review_draft_comparison_response.json()
    assert filtered_literature_review_draft_comparison["changed_field_filter"] == "review_intent"
    assert filtered_literature_review_draft_comparison["report_manifest"]["changed_field_filter"] == "review_intent"

    literature_readiness_response = await client.get(
        "/api/v1/external-sources/literature-extraction-candidates/evidence-chain/readiness",
        headers=operator_headers,
    )
    assert literature_readiness_response.status_code == 200
    literature_readiness = literature_readiness_response.json()
    assert literature_readiness["schema_version"] == "literature_extraction_evidence_chain_readiness_v1"
    assert literature_readiness["chain_complete"] is True
    assert literature_readiness["candidate_count"] == literature_payload["count"]
    assert literature_readiness["packet_export_ready"] is True
    assert literature_readiness["bulk_export_ready"] is True
    assert literature_readiness["review_draft_count"] == 1
    assert literature_readiness["comparison_ready"] is True
    assert literature_readiness["report_ready"] is True
    assert literature_readiness["auto_use_allowed"] is False
    assert literature_readiness["release_evidence_allowed"] is False
    assert literature_readiness["runtime_activation_enabled"] is False
    assert literature_readiness["validated_default_write_enabled"] is False
    assert literature_readiness["promotion_enabled"] is False
    assert literature_readiness["final_action_execution"] is False
    assert literature_readiness["blocking_reason"] is None
    assert all(value is False for value in literature_readiness["side_effects"].values())
    assert "literature_evidence_chain_readiness_is_read_only" in literature_readiness["guardrails"]

    promotion_readiness_response = await client.get(
        f"/api/v1/external-sources/literature-extraction-candidates/{literature_candidate_id}/promotion-readiness",
        headers=operator_headers,
    )
    assert promotion_readiness_response.status_code == 200
    promotion_readiness = promotion_readiness_response.json()
    assert promotion_readiness["schema_version"] == "literature_value_promotion_readiness_v1"
    assert promotion_readiness["chain_complete"] is True
    assert promotion_readiness["promotion_ready"] is True
    assert promotion_readiness["request_status"] == "not_requested"
    assert promotion_readiness["review_draft_id"] == literature_review_draft["review_draft_id"]
    assert promotion_readiness["source_review_packet_hash"] == literature_export["content_hash"]
    assert promotion_readiness["comparison_hash"] == literature_review_draft_comparison["comparison_manifest"]["comparison_hash"]
    assert promotion_readiness["raw_value"] == literature_payload["items"][0]["raw_value"]
    assert promotion_readiness["unit"] == literature_payload["items"][0]["unit"]
    assert promotion_readiness["release_evidence_allowed"] is False
    assert promotion_readiness["runtime_activation_enabled"] is False
    assert promotion_readiness["validated_default_write_enabled"] is False
    assert promotion_readiness["promotion_enabled"] is False
    assert promotion_readiness["final_action_execution"] is False
    assert all(value is False for value in promotion_readiness["side_effects"].values())
    assert "promotion_ready_does_not_enable_promotion" in promotion_readiness["guardrails"]

    empty_lifecycle_response = await client.get(
        f"/api/v1/external-sources/literature-extraction-candidates/{literature_candidate_id}/promotion-lifecycle",
        headers=operator_headers,
    )
    assert empty_lifecycle_response.status_code == 200
    empty_lifecycle = empty_lifecycle_response.json()
    assert empty_lifecycle["schema_version"] == "literature_value_promotion_lifecycle_v1"
    assert empty_lifecycle["promotion_request_count"] == 0
    assert empty_lifecycle["lifecycle_read_only"] is True
    assert all(value is False for value in empty_lifecycle["side_effects"].values())

    promotion_request_response = await client.post(
        f"/api/v1/external-sources/literature-extraction-candidates/{literature_candidate_id}/promotion-requests",
        json={
            "target_use": "candidate_overlay_review",
            "target_scope": {"campaign_key": "frass-agronomy-review"},
            "idempotency_key": "idem-literature-promotion-router",
        },
        headers=operator_headers,
    )
    assert promotion_request_response.status_code == 201
    promotion_request = promotion_request_response.json()
    assert promotion_request["schema_version"] == "literature_value_promotion_request_v1"
    assert promotion_request["promotion_request_id"].startswith("LVPR-")
    assert promotion_request["candidate_id"] == literature_candidate_id
    assert promotion_request["source_review_packet_hash"] == literature_export["content_hash"]
    assert promotion_request["review_draft_id"] == literature_review_draft["review_draft_id"]
    assert promotion_request["comparison_hash"] == literature_review_draft_comparison["comparison_manifest"]["comparison_hash"]
    assert promotion_request["target_use"] == "candidate_overlay_review"
    assert promotion_request["target_scope"] == {"campaign_key": "frass-agronomy-review"}
    assert promotion_request["request_status"] == "requested"
    assert promotion_request["release_evidence_allowed"] is False
    assert promotion_request["runtime_activation_enabled"] is False
    assert promotion_request["validated_default_write_enabled"] is False
    assert promotion_request["promotion_enabled"] is False
    assert promotion_request["final_action_execution"] is False
    assert all(value is False for value in promotion_request["side_effects"].values())
    assert "request_status_requested_not_active" in promotion_request["guardrails"]

    repeated_promotion_request_response = await client.post(
        f"/api/v1/external-sources/literature-extraction-candidates/{literature_candidate_id}/promotion-requests",
        json={
            "target_use": "candidate_overlay_review",
            "target_scope": {"campaign_key": "frass-agronomy-review"},
            "idempotency_key": "idem-literature-promotion-router",
        },
        headers=operator_headers,
    )
    assert repeated_promotion_request_response.status_code == 201
    assert repeated_promotion_request_response.json()["promotion_request_id"] == promotion_request["promotion_request_id"]

    conflicting_promotion_request_response = await client.post(
        f"/api/v1/external-sources/literature-extraction-candidates/{literature_candidate_id}/promotion-requests",
        json={
            "target_use": "candidate_overlay_review",
            "target_scope": {"campaign_key": "different-review-scope"},
            "idempotency_key": "idem-literature-promotion-router",
        },
        headers=operator_headers,
    )
    assert conflicting_promotion_request_response.status_code == 409

    promotion_readiness_after_request_response = await client.get(
        f"/api/v1/external-sources/literature-extraction-candidates/{literature_candidate_id}/promotion-readiness",
        headers=operator_headers,
    )
    assert promotion_readiness_after_request_response.status_code == 200
    promotion_readiness_after_request = promotion_readiness_after_request_response.json()
    assert promotion_readiness_after_request["request_status"] == "requested"
    assert promotion_readiness_after_request["existing_promotion_request_id"] == promotion_request["promotion_request_id"]
    assert promotion_readiness_after_request["promotion_enabled"] is False

    release_manager = User(
        username="test_release_manager_external_sources_router",
        hashed_password="test",
        full_name="Test Release Manager",
        email="test_release_manager_external_sources_router@bos.io",
        role="release_manager",
        tenant_id=test_tenant.id,
        is_active=True,
    )
    db_session.add(release_manager)
    await db_session.commit()
    await db_session.refresh(release_manager)
    release_manager_headers = {
        "Authorization": f"Bearer {create_access_token(release_manager.id, release_manager.role, release_manager.tenant_id)}"
    }

    promotion_approval_response = await client.post(
        f"/api/v1/external-sources/promotion-requests/{promotion_request['promotion_request_id']}/approvals",
        json={
            "approval_action": "approve",
            "approver_notes": "Reviewed packet hash, comparison hash, and target scope for overlay review only.",
            "idempotency_key": "idem-literature-promotion-approval-router",
        },
        headers=scientist_headers,
    )
    assert promotion_approval_response.status_code == 201
    promotion_approval = promotion_approval_response.json()
    assert promotion_approval["schema_version"] == "literature_value_promotion_approval_v1"
    assert promotion_approval["approval_id"].startswith("LVPA-")
    assert promotion_approval["promotion_request_id"] == promotion_request["promotion_request_id"]
    assert promotion_approval["candidate_id"] == literature_candidate_id
    assert promotion_approval["approval_action"] == "approve"
    assert promotion_approval["request_status_before"] == "requested"
    assert promotion_approval["request_status_after"] == "requested"
    assert promotion_approval["approved_by_user_roles"] == ["scientist"]
    assert promotion_approval["approval_audit_only"] is True
    assert promotion_approval["overlay_write_enabled"] is False
    assert promotion_approval["release_evidence_allowed"] is False
    assert promotion_approval["runtime_activation_enabled"] is False
    assert promotion_approval["validated_default_write_enabled"] is False
    assert promotion_approval["promotion_enabled"] is False
    assert promotion_approval["final_action_execution"] is False
    assert all(value is False for value in promotion_approval["side_effects"].values())
    assert "approval_does_not_create_overlay" in promotion_approval["guardrails"]

    repeated_promotion_approval_response = await client.post(
        f"/api/v1/external-sources/promotion-requests/{promotion_request['promotion_request_id']}/approvals",
        json={
            "approval_action": "approve",
            "approver_notes": "Reviewed packet hash, comparison hash, and target scope for overlay review only.",
            "idempotency_key": "idem-literature-promotion-approval-router",
        },
        headers=scientist_headers,
    )
    assert repeated_promotion_approval_response.status_code == 201
    assert repeated_promotion_approval_response.json()["approval_id"] == promotion_approval["approval_id"]

    overlay_before_dual_approval_response = await client.post(
        f"/api/v1/external-sources/promotion-requests/{promotion_request['promotion_request_id']}/promote-overlay",
        json={
            "overlay_notes": "Single-person approval cannot create an overlay.",
            "idempotency_key": "idem-literature-overlay-router-before-dual-approval",
        },
        headers=scientist_headers,
    )
    assert overlay_before_dual_approval_response.status_code == 400
    assert overlay_before_dual_approval_response.json()["detail"] == "literature_value_promotion_request_not_approved"

    duplicate_scientist_approval_response = await client.post(
        f"/api/v1/external-sources/promotion-requests/{promotion_request['promotion_request_id']}/approvals",
        json={
            "approval_action": "approve",
            "approver_notes": "The same scientist cannot count twice toward dual approval.",
            "idempotency_key": "idem-literature-promotion-approval-router-second",
        },
        headers=scientist_headers,
    )
    assert duplicate_scientist_approval_response.status_code == 400
    assert duplicate_scientist_approval_response.json()["detail"] == "literature_value_promotion_approver_already_recorded"

    promotion_readiness_after_approval_response = await client.get(
        f"/api/v1/external-sources/literature-extraction-candidates/{literature_candidate_id}/promotion-readiness",
        headers=operator_headers,
    )
    assert promotion_readiness_after_approval_response.status_code == 200
    promotion_readiness_after_approval = promotion_readiness_after_approval_response.json()
    assert promotion_readiness_after_approval["request_status"] == "requested"
    assert promotion_readiness_after_approval["promotion_enabled"] is False

    second_promotion_approval_response = await client.post(
        f"/api/v1/external-sources/promotion-requests/{promotion_request['promotion_request_id']}/approvals",
        json={
            "approval_action": "approve",
            "approver_notes": "Release manager confirms the scientist approval and scoped overlay review.",
            "idempotency_key": "idem-literature-promotion-approval-router-release-manager",
        },
        headers=release_manager_headers,
    )
    assert second_promotion_approval_response.status_code == 201
    second_promotion_approval = second_promotion_approval_response.json()
    assert second_promotion_approval["request_status_before"] == "requested"
    assert second_promotion_approval["request_status_after"] == "approved_for_promotion"
    assert second_promotion_approval["approved_by_user_roles"] == ["release_manager"]

    promotion_readiness_after_dual_approval_response = await client.get(
        f"/api/v1/external-sources/literature-extraction-candidates/{literature_candidate_id}/promotion-readiness",
        headers=operator_headers,
    )
    assert promotion_readiness_after_dual_approval_response.status_code == 200
    promotion_readiness_after_dual_approval = promotion_readiness_after_dual_approval_response.json()
    assert promotion_readiness_after_dual_approval["request_status"] == "approved_for_promotion"
    assert promotion_readiness_after_dual_approval["promotion_enabled"] is False

    overlay_response = await client.post(
        f"/api/v1/external-sources/promotion-requests/{promotion_request['promotion_request_id']}/promote-overlay",
        json={
            "overlay_notes": "Create inactive overlay only; scoped runtime activation remains separate.",
            "idempotency_key": "idem-literature-overlay-router",
        },
        headers=scientist_headers,
    )
    assert overlay_response.status_code == 201
    overlay = overlay_response.json()
    assert overlay["schema_version"] == "literature_value_overlay_v1"
    assert overlay["overlay_id"].startswith("LVO-")
    assert overlay["promotion_request_id"] == promotion_request["promotion_request_id"]
    assert overlay["approval_id"] == second_promotion_approval["approval_id"]
    assert overlay["candidate_id"] == literature_candidate_id
    assert overlay["overlay_status"] == "inactive"
    assert overlay["overlay_active"] is False
    assert overlay["normalized_value"] == f"{literature_payload['items'][0]['raw_value']} {literature_payload['items'][0]['unit']}"
    assert overlay["source_ref"] == literature_payload["items"][0]["source_ref"]
    assert len(overlay["approval_hash"]) == 64
    assert len(overlay["overlay_hash"]) == 64
    assert overlay["validity_scope"]["target_scope"] == {"campaign_key": "frass-agronomy-review"}
    assert overlay["validity_scope"]["conditions"]["source_ref"] == literature_payload["items"][0]["source_ref"]
    assert overlay["rollback_pointer"]["required"] is True
    assert overlay["rollback_pointer"]["rollback_status"] == "not_rolled_back"
    assert overlay["release_evidence_allowed"] is False
    assert overlay["runtime_activation_enabled"] is False
    assert overlay["validated_default_write_enabled"] is False
    assert overlay["final_action_execution"] is False
    assert overlay["rollback_required_before_use_change"] is True
    assert all(value is False for value in overlay["side_effects"].values())
    assert "overlay_created_inactive" in overlay["guardrails"]

    repeated_overlay_response = await client.post(
        f"/api/v1/external-sources/promotion-requests/{promotion_request['promotion_request_id']}/promote-overlay",
        json={
            "overlay_notes": "Create inactive overlay only; scoped runtime activation remains separate.",
            "idempotency_key": "idem-literature-overlay-router",
        },
        headers=scientist_headers,
    )
    assert repeated_overlay_response.status_code == 201
    assert repeated_overlay_response.json()["overlay_id"] == overlay["overlay_id"]

    second_overlay_response = await client.post(
        f"/api/v1/external-sources/promotion-requests/{promotion_request['promotion_request_id']}/promote-overlay",
        json={
            "overlay_notes": "A different overlay request should not create a second overlay.",
            "idempotency_key": "idem-literature-overlay-router-second",
        },
        headers=scientist_headers,
    )
    assert second_overlay_response.status_code == 400
    assert second_overlay_response.json()["detail"] == "literature_value_overlay_already_exists"

    activation_preview_response = await client.get(
        f"/api/v1/external-sources/overlays/{overlay['overlay_id']}/activation-preview",
        headers=operator_headers,
    )
    assert activation_preview_response.status_code == 200
    activation_preview = activation_preview_response.json()
    assert activation_preview["schema_version"] == "literature_value_runtime_activation_preview_v1"
    assert activation_preview["overlay_id"] == overlay["overlay_id"]
    assert activation_preview["approved_overlay"] is True
    assert activation_preview["can_activate_scoped_runtime"] is True
    assert activation_preview["global_activation_allowed"] is False
    assert "campaign_key" in activation_preview["activation_scope_options"]

    global_activation_response = await client.post(
        f"/api/v1/external-sources/overlays/{overlay['overlay_id']}/runtime-activations",
        json={
            "activation_scope": {"global": True},
            "operator_attestation": "Invalid global activation attempt.",
            "idempotency_key": "idem-literature-runtime-global-router",
        },
        headers=scientist_headers,
    )
    assert global_activation_response.status_code == 422

    activation_response = await client.post(
        f"/api/v1/external-sources/overlays/{overlay['overlay_id']}/runtime-activations",
        json={
            "activation_scope": {"campaign_key": "frass-agronomy-review"},
            "operator_attestation": "Activate only for this campaign scope.",
            "idempotency_key": "idem-literature-runtime-activation-router",
        },
        headers=scientist_headers,
    )
    assert activation_response.status_code == 201
    activation = activation_response.json()
    assert activation["schema_version"] == "literature_value_runtime_activation_v1"
    assert activation["activation_id"].startswith("LVRA-")
    assert activation["overlay_id"] == overlay["overlay_id"]
    assert activation["activation_status"] == "active"
    assert activation["activation_scope"] == {"campaign_key": "frass-agronomy-review"}
    assert activation["scope_key"] == "campaign_key:frass-agronomy-review"
    assert activation["scoped_runtime_activation_enabled"] is True
    assert activation["global_activation_allowed"] is False
    assert activation["release_evidence_allowed"] is False
    assert activation["validated_default_write_enabled"] is False
    assert activation["final_action_execution"] is False
    assert activation["side_effects"]["scoped_runtime_activation"] is True
    assert activation["side_effects"]["global_runtime_activation"] is False
    assert "external literature overlay active for this scope" in activation["runtime_display"]

    repeated_activation_response = await client.post(
        f"/api/v1/external-sources/overlays/{overlay['overlay_id']}/runtime-activations",
        json={
            "activation_scope": {"campaign_key": "frass-agronomy-review"},
            "operator_attestation": "Activate only for this campaign scope.",
            "idempotency_key": "idem-literature-runtime-activation-router",
        },
        headers=scientist_headers,
    )
    assert repeated_activation_response.status_code == 201
    assert repeated_activation_response.json()["activation_id"] == activation["activation_id"]

    release_batch = Batch(
        batch_id="PHASE24-ROUTER-BATCH",
        species="BSF",
        dm_in=10.0,
        dm_out=7.5,
        user_id=scientist_user.id,
        tenant_id=test_tenant.id,
    )
    db_session.add(release_batch)
    await db_session.flush()
    release_decision = ReleaseDecision(
        batch_id=release_batch.id,
        user_id=scientist_user.id,
        tenant_id=test_tenant.id,
        decision="review_required",
        reason_codes=["literature_overlay_requires_human_review"],
        trigger_metrics={"literature_overlay": "linked"},
    )
    db_session.add(release_decision)
    await db_session.commit()
    await db_session.refresh(release_decision)

    release_link_response = await client.post(
        f"/api/v1/external-sources/release-decisions/{release_decision.id}/literature-value-release-evidence-links",
        json={
            "activation_id": activation["activation_id"],
            "link_notes": "Link active scoped literature overlay as evidence only.",
            "idempotency_key": "idem-literature-release-evidence-router",
        },
        headers=release_manager_headers,
    )
    assert release_link_response.status_code == 201
    release_link = release_link_response.json()
    assert release_link["schema_version"] == "literature_value_release_evidence_link_v1"
    assert release_link["link_id"].startswith("LVREL-")
    assert release_link["release_decision_id"] == release_decision.id
    assert release_link["activation_id"] == activation["activation_id"]
    assert release_link["overlay_id"] == overlay["overlay_id"]
    assert release_link["release_decision_before"] == "review_required"
    assert release_link["release_decision_after"] == "review_required"
    assert release_link["release_decision_unchanged"] is True
    assert release_link["human_review_required"] is True
    assert release_link["final_action_execution"] is False
    assert all(value is False for value in release_link["side_effects"].values())
    await db_session.refresh(release_decision)
    assert release_decision.decision == "review_required"

    conflicting_release_link_response = await client.post(
        f"/api/v1/external-sources/release-decisions/{release_decision.id}/literature-value-release-evidence-links",
        json={
            "activation_id": activation["activation_id"],
            "link_notes": "Conflicting notes for the same scoped activation evidence link.",
            "idempotency_key": "idem-literature-release-evidence-router",
        },
        headers=release_manager_headers,
    )
    assert conflicting_release_link_response.status_code == 409

    approved_release_batch = Batch(
        batch_id="PHASE27-ROUTER-APPROVED-BATCH",
        species="BSF",
        dm_in=11.0,
        dm_out=8.0,
        user_id=scientist_user.id,
        tenant_id=test_tenant.id,
    )
    db_session.add(approved_release_batch)
    await db_session.flush()
    approved_release_decision = ReleaseDecision(
        batch_id=approved_release_batch.id,
        user_id=scientist_user.id,
        tenant_id=test_tenant.id,
        decision="approved",
        reason_codes=["not_review_required"],
        trigger_metrics={"literature_overlay": "blocked"},
    )
    db_session.add(approved_release_decision)
    await db_session.commit()
    await db_session.refresh(approved_release_decision)

    non_review_required_link_response = await client.post(
        f"/api/v1/external-sources/release-decisions/{approved_release_decision.id}/literature-value-release-evidence-links",
        json={
            "activation_id": activation["activation_id"],
            "link_notes": "Attempt to link against non-review-required decision.",
            "idempotency_key": "idem-literature-release-evidence-non-review",
        },
        headers=release_manager_headers,
    )
    assert non_review_required_link_response.status_code == 400
    assert non_review_required_link_response.json()["detail"] == "literature_value_release_decision_must_remain_review_required"

    missing_activation_link_response = await client.post(
        f"/api/v1/external-sources/release-decisions/{release_decision.id}/literature-value-release-evidence-links",
        json={
            "activation_id": "LVRA-NOT-REAL",
            "link_notes": "Attempt to link a missing runtime activation.",
            "idempotency_key": "idem-literature-release-evidence-missing-activation",
        },
        headers=release_manager_headers,
    )
    assert missing_activation_link_response.status_code == 404
    assert missing_activation_link_response.json()["detail"] == "literature_value_runtime_activation_not_found"

    rollback_response = await client.post(
        f"/api/v1/external-sources/runtime-activations/{activation['activation_id']}/rollback",
        json={
            "rollback_reason": "Rollback scoped campaign evidence after release review.",
            "operator_attestation": "Rollback only deactivates scoped runtime and preserves review_required release decisions.",
            "idempotency_key": "idem-literature-runtime-rollback-router",
        },
        headers=scientist_headers,
    )
    assert rollback_response.status_code == 201
    rollback = rollback_response.json()
    assert rollback["schema_version"] == "literature_value_rollback_v1"
    assert rollback["rollback_id"].startswith("LVRB-")
    assert rollback["activation_id"] == activation["activation_id"]
    assert rollback["overlay_id"] == overlay["overlay_id"]
    assert rollback["activation_status_before"] == "active"
    assert rollback["activation_status_after"] == "deactivated"
    assert rollback["overlay_status_before"] == "inactive"
    assert rollback["overlay_status_after"] == "rolled_back"
    assert rollback["affected_release_evidence_link_ids"] == [release_link["link_id"]]
    assert rollback["release_evidence_link_status_updates"][0]["link_status_after"] == "rolled_back"
    assert rollback["release_decision_states"][0]["release_decision_before"] == "review_required"
    assert rollback["release_decision_states"][0]["release_decision_after"] == "review_required"
    assert rollback["release_decision_unchanged"] is True
    assert rollback["human_review_required"] is True
    assert rollback["final_action_execution"] is False
    assert rollback["side_effects"]["runtime_deactivation"] is True
    assert rollback["side_effects"]["overlay_status_update"] is True
    assert rollback["side_effects"]["release_evidence_link_status_update"] is True
    assert rollback["side_effects"]["release_decision_update"] is False
    assert rollback["side_effects"]["species_db_write"] is False
    assert rollback["side_effects"]["feedstock_db_write"] is False
    await db_session.refresh(release_decision)
    assert release_decision.decision == "review_required"

    activation_preview_after_rollback_response = await client.get(
        f"/api/v1/external-sources/overlays/{overlay['overlay_id']}/activation-preview",
        headers=operator_headers,
    )
    assert activation_preview_after_rollback_response.status_code == 200
    activation_preview_after_rollback = activation_preview_after_rollback_response.json()
    assert activation_preview_after_rollback["overlay_status"] == "rolled_back"
    assert activation_preview_after_rollback["can_activate_scoped_runtime"] is False

    repeated_rollback_response = await client.post(
        f"/api/v1/external-sources/runtime-activations/{activation['activation_id']}/rollback",
        json={
            "rollback_reason": "Rollback scoped campaign evidence after release review.",
            "operator_attestation": "Rollback only deactivates scoped runtime and preserves review_required release decisions.",
            "idempotency_key": "idem-literature-runtime-rollback-router",
        },
        headers=scientist_headers,
    )
    assert repeated_rollback_response.status_code == 201
    assert repeated_rollback_response.json()["rollback_id"] == rollback["rollback_id"]

    inactive_activation_link_response = await client.post(
        f"/api/v1/external-sources/release-decisions/{release_decision.id}/literature-value-release-evidence-links",
        json={
            "activation_id": activation["activation_id"],
            "link_notes": "Attempt to link rolled-back activation.",
            "idempotency_key": "idem-literature-release-evidence-inactive",
        },
        headers=release_manager_headers,
    )
    assert inactive_activation_link_response.status_code == 400
    assert inactive_activation_link_response.json()["detail"] == "literature_value_release_evidence_requires_active_scoped_activation"

    lifecycle_response = await client.get(
        f"/api/v1/external-sources/literature-extraction-candidates/{literature_candidate_id}/promotion-lifecycle",
        headers=operator_headers,
    )
    assert lifecycle_response.status_code == 200
    lifecycle = lifecycle_response.json()
    assert lifecycle["schema_version"] == "literature_value_promotion_lifecycle_v1"
    assert lifecycle["promotion_request_ids"] == [promotion_request["promotion_request_id"]]
    assert lifecycle["approval_ids"] == [
        promotion_approval["approval_id"],
        second_promotion_approval["approval_id"],
    ]
    assert lifecycle["overlay_ids"] == [overlay["overlay_id"]]
    assert lifecycle["activation_ids"] == [activation["activation_id"]]
    assert lifecycle["release_evidence_link_ids"] == [release_link["link_id"]]
    assert lifecycle["rollback_ids"] == [rollback["rollback_id"]]
    assert lifecycle["request_statuses"] == ["approved_for_promotion"]
    assert lifecycle["overlay_statuses"] == ["rolled_back"]
    assert lifecycle["activation_statuses"] == ["deactivated"]
    assert lifecycle["release_evidence_link_statuses"] == ["rolled_back"]
    assert lifecycle["rollback_statuses"] == ["completed"]
    assert lifecycle["release_decision_unchanged"] is True
    assert lifecycle["human_review_required"] is True
    assert lifecycle["final_action_execution"] is False
    assert all(value is False for value in lifecycle["side_effects"].values())
    assert all(
        state["release_decision_before"] == "review_required"
        and state["release_decision_after"] == "review_required"
        for state in lifecycle["release_decision_states"]
    )
    assert "promotion_lifecycle_is_read_only" in lifecycle["guardrails"]

    audit_export_response = await client.get(
        f"/api/v1/external-sources/literature-extraction-candidates/{literature_candidate_id}/promotion-audit/export",
        headers=operator_headers,
    )
    assert audit_export_response.status_code == 200
    audit_export = audit_export_response.json()
    assert audit_export["schema_version"] == "literature_value_promotion_audit_export_v1"
    assert audit_export["export_format"] == "json"
    assert audit_export["export_policy"] == "response_only_no_file_write"
    assert audit_export["export_manifest"]["export_policy"] == "response_only_no_file_write"
    assert audit_export["export_manifest"]["file_written"] is False
    assert audit_export["export_manifest"]["content_hash"] == audit_export["content_hash"]
    assert len(audit_export["content_hash"]) == 64
    assert audit_export["request"]["promotion_request_id"] == promotion_request["promotion_request_id"]
    assert [approval["approval_id"] for approval in audit_export["approvals"]] == [
        promotion_approval["approval_id"],
        second_promotion_approval["approval_id"],
    ]
    assert audit_export["overlay"]["overlay_id"] == overlay["overlay_id"]
    assert audit_export["runtime_activation"]["activation_id"] == activation["activation_id"]
    assert audit_export["release_evidence_link"]["link_id"] == release_link["link_id"]
    assert audit_export["rollback"]["rollback_id"] == rollback["rollback_id"]
    assert audit_export["db_pollution_proof"]["species_db_write"] is False
    assert audit_export["db_pollution_proof"]["feedstock_db_write"] is False
    assert audit_export["db_pollution_proof"]["validated_default_write"] is False
    assert audit_export["db_pollution_proof"]["candidate_id_present_in_species_db"] is False
    assert audit_export["db_pollution_proof"]["candidate_id_present_in_feedstock_db"] is False
    assert audit_export["final_action_non_execution_proof"]["final_action_execution"] is False
    assert audit_export["final_action_non_execution_proof"]["release_auto_approval"] is False
    assert audit_export["final_action_non_execution_proof"]["release_decision_update"] is False
    assert audit_export["final_action_non_execution_proof"]["release_decisions_all_review_required"] is True
    assert all(
        state["release_decision_before"] == "review_required"
        and state["release_decision_after"] == "review_required"
        for state in audit_export["final_action_non_execution_proof"]["release_decision_states"]
    )
    assert all(value is False for value in audit_export["side_effects"].values())
    assert "promotion_audit_export_is_response_only" in audit_export["guardrails"]

    lifecycle_after_audit_export_response = await client.get(
        f"/api/v1/external-sources/literature-extraction-candidates/{literature_candidate_id}/promotion-lifecycle",
        headers=operator_headers,
    )
    assert lifecycle_after_audit_export_response.status_code == 200
    lifecycle_after_audit_export = lifecycle_after_audit_export_response.json()
    assert lifecycle_after_audit_export["promotion_request_ids"] == lifecycle["promotion_request_ids"]
    assert lifecycle_after_audit_export["approval_ids"] == lifecycle["approval_ids"]
    assert lifecycle_after_audit_export["overlay_ids"] == lifecycle["overlay_ids"]
    assert lifecycle_after_audit_export["activation_ids"] == lifecycle["activation_ids"]
    assert lifecycle_after_audit_export["release_evidence_link_ids"] == lifecycle["release_evidence_link_ids"]
    assert lifecycle_after_audit_export["rollback_ids"] == lifecycle["rollback_ids"]
    await db_session.refresh(release_decision)
    assert release_decision.decision == "review_required"

    rejected_request_response = await client.post(
        f"/api/v1/external-sources/literature-extraction-candidates/{literature_candidate_id}/promotion-requests",
        json={
            "target_use": "candidate_overlay_review",
            "target_scope": {"campaign_key": "frass-agronomy-rejected-review"},
            "idempotency_key": "idem-literature-promotion-router-rejected",
        },
        headers=operator_headers,
    )
    assert rejected_request_response.status_code == 201
    rejected_request = rejected_request_response.json()
    reject_response = await client.post(
        f"/api/v1/external-sources/promotion-requests/{rejected_request['promotion_request_id']}/reject",
        json={
            "rejector_notes": "Reject this candidate promotion request without creating overlay or runtime state.",
            "idempotency_key": "idem-literature-promotion-router-reject",
        },
        headers=scientist_headers,
    )
    assert reject_response.status_code == 201
    rejected_approval = reject_response.json()
    assert rejected_approval["approval_action"] == "reject"
    assert rejected_approval["request_status_before"] == "requested"
    assert rejected_approval["request_status_after"] == "rejected"
    assert all(value is False for value in rejected_approval["side_effects"].values())

    rejected_request_readiness_response = await client.get(
        f"/api/v1/external-sources/literature-extraction-candidates/{literature_candidate_id}/promotion-readiness",
        headers=operator_headers,
    )
    assert rejected_request_readiness_response.status_code == 200
    assert rejected_request_readiness_response.json()["request_status"] == "rejected"

    literature_after_draft_response = await client.get(
        "/api/v1/external-sources/literature-extraction-candidates",
        headers=operator_headers,
    )
    assert literature_after_draft_response.status_code == 200
    literature_after_draft = literature_after_draft_response.json()
    after_draft_candidate = {
        item["candidate_id"]: item
        for item in literature_after_draft["items"]
    }[literature_candidate_id]
    assert after_draft_candidate["review_status"] == "pending_review"
    assert after_draft_candidate["release_evidence_allowed"] is False
    assert after_draft_candidate["runtime_activation_enabled"] is False
    assert after_draft_candidate["validated_default_write_enabled"] is False
    assert after_draft_candidate["promotion_enabled"] is False

    missing_literature_export_response = await client.get(
        "/api/v1/external-sources/literature-extraction-candidates/LIT-NOT-REAL/review-packet/export",
        headers=operator_headers,
    )
    assert missing_literature_export_response.status_code == 404
    missing_audit_export_response = await client.get(
        "/api/v1/external-sources/literature-extraction-candidates/LIT-NOT-REAL/promotion-audit/export",
        headers=operator_headers,
    )
    assert missing_audit_export_response.status_code == 404

    feedstock_dataset_response = await client.get(
        "/api/v1/external-sources/feedstock-dataset-candidates",
        headers=operator_headers,
    )
    assert feedstock_dataset_response.status_code == 200
    feedstock_dataset_payload = feedstock_dataset_response.json()
    assert feedstock_dataset_payload["count"] >= 9
    assert "no_feedstock_db_writes" in feedstock_dataset_payload["guardrails"]
    assert all(item["candidate_type"] == "feedstock_dataset_candidate" for item in feedstock_dataset_payload["items"])
    assert all(item["numeric_values_included"] is False for item in feedstock_dataset_payload["items"])
    assert all(item["runtime_activated"] is False for item in feedstock_dataset_payload["items"])
    assert all(item["validated_default_write_enabled"] is False for item in feedstock_dataset_payload["items"])
    assert any(item["source_id"].startswith("B-FEED-") for item in feedstock_dataset_payload["items"])

    source_detail_response = await client.get("/api/v1/external-sources/catalog/A-BSF-002", headers=operator_headers)
    assert source_detail_response.status_code == 200
    assert source_detail_response.json()["source_id"] == "A-BSF-002"

    cards_response = await client.get("/api/v1/external-sources/review-cards", headers=operator_headers)
    assert cards_response.status_code == 200
    cards_payload = cards_response.json()
    assert cards_payload["count"] == 8
    assert all(card["review_status"] == "pending_review" for card in cards_payload["items"])

    extractions_response = await client.get("/api/v1/external-sources/extractions", headers=operator_headers)
    assert extractions_response.status_code == 200
    extractions_payload = extractions_response.json()
    assert extractions_payload["count"] == 8
    assert all(item["numeric_values_included"] is False for item in extractions_payload["items"])

    extraction_detail_response = await client.get(
        "/api/v1/external-sources/extractions/EXT-BSF-CARD-001",
        headers=operator_headers,
    )
    assert extraction_detail_response.status_code == 200
    assert extraction_detail_response.json()["card_id"] == "BSF-CARD-001"

    resolve_response = await client.post(
        "/api/v1/external-sources/review-cards/BSF-CARD-001/resolve",
        headers=scientist_headers,
        json={
            "reviewer": "Dr. Reviewer",
            "reviewed_at": datetime.now(UTC).isoformat(),
            "license_status": "metadata_only",
            "boundary_condition": "Metadata-only candidate boundary reviewed; no numeric table reuse.",
            "allowed_use": "reviewed candidate metadata for future activation review",
            "blocked_use": "no validated defaults; no release evidence; no runtime activation",
            "candidate_payload": {"review_scope": "api_flow"},
        },
    )
    assert resolve_response.status_code == 200
    resolved = resolve_response.json()
    assert resolved["created_reviewed_candidate"] is True
    assert resolved["reviewed_candidate"]["runtime_activated"] is False
    assert resolved["reviewed_candidate"]["validated_default_write_enabled"] is False
    assert resolved["reviewed_candidate"]["candidate_payload"]["payload_version"] == "bsf-reviewed-metadata-v1"
    assert resolved["reviewed_candidate"]["candidate_payload"]["numeric_values_included"] is False

    lca_resolve_response = await client.post(
        "/api/v1/external-sources/review-cards/BSF-CARD-002/resolve",
        headers=scientist_headers,
        json={
            "reviewer": "Dr. Reviewer",
            "reviewed_at": datetime.now(UTC).isoformat(),
            "license_status": "metadata_only",
            "boundary_condition": "LCA factor metadata boundary only; no numeric factor extraction.",
            "allowed_use": "reviewed candidate metadata for future activation review",
            "blocked_use": "no validated defaults; no release evidence; no runtime activation",
            "candidate_type": "lca_factor_candidate",
            "candidate_payload": {"review_scope": "lca_factor_metadata_only"},
        },
    )
    assert lca_resolve_response.status_code == 200
    lca_resolved = lca_resolve_response.json()
    assert lca_resolved["created_reviewed_candidate"] is True
    assert lca_resolved["reviewed_candidate"]["candidate_type"] == "lca_factor_candidate"
    assert lca_resolved["reviewed_candidate"]["candidate_type_group"] == "reviewed_metadata_candidate"
    assert lca_resolved["reviewed_candidate"]["candidate_domain"] == "lca"
    assert lca_resolved["reviewed_candidate"]["promotion_enabled"] is False
    assert lca_resolved["reviewed_candidate"]["runtime_activated"] is False
    assert lca_resolved["reviewed_candidate"]["validated_default_write_enabled"] is False
    assert lca_resolved["reviewed_candidate"]["candidate_payload"]["payload_version"] == "reviewed-metadata-candidate-v1"
    assert lca_resolved["reviewed_candidate"]["candidate_payload"]["candidate_domain"] == "lca"
    assert lca_resolved["reviewed_candidate"]["candidate_payload"]["metadata_only"] is True
    assert lca_resolved["reviewed_candidate"]["candidate_payload"]["read_only"] is True
    assert lca_resolved["reviewed_candidate"]["candidate_payload"]["numeric_values_included"] is False
    assert lca_resolved["reviewed_candidate"]["candidate_payload"]["extracted_numeric_values"] == {}

    candidates_response = await client.get("/api/v1/external-sources/reviewed-candidates", headers=operator_headers)
    assert candidates_response.status_code == 200
    candidates = candidates_response.json()
    assert candidates["count"] == 2
    assert candidates["total_count"] == 2
    assert candidates["offset"] == 0
    assert candidates["limit"] is None
    assert candidates["has_more"] is False
    assert candidates["candidate_types"] == {
        "bsf_reviewed_metadata_candidate": 1,
        "lca_factor_candidate": 1,
    }
    assert candidates["candidate_domains"] == {
        "bsf_metadata": 1,
        "lca": 1,
    }
    by_id = {item["candidate_id"]: item for item in candidates["items"]}
    assert by_id["REC-BSF-CARD-001"]["candidate_payload"]["reviewer_annotations"]["review_scope"] == "api_flow"
    assert by_id["REC-BSF-CARD-002"]["candidate_type_counts"] == {"lca_factor_candidate": 1}
    assert by_id["REC-BSF-CARD-002"]["candidate_domain_counts"] == {"lca": 1}

    lca_candidates_response = await client.get(
        "/api/v1/external-sources/reviewed-candidates?candidate_type=lca_factor_candidate",
        headers=operator_headers,
    )
    assert lca_candidates_response.status_code == 200
    lca_candidates = lca_candidates_response.json()
    assert lca_candidates["count"] == 1
    assert lca_candidates["candidate_types"] == {"lca_factor_candidate": 1}
    assert lca_candidates["candidate_domains"] == {"lca": 1}
    assert lca_candidates["items"][0]["candidate_id"] == "REC-BSF-CARD-002"

    paged_candidates_response = await client.get(
        "/api/v1/external-sources/reviewed-candidates?limit=1&offset=0",
        headers=operator_headers,
    )
    assert paged_candidates_response.status_code == 200
    paged_candidates = paged_candidates_response.json()
    assert paged_candidates["count"] == 1
    assert paged_candidates["total_count"] == 2
    assert paged_candidates["offset"] == 0
    assert paged_candidates["limit"] == 1
    assert paged_candidates["has_more"] is True
    assert "pagination_is_read_only" in paged_candidates["guardrails"]

    second_page_response = await client.get(
        "/api/v1/external-sources/reviewed-candidates?limit=1&offset=1",
        headers=operator_headers,
    )
    assert second_page_response.status_code == 200
    second_page = second_page_response.json()
    assert second_page["count"] == 1
    assert second_page["total_count"] == 2
    assert second_page["offset"] == 1
    assert second_page["limit"] == 1
    assert second_page["has_more"] is False

    lca_domain_candidates_response = await client.get(
        "/api/v1/external-sources/reviewed-candidates?candidate_domain=lca",
        headers=operator_headers,
    )
    assert lca_domain_candidates_response.status_code == 200
    assert lca_domain_candidates_response.json()["count"] == 1

    mismatched_filter_response = await client.get(
        "/api/v1/external-sources/reviewed-candidates?candidate_type=lca_factor_candidate&candidate_domain=tea",
        headers=operator_headers,
    )
    assert mismatched_filter_response.status_code == 400

    candidate_detail_response = await client.get(
        "/api/v1/external-sources/reviewed-candidates/REC-BSF-CARD-001",
        headers=operator_headers,
    )
    assert candidate_detail_response.status_code == 200
    assert candidate_detail_response.json()["candidate_payload"]["payload_version"] == "bsf-reviewed-metadata-v1"

    summary_response = await client.get("/api/v1/external-sources/reviewed-candidates/summary", headers=operator_headers)
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["reviewed_candidate_count"] == 2
    assert summary["reviewed_metadata_candidate_count"] == 2
    assert summary["pending_runtime_activation_count"] == 2
    assert summary["runtime_activated_count"] == 0
    assert summary["validated_default_write_enabled_count"] == 0
    assert summary["numeric_value_candidate_count"] == 0
    assert summary["candidate_types"] == {
        "bsf_reviewed_metadata_candidate": 1,
        "lca_factor_candidate": 1,
    }
    assert summary["candidate_domains"] == {
        "bsf_metadata": 1,
        "lca": 1,
    }

    lca_summary_response = await client.get(
        "/api/v1/external-sources/reviewed-candidates/summary?candidate_domain=lca",
        headers=operator_headers,
    )
    assert lca_summary_response.status_code == 200
    lca_summary = lca_summary_response.json()
    assert lca_summary["reviewed_candidate_count"] == 1
    assert lca_summary["candidate_types"] == {"lca_factor_candidate": 1}
    assert lca_summary["candidate_domains"] == {"lca": 1}
    assert lca_summary["pending_runtime_activation_count"] == 1

    knowledge_base_response = await client.get(
        "/api/v1/external-sources/reviewed-candidates/knowledge-base",
        headers=operator_headers,
    )
    assert knowledge_base_response.status_code == 200
    knowledge_base = knowledge_base_response.json()
    assert knowledge_base["schema_version"] == "reviewed_external_candidate_knowledge_base_v1"
    assert knowledge_base["status"] == "ready_for_review"
    assert knowledge_base["schema_ready"] is True
    assert knowledge_base["source_catalog_ready"] is True
    assert knowledge_base["phase4a_domain_metadata_ready"] is True
    assert {
        "bsf_reviewed_metadata_candidate",
        "lca_boundary_metadata_candidate",
        "species_metadata_candidate",
        "feedstock_metadata_candidate",
        "lca_factor_candidate",
        "tea_factor_candidate",
        "compliance_rule_candidate",
        "model_provider_capability_candidate",
        "github_reference_candidate",
    }.issubset(set(knowledge_base["supported_candidate_types"]))
    assert {
        "bsf_metadata",
        "lca",
        "tea",
        "compliance",
        "model_provider",
        "github_reference",
        "species_metadata",
        "feedstock_metadata",
    }.issubset(set(knowledge_base["supported_candidate_domains"]))
    assert knowledge_base["reviewed_candidate_count"] == 2
    assert knowledge_base["pending_runtime_activation_count"] == 2
    assert knowledge_base["runtime_activated_count"] == 0
    assert knowledge_base["validated_default_write_enabled_count"] == 0
    assert knowledge_base["numeric_value_candidate_count"] == 0
    assert knowledge_base["candidate_domains"] == {"bsf_metadata": 1, "lca": 1}
    assert knowledge_base["blockers"] == []
    assert "knowledge_base_summary_is_read_only" in knowledge_base["guardrails"]
    assert "no_species_db_writes" in knowledge_base["guardrails"]
    assert "no_feedstock_db_writes" in knowledge_base["guardrails"]
    assert "no_final_action_execution" in knowledge_base["guardrails"]

    review_packet_response = await client.get(
        "/api/v1/external-sources/reviewed-candidates/REC-BSF-CARD-002/review-packet",
        headers=operator_headers,
    )
    assert review_packet_response.status_code == 200
    review_packet = review_packet_response.json()
    assert review_packet["schema_version"] == "reviewed_external_candidate_review_packet_v1"
    assert review_packet["candidate"]["candidate_id"] == "REC-BSF-CARD-002"
    assert review_packet["candidate"]["candidate_type"] == "lca_factor_candidate"
    assert review_packet["candidate"]["candidate_domain"] == "lca"
    assert review_packet["candidate"]["promotion_enabled"] is False
    assert review_packet["candidate"]["runtime_activated"] is False
    assert review_packet["candidate"]["validated_default_write_enabled"] is False
    assert review_packet["candidate"]["candidate_payload"]["numeric_values_included"] is False
    assert review_packet["candidate"]["candidate_payload"]["extracted_numeric_values"] == {}
    assert review_packet["review_card"]["card_id"] == "BSF-CARD-002"
    assert review_packet["extraction"]["card_id"] == "BSF-CARD-002"
    assert review_packet["extraction"]["numeric_values_included"] is False
    assert review_packet["extraction"]["extracted_numeric_values"] == {}
    assert review_packet["source_trace"]["candidate_domain"] == "lca"
    assert review_packet["source_trace"]["runtime_activation_required_before_use"] is True
    assert review_packet["side_effects"] == {
        "runtime_activation": False,
        "validated_default_write": False,
        "species_db_write": False,
        "feedstock_db_write": False,
        "final_action_execution": False,
    }
    assert "review_packet_is_read_only" in review_packet["guardrails"]
    assert "no_final_action_execution" in review_packet["guardrails"]

    review_packet_export_response = await client.get(
        "/api/v1/external-sources/reviewed-candidates/REC-BSF-CARD-002/review-packet/export",
        headers=operator_headers,
    )
    assert review_packet_export_response.status_code == 200
    review_packet_export = review_packet_export_response.json()
    assert review_packet_export["schema_version"] == "reviewed_external_candidate_review_packet_export_v1"
    assert review_packet_export["export_format"] == "json"
    assert review_packet_export["export_filename"] == "REC-BSF-CARD-002-review-packet.json"
    assert len(review_packet_export["content_hash"]) == 64
    assert review_packet_export["export_manifest"]["candidate_id"] == "REC-BSF-CARD-002"
    assert review_packet_export["export_manifest"]["candidate_domain"] == "lca"
    assert review_packet_export["export_manifest"]["content_hash"] == review_packet_export["content_hash"]
    assert review_packet_export["export_manifest"]["export_policy"] == "response_only_no_file_write"
    assert review_packet_export["review_packet"]["candidate"]["candidate_id"] == "REC-BSF-CARD-002"
    assert review_packet_export["side_effects"] == {
        "file_written": False,
        "runtime_activation": False,
        "validated_default_write": False,
        "species_db_write": False,
        "feedstock_db_write": False,
        "final_action_execution": False,
    }
    assert "review_packet_export_is_read_only" in review_packet_export["guardrails"]
    assert "export_response_only_no_file_write" in review_packet_export["guardrails"]
    assert "no_final_action_execution" in review_packet_export["guardrails"]

    activation_preview_response = await client.get(
        "/api/v1/external-sources/reviewed-candidates/REC-BSF-CARD-002/activation-preview",
        headers=operator_headers,
    )
    assert activation_preview_response.status_code == 200
    activation_preview = activation_preview_response.json()
    assert activation_preview["schema_version"] == "reviewed_external_candidate_activation_preview_v1"
    assert activation_preview["candidate"]["candidate_id"] == "REC-BSF-CARD-002"
    assert activation_preview["activation_scope"]["tenant_scoped"] is True
    assert activation_preview["activation_scope"]["candidate_type"] == "lca_factor_candidate"
    assert activation_preview["activation_audit_contract"]["activation_audit_id_required"] is True
    assert activation_preview["activation_audit_contract"]["activation_execution_endpoint_enabled"] is False
    assert activation_preview["activation_audit_contract"]["release_evidence_allowed"] is False
    assert activation_preview["can_execute_activation"] is False
    assert activation_preview["runtime_overlay_preview_only"] is True
    assert activation_preview["rollback_required"] is True
    assert activation_preview["active_overlay_state"]["activation_required_before_runtime_use"] is True
    assert activation_preview["side_effects"] == {
        "runtime_activation": False,
        "validated_default_write": False,
        "species_db_write": False,
        "feedstock_db_write": False,
        "final_action_execution": False,
    }
    assert "activation_preview_is_read_only" in activation_preview["guardrails"]
    assert "no_final_action_execution" in activation_preview["guardrails"]

    runtime_readiness_response = await client.get(
        "/api/v1/external-sources/reviewed-candidates/REC-BSF-CARD-002/runtime-readiness",
        headers=operator_headers,
    )
    assert runtime_readiness_response.status_code == 200
    runtime_readiness = runtime_readiness_response.json()
    assert runtime_readiness["schema_version"] == "reviewed_external_candidate_runtime_readiness_v1"
    assert runtime_readiness["candidate"]["candidate_id"] == "REC-BSF-CARD-002"
    assert runtime_readiness["candidate"]["runtime_activated"] is False
    assert runtime_readiness["activation_scope"]["tenant_scoped"] is True
    assert runtime_readiness["activation_scope"]["candidate_type"] == "lca_factor_candidate"
    assert runtime_readiness["activation_scope"]["runtime_paths"] == ["lca.factor_runtime"]
    assert runtime_readiness["active_overlay_state"]["activation_required_before_runtime_use"] is True
    assert runtime_readiness["active_candidate_payload"] is None
    assert runtime_readiness["can_read_runtime_payload"] is False
    assert runtime_readiness["runtime_read_path_enabled"] is True
    assert runtime_readiness["rollback_required"] is True
    assert runtime_readiness["rollback_contract"]["rollback_execution_endpoint_enabled"] is False
    assert runtime_readiness["side_effects"] == {
        "runtime_activation": False,
        "runtime_rollback": False,
        "validated_default_write": False,
        "species_db_write": False,
        "feedstock_db_write": False,
        "final_action_execution": False,
    }
    assert "runtime_readiness_is_read_only" in runtime_readiness["guardrails"]
    assert "rollback_required" in runtime_readiness["guardrails"]
    assert "no_final_action_execution" in runtime_readiness["guardrails"]

    rollback_preview_response = await client.get(
        "/api/v1/external-sources/reviewed-candidates/REC-BSF-CARD-002/rollback-preview",
        headers=operator_headers,
    )
    assert rollback_preview_response.status_code == 200
    rollback_preview = rollback_preview_response.json()
    assert rollback_preview["schema_version"] == "reviewed_external_candidate_rollback_preview_v1"
    assert rollback_preview["candidate"]["candidate_id"] == "REC-BSF-CARD-002"
    assert rollback_preview["activation_scope"]["tenant_scoped"] is True
    assert rollback_preview["rollback_target_available"] is False
    assert rollback_preview["can_execute_rollback"] is False
    assert rollback_preview["rollback_preview_only"] is True
    assert rollback_preview["rollback_required"] is True
    assert rollback_preview["rollback_blockers"] == ["no_active_runtime_activation_to_rollback"]
    assert rollback_preview["rollback_contract"]["rollback_execution_endpoint_enabled"] is False
    assert rollback_preview["rollback_audit_packet"]["rollback_execution_endpoint_enabled"] is False
    assert rollback_preview["rollback_audit_packet"]["rollback_target_available"] is False
    assert rollback_preview["side_effects"] == {
        "runtime_activation": False,
        "runtime_rollback": False,
        "validated_default_write": False,
        "species_db_write": False,
        "feedstock_db_write": False,
        "final_action_execution": False,
    }
    assert "rollback_preview_is_read_only" in rollback_preview["guardrails"]
    assert "rollback_requires_separate_audit_execution" in rollback_preview["guardrails"]
    assert "no_final_action_execution" in rollback_preview["guardrails"]

    missing_review_packet_response = await client.get(
        "/api/v1/external-sources/reviewed-candidates/REC-NOT-REAL/review-packet",
        headers=operator_headers,
    )
    assert missing_review_packet_response.status_code == 404

    missing_review_packet_export_response = await client.get(
        "/api/v1/external-sources/reviewed-candidates/REC-NOT-REAL/review-packet/export",
        headers=operator_headers,
    )
    assert missing_review_packet_export_response.status_code == 404

    missing_activation_preview_response = await client.get(
        "/api/v1/external-sources/reviewed-candidates/REC-NOT-REAL/activation-preview",
        headers=operator_headers,
    )
    assert missing_activation_preview_response.status_code == 404

    missing_runtime_readiness_response = await client.get(
        "/api/v1/external-sources/reviewed-candidates/REC-NOT-REAL/runtime-readiness",
        headers=operator_headers,
    )
    assert missing_runtime_readiness_response.status_code == 404

    missing_rollback_preview_response = await client.get(
        "/api/v1/external-sources/reviewed-candidates/REC-NOT-REAL/rollback-preview",
        headers=operator_headers,
    )
    assert missing_rollback_preview_response.status_code == 404

    numeric_resolve_response = await client.post(
        "/api/v1/external-sources/review-cards/BSF-CARD-003/resolve",
        headers=scientist_headers,
        json={
            "reviewer": "Dr. Reviewer",
            "reviewed_at": datetime.now(UTC).isoformat(),
            "license_status": "metadata_only",
            "boundary_condition": "TEA factor metadata boundary only.",
            "allowed_use": "reviewed candidate metadata for future activation review",
            "blocked_use": "no validated defaults; no release evidence; no runtime activation",
            "candidate_type": "tea_factor_candidate",
            "numeric_values_included": True,
        },
    )
    assert numeric_resolve_response.status_code == 422

    non_candidate_actions = [
        ("BSF-CARD-004", "approve_metadata", "extracted_metadata", "metadata_only"),
        ("BSF-CARD-005", "request_license_clearance", "needs_license_clearance", "restricted"),
        ("BSF-CARD-006", "reject", "rejected", "blocked"),
    ]
    for card_id, review_action, expected_status, license_status in non_candidate_actions:
        action_response = await client.post(
            f"/api/v1/external-sources/review-cards/{card_id}/resolve",
            headers=scientist_headers,
            json={
                "review_action": review_action,
                "reviewer": "Dr. Reviewer",
                "reviewed_at": datetime.now(UTC).isoformat(),
                "license_status": license_status,
                "boundary_condition": "Reviewed metadata boundary only.",
                "allowed_use": "review workflow metadata only",
                "blocked_use": "no validated defaults; no release evidence; no runtime activation",
                "next_action": "Review action persisted without candidate creation.",
            },
        )
        assert action_response.status_code == 200
        action_payload = action_response.json()
        assert action_payload["review_card"]["review_action"] == review_action
        assert action_payload["review_card"]["review_status"] == expected_status
        assert action_payload["reviewed_candidate"] is None
        assert action_payload["created_reviewed_candidate"] is False

    candidates_after_actions_response = await client.get(
        "/api/v1/external-sources/reviewed-candidates",
        headers=operator_headers,
    )
    assert candidates_after_actions_response.status_code == 200
    assert candidates_after_actions_response.json()["count"] == 2


@pytest.mark.asyncio
async def test_phase4a_reviewed_candidate_fill_flow(
    client: AsyncClient,
    scientist_headers,
    operator_headers,
):
    fill_response = await client.post(
        "/api/v1/external-sources/phase4a/reviewed-candidates/fill",
        headers=scientist_headers,
    )
    assert fill_response.status_code == 201
    fill_payload = fill_response.json()
    assert fill_payload["source_count"] == 24
    assert fill_payload["reviewed_candidate_count"] == 24
    assert fill_payload["created_reviewed_candidate_count"] == 24
    assert fill_payload["updated_reviewed_candidate_count"] == 0
    assert fill_payload["candidate_domains"] == {
        "lca": 6,
        "tea": 6,
        "compliance": 5,
        "model_provider": 4,
        "github_reference": 3,
    }
    assert fill_payload["candidate_types"] == {
        "lca_factor_candidate": 6,
        "tea_factor_candidate": 6,
        "compliance_rule_candidate": 5,
        "model_provider_capability_candidate": 4,
        "github_reference_candidate": 3,
    }
    assert fill_payload["runtime_activated_count"] == 0
    assert fill_payload["validated_default_write_enabled_count"] == 0
    assert fill_payload["numeric_value_candidate_count"] == 0
    assert "no_species_db_writes" in fill_payload["guardrails"]
    assert "no_feedstock_db_writes" in fill_payload["guardrails"]

    candidates_response = await client.get("/api/v1/external-sources/reviewed-candidates?limit=30", headers=operator_headers)
    assert candidates_response.status_code == 200
    candidates = candidates_response.json()
    assert candidates["count"] == 24
    assert candidates["total_count"] == 24
    by_id = {candidate["candidate_id"]: candidate for candidate in candidates["items"]}
    assert by_id["REC-PHASE4A-C-LCA-010"]["candidate_type"] == "lca_factor_candidate"
    assert by_id["REC-PHASE4A-C-LCA-010"]["candidate_payload"]["metadata_only"] is True
    assert by_id["REC-PHASE4A-C-LCA-010"]["candidate_payload"]["read_only"] is True
    assert by_id["REC-PHASE4A-C-LCA-010"]["candidate_payload"]["numeric_values_included"] is False
    assert by_id["REC-PHASE4A-C-LCA-010"]["runtime_activated"] is False
    assert by_id["REC-PHASE4A-C-LCA-010"]["validated_default_write_enabled"] is False

    knowledge_base_response = await client.get(
        "/api/v1/external-sources/reviewed-candidates/knowledge-base",
        headers=operator_headers,
    )
    assert knowledge_base_response.status_code == 200
    knowledge_base = knowledge_base_response.json()
    assert knowledge_base["reviewed_candidate_count"] == 24
    assert knowledge_base["knowledge_coverage_ready"] is True
    assert knowledge_base["knowledge_coverage_percent"] == 100
    assert knowledge_base["source_metadata_coverage_percent"] == 100
    assert knowledge_base["business_knowledge_coverage_percent"] == 84.17
    assert knowledge_base["business_knowledge_coverage_percent"] < knowledge_base["source_metadata_coverage_percent"]
    business_groups = {group["group_key"]: group for group in knowledge_base["business_knowledge_coverage_groups"]}
    product_items = {
        item["item_key"]: item
        for item in business_groups["product_agronomy_outputs"]["items"]
    }
    germination_workflow = product_items["germination_rate"]["review_workflow"]
    assert germination_workflow["review_packet_id"] == "AGR-GERMINATION-RATE-REVIEW-PACKET"
    assert germination_workflow["review_state"] == "pending_review"
    assert germination_workflow["source_packet_persistence"] == "read_model_only"
    assert germination_workflow["reviewer_notes_required"] is True
    assert germination_workflow["approval_enabled"] is False
    assert germination_workflow["rejection_enabled"] is True
    assert germination_workflow["release_evidence_allowed"] is False
    assert germination_workflow["runtime_activation_enabled"] is False
    assert germination_workflow["validated_default_write_enabled"] is False
    assert germination_workflow["numeric_values_allowed"] is False
    agronomy_export_response = await client.get(
        "/api/v1/external-sources/business-knowledge/germination_rate/review-packet/export",
        headers=operator_headers,
    )
    assert agronomy_export_response.status_code == 200
    agronomy_export = agronomy_export_response.json()
    assert agronomy_export["schema_version"] == "business_knowledge_review_packet_export_v1"
    assert agronomy_export["export_format"] == "json"
    assert agronomy_export["export_filename"] == "AGR-GERMINATION-RATE-REVIEW-PACKET.json"
    assert len(agronomy_export["content_hash"]) == 64
    assert agronomy_export["export_manifest"]["item_key"] == "germination_rate"
    assert agronomy_export["export_manifest"]["group_key"] == "product_agronomy_outputs"
    assert agronomy_export["export_manifest"]["review_state"] == "pending_review"
    assert agronomy_export["export_manifest"]["source_packet_persistence"] == "read_model_only"
    assert agronomy_export["export_manifest"]["export_policy"] == "response_only_no_file_write"
    assert agronomy_export["review_packet"]["item"]["item_key"] == "germination_rate"
    assert agronomy_export["review_packet"]["review_workflow"]["release_evidence_allowed"] is False
    assert agronomy_export["review_packet"]["review_workflow"]["runtime_activation_enabled"] is False
    assert agronomy_export["review_packet"]["review_workflow"]["validated_default_write_enabled"] is False
    assert agronomy_export["review_packet"]["review_workflow"]["numeric_values_allowed"] is False
    assert agronomy_export["review_packet"]["source_trace"]["release_evidence_allowed"] is False
    assert agronomy_export["review_packet"]["source_trace"]["numeric_values_included"] is False
    assert agronomy_export["review_packet"]["candidate_payload"]["value"] is None
    assert agronomy_export["side_effects"] == {
        "file_written": False,
        "runtime_activation": False,
        "validated_default_write": False,
        "species_db_write": False,
        "feedstock_db_write": False,
        "numeric_value_extraction": False,
        "final_action_execution": False,
    }
    assert "export_response_only_no_file_write" in agronomy_export["guardrails"]
    missing_agronomy_export_response = await client.get(
        "/api/v1/external-sources/business-knowledge/organic_fertilizer_assay_metadata/review-packet/export",
        headers=operator_headers,
    )
    assert missing_agronomy_export_response.status_code == 404
    assert knowledge_base["pending_runtime_activation_count"] == 24
    assert knowledge_base["runtime_activated_count"] == 0
    assert knowledge_base["validated_default_write_enabled_count"] == 0
    assert knowledge_base["numeric_value_candidate_count"] == 0

    second_fill_response = await client.post(
        "/api/v1/external-sources/phase4a/reviewed-candidates/fill",
        headers=scientist_headers,
    )
    assert second_fill_response.status_code == 201
    second_fill = second_fill_response.json()
    assert second_fill["created_reviewed_candidate_count"] == 0
    assert second_fill["updated_reviewed_candidate_count"] == 24
    assert second_fill["reviewed_candidate_count"] == 24


@pytest.mark.asyncio
async def test_external_sources_seed_and_resolve_require_scientist_role(
    client: AsyncClient,
    operator_headers,
):
    seed_response = await client.post("/api/v1/external-sources/p0/seed", headers=operator_headers)
    assert seed_response.status_code == 403

    phase4a_seed_response = await client.post(
        "/api/v1/external-sources/phase4a/domain-metadata/seed",
        headers=operator_headers,
    )
    assert phase4a_seed_response.status_code == 403

    phase4a_fill_response = await client.post(
        "/api/v1/external-sources/phase4a/reviewed-candidates/fill",
        headers=operator_headers,
    )
    assert phase4a_fill_response.status_code == 403

    resolve_response = await client.post(
        "/api/v1/external-sources/review-cards/BSF-CARD-001/resolve",
        headers=operator_headers,
        json={
            "reviewer": "Operator",
            "reviewed_at": datetime.now(UTC).isoformat(),
            "license_status": "metadata_only",
            "boundary_condition": "Metadata boundary.",
            "allowed_use": "candidate metadata only",
            "blocked_use": "no validated defaults; no release evidence",
        },
    )
    assert resolve_response.status_code == 403

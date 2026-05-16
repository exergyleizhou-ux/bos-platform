import json
from pathlib import Path

from app.services.external_source_catalog_validator import (
    collect_external_source_catalog_errors,
    validate_external_source_catalog,
)


CATALOG_PATH = Path(__file__).resolve().parents[3] / "docs" / "knowledge" / "BOS_EXTERNAL_SOURCE_CATALOG_P0.md"
PHASE4A_SEEDS_PATH = Path(__file__).resolve().parents[3] / "docs" / "knowledge" / "BOS_PHASE4A_DOMAIN_METADATA_SEEDS.json"
PHASE4A_REVIEW_QUEUE_PATH = (
    Path(__file__).resolve().parents[3] / "docs" / "knowledge" / "BOS_PHASE4A_SOURCE_REVIEW_QUEUE.md"
)
PHASE4A_MANIFEST_PATH = (
    Path(__file__).resolve().parents[3] / "docs" / "knowledge" / "BOS_PHASE4A_THREAD_B_MANIFEST.json"
)
REPO_ROOT = Path(__file__).resolve().parents[3]

PHASE4A_DOMAIN_IDS = {
    "lca": {"C-LCA-010", "C-LCA-011", "C-LCA-012", "C-LCA-013", "C-LCA-014", "C-LCA-015"},
    "tea": {"D-TEA-008", "D-TEA-009", "D-TEA-010", "D-TEA-011", "D-TEA-012", "D-TEA-013"},
    "compliance": {"E-COMP-011", "E-COMP-012", "E-COMP-013", "E-COMP-014", "E-COMP-015"},
    "model": {"F-MODEL-017", "F-MODEL-018", "F-MODEL-019", "F-MODEL-020"},
    "oss": {"G-OSS-011", "G-OSS-012", "G-OSS-013"},
}


def _rows_by_id():
    rows = validate_external_source_catalog(CATALOG_PATH)
    return {row.source_id: row for row in rows}


def _phase4a_seed_artifact():
    return json.loads(PHASE4A_SEEDS_PATH.read_text(encoding="utf-8"))


def _phase4a_review_queue_text():
    return PHASE4A_REVIEW_QUEUE_PATH.read_text(encoding="utf-8")


def _phase4a_manifest():
    return json.loads(PHASE4A_MANIFEST_PATH.read_text(encoding="utf-8"))


def test_p0_external_source_catalog_has_expected_source_rows():
    rows = validate_external_source_catalog(CATALOG_PATH)

    assert len(rows) == 94
    assert collect_external_source_catalog_errors(rows) == []


def test_p0_external_source_catalog_keeps_validated_defaults_untouched():
    rows = validate_external_source_catalog(CATALOG_PATH)

    for row in rows:
        lowered = row.all_text.lower().replace("`", "")
        assert "write to species_db" not in lowered
        assert "write to feedstock_db" not in lowered
        assert "modify species_db" not in lowered
        assert "modify feedstock_db" not in lowered
        assert "promote into validated defaults" not in lowered
        assert "promote to validated defaults" not in lowered
        assert "insert as validated defaults" not in lowered


def test_cabi_compendium_is_metadata_only_literature_not_industry_reference():
    rows = _rows_by_id()
    cabi = rows["A-BSF-003"]

    assert cabi.source_name == "CABI Compendium: Hermetia illucens"
    assert cabi.source_kind == "peer_reviewed_literature"
    assert cabi.ingestion_mode == "metadata_only"
    assert cabi.source_kind != "industry_reference"


def test_restricted_sources_stay_metadata_only_or_manual_review_first():
    rows = _rows_by_id()
    restricted_ids = {
        "C-LCA-006",  # ecoinvent
        "C-LCA-008",  # IEA
        "D-TEA-006",  # market reports
        "D-TEA-012",  # Phase 4A market/offtake metadata
        "E-COMP-010",  # ISO
        "E-COMP-015",  # Phase 4A ISO metadata
        "C-LCA-014",  # Phase 4A openLCA catalog
        "C-LCA-015",  # Phase 4A ecoinvent metadata-only seed
        "A-BSF-006",  # ScienceDirect
        "A-BSF-008",  # SpringerLink
    }

    for source_id in restricted_ids:
        row = rows[source_id]
        assert row.ingestion_mode in {"metadata_only", "manual_review_first"}
        assert row.human_review_note.startswith("是")


def test_model_provider_rows_are_volatile_metadata_and_review_gated():
    rows = _rows_by_id()
    model_rows = [row for row in rows.values() if row.source_id.startswith("F-MODEL-")]

    assert len(model_rows) == 20
    for row in model_rows:
        assert row.ingestion_mode in {"metadata_only", "reference_only"}
        assert row.human_review_note.startswith("是")
        lowered = row.all_text.lower()
        assert "checked-date" in lowered or "checked_date" in lowered or "checked_at" in lowered


def test_phase4a_domain_metadata_seed_rows_are_present_and_review_gated():
    rows = _rows_by_id()

    for source_ids in PHASE4A_DOMAIN_IDS.values():
        assert source_ids <= set(rows)

    phase4a_rows = [rows[source_id] for source_ids in PHASE4A_DOMAIN_IDS.values() for source_id in source_ids]
    for row in phase4a_rows:
        lowered = row.all_text.lower()
        assert row.human_review_note.startswith("是")
        assert "checked_at" in lowered
        assert "metadata" in lowered
        assert "promotion_enabled=true" not in lowered
        assert "runtime_activated=true" not in lowered
        assert "validated_default_write_enabled=true" not in lowered


def test_phase4a_tea_rows_require_geography_currency_year_and_checked_at():
    rows = _rows_by_id()

    for source_id in PHASE4A_DOMAIN_IDS["tea"]:
        lowered = rows[source_id].all_text.lower()
        assert "geography" in lowered
        assert "currency_year" in lowered
        assert "checked_at" in lowered


def test_phase4a_compliance_threshold_candidates_stay_blocked_until_review():
    rows = _rows_by_id()

    for source_id in PHASE4A_DOMAIN_IDS["compliance"]:
        lowered = rows[source_id].all_text.lower()
        assert "threshold" in lowered
        assert "legal" in lowered
        assert "technical review" in lowered
        assert rows[source_id].ingestion_mode in {"metadata_only", "manual_review_first"}


def test_phase4a_oss_rows_block_production_code_import():
    rows = _rows_by_id()

    for source_id in PHASE4A_DOMAIN_IDS["oss"]:
        lowered = rows[source_id].all_text.lower()
        assert "no production code import" in lowered
        assert rows[source_id].ingestion_mode == "reference_only"


def test_phase4a_json_seed_artifact_matches_catalog_and_keeps_activation_disabled():
    rows = _rows_by_id()
    artifact = _phase4a_seed_artifact()
    records = artifact["records"]
    expected_ids = set().union(*PHASE4A_DOMAIN_IDS.values())

    assert artifact["promotion_enabled"] is False
    assert artifact["runtime_activated"] is False
    assert artifact["validated_default_write_enabled"] is False
    assert artifact["numeric_values_included"] is False
    assert {record["source_id"] for record in records} == expected_ids

    for record in records:
        catalog_row = rows[record["source_id"]]
        assert record["evidence_source_kind"] == catalog_row.source_kind
        assert record["ingestion_mode"] == catalog_row.ingestion_mode
        assert record["human_review_required"] is True
        assert "checked_at" in record["required_metadata"]
        assert "validated defaults" in record["blocked_use"]
        assert "release evidence" in record["blocked_use"]
        assert "runtime activation" in record["blocked_use"]


def test_phase4a_json_seed_artifact_has_domain_specific_required_metadata():
    artifact = _phase4a_seed_artifact()
    records = {record["source_id"]: record for record in artifact["records"]}

    for source_id in PHASE4A_DOMAIN_IDS["tea"]:
        required_metadata = set(records[source_id]["required_metadata"])
        assert {"geography", "currency_year", "checked_at"} <= required_metadata

    for source_id in PHASE4A_DOMAIN_IDS["compliance"]:
        blocked_use = records[source_id]["blocked_use"]
        assert "threshold extraction" in blocked_use or "standard text copying" in blocked_use

    for source_id in PHASE4A_DOMAIN_IDS["model"]:
        required_metadata = set(records[source_id]["required_metadata"])
        assert {"source_url", "provider", "checked_at", "reviewer"} <= required_metadata

    for source_id in PHASE4A_DOMAIN_IDS["oss"]:
        assert "production code import" in records[source_id]["blocked_use"]


def test_phase4a_review_queue_covers_every_seed_and_keeps_guardrails_closed():
    queue_text = _phase4a_review_queue_text()
    lowered = queue_text.lower().replace("`", "")
    expected_ids = set().union(*PHASE4A_DOMAIN_IDS.values())

    for source_id in expected_ids:
        assert source_id in queue_text

    for required_phrase in (
        "human_review_required=true",
        "numeric_values_included=false",
        "promotion_enabled=false",
        "runtime_activated=false",
        "validated_default_write_enabled=false",
    ):
        assert required_phrase in lowered

    assert "promotion_enabled=true" not in lowered
    assert "runtime_activated=true" not in lowered
    assert "validated_default_write_enabled=true" not in lowered
    assert "write to species_db" not in lowered
    assert "write to feedstock_db" not in lowered


def test_phase4a_review_queue_blocks_domain_specific_unsafe_uses():
    queue_text = _phase4a_review_queue_text().lower()

    for required_phrase in (
        "no numeric factor extraction",
        "no cost value extraction",
        "no threshold extraction",
        "no production routing",
        "no production code import",
    ):
        assert required_phrase in queue_text


def test_phase4a_thread_b_manifest_matches_catalog_seed_artifact_and_queue():
    rows = validate_external_source_catalog(CATALOG_PATH)
    seed_artifact = _phase4a_seed_artifact()
    queue_text = _phase4a_review_queue_text()
    manifest = _phase4a_manifest()
    expected_ids = set().union(*PHASE4A_DOMAIN_IDS.values())

    assert manifest["source_catalog"]["expected_rows"] == len(rows)
    assert manifest["metadata_seed_artifact"]["expected_records"] == len(seed_artifact["records"])
    assert manifest["review_queue"]["expected_queues"] == queue_text.count("| PHASE4A-")
    assert set().union(*[set(ids) for ids in manifest["domains"].values()]) == expected_ids

    for artifact in ("source_catalog", "policy_doc", "metadata_seed_artifact", "review_queue"):
        assert (REPO_ROOT / manifest[artifact]["path"]).exists()

    assert manifest["guardrails"]["human_review_required"] is True
    assert manifest["guardrails"]["numeric_values_included"] is False
    assert manifest["guardrails"]["promotion_enabled"] is False
    assert manifest["guardrails"]["runtime_activated"] is False
    assert manifest["guardrails"]["validated_default_write_enabled"] is False
    assert manifest["guardrails"]["species_db_write_enabled"] is False
    assert manifest["guardrails"]["feedstock_db_write_enabled"] is False
    assert manifest["guardrails"]["production_code_import_enabled"] is False


def test_phase4a_thread_b_manifest_preserves_thread_a_boundary():
    manifest = _phase4a_manifest()
    boundary = manifest["thread_a_boundary"]

    assert boundary["backend_contract_owned_by_thread_a"] is True
    assert boundary["thread_b_schema_service_router_changes"] is False
    assert boundary["thread_b_runtime_service_changes"] is False
    assert "test_external_source_catalog_p0.py" in manifest["acceptance_command"]
    assert "test_validate_external_source_catalog_p0_script.py" in manifest["acceptance_command"]

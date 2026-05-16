from scripts.validate_external_source_catalog_p0 import validate_artifacts


def test_validate_external_source_catalog_p0_script_summary():
    summary = validate_artifacts()

    assert summary["ok"] is True
    assert summary["catalog_rows"] == 94
    assert summary["shortlist_rows"] == 8
    assert summary["review_card_rows"] == 8
    assert summary["staged_metadata_records"] == 8
    assert summary["promotion_enabled"] is False
    assert summary["numeric_values_included"] is False
    assert summary["validated_default_write_enabled"] is False

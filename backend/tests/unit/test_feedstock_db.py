"""
BOS Pipeline v9.0 feedstock reference database unit tests.
"""

from app.engine.feedstock_db import (
    get_all_feedstock_candidates,
    get_all_feedstocks,
    get_feedstock,
    get_feedstock_candidate,
    get_feedstock_candidate_keys,
    get_feedstock_keys,
)


class TestFeedstockDB:
    def test_distillers_grains_exists(self):
        item = get_feedstock("distillers_grains")

        assert item is not None
        assert item.key == "distillers_grains"
        assert "Distillers" in item.display_name
        assert item.contamination_risk in {"low", "medium", "high", "critical"}
        assert len(item.references) >= 1

    def test_straw_sludge_blend_exists(self):
        item = get_feedstock("straw_sludge_blend")

        assert item is not None
        assert item.typical_cn_min == 9.25
        assert item.typical_cn_max == 15.51
        assert item.contamination_risk == "high"

    def test_tcm_residue_exists(self):
        item = get_feedstock("tcm_residue")

        assert item is not None
        assert "medicine" in item.display_name.lower() or "TCM" in item.display_name
        assert item.evidence_basis
        assert len(item.references) >= 1

    def test_get_feedstock_keys(self):
        keys = get_feedstock_keys()

        assert "distillers_grains" in keys
        assert "sewage_sludge" in keys
        assert "tcm_residue" in keys

    def test_get_all_feedstocks(self):
        items = get_all_feedstocks()

        assert len(items) >= 6

    def test_feedstock_candidates_are_review_gated(self):
        candidates = get_all_feedstock_candidates()
        keys = {candidate.key for candidate in candidates}

        assert {
            "distillers_grains",
            "brewery_spent_grains",
            "washed_kitchen_waste",
            "mixed_food_waste",
            "manure_sludge_high_risk",
        }.issubset(keys)
        for candidate in candidates:
            assert candidate.source_kind
            assert candidate.source_ref
            assert candidate.license_note
            assert candidate.ingestion_mode == "manual_review_first"
            assert candidate.human_review_required is True
            assert candidate.review_status == "pending_review"

    def test_feedstock_candidates_do_not_pollute_validated_lookup(self):
        assert get_feedstock_candidate("food_waste").key == "mixed_food_waste"
        assert get_feedstock("mixed_food_waste") is None
        assert "mixed_food_waste" not in get_feedstock_keys()
        assert "mixed_food_waste" in get_feedstock_candidate_keys()

    def test_feedstock_candidates_can_filter_review_status(self):
        pending = get_all_feedstock_candidates(review_status="pending_review")
        reviewed = get_all_feedstock_candidates(review_status="reviewed")

        assert pending
        assert reviewed == []

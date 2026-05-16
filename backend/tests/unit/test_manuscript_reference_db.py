"""
BOS Pipeline v9.0 manuscript reference database unit tests.
"""

from app.engine.manuscript_reference_db import (
    get_all_campaigns,
    get_campaign,
    get_campaign_keys,
)


class TestManuscriptReferenceDB:
    def test_core_tm_pb_campaign_exists(self):
        item = get_campaign("core_tm_pb_distillers_grains")

        assert item is not None
        assert item["species_chain"] == ("MW", "PB")
        assert item["key_parameters"]["ser"] == 0.68
        assert len(item["references"]) >= 1

    def test_bsf_portability_audit_exists(self):
        item = get_campaign("bsf_hal_portability_audit")

        assert item is not None
        assert item["species_chain"] == ("MW", "BSF")
        assert item["key_parameters"]["hydraulic_loading_ml_per_kg_dry"] == 4.0
        assert item["observed_outputs"]["classification"] == "PASS_WITH_GAIN"
        assert len(item["references"]) >= 1

    def test_straw_sludge_series_exists(self):
        item = get_campaign("straw_sludge_series")

        assert item is not None
        assert item["feedstocks"] == ("straw_sludge_blend",)
        assert item["key_parameters"]["initial_cn_range"] == [9.25, 15.51]

    def test_get_campaign_keys(self):
        keys = get_campaign_keys()

        assert "core_tm_pb_distillers_grains" in keys
        assert "tcm_residue_screen" in keys

    def test_get_all_campaigns(self):
        items = get_all_campaigns()

        assert len(items) >= 6

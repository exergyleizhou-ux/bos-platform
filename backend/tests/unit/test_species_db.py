"""
BOS Pipeline v9.0 species database unit tests.
"""

import pytest

from app.engine.species_db import (
    compare_species,
    get_all_bioexecutor_candidates,
    get_all_species,
    get_bioexecutor_candidate,
    get_optimal_ranges,
    get_species,
    get_species_codes,
    get_species_summary,
)


class TestSpeciesDB:
    """Tests for the species database module."""

    def test_get_bsf(self):
        """BSF species should exist and have expected properties."""
        sp = get_species("BSF")

        assert sp is not None
        assert sp.code == "BSF"
        assert sp.scientific_name == "Hermetia illucens"
        assert sp.common_name is not None
        assert sp.ser_typical > 0
        assert sp.development_days > 0
        assert sp.protein_content > 0
        assert sp.fat_content > 0

    def test_get_mealworm(self):
        """Mealworm species should exist."""
        sp = get_species("MW")
        if sp is None:
            sp = get_species("YMW")

        assert sp is not None
        assert "Tenebrio" in sp.scientific_name or "mealworm" in sp.common_name.lower()

    def test_get_mealworm_alias(self):
        """Yellow mealworm alias should resolve to the mealworm canonical species."""
        sp = get_species("YMW")

        assert sp is not None
        assert sp.code == "MW"
        assert sp.scientific_name == "Tenebrio molitor"

    def test_get_grub_species(self):
        """Protaetia brevitarsis / grub species should exist."""
        sp = get_species("PB")

        assert sp is not None
        assert sp.code == "PB"
        assert "Protaetia" in sp.scientific_name
        assert "Grub" in sp.common_name or "Chafer" in sp.common_name
        assert "straw_sludge_blend" in sp.best_fit_feedstocks

    def test_get_grub_alias(self):
        """Generic grub alias should resolve to the canonical PB species."""
        sp = get_species("GRUB")

        assert sp is not None
        assert sp.code == "PB"

    def test_get_unknown_species(self):
        """Unknown species code returns None."""
        assert get_species("NONEXISTENT_CODE") is None

    def test_get_all_species(self):
        """At least BSF should be present in the database."""
        all_sp = get_all_species()
        codes = [sp.code for sp in all_sp]

        assert len(all_sp) >= 3
        assert "BSF" in codes
        assert "MW" in codes
        assert "PB" in codes

    def test_get_species_codes(self):
        """Get all species codes."""
        codes = get_species_codes()

        assert isinstance(codes, list)
        assert len(codes) >= 1
        assert "BSF" in codes

    def test_get_optimal_ranges_bsf(self):
        """BSF optimal ranges include temperature and moisture."""
        ranges = get_optimal_ranges("BSF")

        assert ranges is not None
        assert "temperature" in ranges
        assert "moisture" in ranges

        temp_range = ranges["temperature"]
        assert "optimal_min" in temp_range
        assert "optimal_max" in temp_range
        assert temp_range["optimal_min"] < temp_range["optimal_max"]

    def test_get_optimal_ranges_unknown(self):
        """Unknown species returns None or empty."""
        ranges = get_optimal_ranges("NONEXISTENT")
        assert ranges is None or ranges == {}

    def test_compare_species(self):
        """Compare at least two species."""
        codes = get_species_codes()
        if len(codes) < 2:
            pytest.skip("Need at least 2 species for comparison")

        result = compare_species(codes[:2])

        assert len(result) == 2
        for item in result:
            assert "code" in item
            assert "ser_typical" in item

    def test_compare_with_invalid_code(self):
        """Comparison skips invalid codes gracefully."""
        result = compare_species(["BSF", "INVALID_CODE"])
        assert len(result) >= 1

    def test_get_species_summary(self):
        """Species summary includes key parameters."""
        summary = get_species_summary("BSF")

        assert summary is not None
        assert "code" in summary
        assert "scientific_name" in summary
        assert "parameters" in summary or "development_days" in summary
        assert "aliases" in summary
        assert "source_basis" in summary
        assert "notes" in summary
        assert "references" in summary
        assert len(summary["references"]) >= 1
        assert "best_fit_feedstocks" in summary
        assert "caution_feedstocks" in summary

    def test_bsf_temperature_range(self):
        """BSF optimal temperature should be roughly 25-32 degC."""
        ranges = get_optimal_ranges("BSF")
        temp = ranges["temperature"]

        assert temp["optimal_min"] >= 20.0
        assert temp["optimal_max"] <= 40.0
        assert temp["optimal_min"] < temp["optimal_max"]

    def test_bsf_moisture_range(self):
        """BSF optimal moisture should be roughly 60-80%."""
        ranges = get_optimal_ranges("BSF")
        moisture = ranges["moisture"]

        assert moisture["optimal_min"] >= 40.0
        assert moisture["optimal_max"] <= 90.0

    def test_lethal_thresholds(self):
        """BSF should have lethal temperature thresholds."""
        sp = get_species("BSF")

        assert sp.temp_lethal_low is not None
        assert sp.temp_lethal_high is not None
        assert sp.temp_lethal_low < sp.temp_lethal_high

    def test_bioexecutor_candidates_are_review_gated(self):
        """External bioexecutor seeds stay pending until human review promotes them."""
        candidates = get_all_bioexecutor_candidates()
        codes = {candidate.code for candidate in candidates}

        assert {"BSF", "MW", "PB"}.issubset(codes)
        for candidate in candidates:
            assert candidate.source_kind
            assert candidate.source_ref
            assert candidate.license_note
            assert candidate.ingestion_mode == "manual_review_first"
            assert candidate.human_review_required is True
            assert candidate.review_status == "pending_review"

    def test_bioexecutor_candidates_do_not_pollute_species_lookup(self):
        """Candidate-only aliases must not become validated species aliases."""
        assert get_bioexecutor_candidate("HERMETIA_ILLUCENS").code == "BSF"
        assert get_species("HERMETIA_ILLUCENS") is None

        validated_codes = set(get_species_codes())
        candidate_codes = {candidate.code for candidate in get_all_bioexecutor_candidates()}
        assert candidate_codes.issubset(validated_codes)

    def test_bioexecutor_candidates_can_filter_review_status(self):
        pending = get_all_bioexecutor_candidates(review_status="pending_review")
        reviewed = get_all_bioexecutor_candidates(review_status="reviewed")

        assert pending
        assert reviewed == []

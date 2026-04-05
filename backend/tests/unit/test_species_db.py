"""
BOS Pipeline v9.0 �� Species Database Unit Tests

Tests the species reference database module.
"""

import pytest

from app.engine.species_db import (
    get_species,
    get_all_species,
    get_species_codes,
    get_optimal_ranges,
    compare_species,
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

    def test_get_unknown_species(self):
        """Unknown species code returns None."""
        sp = get_species("NONEXISTENT_CODE")
        assert sp is None

    def test_get_all_species(self):
        """At least BSF should be in the database."""
        all_sp = get_all_species()

        assert len(all_sp) >= 1
        codes = [sp.code for sp in all_sp]
        assert "BSF" in codes

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

        # Should return at least BSF
        assert len(result) >= 1

    def test_get_species_summary(self):
        """Species summary includes all key parameters."""
        summary = get_species_summary("BSF")

        assert summary is not None
        assert "code" in summary
        assert "scientific_name" in summary
        assert "parameters" in summary or "development_days" in summary

    def test_bsf_temperature_range(self):
        """BSF optimal temperature should be roughly 25�C32��C."""
        ranges = get_optimal_ranges("BSF")
        temp = ranges["temperature"]

        assert temp["optimal_min"] >= 20.0
        assert temp["optimal_max"] <= 40.0
        assert temp["optimal_min"] < temp["optimal_max"]

    def test_bsf_moisture_range(self):
        """BSF optimal moisture should be roughly 60�C80%."""
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


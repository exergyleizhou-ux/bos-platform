"""Shared BOS benchmark case seed definitions."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models_bos import BenchmarkCaseRecord

DEFAULT_BENCHMARK_CASES: list[tuple[str, str, dict[str, Any], dict[str, Any]]] = [
    ("CASE-moisture_drift", "moisture_drift", {"scenario": "moisture_drift"}, {"max_ending_risk": 0.55}),
    ("CASE-temperature_spike", "temperature_spike", {"scenario": "temperature_spike"}, {"max_ending_risk": 0.65}),
    ("CASE-underfeeding", "underfeeding", {"scenario": "underfeeding"}, {"max_ending_risk": 0.7}),
    ("CASE-sensor_missingness", "sensor_missingness", {"scenario": "normal", "missingness": True}, {"audit_required": True}),
    (
        "CASE-bsf_mixed_food_waste",
        "bsf_mixed_food_waste",
        {"species": "BSF", "feedstock": "mixed_food_waste", "scenario": "normal", "expected_output": "larval_biomass_and_frass"},
        {"max_ending_risk": 0.62, "bioexecutor": "BSF"},
    ),
    (
        "CASE-tenebrio_brewery_spent_grains",
        "tenebrio_brewery_spent_grains",
        {"species": "Tenebrio molitor", "feedstock": "brewery_spent_grains", "scenario": "underfeeding", "expected_output": "mealworm_biomass"},
        {"max_ending_risk": 0.72, "bioexecutor": "Tenebrio molitor"},
    ),
    (
        "CASE-protaetia_distillers_grains",
        "protaetia_distillers_grains",
        {"species": "Protaetia brevitarsis", "feedstock": "distillers_grains", "scenario": "moisture_drift", "expected_output": "scarab_larval_biomass"},
        {"max_ending_risk": 0.78, "bioexecutor": "Protaetia brevitarsis"},
    ),
    (
        "CASE-vermicompost_food_waste_baseline",
        "vermicompost_food_waste_baseline",
        {"species": "vermicompost_baseline", "feedstock": "mixed_food_waste", "scenario": "temperature_spike", "expected_output": "compost_soil_amendment"},
        {"max_ending_risk": 0.82, "bioexecutor": "vermicompost baseline"},
    ),
    (
        "CASE-microbial_composting_food_waste_baseline",
        "microbial_composting_food_waste_baseline",
        {"species": "microbial_composting_baseline", "feedstock": "mixed_food_waste", "scenario": "normal", "expected_output": "stabilized_compost"},
        {"max_ending_risk": 0.8, "bioexecutor": "microbial composting baseline"},
    ),
    (
        "CASE-anaerobic_digestion_food_waste_baseline",
        "anaerobic_digestion_food_waste_baseline",
        {"species": "anaerobic_digestion_baseline", "feedstock": "mixed_food_waste", "scenario": "normal", "missingness": True, "expected_output": "biogas_and_digestate"},
        {"max_ending_risk": 0.84, "bioexecutor": "anaerobic digestion baseline"},
    ),
]


async def ensure_default_benchmark_cases(db: AsyncSession) -> list[BenchmarkCaseRecord]:
    cases: list[BenchmarkCaseRecord] = []
    for case_id, name, scenario_payload, expected_metrics in DEFAULT_BENCHMARK_CASES:
        record = await db.scalar(select(BenchmarkCaseRecord).where(BenchmarkCaseRecord.case_id == case_id))
        if record is None:
            record = BenchmarkCaseRecord(
                case_id=case_id,
                tenant_id=None,
                name=name,
                scenario_payload=scenario_payload,
                expected_metrics=expected_metrics,
            )
            db.add(record)
        cases.append(record)
    await db.flush()
    return cases

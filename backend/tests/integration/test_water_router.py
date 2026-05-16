"""
BOS Pipeline v9.0 Water Router Integration Tests

Tests the water footprint API endpoint.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models import Calculation


class TestWaterCompute:
    """Tests for POST /api/v1/water/compute."""

    @pytest.mark.asyncio
    async def test_water_compute_success(self, client: AsyncClient, admin_headers, scientist_headers, db_session):
        """Existing batches should compute and persist a water footprint result."""
        batch_resp = await client.post("/api/v1/batches", json={
            "batch_id": "WATER-TEST-001",
            "dm_in": 10.0,
            "dm_out": 2.3,
        }, headers=admin_headers)
        batch_id = batch_resp.json()["id"]

        response = await client.post("/api/v1/water/compute", json={
            "batch_id": batch_id,
            "dm_in": 10.0,
            "dm_out_larvae": 2.3,
            "process_water": 500.0,
            "cleaning_water": 25.0,
            "cooling_energy_kwh": 10.0,
            "protein_content": 42.0,
        }, headers=scientist_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total_water_liters"] > 0
        assert data["components"]["blue"] >= 0
        assert data["intensity"]["per_kg_larvae"] > 0

        calc = (
            await db_session.execute(
                select(Calculation).where(Calculation.batch_id == batch_id, Calculation.calc_type == "water")
            )
        ).scalar_one_or_none()
        assert calc is not None
        assert calc.status == "completed"

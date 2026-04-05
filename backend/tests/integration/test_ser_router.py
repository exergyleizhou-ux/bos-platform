"""
BOS Pipeline v9.0 �� SER Router Integration Tests

Tests the SER computation API endpoint.
"""

import pytest
from httpx import AsyncClient


class TestSERCompute:
    """Tests for POST /api/v1/ser/compute."""

    @pytest.mark.asyncio
    async def test_ser_compute_basic(self, client: AsyncClient, admin_headers):
        """Compute SER for a batch."""
        # Create batch first
        batch_resp = await client.post("/api/v1/batches", json={
            "batch_id": "SER-TEST-001",
            "dm_in": 10.0,
            "dm_out": 2.3,
        }, headers=admin_headers)
        batch_id = batch_resp.json()["id"]

        # Compute SER
        response = await client.post("/api/v1/ser/compute", json={
            "batch_id": batch_id,
            "dm_in": 10.0,
            "dm_out": 2.3,
        }, headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert "ser_value" in data
        assert data["ser_value"] == pytest.approx(0.23, abs=0.02)
        assert data["passed"] is True
        assert data["grade"] in ("A+", "A", "B", "C", "D", "F")

    @pytest.mark.asyncio
    async def test_ser_compute_with_nitrogen(self, client: AsyncClient, admin_headers):
        """SER with nitrogen balance."""
        batch_resp = await client.post("/api/v1/batches", json={
            "batch_id": "SER-TEST-002",
            "dm_in": 10.0,
            "dm_out": 2.3,
        }, headers=admin_headers)
        batch_id = batch_resp.json()["id"]

        response = await client.post("/api/v1/ser/compute", json={
            "batch_id": batch_id,
            "dm_in": 10.0,
            "dm_out": 2.3,
            "n_in": 50.0,
            "n_larvae": 30.0,
            "n_frass": 15.0,
        }, headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert "nitrogen_balance" in data

    @pytest.mark.asyncio
    async def test_ser_compute_requires_auth(self, client: AsyncClient):
        """Unauthenticated request returns 401."""
        response = await client.post("/api/v1/ser/compute", json={
            "batch_id": 1,
            "dm_in": 10.0,
            "dm_out": 2.3,
        })

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_ser_compute_invalid_dm(self, client: AsyncClient, admin_headers):
        """Invalid dm_in (zero or negative) returns 422."""
        response = await client.post("/api/v1/ser/compute", json={
            "batch_id": 1,
            "dm_in": 0.0,
            "dm_out": 2.3,
        }, headers=admin_headers)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_ser_response_has_recommendations(self, client: AsyncClient, admin_headers):
        """SER response includes recommendations list."""
        batch_resp = await client.post("/api/v1/batches", json={
            "batch_id": "SER-TEST-003",
            "dm_in": 10.0,
            "dm_out": 0.5,  # Very low �� should generate recommendations
        }, headers=admin_headers)
        batch_id = batch_resp.json()["id"]

        response = await client.post("/api/v1/ser/compute", json={
            "batch_id": batch_id,
            "dm_in": 10.0,
            "dm_out": 0.5,
        }, headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert "recommendations" in data
        assert isinstance(data["recommendations"], list)


class TestSERBatchCompute:
    """Tests for POST /api/v1/ser/compute-batch (batch-level compute)."""

    @pytest.mark.asyncio
    async def test_compute_from_batch(self, client: AsyncClient, admin_headers):
        """Compute SER directly from batch ID (server reads batch data)."""
        # Create batch with full data
        batch_resp = await client.post("/api/v1/batches", json={
            "batch_id": "SER-BATCH-001",
            "dm_in": 12.0,
            "dm_out": 2.8,
            "n_in": 60.0,
            "n_larvae": 35.0,
            "n_frass": 18.0,
        }, headers=admin_headers)
        batch_id = batch_resp.json()["id"]

        response = await client.post(
            f"/api/v1/ser/compute-batch/{batch_id}",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "ser_value" in data
        assert data["ser_value"] > 0

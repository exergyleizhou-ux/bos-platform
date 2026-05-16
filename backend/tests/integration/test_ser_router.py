"""
BOS Pipeline v9.0 — SER Router Integration Tests

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
            "dm_out": 0.5,  # Very low → should generate recommendations
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

    @pytest.mark.asyncio
    async def test_ser_compute_manual_without_batch_id(self, client: AsyncClient, admin_headers):
        """Manual SER compute should work even when batch_id is omitted."""
        response = await client.post("/api/v1/ser/compute", json={
            "dm_in": 10.0,
            "dm_out": 2.3,
            "n_in": 50.0,
            "n_larvae": 30.0,
            "n_frass": 15.0,
        }, headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["batch_id"] is None
        assert "ser_value" in data
        assert "computed_at" in data


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

    @pytest.mark.asyncio
    async def test_get_result_for_batch(self, client: AsyncClient, admin_headers):
        """Get latest SER result for a batch via read endpoint."""
        batch_resp = await client.post("/api/v1/batches", json={
            "batch_id": "SER-BATCH-RESULT-001",
            "dm_in": 9.0,
            "dm_out": 2.2,
        }, headers=admin_headers)
        batch_id = batch_resp.json()["id"]

        compute_resp = await client.post(
            f"/api/v1/ser/compute-batch/{batch_id}",
            headers=admin_headers,
        )
        assert compute_resp.status_code == 200

        response = await client.get(f"/api/v1/ser/result/batch/{batch_id}", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["batch_id"] == batch_id
        assert "grade" in data
        assert "computed_at" in data


class TestSERStatistics:
    """Tests for GET /api/v1/ser/statistics."""

    @pytest.mark.asyncio
    async def test_statistics_use_result_grading(self, client: AsyncClient, admin_headers):
        """Statistics should use the same user-facing grading as SER results."""
        batch_resp = await client.post("/api/v1/batches", json={
            "batch_id": "SER-STATS-F",
            "dm_in": 10.0,
            "dm_out": 0.8,
        }, headers=admin_headers)
        batch_id = batch_resp.json()["id"]

        compute_resp = await client.post("/api/v1/ser/compute", json={
            "batch_id": batch_id,
            "dm_in": 10.0,
            "dm_out": 0.8,
        }, headers=admin_headers)

        assert compute_resp.status_code == 200
        assert compute_resp.json()["grade"] == "F"

        response = await client.get("/api/v1/ser/statistics", headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["stats"]["grade_distribution"]["F"] >= 1

    @pytest.mark.asyncio
    async def test_history_endpoint(self, client: AsyncClient, admin_headers):
        """History endpoint returns paginated SER records."""
        batch_resp = await client.post("/api/v1/batches", json={
            "batch_id": "SER-HISTORY-001",
            "dm_in": 10.0,
            "dm_out": 2.0,
        }, headers=admin_headers)
        batch_id = batch_resp.json()["id"]

        compute_resp = await client.post(
            f"/api/v1/ser/compute-batch/{batch_id}",
            headers=admin_headers,
        )
        assert compute_resp.status_code == 200

        response = await client.get("/api/v1/ser/history?page=1&page_size=10", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["page"] == 1
        assert data["page_size"] == 10
        assert data["total"] >= 1

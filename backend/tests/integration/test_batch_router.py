"""
BOS Pipeline v9.0 �� Batch Router Integration Tests

Tests batch CRUD endpoints.
"""

import pytest
from httpx import AsyncClient


class TestListBatches:
    """Tests for GET /api/v1/batches."""

    @pytest.mark.asyncio
    async def test_list_empty(self, client: AsyncClient, admin_headers):
        """Empty tenant returns empty list."""
        response = await client.get("/api/v1/batches", headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    @pytest.mark.asyncio
    async def test_list_requires_auth(self, client: AsyncClient):
        """Unauthenticated request returns 401."""
        response = await client.get("/api/v1/batches")
        assert response.status_code == 401


class TestCreateBatch:
    """Tests for POST /api/v1/batches."""

    @pytest.mark.asyncio
    async def test_create_batch(self, client: AsyncClient, admin_headers):
        """Create a valid batch."""
        response = await client.post("/api/v1/batches", json={
            "batch_id": "TEST-BATCH-001",
            "species": "BSF",
            "dm_in": 10.0,
            "dm_out": 2.3,
            "temperature": 28.5,
            "moisture": 70.0,
            "operator": "Test User",
        }, headers=admin_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["batch_id"] == "TEST-BATCH-001"
        assert data["species"] == "BSF"
        assert data["dm_in"] == 10.0

    @pytest.mark.asyncio
    async def test_create_batch_minimal(self, client: AsyncClient, admin_headers):
        """Create a batch with only required fields."""
        response = await client.post("/api/v1/batches", json={
            "batch_id": "TEST-BATCH-002",
            "dm_in": 8.0,
            "dm_out": 1.5,
        }, headers=admin_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["species"] == "BSF"  # Default

    @pytest.mark.asyncio
    async def test_create_batch_invalid_dm(self, client: AsyncClient, admin_headers):
        """dm_in must be > 0."""
        response = await client.post("/api/v1/batches", json={
            "batch_id": "TEST-BAD",
            "dm_in": -1.0,
            "dm_out": 1.0,
        }, headers=admin_headers)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_batch_missing_required(self, client: AsyncClient, admin_headers):
        """Missing required fields return 422."""
        response = await client.post("/api/v1/batches", json={
            "species": "BSF",
        }, headers=admin_headers)

        assert response.status_code == 422


class TestGetBatch:
    """Tests for GET /api/v1/batches/{id}."""

    @pytest.mark.asyncio
    async def test_get_batch(self, client: AsyncClient, admin_headers):
        """Get a batch by ID."""
        # Create first
        create_resp = await client.post("/api/v1/batches", json={
            "batch_id": "TEST-GET-001",
            "dm_in": 10.0,
            "dm_out": 2.3,
        }, headers=admin_headers)
        batch_id = create_resp.json()["id"]

        # Retrieve
        response = await client.get(f"/api/v1/batches/{batch_id}", headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["batch_id"] == "TEST-GET-001"

    @pytest.mark.asyncio
    async def test_get_batch_not_found(self, client: AsyncClient, admin_headers):
        """Non-existent batch returns 404."""
        response = await client.get("/api/v1/batches/999999", headers=admin_headers)
        assert response.status_code == 404


class TestUpdateBatch:
    """Tests for PATCH /api/v1/batches/{id}."""

    @pytest.mark.asyncio
    async def test_update_batch(self, client: AsyncClient, admin_headers):
        """Update a batch's status."""
        # Create
        create_resp = await client.post("/api/v1/batches", json={
            "batch_id": "TEST-UPD-001",
            "dm_in": 10.0,
            "dm_out": 2.3,
        }, headers=admin_headers)
        batch_id = create_resp.json()["id"]

        # Update
        response = await client.patch(f"/api/v1/batches/{batch_id}", json={
            "status": "completed",
            "notes": "All done",
        }, headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"

    @pytest.mark.asyncio
    async def test_update_invalid_status(self, client: AsyncClient, admin_headers):
        """Invalid status value returns 422."""
        create_resp = await client.post("/api/v1/batches", json={
            "batch_id": "TEST-UPD-002",
            "dm_in": 10.0,
            "dm_out": 2.3,
        }, headers=admin_headers)
        batch_id = create_resp.json()["id"]

        response = await client.patch(f"/api/v1/batches/{batch_id}", json={
            "status": "invalid_status",
        }, headers=admin_headers)

        assert response.status_code == 422


class TestDeleteBatch:
    """Tests for DELETE /api/v1/batches/{id}."""

    @pytest.mark.asyncio
    async def test_delete_batch(self, client: AsyncClient, admin_headers):
        """Delete (archive) a batch."""
        create_resp = await client.post("/api/v1/batches", json={
            "batch_id": "TEST-DEL-001",
            "dm_in": 10.0,
            "dm_out": 2.3,
        }, headers=admin_headers)
        batch_id = create_resp.json()["id"]

        response = await client.delete(f"/api/v1/batches/{batch_id}", headers=admin_headers)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_not_found(self, client: AsyncClient, admin_headers):
        """Deleting non-existent batch returns 404."""
        response = await client.delete("/api/v1/batches/999999", headers=admin_headers)
        assert response.status_code == 404


class TestBatchPagination:
    """Tests for pagination and filtering."""

    @pytest.mark.asyncio
    async def test_pagination_params(self, client: AsyncClient, admin_headers):
        """Page and page_size query parameters work."""
        response = await client.get(
            "/api/v1/batches?page=1&page_size=5",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 5

    @pytest.mark.asyncio
    async def test_species_filter(self, client: AsyncClient, admin_headers):
        """Filter by species."""
        # Create BSF and MW batches
        await client.post("/api/v1/batches", json={
            "batch_id": "FILTER-BSF", "species": "BSF", "dm_in": 10.0, "dm_out": 2.3,
        }, headers=admin_headers)
        await client.post("/api/v1/batches", json={
            "batch_id": "FILTER-MW", "species": "MW", "dm_in": 5.0, "dm_out": 0.8,
        }, headers=admin_headers)

        response = await client.get(
            "/api/v1/batches?species=BSF",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["species"] == "BSF"

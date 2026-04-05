"""
BOS Pipeline v9.0 �� Digital Twin Router Integration Tests

Tests the digital twin API endpoints.
"""

import pytest
from httpx import AsyncClient


class TestCreateTwin:
    """Tests for POST /api/v1/twin."""

    @pytest.mark.asyncio
    async def test_create_twin(self, client: AsyncClient, admin_headers):
        """Create a digital twin."""
        response = await client.post("/api/v1/twin", json={
            "twin_id": "TWIN-TEST-001",
            "name": "Test Bioreactor Alpha",
            "species": "BSF",
            "parameters": {
                "mu_max": 0.025,
                "K_s": 5.0,
                "Y": 0.22,
                "k_death": 0.001,
                "T_env": 28.0,
                "M_env": 70.0,
            },
        }, headers=admin_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["twin_id"] == "TWIN-TEST-001"
        assert data["name"] == "Test Bioreactor Alpha"
        assert data["species"] == "BSF"
        assert data["is_active"] is True
        assert data["parameters"]["mu_max"] == 0.025

    @pytest.mark.asyncio
    async def test_create_twin_defaults(self, client: AsyncClient, admin_headers):
        """Create a twin with default parameters."""
        response = await client.post("/api/v1/twin", json={
            "twin_id": "TWIN-TEST-002",
            "name": "Default Twin",
        }, headers=admin_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["species"] == "BSF"  # Default
        assert data["parameters"] is not None

    @pytest.mark.asyncio
    async def test_create_twin_requires_auth(self, client: AsyncClient):
        """Unauthenticated request returns 401."""
        response = await client.post("/api/v1/twin", json={
            "twin_id": "TWIN-NOAUTH",
            "name": "No Auth Twin",
        })
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_twin_missing_name(self, client: AsyncClient, admin_headers):
        """Missing required name returns 422."""
        response = await client.post("/api/v1/twin", json={
            "twin_id": "TWIN-BAD",
        }, headers=admin_headers)
        assert response.status_code == 422


class TestGetTwin:
    """Tests for GET /api/v1/twin/{id}."""

    @pytest.mark.asyncio
    async def test_get_twin(self, client: AsyncClient, admin_headers):
        """Retrieve a twin by ID."""
        create_resp = await client.post("/api/v1/twin", json={
            "twin_id": "TWIN-GET-001",
            "name": "Fetchable Twin",
        }, headers=admin_headers)
        twin_id = create_resp.json()["id"]

        response = await client.get(f"/api/v1/twin/{twin_id}", headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["twin_id"] == "TWIN-GET-001"

    @pytest.mark.asyncio
    async def test_get_twin_not_found(self, client: AsyncClient, admin_headers):
        """Non-existent twin returns 404."""
        response = await client.get("/api/v1/twin/999999", headers=admin_headers)
        assert response.status_code == 404


class TestTwinSimulate:
    """Tests for POST /api/v1/twin/{id}/simulate."""

    @pytest.mark.asyncio
    async def test_simulate_twin(self, client: AsyncClient, admin_headers):
        """Run a simulation on a digital twin."""
        create_resp = await client.post("/api/v1/twin", json={
            "twin_id": "TWIN-SIM-001",
            "name": "Sim Twin",
            "parameters": {
                "mu_max": 0.025,
                "K_s": 5.0,
                "Y": 0.22,
                "k_death": 0.001,
                "T_env": 28.0,
                "M_env": 70.0,
            },
        }, headers=admin_headers)
        twin_id = create_resp.json()["id"]

        response = await client.post(f"/api/v1/twin/{twin_id}/simulate", json={
            "initial_biomass": 0.5,
            "initial_substrate": 10.0,
            "n_steps": 100,
            "dt": 1.0,
        }, headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert "trajectory" in data
        assert len(data["trajectory"]) > 0
        assert data["trajectory"][0]["biomass"] == pytest.approx(0.5, abs=0.1)
        assert data["final_state"]["biomass"] > 0

    @pytest.mark.asyncio
    async def test_simulate_twin_invalid_params(self, client: AsyncClient, admin_headers):
        """Invalid simulation params return 422."""
        create_resp = await client.post("/api/v1/twin", json={
            "twin_id": "TWIN-SIM-002",
            "name": "Sim Twin 2",
        }, headers=admin_headers)
        twin_id = create_resp.json()["id"]

        response = await client.post(f"/api/v1/twin/{twin_id}/simulate", json={
            "initial_biomass": -1.0,  # Invalid
            "initial_substrate": 10.0,
            "n_steps": 100,
        }, headers=admin_headers)

        assert response.status_code == 422


class TestTwinUpdate:
    """Tests for PATCH /api/v1/twin/{id}."""

    @pytest.mark.asyncio
    async def test_update_twin(self, client: AsyncClient, admin_headers):
        """Update twin parameters."""
        create_resp = await client.post("/api/v1/twin", json={
            "twin_id": "TWIN-UPD-001",
            "name": "Updatable Twin",
        }, headers=admin_headers)
        twin_id = create_resp.json()["id"]

        response = await client.patch(f"/api/v1/twin/{twin_id}", json={
            "name": "Updated Twin Name",
            "parameters": {"mu_max": 0.03},
        }, headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Twin Name"

    @pytest.mark.asyncio
    async def test_deactivate_twin(self, client: AsyncClient, admin_headers):
        """Deactivate a twin."""
        create_resp = await client.post("/api/v1/twin", json={
            "twin_id": "TWIN-DEACT-001",
            "name": "Deactivatable",
        }, headers=admin_headers)
        twin_id = create_resp.json()["id"]

        response = await client.patch(f"/api/v1/twin/{twin_id}", json={
            "is_active": False,
        }, headers=admin_headers)

        assert response.status_code == 200
        assert response.json()["is_active"] is False


class TestTwinList:
    """Tests for GET /api/v1/twin."""

    @pytest.mark.asyncio
    async def test_list_twins(self, client: AsyncClient, admin_headers):
        """List all twins for tenant."""
        # Create a twin first
        await client.post("/api/v1/twin", json={
            "twin_id": "TWIN-LIST-001",
            "name": "List Twin",
        }, headers=admin_headers)

        response = await client.get("/api/v1/twin", headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)

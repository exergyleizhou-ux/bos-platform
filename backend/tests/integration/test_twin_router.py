"""
BOS Pipeline v9.0 — Digital Twin Router Integration Tests

Tests the digital twin API endpoints.
"""

import pytest
from httpx import AsyncClient


def twin_create_payload(twin_id: str, name: str) -> dict:
    return {
        "twin_id": twin_id,
        "name": name,
        "species": "BSF",
        "config": {
            "description": f"{name} created by integration test",
        },
        "parameters": {
            "mu_max": 0.025,
            "K_s": 5.0,
            "Y": 0.22,
            "k_death": 0.001,
            "T_env": 28.0,
            "M_env": 70.0,
        },
    }


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

    @pytest.mark.asyncio
    async def test_operator_cannot_create_twin(self, client: AsyncClient, operator_headers):
        """Operator role should be blocked from twin creation."""
        response = await client.post(
            "/api/v1/twin",
            json=twin_create_payload("TWIN-OP-403", "Operator Blocked Twin"),
            headers=operator_headers,
        )

        assert response.status_code == 403
        assert "scientist" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_scientist_can_create_twin(self, client: AsyncClient, scientist_headers):
        """Scientist role should be allowed to create a twin."""
        response = await client.post(
            "/api/v1/twin",
            json=twin_create_payload("TWIN-SCI-201", "Scientist Created Twin"),
            headers=scientist_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["twin_id"] == "TWIN-SCI-201"
        assert data["user_id"] is not None
        assert data["config"]["description"] == "Scientist Created Twin created by integration test"


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

    @pytest.mark.asyncio
    async def test_operator_cannot_simulate_twin(self, client: AsyncClient, admin_headers, operator_headers):
        """Operator role should be blocked from simulation."""
        create_resp = await client.post(
            "/api/v1/twin",
            json=twin_create_payload("TWIN-SIM-OP-403", "Simulation RBAC Twin"),
            headers=admin_headers,
        )
        twin_id = create_resp.json()["id"]

        response = await client.post(
            f"/api/v1/twin/{twin_id}/simulate",
            json={
                "initial_biomass": 0.5,
                "initial_substrate": 10.0,
                "n_steps": 12,
                "dt": 1.0,
            },
            headers=operator_headers,
        )

        assert response.status_code == 403
        assert "scientist" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_scientist_can_simulate_twin(self, client: AsyncClient, scientist_headers):
        """Scientist role should be allowed to simulate twins."""
        create_resp = await client.post(
            "/api/v1/twin",
            json=twin_create_payload("TWIN-SIM-SCI-200", "Scientist Simulation Twin"),
            headers=scientist_headers,
        )
        twin_id = create_resp.json()["id"]

        response = await client.post(
            f"/api/v1/twin/{twin_id}/simulate",
            json={
                "initial_biomass": 0.5,
                "initial_substrate": 10.0,
                "initial_temperature": 27.5,
                "initial_moisture": 66.0,
                "n_steps": 12,
                "dt": 1.0,
                "inputs_schedule": [{"feed_rate": 0.15, "ventilation": 0.0, "heating": 0.0}],
            },
            headers=scientist_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["n_steps"] == 12
        assert len(data["trajectory"]) == 12
        assert data["final_state"]["timestamp_hours"] == pytest.approx(12.0)

    @pytest.mark.asyncio
    async def test_cannot_simulate_inactive_twin(self, client: AsyncClient, scientist_headers):
        """Inactive twins should reject simulation even for scientist users."""
        create_resp = await client.post(
            "/api/v1/twin",
            json=twin_create_payload("TWIN-SIM-INACTIVE-409", "Inactive Simulation Twin"),
            headers=scientist_headers,
        )
        twin_id = create_resp.json()["id"]

        deactivate_resp = await client.patch(
            f"/api/v1/twin/{twin_id}",
            json={"is_active": False},
            headers=scientist_headers,
        )
        assert deactivate_resp.status_code == 200
        assert deactivate_resp.json()["is_active"] is False

        simulate_resp = await client.post(
            f"/api/v1/twin/{twin_id}/simulate",
            json={
                "initial_biomass": 0.5,
                "initial_substrate": 10.0,
                "n_steps": 8,
                "dt": 1.0,
            },
            headers=scientist_headers,
        )

        assert simulate_resp.status_code == 409
        assert "re-activated" in simulate_resp.json()["detail"]


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

    @pytest.mark.asyncio
    async def test_delete_twin_via_twins_alias(self, client: AsyncClient, admin_headers):
        """DELETE /api/v1/twins/{id} should be supported for frontend compatibility."""
        create_resp = await client.post("/api/v1/twin", json={
            "twin_id": "TWIN-DEL-001",
            "name": "Deletable Twin",
        }, headers=admin_headers)
        twin_id = create_resp.json()["id"]

        delete_resp = await client.delete(f"/api/v1/twins/{twin_id}", headers=admin_headers)
        assert delete_resp.status_code == 200

        get_resp = await client.get(f"/api/v1/twins/{twin_id}", headers=admin_headers)
        assert get_resp.status_code == 404


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

    @pytest.mark.asyncio
    async def test_list_twins_can_filter_by_is_active(self, client: AsyncClient, scientist_headers):
        """List endpoints should support active/inactive filtering for the frontend twin filter rail."""
        active_resp = await client.post(
            "/api/v1/twins",
            json=twin_create_payload("TWIN-FILTER-ACTIVE", "Filter Active Twin"),
            headers=scientist_headers,
        )
        assert active_resp.status_code == 201
        active_id = active_resp.json()["id"]

        inactive_resp = await client.post(
            "/api/v1/twins",
            json=twin_create_payload("TWIN-FILTER-INACTIVE", "Filter Inactive Twin"),
            headers=scientist_headers,
        )
        assert inactive_resp.status_code == 201
        inactive_id = inactive_resp.json()["id"]

        deactivate_resp = await client.patch(
            f"/api/v1/twins/{inactive_id}",
            json={"is_active": False},
            headers=scientist_headers,
        )
        assert deactivate_resp.status_code == 200
        assert deactivate_resp.json()["is_active"] is False

        list_active = await client.get("/api/v1/twins?is_active=true&page_size=100", headers=scientist_headers)
        assert list_active.status_code == 200
        active_items = list_active.json()["items"]
        assert any(item["id"] == active_id for item in active_items)
        assert all(item["is_active"] is True for item in active_items)

        list_inactive = await client.get("/api/v1/twins?is_active=false&page_size=100", headers=scientist_headers)
        assert list_inactive.status_code == 200
        inactive_items = list_inactive.json()["items"]
        assert any(item["id"] == inactive_id for item in inactive_items)
        assert all(item["is_active"] is False for item in inactive_items)


class TestTwinAliasCompatibility:
    """Tests for frontend-facing /api/v1/twins alias routes."""

    @pytest.mark.asyncio
    async def test_create_twin_via_twins_alias(self, client: AsyncClient, scientist_headers):
        """POST /api/v1/twins should match the mounted /twin router behavior."""
        response = await client.post(
            "/api/v1/twins",
            json=twin_create_payload("TWIN-ALIAS-001", "Alias Created Twin"),
            headers=scientist_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["twin_id"] == "TWIN-ALIAS-001"
        assert data["name"] == "Alias Created Twin"

    @pytest.mark.asyncio
    async def test_list_and_get_twin_via_twins_alias(self, client: AsyncClient, scientist_headers):
        """GET /api/v1/twins and /api/v1/twins/{id} should serve frontend reads."""
        create_resp = await client.post(
            "/api/v1/twin",
            json=twin_create_payload("TWIN-ALIAS-002", "Alias Read Twin"),
            headers=scientist_headers,
        )
        twin_id = create_resp.json()["id"]

        list_resp = await client.get("/api/v1/twins?page=1&page_size=10", headers=scientist_headers)
        assert list_resp.status_code == 200
        list_payload = list_resp.json()
        assert any(item["id"] == twin_id for item in list_payload["items"])

        detail_resp = await client.get(f"/api/v1/twins/{twin_id}", headers=scientist_headers)
        assert detail_resp.status_code == 200
        detail_payload = detail_resp.json()
        assert detail_payload["id"] == twin_id
        assert detail_payload["twin_id"] == "TWIN-ALIAS-002"

    @pytest.mark.asyncio
    async def test_patch_and_simulate_twin_via_twins_alias(self, client: AsyncClient, scientist_headers):
        """PATCH and simulate over /api/v1/twins should match frontend expectations."""
        create_resp = await client.post(
            "/api/v1/twin",
            json=twin_create_payload("TWIN-ALIAS-003", "Alias Mutate Twin"),
            headers=scientist_headers,
        )
        twin_id = create_resp.json()["id"]

        patch_resp = await client.patch(
            f"/api/v1/twins/{twin_id}",
            json={
                "name": "Alias Mutate Twin Updated",
                "parameters": {"mu_max": 0.041},
            },
            headers=scientist_headers,
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["name"] == "Alias Mutate Twin Updated"
        assert patch_resp.json()["parameters"]["mu_max"] == pytest.approx(0.041)

        simulate_resp = await client.post(
            f"/api/v1/twins/{twin_id}/simulate",
            json={
                "initial_biomass": 0.5,
                "initial_substrate": 10.0,
                "n_steps": 8,
                "dt": 1.0,
            },
            headers=scientist_headers,
        )
        assert simulate_resp.status_code == 200
        simulate_payload = simulate_resp.json()
        assert simulate_payload["n_steps"] == 8
        assert len(simulate_payload["trajectory"]) == 8

    @pytest.mark.asyncio
    async def test_predict_and_update_twin_via_twins_alias(
        self,
        client: AsyncClient,
        scientist_headers,
        operator_headers,
    ):
        """Predict and observation update should also remain available through /api/v1/twins."""
        create_resp = await client.post(
            "/api/v1/twin",
            json=twin_create_payload("TWIN-ALIAS-004", "Alias Runtime Twin"),
            headers=scientist_headers,
        )
        twin_id = create_resp.json()["id"]

        predict_resp = await client.post(
            f"/api/v1/twins/{twin_id}/predict",
            json={
                "dt": 1.5,
                "inputs": {
                    "feed_rate": 0.12,
                    "ventilation": 0.15,
                    "heating": 0.05,
                },
            },
            headers=operator_headers,
        )
        assert predict_resp.status_code == 200
        predict_payload = predict_resp.json()
        assert "state" in predict_payload
        assert predict_payload["timestamp_hours"] == pytest.approx(1.5)

        update_resp = await client.post(
            f"/api/v1/twins/{twin_id}/update",
            json={
                "observations": {
                    "weight": 10.1,
                    "temperature": 27.3,
                    "moisture": 66.2,
                },
            },
            headers=operator_headers,
        )
        assert update_resp.status_code == 200
        update_payload = update_resp.json()
        assert "state" in update_payload
        assert isinstance(update_payload["innovation"], list)
        assert len(update_payload["innovation"]) == 3


class TestTwinRuntimeOperations:
    """Tests for predict and observation update runtime operations."""

    @pytest.mark.asyncio
    async def test_operator_can_predict_twin_step(self, client: AsyncClient, scientist_headers, operator_headers):
        """Operator role should be able to advance the twin by one predictive step."""
        create_resp = await client.post(
            "/api/v1/twin",
            json=twin_create_payload("TWIN-PREDICT-001", "Predict Twin"),
            headers=scientist_headers,
        )
        twin_id = create_resp.json()["id"]
        starting_version = create_resp.json()["version"]

        response = await client.post(
            f"/api/v1/twin/{twin_id}/predict",
            json={
                "dt": 2.0,
                "inputs": {
                    "feed_rate": 0.15,
                    "ventilation": 0.2,
                    "heating": 0.1,
                },
            },
            headers=operator_headers,
        )

        assert response.status_code == 200
        payload = response.json()
        assert "state" in payload
        assert payload["growth_rate"] >= 0
        assert payload["ser_instantaneous"] >= 0
        assert payload["timestamp_hours"] == pytest.approx(2.0)
        assert payload["version"] == starting_version + 1

    @pytest.mark.asyncio
    async def test_operator_can_apply_twin_observations(self, client: AsyncClient, scientist_headers, operator_headers):
        """Operator role should be able to correct the twin state with observations."""
        create_resp = await client.post(
            "/api/v1/twin",
            json=twin_create_payload("TWIN-OBS-001", "Observation Twin"),
            headers=scientist_headers,
        )
        twin_id = create_resp.json()["id"]

        predict_resp = await client.post(
            f"/api/v1/twin/{twin_id}/predict",
            json={
                "dt": 1.0,
                "inputs": {
                    "feed_rate": 0.1,
                    "ventilation": 0.1,
                    "heating": 0.0,
                },
            },
            headers=operator_headers,
        )
        assert predict_resp.status_code == 200
        predicted_version = predict_resp.json()["version"]

        response = await client.post(
            f"/api/v1/twin/{twin_id}/update",
            json={
                "observations": {
                    "weight": 10.2,
                    "temperature": 27.4,
                    "moisture": 66.5,
                },
            },
            headers=operator_headers,
        )

        assert response.status_code == 200
        payload = response.json()
        assert "state" in payload
        assert isinstance(payload["innovation"], list)
        assert len(payload["innovation"]) == 3
        assert payload["version"] == predicted_version + 1

    @pytest.mark.asyncio
    async def test_cannot_predict_inactive_twin(self, client: AsyncClient, scientist_headers, operator_headers):
        """Inactive twins should reject predictive control steps."""
        create_resp = await client.post(
            "/api/v1/twin",
            json=twin_create_payload("TWIN-PREDICT-INACTIVE-409", "Inactive Predict Twin"),
            headers=scientist_headers,
        )
        twin_id = create_resp.json()["id"]

        deactivate_resp = await client.patch(
            f"/api/v1/twin/{twin_id}",
            json={"is_active": False},
            headers=scientist_headers,
        )
        assert deactivate_resp.status_code == 200

        response = await client.post(
            f"/api/v1/twin/{twin_id}/predict",
            json={"dt": 1.0, "inputs": {"feed_rate": 0.1}},
            headers=operator_headers,
        )

        assert response.status_code == 409
        assert "re-activated" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_cannot_apply_observations_to_inactive_twin(
        self,
        client: AsyncClient,
        scientist_headers,
        operator_headers,
    ):
        """Inactive twins should reject observation updates."""
        create_resp = await client.post(
            "/api/v1/twin",
            json=twin_create_payload("TWIN-OBS-INACTIVE-409", "Inactive Observation Twin"),
            headers=scientist_headers,
        )
        twin_id = create_resp.json()["id"]

        deactivate_resp = await client.patch(
            f"/api/v1/twin/{twin_id}",
            json={"is_active": False},
            headers=scientist_headers,
        )
        assert deactivate_resp.status_code == 200

        response = await client.post(
            f"/api/v1/twin/{twin_id}/update",
            json={"observations": {"weight": 10.2, "temperature": 27.2, "moisture": 66.0}},
            headers=operator_headers,
        )

        assert response.status_code == 409
        assert "re-activated" in response.json()["detail"]

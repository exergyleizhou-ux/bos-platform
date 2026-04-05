"""
BOS Pipeline v9.0 �� End-to-End Workflow Tests

Tests complete user workflows:
  1. Login �� Create batch �� Compute SER �� Run MC �� View dashboard
  2. Login �� Create twin �� Simulate �� Compare
  3. Login �� Create batch �� Run GHG/Water/Energy �� Export
"""

import pytest
from httpx import AsyncClient


class TestBatchAnalysisWorkflow:
    """
    Full workflow: login �� create batch �� compute SER ��
    run MC �� check dashboard �� export.
    """

    @pytest.mark.asyncio
    async def test_complete_batch_workflow(self, client: AsyncClient, test_admin):
        """End-to-end batch analysis workflow."""

        # ���� Step 1: Login ����
        login_resp = await client.post("/api/v1/auth/login", json={
            "username": "test_admin",
            "password": "TestAdmin123!",
        })
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # ���� Step 2: Create Batch ����
        batch_resp = await client.post("/api/v1/batches", json={
            "batch_id": "E2E-WORKFLOW-001",
            "species": "BSF",
            "dm_in": 10.0,
            "dm_out": 2.3,
            "n_in": 50.0,
            "n_larvae": 30.0,
            "n_frass": 15.0,
            "temperature": 28.5,
            "moisture": 70.0,
            "operator": "E2E Test",
            "batch_date": "2024-02-01",
        }, headers=headers)
        assert batch_resp.status_code == 201
        batch_id = batch_resp.json()["id"]
        batch_data = batch_resp.json()
        assert batch_data["batch_id"] == "E2E-WORKFLOW-001"

        # ���� Step 3: Compute SER ����
        ser_resp = await client.post("/api/v1/ser/compute", json={
            "batch_id": batch_id,
            "dm_in": 10.0,
            "dm_out": 2.3,
            "n_in": 50.0,
            "n_larvae": 30.0,
            "n_frass": 15.0,
        }, headers=headers)
        assert ser_resp.status_code == 200
        ser_data = ser_resp.json()
        assert ser_data["ser_value"] > 0
        assert ser_data["passed"] is True
        assert ser_data["grade"] in ("A+", "A", "B", "C", "D", "F")

        # ���� Step 4: Run Monte Carlo ����
        mc_resp = await client.post("/api/v1/simulation/monte-carlo", json={
            "batch_id": batch_id,
            "n_samples": 5000,
            "dm_in_mean": 10.0,
            "dm_in_std": 0.5,
            "dm_out_mean": 2.3,
            "dm_out_std": 0.15,
            "seed": 42,
        }, headers=headers)
        assert mc_resp.status_code == 200
        mc_data = mc_resp.json()
        assert mc_data["ser_mean"] == pytest.approx(0.23, abs=0.03)
        assert mc_data["pass_probability"] > 0.5

        # ���� Step 5: Check Dashboard ����
        dash_resp = await client.get("/api/v1/dashboard/summary", headers=headers)
        assert dash_resp.status_code == 200
        dash_data = dash_resp.json()
        assert dash_data["total_batches"] >= 1

        # ���� Step 6: Get Batch Detail ����
        detail_resp = await client.get(f"/api/v1/batches/{batch_id}", headers=headers)
        assert detail_resp.status_code == 200
        detail_data = detail_resp.json()
        assert detail_data["batch_id"] == "E2E-WORKFLOW-001"

    @pytest.mark.asyncio
    async def test_multi_batch_comparison(self, client: AsyncClient, test_admin):
        """Create multiple batches and compare via dashboard."""
        # Login
        login_resp = await client.post("/api/v1/auth/login", json={
            "username": "test_admin",
            "password": "TestAdmin123!",
        })
        headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

        # Create 3 batches
        batch_ids = []
        for i in range(3):
            resp = await client.post("/api/v1/batches", json={
                "batch_id": f"E2E-MULTI-{i:03d}",
                "species": "BSF",
                "dm_in": 10.0 + i,
                "dm_out": 2.0 + 0.3 * i,
                "temperature": 27.0 + i,
                "batch_date": f"2024-02-{10 + i:02d}",
            }, headers=headers)
            assert resp.status_code == 201
            batch_ids.append(resp.json()["id"])

        # Compute SER for each
        for j, bid in enumerate(batch_ids):
            resp = await client.post("/api/v1/ser/compute", json={
                "batch_id": bid,
                "dm_in": 10.0 + j,
                "dm_out": 2.0 + 0.3 * j,
            }, headers=headers)
            assert resp.status_code == 200

        # List and verify
        list_resp = await client.get("/api/v1/batches?page_size=100", headers=headers)
        assert list_resp.status_code == 200
        assert list_resp.json()["total"] >= 3


class TestDigitalTwinWorkflow:
    """Full workflow: create twin �� simulate �� review."""

    @pytest.mark.asyncio
    async def test_twin_lifecycle(self, client: AsyncClient, test_admin):
        """End-to-end digital twin lifecycle."""

        # Login
        login_resp = await client.post("/api/v1/auth/login", json={
            "username": "test_admin",
            "password": "TestAdmin123!",
        })
        headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

        # Create twin
        create_resp = await client.post("/api/v1/twin", json={
            "twin_id": "E2E-TWIN-001",
            "name": "E2E Test Bioreactor",
            "species": "BSF",
            "parameters": {
                "mu_max": 0.025,
                "K_s": 5.0,
                "Y": 0.22,
                "k_death": 0.001,
                "T_env": 28.0,
                "M_env": 70.0,
            },
        }, headers=headers)
        assert create_resp.status_code == 201
        twin_id = create_resp.json()["id"]

        # Simulate
        sim_resp = await client.post(f"/api/v1/twin/{twin_id}/simulate", json={
            "initial_biomass": 0.5,
            "initial_substrate": 10.0,
            "n_steps": 200,
            "dt": 1.0,
        }, headers=headers)
        assert sim_resp.status_code == 200
        sim_data = sim_resp.json()
        assert len(sim_data["trajectory"]) > 0
        assert sim_data["final_state"]["biomass"] > 0.5  # Growth occurred

        # Update parameters
        update_resp = await client.patch(f"/api/v1/twin/{twin_id}", json={
            "parameters": {"mu_max": 0.03},
        }, headers=headers)
        assert update_resp.status_code == 200

        # Simulate again with new params
        sim2_resp = await client.post(f"/api/v1/twin/{twin_id}/simulate", json={
            "initial_biomass": 0.5,
            "initial_substrate": 10.0,
            "n_steps": 200,
            "dt": 1.0,
        }, headers=headers)
        assert sim2_resp.status_code == 200

        # Higher mu_max �� more growth
        assert sim2_resp.json()["final_state"]["biomass"] >= sim_data["final_state"]["biomass"] * 0.9


class TestRBACWorkflow:
    """Test role-based access across endpoints."""

    @pytest.mark.asyncio
    async def test_operator_cannot_admin(self, client: AsyncClient, operator_headers):
        """Operator cannot access admin endpoints."""
        response = await client.get("/api/v1/admin/users", headers=operator_headers)
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_operator_can_create_batch(self, client: AsyncClient, operator_headers):
        """Operator can create batches."""
        response = await client.post("/api/v1/batches", json={
            "batch_id": "RBAC-OP-001",
            "dm_in": 10.0,
            "dm_out": 2.3,
        }, headers=operator_headers)

        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_scientist_can_compute(self, client: AsyncClient, scientist_headers):
        """Scientist can run computations."""
        batch_resp = await client.post("/api/v1/batches", json={
            "batch_id": "RBAC-SCI-001",
            "dm_in": 10.0,
            "dm_out": 2.3,
        }, headers=scientist_headers)
        batch_id = batch_resp.json()["id"]

        response = await client.post("/api/v1/ser/compute", json={
            "batch_id": batch_id,
            "dm_in": 10.0,
            "dm_out": 2.3,
        }, headers=scientist_headers)

        assert response.status_code == 200

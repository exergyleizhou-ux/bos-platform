"""
BOS Pipeline v9.0 �� Monte Carlo Simulation Router Integration Tests

Tests the simulation API endpoint.
"""

import pytest
from httpx import AsyncClient


class TestMonteCarloSimulation:
    """Tests for POST /api/v1/simulation/monte-carlo."""

    @pytest.mark.asyncio
    async def test_simulation_basic(self, client: AsyncClient, admin_headers):
        """Run a basic MC simulation."""
        batch_resp = await client.post("/api/v1/batches", json={
            "batch_id": "MC-TEST-001",
            "dm_in": 10.0,
            "dm_out": 2.3,
        }, headers=admin_headers)
        batch_id = batch_resp.json()["id"]

        response = await client.post("/api/v1/simulation/monte-carlo", json={
            "batch_id": batch_id,
            "n_samples": 1000,
            "dm_in_mean": 10.0,
            "dm_in_std": 0.5,
            "dm_out_mean": 2.3,
            "dm_out_std": 0.15,
            "seed": 42,
        }, headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert "ser_mean" in data
        assert "ser_std" in data
        assert "pass_probability" in data
        assert "histogram_bins" in data
        assert "histogram_counts" in data
        assert data["n_samples"] == 1000

    @pytest.mark.asyncio
    async def test_simulation_large_n(self, client: AsyncClient, admin_headers):
        """Simulation with larger sample count."""
        batch_resp = await client.post("/api/v1/batches", json={
            "batch_id": "MC-TEST-002",
            "dm_in": 10.0,
            "dm_out": 2.3,
        }, headers=admin_headers)
        batch_id = batch_resp.json()["id"]

        response = await client.post("/api/v1/simulation/monte-carlo", json={
            "batch_id": batch_id,
            "n_samples": 50000,
            "dm_in_mean": 10.0,
            "dm_in_std": 0.5,
            "dm_out_mean": 2.3,
            "dm_out_std": 0.15,
            "seed": 42,
        }, headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["n_samples"] == 50000
        assert data["ser_mean"] == pytest.approx(0.23, abs=0.02)

    @pytest.mark.asyncio
    async def test_simulation_requires_auth(self, client: AsyncClient):
        """Unauthenticated request returns 401."""
        response = await client.post("/api/v1/simulation/monte-carlo", json={
            "batch_id": 1,
            "n_samples": 100,
            "dm_in_mean": 10.0,
            "dm_in_std": 0.5,
            "dm_out_mean": 2.3,
            "dm_out_std": 0.15,
        })

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_simulation_invalid_n(self, client: AsyncClient, admin_headers):
        """n_samples below minimum returns 422."""
        response = await client.post("/api/v1/simulation/monte-carlo", json={
            "batch_id": 1,
            "n_samples": 10,  # Below minimum
            "dm_in_mean": 10.0,
            "dm_in_std": 0.5,
            "dm_out_mean": 2.3,
            "dm_out_std": 0.15,
        }, headers=admin_headers)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_simulation_percentiles(self, client: AsyncClient, admin_headers):
        """Simulation result includes percentiles."""
        batch_resp = await client.post("/api/v1/batches", json={
            "batch_id": "MC-TEST-003",
            "dm_in": 10.0,
            "dm_out": 2.3,
        }, headers=admin_headers)
        batch_id = batch_resp.json()["id"]

        response = await client.post("/api/v1/simulation/monte-carlo", json={
            "batch_id": batch_id,
            "n_samples": 5000,
            "dm_in_mean": 10.0,
            "dm_in_std": 0.5,
            "dm_out_mean": 2.3,
            "dm_out_std": 0.15,
            "seed": 42,
        }, headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert "percentiles" in data
        assert "p5" in data["percentiles"]
        assert "p95" in data["percentiles"]

    @pytest.mark.asyncio
    async def test_simulation_ci(self, client: AsyncClient, admin_headers):
        """Confidence interval is valid."""
        batch_resp = await client.post("/api/v1/batches", json={
            "batch_id": "MC-TEST-004",
            "dm_in": 10.0,
            "dm_out": 2.3,
        }, headers=admin_headers)
        batch_id = batch_resp.json()["id"]

        response = await client.post("/api/v1/simulation/monte-carlo", json={
            "batch_id": batch_id,
            "n_samples": 5000,
            "dm_in_mean": 10.0,
            "dm_in_std": 0.5,
            "dm_out_mean": 2.3,
            "dm_out_std": 0.15,
            "seed": 42,
        }, headers=admin_headers)

        data = response.json()
        assert data["ser_ci_lower"] < data["ser_mean"]
        assert data["ser_ci_upper"] > data["ser_mean"]


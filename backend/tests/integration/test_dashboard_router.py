"""
BOS Pipeline v9.0 — Dashboard Router Integration Tests

Tests the dashboard summary and analytics endpoints.
"""

import pytest
from httpx import AsyncClient


class TestDashboardSummary:
    """Tests for GET /api/v1/dashboard/summary."""

    @pytest.mark.asyncio
    async def test_summary(self, client: AsyncClient, admin_headers):
        """Dashboard summary returns aggregate statistics."""
        response = await client.get("/api/v1/dashboard/summary", headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert "total_batches" in data
        assert "active_batches" in data
        assert "completed_batches" in data
        assert "total_calculations" in data
        assert isinstance(data["total_batches"], int)

    @pytest.mark.asyncio
    async def test_summary_requires_auth(self, client: AsyncClient):
        """Unauthenticated request returns 401."""
        response = await client.get("/api/v1/dashboard/summary")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_bos_ledger_summary(self, client: AsyncClient, admin_headers):
        """BOS ledger summary endpoint should always respond with stable payload keys."""
        response = await client.get("/api/v1/dashboard/bos-ledger-summary", headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert "total_dm_in" in data
        assert "total_dm_out" in data
        assert "release_pass_rate" in data
        assert "decision_counts" in data
        assert "evidence_distribution" in data


class TestDashboardSERTrend:
    """Tests for GET /api/v1/dashboard/ser-trend."""

    @pytest.mark.asyncio
    async def test_ser_trend(self, client: AsyncClient, admin_headers):
        """SER trend returns time series data."""
        response = await client.get("/api/v1/dashboard/ser-trend", headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert "data_points" in data
        assert isinstance(data["data_points"], list)

    @pytest.mark.asyncio
    async def test_ser_trend_with_period(self, client: AsyncClient, admin_headers):
        """SER trend with custom period parameter."""
        response = await client.get(
            "/api/v1/dashboard/ser-trend?period=30",
            headers=admin_headers,
        )

        assert response.status_code == 200


class TestDashboardGradeDistribution:
    """Tests for GET /api/v1/dashboard/grade-distribution."""

    @pytest.mark.asyncio
    async def test_grade_distribution_matches_ser_result_grading(self, client: AsyncClient, admin_headers):
        """Low SER batches should use the same displayed grade as compute_ser results."""
        batch_resp = await client.post("/api/v1/batches", json={
            "batch_id": "DASH-GRADE-F",
            "species": "BSF",
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

        response = await client.get("/api/v1/dashboard/grade-distribution", headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["distribution"]["F"] >= 1
        assert data["distribution"]["D"] == 0


class TestDashboardSpeciesDistribution:
    """Tests for GET /api/v1/dashboard/species-distribution."""

    @pytest.mark.asyncio
    async def test_species_distribution(self, client: AsyncClient, admin_headers):
        """Species distribution returns breakdown."""
        # Create batches with different species
        await client.post("/api/v1/batches", json={
            "batch_id": "DASH-BSF", "species": "BSF", "dm_in": 10.0, "dm_out": 2.3,
        }, headers=admin_headers)
        await client.post("/api/v1/batches", json={
            "batch_id": "DASH-MW", "species": "MW", "dm_in": 5.0, "dm_out": 0.8,
        }, headers=admin_headers)

        response = await client.get(
            "/api/v1/dashboard/species-distribution",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "distribution" in data
        assert isinstance(data["distribution"], list)


class TestDashboardRecentActivity:
    """Tests for GET /api/v1/dashboard/recent-activity."""

    @pytest.mark.asyncio
    async def test_recent_activity(self, client: AsyncClient, admin_headers):
        """Recent activity returns latest actions."""
        response = await client.get(
            "/api/v1/dashboard/recent-activity",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "activities" in data
        assert isinstance(data["activities"], list)

    @pytest.mark.asyncio
    async def test_recent_activity_limit(self, client: AsyncClient, admin_headers):
        """Limit parameter controls number of results."""
        response = await client.get(
            "/api/v1/dashboard/recent-activity?limit=5",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["activities"]) <= 5


class TestDashboardRBAC:
    """Tests role-based access to dashboard endpoints."""

    @pytest.mark.asyncio
    async def test_viewer_can_access(self, client: AsyncClient, db_session, test_tenant):
        """Viewer role can access dashboard (read-only)."""
        from app.models import User
        from passlib.context import CryptContext
        from tests.conftest import _make_token

        pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
        viewer = User(
            username="test_viewer",
            hashed_password=pwd.hash("ViewerPass123!"),
            full_name="Test Viewer",
            email="viewer@test.io",
            role="viewer",
            tenant_id=test_tenant.id,
        )
        db_session.add(viewer)
        await db_session.flush()

        token = _make_token(viewer)
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.get("/api/v1/dashboard/summary", headers=headers)
        assert response.status_code == 200

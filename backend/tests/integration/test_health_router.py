"""
BOS Pipeline v9.0 — Health Router Integration Tests

Tests the health check endpoints.
"""

import pytest
from httpx import AsyncClient


class TestLiveness:
    """Tests for GET /api/v1/health/live."""

    @pytest.mark.asyncio
    async def test_liveness(self, client: AsyncClient):
        """Liveness probe returns 200 (no auth required)."""
        response = await client.get("/api/v1/health/live")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
        assert "version" in data
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_liveness_response_format(self, client: AsyncClient):
        """Liveness response matches HealthResponse schema."""
        response = await client.get("/api/v1/health/live")
        data = response.json()

        assert isinstance(data["status"], str)
        assert isinstance(data["version"], str)
        assert isinstance(data["environment"], str)


class TestReadiness:
    """Tests for GET /api/v1/health/ready."""

    @pytest.mark.asyncio
    async def test_readiness(self, client: AsyncClient):
        """Readiness probe checks database and redis."""
        response = await client.get("/api/v1/health/ready")

        assert response.status_code in (200, 503)
        data = response.json()
        assert "database" in data
        assert "redis" in data

    @pytest.mark.asyncio
    async def test_readiness_db_status(self, client: AsyncClient):
        """Readiness reports database as connected or not."""
        response = await client.get("/api/v1/health/ready")
        data = response.json()

        assert data["database"] in ("connected", "disconnected", "error")


class TestInfo:
    """Tests for GET /api/v1/health/info."""

    @pytest.mark.asyncio
    async def test_info(self, client: AsyncClient):
        """Info endpoint returns system information."""
        response = await client.get("/api/v1/health/info")

        assert response.status_code == 200
        data = response.json()
        assert "app_name" in data
        assert "version" in data
        assert "python_version" in data

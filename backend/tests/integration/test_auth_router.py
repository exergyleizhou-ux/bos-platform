"""
BOS Pipeline v9.0 — Auth Router Integration Tests

Tests the authentication endpoints end-to-end.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient


class TestLogin:
    """Tests for POST /api/v1/auth/login."""

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, test_admin):
        """Valid credentials return access + refresh tokens."""
        response = await client.post("/api/v1/auth/login", json={
            "username": "test_admin",
            "password": "TestAdmin123!",
        })

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient, test_admin):
        """Wrong password returns 401."""
        response = await client.post("/api/v1/auth/login", json={
            "username": "test_admin",
            "password": "WrongPassword123!",
        })

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Non-existent user returns 401."""
        response = await client.post("/api/v1/auth/login", json={
            "username": "ghost_user",
            "password": "SomePass123!",
        })

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_missing_fields(self, client: AsyncClient):
        """Missing fields return 422."""
        response = await client.post("/api/v1/auth/login", json={
            "username": "test_admin",
        })

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_login_short_password(self, client: AsyncClient):
        """Password below min length returns 422."""
        response = await client.post("/api/v1/auth/login", json={
            "username": "test_admin",
            "password": "short",
        })

        assert response.status_code == 422


class TestTokenRefresh:
    """Tests for POST /api/v1/auth/refresh."""

    @pytest.mark.asyncio
    async def test_refresh_success(self, client: AsyncClient, test_admin):
        """Valid refresh token returns new access token."""
        # First login
        login_resp = await client.post("/api/v1/auth/login", json={
            "username": "test_admin",
            "password": "TestAdmin123!",
        })
        refresh_token = login_resp.json()["refresh_token"]

        # Refresh
        response = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token,
        })

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self, client: AsyncClient):
        """Invalid refresh token returns 401."""
        response = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": "invalid-token-string",
        })

        assert response.status_code == 401


class TestProfile:
    """Tests for GET /api/v1/auth/me."""

    @pytest.mark.asyncio
    async def test_get_profile(self, client: AsyncClient, admin_headers):
        """Authenticated user can get their profile."""
        response = await client.get("/api/v1/auth/me", headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "test_admin"
        assert data["role"] == "admin"

    @pytest.mark.asyncio
    async def test_get_profile_no_auth(self, client: AsyncClient):
        """No auth header returns 401."""
        response = await client.get("/api/v1/auth/me")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_profile_invalid_token(self, client: AsyncClient):
        """Invalid token returns 401."""
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid-token"},
        )

        assert response.status_code == 401


class TestChangePassword:
    """Tests for POST /api/v1/auth/change-password."""

    @pytest.mark.asyncio
    async def test_change_password_success(self, client: AsyncClient, admin_headers):
        """Valid password change succeeds."""
        response = await client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "TestAdmin123!",
                "new_password": "NewAdmin456!",
            },
            headers=admin_headers,
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_change_password_wrong_current(self, client: AsyncClient, admin_headers):
        """Wrong current password returns 400."""
        response = await client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "WrongPass123!",
                "new_password": "NewAdmin456!",
            },
            headers=admin_headers,
        )

        assert response.status_code == 400

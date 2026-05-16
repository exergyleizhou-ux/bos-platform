import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models import FeatureFlag, User


class TestFeatureFlagFallback:
    @pytest.mark.asyncio
    async def test_admin_can_manage_feature_flags_without_redis(
        self,
        client: AsyncClient,
        admin_headers,
        admin_user: User,
        db_session: AsyncSession,
    ):
        previous_redis = getattr(app.state, "redis", None)
        app.state.redis = None

        try:
            set_response = await client.put(
                "/api/v1/feature-flags/billing",
                json={"enabled": True},
                headers=admin_headers,
            )

            assert set_response.status_code == 200
            set_body = set_response.json()
            assert set_body["enabled"] is True
            assert set_body["storage"] == "database"
            assert set_body["cache_synced"] is False

            record = (
                await db_session.execute(select(FeatureFlag).where(FeatureFlag.name == "billing"))
            ).scalar_one()
            assert record.tenant_overrides[str(admin_user.tenant_id)] is True

            get_response = await client.get("/api/v1/feature-flags/billing", headers=admin_headers)
            assert get_response.status_code == 200
            get_body = get_response.json()
            assert get_body["enabled"] is True
            assert get_body["source"] == "config+db"

            reset_response = await client.delete("/api/v1/feature-flags/billing", headers=admin_headers)
            assert reset_response.status_code == 200
            reset_body = reset_response.json()
            assert reset_body["override_removed"] is True
            assert reset_body["cache_cleared"] is False

            get_after_reset = await client.get("/api/v1/feature-flags/billing", headers=admin_headers)
            assert get_after_reset.status_code == 200
            final_body = get_after_reset.json()
            assert final_body["enabled"] == reset_body["default_value"]
            assert final_body["source"] == "config"
        finally:
            app.state.redis = previous_redis

    @pytest.mark.asyncio
    async def test_unknown_feature_flag_returns_404(self, client: AsyncClient, admin_headers):
        response = await client.put(
            "/api/v1/feature-flags/not-a-real-flag",
            json={"enabled": True},
            headers=admin_headers,
        )

        assert response.status_code == 404

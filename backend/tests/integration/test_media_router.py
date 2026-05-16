import json
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.config import get_settings
from app.models import Tenant, User
from app.routers.auth import create_access_token, pwd_context


class TestRemotionMediaRouter:
    @pytest.mark.asyncio
    async def test_health_endpoint_returns_runtime_posture(
        self,
        client: AsyncClient,
        operator_headers,
    ):
        response = await client.get("/api/v1/media/remotion/health", headers=operator_headers)

        assert response.status_code == 200
        payload = response.json()
        assert "enabled" in payload
        assert "ready" in payload
        assert "runtime_dir" in payload
        assert isinstance(payload["details"], list)

    @pytest.mark.asyncio
    async def test_templates_endpoint_returns_seeded_templates(
        self,
        client: AsyncClient,
        operator_headers,
    ):
        response = await client.get("/api/v1/media/remotion/templates", headers=operator_headers)

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) >= 5
        assert {item["id"] for item in payload} >= {
            "bos-assistant-safe-still",
            "bos-launch-card",
            "bos-signal-beacon",
            "bos-story-stack",
            "bos-metric-board",
        }

    @pytest.mark.asyncio
    async def test_suggest_endpoint_returns_autofill_payload(
        self,
        client: AsyncClient,
        operator_headers,
    ):
        response = await client.post(
            "/api/v1/media/remotion/suggest",
            headers=operator_headers,
            json={
                "brief": "Create a release readiness animation for this week's BOS signal review.",
                "audience": "executives",
                "brand_voice": "operations",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["template_id"] in {"bos-launch-card", "bos-signal-beacon"}
        assert payload["kind"] in {"still", "video"}
        assert payload["source"] in {"heuristic", "model"}
        assert payload["title"]
        assert isinstance(payload["extra_props"], dict)
        assert payload["rationale"]

    @pytest.mark.asyncio
    async def test_renders_endpoint_lists_recent_artifacts(
        self,
        client: AsyncClient,
        operator_headers,
        operator_user,
    ):
        settings = get_settings()
        output_dir = Path(settings.BOS_MEDIA_REMOTION_OUTPUT_DIR) / f"tenant-{operator_user.tenant_id}"
        output_dir.mkdir(parents=True, exist_ok=True)
        artifact = output_dir / "history-smoke.png"
        metadata = output_dir / "history-smoke.png.json"
        artifact.write_bytes(b"fake-png")
        metadata.write_text(
            json.dumps(
                {
                    "job_id": "history-smoke",
                    "kind": "still",
                    "template_id": "bos-launch-card",
                    "file_name": artifact.name,
                    "mime_type": "image/png",
                    "width": 1080,
                    "height": 1080,
                    "fps": 30,
                    "duration_in_frames": 1,
                    "created_at": "2026-04-14T00:00:00+00:00",
                }
            ),
            encoding="utf-8",
        )
        try:
            response = await client.get("/api/v1/media/remotion/renders", headers=operator_headers)
            assert response.status_code == 200
            payload = response.json()
            assert any(item["file_name"] == "history-smoke.png" for item in payload)
        finally:
            artifact.unlink(missing_ok=True)
            metadata.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_presets_are_scoped_to_the_current_tenant(
        self,
        client: AsyncClient,
        db_session,
        operator_headers,
    ):
        other_tenant = Tenant(name="Other Tenant", slug="other-tenant-media")
        db_session.add(other_tenant)
        await db_session.commit()
        await db_session.refresh(other_tenant)

        other_user = User(
            username="other_media_operator",
            email="other_media_operator@bos.io",
            full_name="Other Media Operator",
            hashed_password=pwd_context.hash("OtherMedia123!"),
            role="operator",
            is_active=True,
            tenant_id=other_tenant.id,
        )
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)
        other_headers = {"Authorization": f"Bearer {create_access_token(other_user.id, other_user.role, other_user.tenant_id)}"}

        create_response = await client.post(
            "/api/v1/media/remotion/presets",
            headers=operator_headers,
            json={
                "name": "Tenant-scoped preset",
                "tags": ["ops"],
                "snapshot_file_name": None,
                "snapshot_kind": None,
                "template_id": "bos-launch-card",
                "kind": "still",
                "export_recipe_id": "web-hero",
                "creative_brief": "Tenant scoped media preset.",
                "audience": "operators",
                "brand_voice": "operations",
                "title": "Scoped preset",
                "subtitle": "Scoped subtitle",
                "caption": "SCOPED",
                "accent_color": "#7CFFB2",
                "background_color": "#07111F",
                "width": "1080",
                "height": "1080",
                "fps": "30",
                "duration_in_frames": "1",
                "dynamic_fields": {"status": "Ready"},
            },
        )
        assert create_response.status_code == 201
        preset_id = create_response.json()["id"]

        own_list = await client.get("/api/v1/media/remotion/presets", headers=operator_headers)
        other_list = await client.get("/api/v1/media/remotion/presets", headers=other_headers)
        assert any(item["id"] == preset_id for item in own_list.json())
        assert all(item["id"] != preset_id for item in other_list.json())

    @pytest.mark.asyncio
    async def test_renders_are_scoped_to_the_current_tenant(
        self,
        client: AsyncClient,
        db_session,
        operator_headers,
        operator_user,
    ):
        other_tenant = Tenant(name="Other Tenant Render", slug="other-tenant-render")
        db_session.add(other_tenant)
        await db_session.commit()
        await db_session.refresh(other_tenant)

        other_user = User(
            username="other_render_operator",
            email="other_render_operator@bos.io",
            full_name="Other Render Operator",
            hashed_password=pwd_context.hash("OtherRender123!"),
            role="operator",
            is_active=True,
            tenant_id=other_tenant.id,
        )
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)
        other_headers = {"Authorization": f"Bearer {create_access_token(other_user.id, other_user.role, other_user.tenant_id)}"}

        settings = get_settings()
        own_output_dir = Path(settings.BOS_MEDIA_REMOTION_OUTPUT_DIR) / f"tenant-{operator_user.tenant_id}"
        own_output_dir.mkdir(parents=True, exist_ok=True)
        artifact = own_output_dir / "tenant-owned.png"
        metadata = own_output_dir / "tenant-owned.png.json"
        artifact.write_bytes(b"tenant-png")
        metadata.write_text(
            json.dumps(
                {
                    "job_id": "tenant-owned",
                    "kind": "still",
                    "template_id": "bos-launch-card",
                    "file_name": artifact.name,
                    "mime_type": "image/png",
                    "width": 1080,
                    "height": 1080,
                    "fps": 30,
                    "duration_in_frames": 1,
                    "created_at": "2026-04-14T00:00:00+00:00",
                }
            ),
            encoding="utf-8",
        )
        try:
            own_list = await client.get("/api/v1/media/remotion/renders", headers=operator_headers)
            other_list = await client.get("/api/v1/media/remotion/renders", headers=other_headers)
            assert any(item["file_name"] == "tenant-owned.png" for item in own_list.json())
            assert all(item["file_name"] != "tenant-owned.png" for item in other_list.json())

            other_download = await client.get("/api/v1/media/remotion/renders/tenant-owned.png", headers=other_headers)
            assert other_download.status_code == 404
        finally:
            artifact.unlink(missing_ok=True)
            metadata.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_presets_can_be_created_listed_and_deleted(
        self,
        client: AsyncClient,
        operator_headers,
    ):
        create_response = await client.post(
            "/api/v1/media/remotion/presets",
            headers=operator_headers,
            json={
                "name": "Weekly signal update",
                "tags": ["ops", "signal"],
                "snapshot_file_name": "history-smoke.png",
                "snapshot_kind": "still",
                "template_id": "bos-signal-beacon",
                "kind": "video",
                "export_recipe_id": "deck-header",
                "creative_brief": "Weekly BOS signal recap for operators.",
                "audience": "operators",
                "brand_voice": "operations",
                "title": "Signal is holding",
                "subtitle": "The latest control-room recap is stable and clear.",
                "caption": "OPS SIGNAL",
                "accent_color": "#7CFFB2",
                "background_color": "#07111F",
                "width": "1920",
                "height": "1080",
                "fps": "30",
                "duration_in_frames": "150",
                "dynamic_fields": {"status": "Ready"},
            },
        )
        assert create_response.status_code == 201
        preset_id = create_response.json()["id"]

        list_response = await client.get("/api/v1/media/remotion/presets", headers=operator_headers)
        assert list_response.status_code == 200
        created = next(item for item in list_response.json() if item["id"] == preset_id)
        assert created["tags"] == ["ops", "signal"]

        update_response = await client.put(
            f"/api/v1/media/remotion/presets/{preset_id}",
            headers=operator_headers,
            json={
                "name": "Weekly signal update v2",
                "tags": ["ops", "signal", "weekly"],
                "snapshot_file_name": "history-smoke.png",
                "snapshot_kind": "still",
                "template_id": "bos-signal-beacon",
                "kind": "video",
                "export_recipe_id": "deck-header",
                "creative_brief": "Updated BOS signal recap for operators.",
                "audience": "operators",
                "brand_voice": "operations",
                "title": "Signal is stable",
                "subtitle": "The latest recap is stable and clearer than before.",
                "caption": "OPS SIGNAL",
                "accent_color": "#7CFFB2",
                "background_color": "#07111F",
                "width": "1920",
                "height": "1080",
                "fps": "30",
                "duration_in_frames": "150",
                "dynamic_fields": {"status": "Ready"},
            },
        )
        assert update_response.status_code == 200
        assert update_response.json()["name"] == "Weekly signal update v2"
        assert update_response.json()["tags"] == ["ops", "signal", "weekly"]
        assert update_response.json()["snapshot_kind"] == "still"

        delete_response = await client.delete(
            f"/api/v1/media/remotion/presets/{preset_id}",
            headers=operator_headers,
        )
        assert delete_response.status_code == 204

    @pytest.mark.asyncio
    async def test_assistant_run_returns_summary_and_render(
        self,
        client: AsyncClient,
        operator_headers,
    ):
        response = await client.post(
            "/api/v1/media/remotion/assistant-run",
            headers=operator_headers,
            json={
                "prompt": "Create a launch graphic announcing BOS Media Studio with a premium release tone.",
                "preferred_kind": "still",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["summary"]
        assert payload["suggestion"]["template_id"]
        assert payload["render"]["file_name"]

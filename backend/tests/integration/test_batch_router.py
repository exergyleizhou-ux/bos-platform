"""
BOS Pipeline v9.0 — Batch Router Integration Tests

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
            "substrate": "distillers_grains",
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
        assert data["substrate"] == "distillers_grains"
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
        assert data["bos"]["signal_batch"] is None
        assert data["bos"]["audit_packet"] is None
        assert data["bos"]["portability_audits"] == []
        assert data["bos"]["compile_status"] == "not_started"
        assert data["bos"]["latest_signal_status"] == "missing"

    @pytest.mark.asyncio
    async def test_get_batch_includes_bos_overview(
        self,
        client: AsyncClient,
        admin_headers,
        scientist_headers,
    ):
        """Batch detail includes the latest BOS aggregate view."""
        create_batch_resp = await client.post(
            "/api/v1/batches",
            json={
                "batch_id": "TEST-BOS-001",
                "dm_in": 12.0,
                "dm_out": 2.8,
                "temperature": 28.5,
                "moisture": 69.0,
            },
            headers=admin_headers,
        )
        assert create_batch_resp.status_code == 201
        batch_id = create_batch_resp.json()["id"]

        create_control_resp = await client.post(
            "/api/v1/control-profiles",
            json={
                "name": "Baseline contract",
                "version": "CTRL-2.0",
                "mtt": 6.0,
                "dose_window_min": 0.1,
                "dose_window_max": 0.3,
                "stability_window_hours": 8.0,
            },
            headers=scientist_headers,
        )
        assert create_control_resp.status_code == 201
        control_profile_id = create_control_resp.json()["id"]

        create_signal_resp = await client.post(
            "/api/v1/signals",
            json={
                "batch_id": batch_id,
                "potency": 0.22,
                "signal_api_version": "SIG-1.0",
                "compiled_signal_id": "SIG-TEST-BOS-001",
                "freshness_state": "Fresh",
                "stability_window_hours": 8.0,
            },
            headers=admin_headers,
        )
        assert create_signal_resp.status_code == 201
        signal_batch_id = create_signal_resp.json()["id"]

        release_resp = await client.post(
            "/api/v1/release-decisions/evaluate",
            json={
                "batch_id": batch_id,
                "signal_batch_id": signal_batch_id,
                "control_profile_id": control_profile_id,
            },
            headers=admin_headers,
        )
        assert release_resp.status_code == 200

        create_executor_resp = await client.post(
            "/api/v1/executor-profiles",
            json={
                "executor_code": "EXEC-TEST-001",
                "name": "Pilot executor",
                "plugin_mode": "standard",
                "hal_min": 0.1,
                "hal_max": 0.3,
            },
            headers=scientist_headers,
        )
        assert create_executor_resp.status_code == 201
        executor_profile_id = create_executor_resp.json()["id"]

        portability_resp = await client.post(
            "/api/v1/portability-audits",
            json={
                "signal_batch_id": signal_batch_id,
                "executor_profile_id": executor_profile_id,
                "outcome": "PASS",
                "retuning_required": False,
            },
            headers=scientist_headers,
        )
        assert portability_resp.status_code == 201

        audit_packet_resp = await client.get(
            f"/api/v1/audit-packets/batch/{batch_id}",
            headers=admin_headers,
        )
        assert audit_packet_resp.status_code == 200
        audit_packet = audit_packet_resp.json()

        batch_resp = await client.get(f"/api/v1/batches/{batch_id}", headers=admin_headers)

        assert batch_resp.status_code == 200
        data = batch_resp.json()
        bos = data["bos"]
        assert bos["signal_batch"]["id"] == signal_batch_id
        assert bos["control_profile"]["id"] == control_profile_id
        assert bos["boundary_ledger"]["batch_id"] == batch_id
        assert bos["release_decision"]["batch_id"] == batch_id
        assert bos["audit_packet"]["id"] == audit_packet["id"]
        assert bos["audit_packet"]["packet_version"] == audit_packet["packet_version"]
        assert len(bos["portability_audits"]) == 1
        assert bos["portability_audits"][0]["executor_profile_id"] == executor_profile_id
        assert bos["compile_status"] == "manual"
        assert bos["latest_signal_status"] in {"valid", "review", "blocked"}

    @pytest.mark.asyncio
    async def test_get_batch_includes_latest_native_run_summary(
        self,
        client: AsyncClient,
        admin_headers,
        scientist_headers,
    ):
        create_batch_resp = await client.post(
            "/api/v1/batches",
            json={
                "batch_id": "TEST-NATIVE-RUN-001",
                "dm_in": 12.0,
                "dm_out": 2.8,
                "temperature": 28.5,
                "moisture": 69.0,
            },
            headers=admin_headers,
        )
        assert create_batch_resp.status_code == 201
        batch_id = create_batch_resp.json()["id"]

        create_control_resp = await client.post(
            "/api/v1/control-profiles",
            json={
                "name": "Native run contract",
                "version": "CTRL-2.0",
                "mtt": 6.0,
                "dose_window_min": 0.1,
                "dose_window_max": 0.3,
                "stability_window_hours": 8.0,
            },
            headers=scientist_headers,
        )
        assert create_control_resp.status_code == 201
        control_profile_id = create_control_resp.json()["id"]

        create_signal_resp = await client.post(
            "/api/v1/signals",
            json={
                "batch_id": batch_id,
                "potency": 0.22,
                "signal_api_version": "SIG-1.0",
                "compiled_signal_id": "SIG-TEST-NATIVE-RUN-001",
                "freshness_state": "Fresh",
                "stability_window_hours": 8.0,
            },
            headers=admin_headers,
        )
        assert create_signal_resp.status_code == 201
        signal_batch_id = create_signal_resp.json()["id"]

        release_resp = await client.post(
            "/api/v1/release-decisions/evaluate",
            json={
                "batch_id": batch_id,
                "signal_batch_id": signal_batch_id,
                "control_profile_id": control_profile_id,
            },
            headers=admin_headers,
        )
        assert release_resp.status_code == 200

        infer_resp = await client.post(
            "/api/v1/native-models/infer",
            json={
                "model_key": "timer_s1",
                "batch_id": batch_id,
                "dry_run": False,
                "payload": {
                    "metric_name": "decomposition_rate",
                    "horizon": 3,
                    "sensor_history": [0.21, 0.29, 0.33, 0.41],
                },
            },
            headers=admin_headers,
        )
        assert infer_resp.status_code == 200

        batch_resp = await client.get(f"/api/v1/batches/{batch_id}", headers=admin_headers)

        assert batch_resp.status_code == 200
        payload = batch_resp.json()
        latest_native_run = payload["bos"]["latest_native_run"]
        assert latest_native_run["model_key"] == "timer_s1"
        assert latest_native_run["metric_name"] == "decomposition_rate"
        assert latest_native_run["prediction_horizon"] == 3
        assert latest_native_run["artifact_path"]
        audit_packet = payload["bos"]["audit_packet"]
        assert audit_packet["packet"]["native_forecast_evidence"]["model_key"] == "timer_s1"
        assert audit_packet["packet"]["native_forecast_evidence"]["prediction_horizon"] == 3

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

    @pytest.mark.asyncio
    async def test_substrate_filter(self, client: AsyncClient, admin_headers):
        """Filter by substrate."""
        await client.post("/api/v1/batches", json={
            "batch_id": "FILTER-DG", "species": "MW", "substrate": "distillers_grains", "dm_in": 10.0, "dm_out": 2.3,
        }, headers=admin_headers)
        await client.post("/api/v1/batches", json={
            "batch_id": "FILTER-SLUDGE", "species": "BSF", "substrate": "sewage_sludge", "dm_in": 5.0, "dm_out": 0.8,
        }, headers=admin_headers)

        response = await client.get(
            "/api/v1/batches?substrate=distillers_grains",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["substrate"] == "distillers_grains"


class TestBatchStatsAndExport:
    """Tests for /api/v1/batches/stats and /api/v1/batches/export."""

    @pytest.mark.asyncio
    async def test_batch_stats_endpoint(self, client: AsyncClient, admin_headers):
        await client.post("/api/v1/batches", json={
            "batch_id": "STATS-001",
            "dm_in": 10.0,
            "dm_out": 2.3,
            "status": "active",
        }, headers=admin_headers)
        await client.post("/api/v1/batches", json={
            "batch_id": "STATS-002",
            "dm_in": 8.0,
            "dm_out": 1.5,
            "status": "completed",
        }, headers=admin_headers)

        response = await client.get("/api/v1/batches/stats", headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "by_status" in data
        assert "by_species" in data
        assert data["total"] >= 2
        assert data["by_status"]["active"] >= 1
        assert data["by_status"]["completed"] >= 1

    @pytest.mark.asyncio
    async def test_batch_export_endpoint(self, client: AsyncClient, admin_headers):
        await client.post("/api/v1/batches", json={
            "batch_id": "EXPORT-001",
            "dm_in": 11.0,
            "dm_out": 2.6,
        }, headers=admin_headers)

        response = await client.get("/api/v1/batches/export?format=json", headers=admin_headers)

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")

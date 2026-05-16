"""
BOS Pipeline v9.0 -Batch API Integration Tests

Tests for batch CRUD endpoints: create, list, detail, update, delete.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestBatchCreate:
    """POST /batches"""

    async def test_create_batch_success(
        self,
        client: AsyncClient,
        auth_headers: dict,
        sample_batch_payload: dict,
    ):
        resp = await client.post("/api/v1/batches", json=sample_batch_payload, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["batch_id"] == "BSF-TEST-001"
        assert data["species"] == "BSF"
        assert data["dm_in"] == 10.0
        assert data["dm_out"] == 8.5
        assert data["status"] == "logged"
        assert "id" in data
        assert "created_at" in data

        async def test_create_batch_missing_required(self, client: AsyncClient, auth_headers: dict):
            resp = await client.post(
                "/api/v1/batches",
                json={"species": "BSF"},
                headers=auth_headers,
            )
            assert resp.status_code == 422

            async def test_create_batch_unauthorized(self, client: AsyncClient, sample_batch_payload: dict):
                resp = await client.post("/api/v1/batches", json=sample_batch_payload)
                assert resp.status_code == 401

                async def test_create_batch_negative_dm(self, client: AsyncClient, auth_headers: dict):
                    payload = {
                        "batch_id": "BSF-NEG",
                        "species": "BSF",
                        "dm_in": -5.0,
                        "dm_out": 3.0,
                    }
                    resp = await client.post("/api/v1/batches", json=payload, headers=auth_headers)
                    assert resp.status_code == 422

                    @pytest.mark.asyncio
                    class TestBatchList:
                        """GET /batches"""

                        async def test_list_batches_empty(self, client: AsyncClient, auth_headers: dict):
                            resp = await client.get("/api/v1/batches", headers=auth_headers)
                            assert resp.status_code == 200
                            data = resp.json()
                            assert "items" in data
                            assert "total" in data
                            assert "page" in data
                            assert "total_pages" in data

                            async def test_list_batches_with_data(
                                self,
                                client: AsyncClient,
                                auth_headers: dict,
                                sample_batch_payload: dict,
                            ):
                                # Create a batch first
                                await client.post("/api/v1/batches", json=sample_batch_payload, headers=auth_headers)
                                resp = await client.get("/api/v1/batches", headers=auth_headers)
                                assert resp.status_code == 200
                                data = resp.json()
                                assert data["total"] >= 1
                                assert len(data["items"]) >= 1

                                async def test_list_batches_pagination(self, client: AsyncClient, auth_headers: dict):
                                    resp = await client.get(
                                        "/api/v1/batches",
                                        params={"page": 1, "page_size": 5},
                                        headers=auth_headers,
                                    )
                                    assert resp.status_code == 200
                                    data = resp.json()
                                    assert data["page"] == 1
                                    assert len(data["items"]) <= 5

                                    async def test_list_batches_filter_species(
                                        self,
                                        client: AsyncClient,
                                        auth_headers: dict,
                                        sample_batch_payload: dict,
                                    ):
                                        await client.post(
                                            "/api/v1/batches", json=sample_batch_payload, headers=auth_headers
                                        )
                                        resp = await client.get(
                                            "/api/v1/batches",
                                            params={"species": "BSF"},
                                            headers=auth_headers,
                                        )
                                        assert resp.status_code == 200
                                        data = resp.json()
                                        for item in data["items"]:
                                            assert item["species"] == "BSF"

                                            @pytest.mark.asyncio
                                            class TestBatchDetail:
                                                """GET /batches/{id}"""

                                                async def test_get_batch_success(
                                                    self,
                                                    client: AsyncClient,
                                                    auth_headers: dict,
                                                    sample_batch_payload: dict,
                                                ):
                                                    create_resp = await client.post(
                                                        "/api/v1/batches",
                                                        json=sample_batch_payload,
                                                        headers=auth_headers,
                                                    )
                                                    batch_id = create_resp.json()["id"]

                                                    resp = await client.get(
                                                        f"/api/v1/batches/{batch_id}", headers=auth_headers
                                                    )
                                                    assert resp.status_code == 200
                                                    data = resp.json()
                                                    assert data["id"] == batch_id
                                                    assert data["batch_id"] == "BSF-TEST-001"

                                                    async def test_get_batch_not_found(
                                                        self, client: AsyncClient, auth_headers: dict
                                                    ):
                                                        resp = await client.get(
                                                            "/api/v1/batches/99999", headers=auth_headers
                                                        )
                                                        assert resp.status_code == 404

                                                        @pytest.mark.asyncio
                                                        class TestBatchUpdate:
                                                            """PATCH /batches/{id}"""

                                                            async def test_update_batch_success(
                                                                self,
                                                                client: AsyncClient,
                                                                auth_headers: dict,
                                                                sample_batch_payload: dict,
                                                            ):
                                                                create_resp = await client.post(
                                                                    "/api/v1/batches",
                                                                    json=sample_batch_payload,
                                                                    headers=auth_headers,
                                                                )
                                                                batch_id = create_resp.json()["id"]

                                                                resp = await client.patch(
                                                                    f"/api/v1/batches/{batch_id}",
                                                                    json={
                                                                        "notes": "Updated notes",
                                                                        "temperature": 30.0,
                                                                    },
                                                                    headers=auth_headers,
                                                                )
                                                                assert resp.status_code == 200
                                                                data = resp.json()
                                                                assert data["notes"] == "Updated notes"
                                                                assert data["temperature"] == 30.0

                                                                async def test_update_batch_not_found(
                                                                    self, client: AsyncClient, auth_headers: dict
                                                                ):
                                                                    resp = await client.patch(
                                                                        "/api/v1/batches/99999",
                                                                        json={"notes": "nope"},
                                                                        headers=auth_headers,
                                                                    )
                                                                    assert resp.status_code == 404

                                                                    @pytest.mark.asyncio
                                                                    class TestBatchDelete:
                                                                        """DELETE /batches/{id}"""

                                                                        async def test_delete_batch_success(
                                                                            self,
                                                                            client: AsyncClient,
                                                                            auth_headers: dict,
                                                                            sample_batch_payload: dict,
                                                                        ):
                                                                            create_resp = await client.post(
                                                                                "/api/v1/batches",
                                                                                json=sample_batch_payload,
                                                                                headers=auth_headers,
                                                                            )
                                                                            batch_id = create_resp.json()["id"]

                                                                            resp = await client.delete(
                                                                                f"/api/v1/batches/{batch_id}",
                                                                                headers=auth_headers,
                                                                            )
                                                                            assert resp.status_code == 204

                                                                            # Verify deleted
                                                                            get_resp = await client.get(
                                                                                f"/api/v1/batches/{batch_id}",
                                                                                headers=auth_headers,
                                                                            )
                                                                            assert get_resp.status_code == 404

                                                                            async def test_delete_batch_not_found(
                                                                                self,
                                                                                client: AsyncClient,
                                                                                auth_headers: dict,
                                                                            ):
                                                                                resp = await client.delete(
                                                                                    "/api/v1/batches/99999",
                                                                                    headers=auth_headers,
                                                                                )
                                                                                assert resp.status_code == 404

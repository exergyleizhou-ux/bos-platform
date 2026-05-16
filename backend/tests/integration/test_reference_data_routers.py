"""
BOS Pipeline v9.0 reference data router integration tests.
"""

import pytest
from httpx import AsyncClient


class TestSpeciesRouter:
    @pytest.mark.asyncio
    async def test_species_list_includes_expanded_species_and_references(
        self,
        client: AsyncClient,
        admin_headers,
    ):
        response = await client.get("/api/v1/species", headers=admin_headers)

        assert response.status_code == 200
        payload = response.json()
        codes = {item["code"] for item in payload["species"]}
        assert {"BSF", "MW", "PB"}.issubset(codes)

        pb = next(item for item in payload["species"] if item["code"] == "PB")
        assert pb["aliases"]
        assert pb["references"]

    @pytest.mark.asyncio
    async def test_species_detail_supports_alias_lookup(
        self,
        client: AsyncClient,
        admin_headers,
    ):
        response = await client.get("/api/v1/species/GRUB", headers=admin_headers)

        assert response.status_code == 200
        payload = response.json()
        assert payload["code"] == "PB"
        assert "Protaetia" in payload["scientific_name"]

    @pytest.mark.asyncio
    async def test_species_candidates_are_pending_review_read_model(
        self,
        client: AsyncClient,
        admin_headers,
    ):
        response = await client.get("/api/v1/species/candidates", headers=admin_headers)

        assert response.status_code == 200
        payload = response.json()
        codes = {item["code"] for item in payload["candidates"]}
        assert {"BSF", "MW", "PB"}.issubset(codes)
        assert all(item["human_review_required"] is True for item in payload["candidates"])
        assert all(item["review_status"] == "pending_review" for item in payload["candidates"])
        assert all(item["source_kind"] and item["source_ref"] for item in payload["candidates"])

        reviewed = await client.get("/api/v1/species/candidates?review_status=reviewed", headers=admin_headers)
        assert reviewed.status_code == 200
        assert reviewed.json()["candidates"] == []


class TestFeedstockRouter:
    @pytest.mark.asyncio
    async def test_feedstock_list_returns_manuscript_backed_profiles(
        self,
        client: AsyncClient,
        admin_headers,
    ):
        response = await client.get("/api/v1/feedstocks", headers=admin_headers)

        assert response.status_code == 200
        payload = response.json()
        keys = {item["key"] for item in payload["feedstocks"]}
        assert {"distillers_grains", "straw_sludge_blend", "sewage_sludge", "tcm_residue"}.issubset(keys)

        sludge = next(item for item in payload["feedstocks"] if item["key"] == "sewage_sludge")
        assert sludge["references"]
        assert sludge["contamination_risk"] == "critical"

    @pytest.mark.asyncio
    async def test_feedstock_candidates_are_pending_review_read_model(
        self,
        client: AsyncClient,
        admin_headers,
    ):
        response = await client.get("/api/v1/feedstocks/candidates", headers=admin_headers)

        assert response.status_code == 200
        payload = response.json()
        keys = {item["key"] for item in payload["candidates"]}
        assert {
            "distillers_grains",
            "brewery_spent_grains",
            "washed_kitchen_waste",
            "mixed_food_waste",
            "manure_sludge_high_risk",
        }.issubset(keys)
        assert "mixed_food_waste" not in payload["validated_feedstock_keys"]
        assert all(item["human_review_required"] is True for item in payload["candidates"])
        assert all(item["review_status"] == "pending_review" for item in payload["candidates"])

        food_waste = await client.get("/api/v1/feedstocks/candidates/food_waste", headers=admin_headers)
        assert food_waste.status_code == 200
        assert food_waste.json()["key"] == "mixed_food_waste"


class TestManuscriptReferenceRouter:
    @pytest.mark.asyncio
    async def test_manuscript_campaigns_endpoint_returns_core_and_supporting_campaigns(
        self,
        client: AsyncClient,
        admin_headers,
    ):
        response = await client.get("/api/v1/references/campaigns", headers=admin_headers)

        assert response.status_code == 200
        payload = response.json()
        keys = {item["key"] for item in payload["campaigns"]}
        assert "core_tm_pb_distillers_grains" in keys
        assert "bsf_hal_portability_audit" in keys
        assert "tcm_residue_screen" in keys

    @pytest.mark.asyncio
    async def test_manuscript_campaign_detail_returns_key_metrics(
        self,
        client: AsyncClient,
        admin_headers,
    ):
        response = await client.get(
            "/api/v1/references/campaigns/core_tm_pb_distillers_grains",
            headers=admin_headers,
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["key_parameters"]["ser"] == 0.68
        assert payload["species_chain"] == ["MW", "PB"]
        assert payload["references"]


class TestRiskRouterReferenceProfiles:
    @pytest.mark.asyncio
    async def test_risk_limits_endpoint_returns_substrate_profiles(
        self,
        client: AsyncClient,
        admin_headers,
    ):
        response = await client.get("/api/v1/risk/limits", headers=admin_headers)

        assert response.status_code == 200
        payload = response.json()
        assert "substrate_profiles" in payload
        assert "distillers_grains" in payload["substrate_profiles"]
        assert payload["substrate_profiles"]["sewage_sludge"]["references"]

    @pytest.mark.asyncio
    async def test_risk_assessment_inherits_batch_substrate_when_not_explicit(
        self,
        client: AsyncClient,
        admin_headers,
    ):
        create_batch_resp = await client.post(
            "/api/v1/batches",
            json={
                "batch_id": "RISK-INHERIT-001",
                "species": "MW",
                "substrate": "distillers_grains",
                "dm_in": 10.0,
                "dm_out": 2.0,
            },
            headers=admin_headers,
        )
        assert create_batch_resp.status_code == 201
        batch_id = create_batch_resp.json()["id"]

        response = await client.post(
            "/api/v1/risk/assess",
            json={
                "batch_id": batch_id,
                "species": "MW",
                "product_use": "feed",
                "contaminants": [],
            },
            headers=admin_headers,
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["substrate_profile"]["key"] == "distillers_grains"

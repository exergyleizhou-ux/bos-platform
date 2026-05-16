import pytest
from httpx import AsyncClient

from app.services.reference_ingestion_service import reference_ingestion_service


def _fake_pdf(text: str) -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /Contents 4 0 R >>
endobj
4 0 obj
<< /Length {len(escaped) + 32} >>
stream
BT
({escaped}) Tj
ET
endstream
endobj
trailer
<< /Root 1 0 R >>
%%EOF
""".encode("latin-1")


@pytest.fixture(autouse=True)
def isolated_reference_ingestion_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(reference_ingestion_service, "storage_root", tmp_path)


@pytest.mark.asyncio
async def test_parse_two_pdfs_stage_and_promote_campaign(
    client: AsyncClient,
    admin_headers,
):
    first_pdf = _fake_pdf(
        "Core validation manuscript. Tenebrio molitor and Protaetia brevitarsis on distillers grains. "
        "source_anchor: Abstract + Methods 2.2 + Results core validation. "
        "ser: 0.68. d_prime: 0.683. g_prime: 0.672. "
        "best_single_stage_ser: 0.53. signal_api_cellulase_uplift_pct: 47. "
        "Reference: Supplied BOS manuscript."
    )
    second_pdf = _fake_pdf(
        "Analytical sludge trial. Hermetia illucens on sewage sludge. "
        "source_anchor: Methods sludge screen + Analytical results. "
        "initial_cn_range: 5.0-10.0. audit_window_h: 24. classification: PASS_WITH_REVIEW. "
        "DOI:10.3390/insects15070541."
    )

    first_response = await client.post(
        "/api/v1/references/ingestion/parse",
        files={"file": ("core-relay.pdf", first_pdf, "application/pdf")},
        data={
            "source_title": "Core relay manuscript",
            "source_type": "pdf",
            "source_owner": "BOS research team",
            "license_note": "internal manuscript reference; do not externalize without review",
            "region": "Global",
            "units_json": '{"ser":"ratio","kernel_temperature_c":"degC"}',
            "ingestion_mode": "manual_review_first",
            "human_review_required": "true",
        },
        headers=admin_headers,
    )
    second_response = await client.post(
        "/api/v1/references/ingestion/parse",
        files={"file": ("sludge-screen.pdf", second_pdf, "application/pdf")},
        data={"source_title": "Sludge analytical screen", "source_type": "pdf"},
        headers=admin_headers,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    first_item = first_response.json()
    second_item = second_response.json()

    assert first_item["species_chain"] == ["MW", "PB"]
    assert first_item["feedstocks"] == ["distillers_grains"]
    assert first_item["source_owner"] == "BOS research team"
    assert first_item["license_note"].startswith("internal manuscript")
    assert first_item["region"] == "Global"
    assert first_item["units"]["ser"] == "ratio"
    assert first_item["ingestion_mode"] == "manual_review_first"
    assert first_item["human_review_required"] is True
    assert first_item["evidence_level"] == "manuscript_core"
    assert first_item["parser_metadata"]["extracted_field_count"] >= 5
    assert second_item["feedstocks"] == ["sewage_sludge"]

    list_response = await client.get("/api/v1/references/ingestion/staged", headers=admin_headers)
    assert list_response.status_code == 200
    assert list_response.json()["count"] == 2

    health_response = await client.get("/api/v1/references/ingestion/health", headers=admin_headers)
    assert health_response.status_code == 200
    health = health_response.json()
    assert health["parser_name"] == "mineru"
    assert "pipeline" in health["parser_extra_args"]
    assert health["staged_count"] == 2
    assert health["promotion_enabled"] is True

    detail_response = await client.get(
        f"/api/v1/references/ingestion/staged/{first_item['id']}",
        headers=admin_headers,
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["source_anchor"] == "Abstract + Methods 2.2 + Results core validation."

    promote_response = await client.post(
        f"/api/v1/references/ingestion/staged/{first_item['id']}/promote",
        json={"target_type": "campaign", "notes": "integration-test promotion"},
        headers=admin_headers,
    )
    assert promote_response.status_code == 200
    promoted = promote_response.json()
    assert promoted["staged_item"]["status"] == "promoted"
    assert promoted["campaign"]["species_chain"] == ["MW", "PB"]
    assert promoted["campaign"]["feedstocks"] == ["distillers_grains"]
    assert promoted["campaign"]["staging_meta"]["source_owner"] == "BOS research team"
    assert promoted["campaign"]["staging_meta"]["units"]["ser"] == "ratio"

    campaigns_response = await client.get("/api/v1/references/campaigns", headers=admin_headers)
    assert campaigns_response.status_code == 200
    campaign_keys = {campaign["key"] for campaign in campaigns_response.json()["campaigns"]}
    assert promoted["campaign"]["key"] in campaign_keys


@pytest.mark.asyncio
async def test_promotion_can_be_disabled_without_losing_staging(
    client: AsyncClient,
    admin_headers,
    monkeypatch,
):
    pdf = _fake_pdf(
        "Tenebrio molitor on distillers grains. "
        "source_anchor: Methods + Results. ser: 0.68. best_single_stage_ser: 0.53."
    )
    parse_response = await client.post(
        "/api/v1/references/ingestion/parse",
        files={"file": ("rollback.pdf", pdf, "application/pdf")},
        data={"source_title": "Rollback staged item", "source_type": "pdf"},
        headers=admin_headers,
    )
    assert parse_response.status_code == 201
    staged_id = parse_response.json()["id"]

    monkeypatch.setattr(reference_ingestion_service, "promotion_enabled", False)
    promote_response = await client.post(
        f"/api/v1/references/ingestion/staged/{staged_id}/promote",
        json={"target_type": "campaign"},
        headers=admin_headers,
    )
    assert promote_response.status_code == 400
    assert promote_response.json()["detail"] == "reference_ingestion_promotion_disabled"

    list_response = await client.get("/api/v1/references/ingestion/staged", headers=admin_headers)
    assert list_response.status_code == 200
    assert list_response.json()["count"] == 1

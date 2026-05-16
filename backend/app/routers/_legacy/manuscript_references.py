"""
BOS Pipeline v9.0 - Manuscript reference router.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.deps import require_minimum_role
from app.engine.manuscript_reference_db import (
    get_all_campaigns,
    get_campaign,
    get_campaign_keys,
)
from app.models import User
from app.services.reference_ingestion_service import reference_ingestion_service

router = APIRouter()


@router.get("/campaigns")
async def list_manuscript_campaigns(
    current_user: User = Depends(require_minimum_role("viewer")),
):
    campaigns = get_all_campaigns()
    campaigns.extend(reference_ingestion_service.list_promoted_campaigns(current_user.tenant_id))
    return {
        "campaigns": campaigns,
        "count": len(campaigns),
    }


@router.get("/campaigns/keys")
async def list_manuscript_campaign_keys(
    current_user: User = Depends(require_minimum_role("viewer")),
):
    keys = get_campaign_keys()
    keys.extend(
        campaign["key"]
        for campaign in reference_ingestion_service.list_promoted_campaigns(current_user.tenant_id)
        if isinstance(campaign.get("key"), str)
    )
    return {"keys": keys}


@router.get("/campaigns/{campaign_key}")
async def get_manuscript_campaign(
    campaign_key: str,
    current_user: User = Depends(require_minimum_role("viewer")),
):
    campaign = get_campaign(campaign_key)
    if campaign is None:
        campaign = reference_ingestion_service.get_promoted_campaign(current_user.tenant_id, campaign_key)
    if campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown manuscript campaign: {campaign_key}. Available: {get_campaign_keys()}",
        )
    return campaign

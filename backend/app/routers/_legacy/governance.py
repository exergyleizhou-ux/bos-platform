"""Shared release governance envelope endpoints."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps import require_minimum_role
from app.models import User
from app.schemas.governance import BOSV9RCManifestResponse, ReleaseGovernanceEnvelope
from app.services.release_guardrail_service import build_release_governance_envelope

router = APIRouter()
REPO_ROOT = Path(__file__).resolve().parents[3]
RC_MANIFEST_PATH = REPO_ROOT / "reports" / "stabilize-v9" / "BOS_V9_RC_MANIFEST.json"


@router.get("/governance/release-envelope", response_model=ReleaseGovernanceEnvelope)
async def get_release_governance_envelope_endpoint(
    current_user: User = Depends(require_minimum_role("operator")),
    evidence_chain_id: str | None = Query(default=None),
    source_boundary: str = Query(default="operator_requested_release_surface", min_length=1),
):
    _ = current_user
    return build_release_governance_envelope(
        evidence_chain_id=evidence_chain_id,
        source_boundary=source_boundary,
        review_required_reason="operator_requested_release_surface_requires_human_review",
    )


@router.get("/governance/rc-manifest", response_model=BOSV9RCManifestResponse)
async def get_rc_manifest_endpoint(
    current_user: User = Depends(require_minimum_role("operator")),
):
    _ = current_user
    if not RC_MANIFEST_PATH.exists():
        raise HTTPException(status_code=404, detail="rc_manifest_not_found")
    try:
        payload = json.loads(RC_MANIFEST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="rc_manifest_invalid_json") from exc
    return payload

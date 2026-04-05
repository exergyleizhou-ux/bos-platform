"""
BOS Pipeline v9.0 �� GDPR Compliance Router

Implements data subject rights under GDPR/CCPA:
  - Right to access (data export)
  - Right to erasure (account deletion)
  - Right to data portability
  - Right to rectification
  - Consent management
"""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.deps import get_current_user
from app.models import User, Batch, Calculation, AuditLog

router = APIRouter()


class ErasureRequest(BaseModel):
    """Data erasure (right to be forgotten) request."""

    confirm_username: str = Field(..., description="Type your username to confirm deletion")
    confirm_phrase: str = Field(..., pattern=r"^DELETE MY DATA$", description="Type 'DELETE MY DATA' to confirm")


class RectificationRequest(BaseModel):
    """Data rectification request."""

    field: str = Field(..., max_length=100)
    old_value: str = Field(..., max_length=500)
    new_value: str = Field(..., max_length=500)
    reason: str = Field(..., max_length=1000)


@router.get("/export")
async def export_personal_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Right to access / data portability �� export all personal data.

    Returns a JSON file containing all data associated with the user.
    """
    # User profile
    profile = {
        "id": current_user.id,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "email": current_user.email,
        "role": current_user.role,
        "tenant_id": current_user.tenant_id,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None,
        "preferences": current_user.preferences,
    }

    # Batches created by user
    batch_result = await db.execute(
        select(Batch).where(Batch.user_id == current_user.id).limit(10000)
    )
    batches = batch_result.scalars().all()
    batch_data = [
        {
            "id": b.id,
            "batch_id": b.batch_id,
            "species": b.species,
            "status": b.status,
            "dm_in": b.dm_in,
            "dm_out": b.dm_out,
            "score": b.score,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in batches
    ]

    # Calculations by user
    calc_result = await db.execute(
        select(Calculation).where(Calculation.user_id == current_user.id).limit(10000)
    )
    calcs = calc_result.scalars().all()
    calc_data = [
        {
            "id": c.id,
            "calc_type": c.calc_type,
            "status": c.status,
            "ser_value": c.ser_value,
            "passed": c.passed,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in calcs
    ]

    # Audit logs
    audit_result = await db.execute(
        select(AuditLog).where(AuditLog.user_id == current_user.id).limit(5000)
    )
    audits = audit_result.scalars().all()
    audit_data = [
        {
            "action": a.action,
            "resource": a.resource,
            "ip_address": a.ip_address,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in audits
    ]

    export_data = {
        "export_date": datetime.now(timezone.utc).isoformat(),
        "data_controller": "BOS Pipeline v9.0",
        "profile": profile,
        "batches": batch_data,
        "calculations": calc_data,
        "audit_logs": audit_data,
        "total_records": len(batch_data) + len(calc_data) + len(audit_data),
    }

    json_str = json.dumps(export_data, indent=2, default=str)

    return StreamingResponse(
        iter([json_str]),
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=personal_data_{current_user.username}.json",
        },
    )


@router.post("/erasure")
async def request_erasure(
    body: ErasureRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Right to erasure �� delete all personal data.

    This anonymizes the user account and removes PII from associated records.
    Batch/calculation data is retained in anonymized form for scientific integrity.
    """
    if body.confirm_username != current_user.username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username confirmation does not match",
        )

    # Anonymize user
    current_user.username = f"deleted_user_{current_user.id}"
    current_user.full_name = "[REDACTED]"
    current_user.email = f"deleted_{current_user.id}@redacted.invalid"
    current_user.hashed_password = "DELETED"
    current_user.is_active = False
    current_user.preferences = {}

    # Anonymize audit logs
    await db.execute(
        AuditLog.__table__.update()
        .where(AuditLog.user_id == current_user.id)
        .values(
            username="[REDACTED]",
            ip_address=None,
            user_agent=None,
        )
    )

    # Remove operator name from batches
    await db.execute(
        Batch.__table__.update()
        .where(Batch.user_id == current_user.id)
        .values(operator="[REDACTED]")
    )

    # Audit the erasure itself
    audit = AuditLog(
        action="GDPR_ERASURE",
        resource="user",
        resource_id=str(current_user.id),
        username="[REDACTED]",
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    db.add(audit)
    await db.commit()

    return {
        "message": "Personal data has been erased. Account has been deactivated.",
        "note": "Anonymized batch and calculation data is retained for scientific record integrity.",
    }


@router.post("/rectification")
async def request_rectification(
    body: RectificationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Right to rectification �� request correction of personal data.

    Creates an audit record for manual review by admin.
    """
    audit = AuditLog(
        action="GDPR_RECTIFICATION_REQUEST",
        resource="user",
        resource_id=str(current_user.id),
        username=current_user.username,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        details={
            "field": body.field,
            "old_value": body.old_value,
            "new_value": body.new_value,
            "reason": body.reason,
        },
    )
    db.add(audit)
    await db.commit()

    return {
        "message": "Rectification request has been logged for admin review",
        "request_id": audit.id,
    }

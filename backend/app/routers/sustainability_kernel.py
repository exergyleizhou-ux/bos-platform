"""Sustainability result lookup endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.deps import require_minimum_role
from app.models import User
from app.schemas.sustainability_kernel import SustainabilityResultResponse
from app.services.sustainability_kernel_service import get_sustainability_result

router = APIRouter()


@router.get("/sustainability/results/{result_id}", response_model=SustainabilityResultResponse)
async def get_sustainability_result_endpoint(
    result_id: str,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    result = await get_sustainability_result(db, tenant_id=current_user.tenant_id, result_id=result_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sustainability result not found")
    return result

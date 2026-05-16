"""
Legacy schema compatibility shim.

The canonical schema source lives in the ``app.schemas`` package. This module
keeps the historical import path alive by re-exporting the maintained schemas
instead of preserving a diverged single-file copy.
"""

from app.schemas import *  # noqa: F403
from app.schemas import __all__ as canonical_all
from app.schemas import BatchCreate, BatchResponse, TenantCreate, UserCreate, UserResponse

# Legacy names that historically pointed at "base" request models.
TenantBase = TenantCreate
UserBase = UserCreate
BatchBase = BatchCreate

__all__ = [*canonical_all, "TenantBase", "UserBase", "BatchBase", "UserResponse", "BatchResponse"]

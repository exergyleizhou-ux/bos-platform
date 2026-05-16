"""
BOS Pipeline v9.0 — Common Schemas

Shared response schemas used across multiple routers.
"""

from datetime import datetime
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str


class HealthResponse(BaseModel):
    """Liveness probe response."""

    status: str
    version: str
    environment: str
    timestamp: datetime


class ReadinessResponse(BaseModel):
    """Readiness probe response."""

    status: str
    database: str
    redis: str
    celery: str
    timestamp: datetime


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Generic paginated response wrapper.

    Usage:
        PaginatedResponse[BatchResponse]
    """

    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_previous(self) -> bool:
        return self.page > 1


class ErrorDetail(BaseModel):
    """Structured error detail."""

    code: str
    message: str
    field: Optional[str] = None


class ErrorResponse(BaseModel):
    """Structured error response."""

    detail: str
    errors: Optional[List[ErrorDetail]] = None
    request_id: Optional[str] = None

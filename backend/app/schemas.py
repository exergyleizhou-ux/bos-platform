"""
BOS Pipeline v9.0 �� Pydantic Schemas

Request/response models for API validation and serialization.
Organized by domain: auth, tenant, user, batch, calculation, etc.
"""

from datetime import datetime, date
from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, EmailStr, field_validator


T = TypeVar("T")


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Generic Response Wrappers
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated response envelope."""
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int

    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    """Simple message response."""
    message: str
    detail: Optional[str] = None


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Auth Schemas
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

class LoginRequest(BaseModel):
    """Login request body."""
    username: str = Field(..., min_length=3, max_length=150)
    password: str = Field(..., min_length=6, max_length=128)


class TokenResponse(BaseModel):
    """JWT token pair response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token expiry in seconds")


class RefreshTokenRequest(BaseModel):
    """Refresh token request body."""
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """Password change request."""
    current_password: str = Field(..., min_length=6)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Tenant Schemas
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

class TenantBase(BaseModel):
    """Base tenant fields."""
    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=63, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
    plan: str = Field(default="free", pattern=r"^(free|starter|professional|enterprise)$")


class TenantCreate(TenantBase):
    """Tenant creation request."""
    pass


class TenantUpdate(BaseModel):
    """Tenant update request (partial)."""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    plan: Optional[str] = Field(None, pattern=r"^(free|starter|professional|enterprise)$")
    is_active: Optional[bool] = None
    max_users: Optional[int] = Field(None, ge=1, le=10000)
    max_batches: Optional[int] = Field(None, ge=1, le=1000000)
    max_calculations: Optional[int] = Field(None, ge=1, le=10000000)
    settings: Optional[dict] = None


class TenantResponse(TenantBase):
    """Tenant response."""
    id: int
    is_active: bool
    max_users: int
    max_batches: int
    max_calculations: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# User Schemas
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

class UserBase(BaseModel):
    """Base user fields."""
    username: str = Field(..., min_length=3, max_length=150)
    full_name: Optional[str] = Field(None, max_length=255)
    email: Optional[EmailStr] = None
    role: str = Field(default="viewer", pattern=r"^(admin|scientist|operator|viewer|billing)$")


class UserCreate(UserBase):
    """User creation request."""
    password: str = Field(..., min_length=8, max_length=128)


class UserUpdate(BaseModel):
    """User update request (partial)."""
    full_name: Optional[str] = Field(None, max_length=255)
    email: Optional[EmailStr] = None
    role: Optional[str] = Field(None, pattern=r"^(admin|scientist|operator|viewer|billing)$")
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    """User response (no password)."""
    id: int
    tenant_id: int
    is_active: bool
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserProfileResponse(UserResponse):
    """Extended user profile with preferences."""
    preferences: Optional[dict] = None
    password_changed_at: Optional[datetime] = None


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Batch Schemas
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

class BatchBase(BaseModel):
    """Base batch fields."""
    batch_id: str = Field(..., min_length=1, max_length=100)
    species: str = Field(default="BSF", max_length=100)
    substrate: Optional[str] = Field(None, max_length=255)
    dm_in: Optional[float] = Field(None, ge=0)
    dm_out: Optional[float] = Field(None, ge=0)
    n_in: Optional[float] = Field(None, ge=0)
    n_larvae: Optional[float] = Field(None, ge=0)
    n_frass: Optional[float] = Field(None, ge=0)
    ash_in: Optional[float] = Field(None, ge=0)
    ash_out: Optional[float] = Field(None, ge=0)
    fat_in: Optional[float] = Field(None, ge=0)
    fat_out: Optional[float] = Field(None, ge=0)
    temperature: Optional[float] = Field(None, ge=-50, le=100)
    moisture: Optional[float] = Field(None, ge=0, le=100)
    feed_rate: Optional[float] = Field(None, ge=0)
    density: Optional[float] = Field(None, ge=0)
    operator: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata_json: Optional[dict] = None
    batch_date: Optional[date] = None


class BatchCreate(BatchBase):
    """Batch creation request."""
    pass


class BatchUpdate(BaseModel):
    """Batch update request (partial)."""
    batch_id: Optional[str] = Field(None, min_length=1, max_length=100)
    species: Optional[str] = Field(None, max_length=100)
    substrate: Optional[str] = Field(None, max_length=255)
    dm_in: Optional[float] = Field(None, ge=0)
    dm_out: Optional[float] = Field(None, ge=0)
    n_in: Optional[float] = Field(None, ge=0)
    n_larvae: Optional[float] = Field(None, ge=0)
    n_frass: Optional[float] = Field(None, ge=0)
    ash_in: Optional[float] = Field(None, ge=0)
    ash_out: Optional[float] = Field(None, ge=0)
    fat_in: Optional[float] = Field(None, ge=0)
    fat_out: Optional[float] = Field(None, ge=0)
    temperature: Optional[float] = Field(None, ge=-50, le=100)
    moisture: Optional[float] = Field(None, ge=0, le=100)
    feed_rate: Optional[float] = Field(None, ge=0)
    density: Optional[float] = Field(None, ge=0)
    status: Optional[str] = Field(None, pattern=r"^(logged|active|completed|archived)$")
    operator: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata_json: Optional[dict] = None
    batch_date: Optional[date] = None


class BatchResponse(BatchBase):
    """Batch response."""
    id: int
    status: str
    score: Optional[float] = None
    user_id: int
    tenant_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BatchDetailResponse(BatchResponse):
    """Batch detail with calculations."""
    calculations: List["CalculationResponse"] = []


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Calculation Schemas
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

class CalculationResponse(BaseModel):
    """Calculation result response."""
    id: int
    batch_id: int
    calc_type: str
    status: str
    inputs: Optional[dict] = None
    result: Optional[dict] = None
    ser_value: Optional[float] = None
    passed: Optional[bool] = None
    fail_codes: Optional[list] = None
    duration_ms: Optional[float] = None
    mc_samples: Optional[int] = None
    engine_version: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# SER Schemas
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

class SERRequest(BaseModel):
    """SER computation request."""
    batch_id: Optional[int] = None
    dm_in: float = Field(..., gt=0, description="Dry matter input (kg)")
    dm_out: float = Field(..., gt=0, description="Dry matter output (kg)")
    n_in: float = Field(default=0.0, ge=0, description="Nitrogen input (g)")
    n_larvae: float = Field(default=0.0, ge=0, description="Nitrogen in larvae (g)")
    n_frass: float = Field(default=0.0, ge=0, description="Nitrogen in frass (g)")
    ash_in: Optional[float] = Field(None, ge=0, description="Ash input (g)")
    ash_out: Optional[float] = Field(None, ge=0, description="Ash output (g)")
    fat_in: Optional[float] = Field(None, ge=0, description="Fat input (g)")
    fat_out: Optional[float] = Field(None, ge=0, description="Fat output (g)")


class SERResponse(BaseModel):
    """SER computation result."""
    ser_value: float
    eer: Optional[float] = None
    mcr: Optional[float] = None
    bcr: Optional[float] = None
    nitrogen_balance: Optional[Dict[str, float]] = None
    ash_balance: Optional[Dict[str, float]] = None
    fat_balance: Optional[Dict[str, float]] = None
    passed: bool
    fail_codes: List[str]
    grade: str
    recommendations: List[str]
    batch_id: Optional[int] = None
    computed_at: Optional[datetime] = None
    computation_time_ms: Optional[float] = None


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Monte Carlo Schemas
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

class MonteCarloRequest(BaseModel):
    """Monte Carlo simulation request."""
    batch_id: int
    n_samples: int = Field(default=10000, ge=100, le=1000000)
    dm_in_mean: float = Field(..., gt=0)
    dm_in_std: float = Field(default=0.5, ge=0)
    dm_out_mean: float = Field(..., gt=0)
    dm_out_std: float = Field(default=0.3, ge=0)
    seed: Optional[int] = None


class MonteCarloResponse(BaseModel):
    """Monte Carlo simulation result."""
    n_samples: int
    ser_mean: float
    ser_std: float
    ser_median: float
    ser_ci_lower: float
    ser_ci_upper: float
    percentiles: Dict[str, float]
    pass_probability: float
    histogram_bins: List[float]
    histogram_counts: List[int]
    computation_time_ms: float


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# API Key Schemas
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

class ApiKeyCreate(BaseModel):
    """API key creation request."""
    name: str = Field(..., min_length=1, max_length=255)
    expires_in_days: Optional[int] = Field(None, ge=1, le=365)
    scopes: Optional[List[str]] = None


class ApiKeyResponse(BaseModel):
    """API key response (shown only once on creation)."""
    id: int
    name: str
    prefix: str
    raw_key: Optional[str] = Field(None, description="Full key, shown only on creation")
    is_active: bool
    expires_at: Optional[datetime]
    last_used: Optional[datetime]
    usage_count: int
    scopes: Optional[list]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Webhook Schemas
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

class WebhookCreate(BaseModel):
    """Webhook registration request."""
    url: str = Field(..., min_length=10, max_length=2048)
    events: List[str] = Field(..., min_length=1)
    headers: Optional[dict] = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class WebhookResponse(BaseModel):
    """Webhook response."""
    id: int
    url: str
    events: list
    is_active: bool
    failure_count: int
    last_triggered: Optional[datetime]
    last_status_code: Optional[int]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WebhookTestRequest(BaseModel):
    """Webhook test request."""
    webhook_id: int


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Audit Log Schemas
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

class AuditLogResponse(BaseModel):
    """Audit log entry response."""
    id: int
    table_name: Optional[str]
    record_id: Optional[int]
    action: str
    resource: Optional[str]
    changed_fields: Optional[dict]
    username: Optional[str]
    user_id: Optional[int]
    ip_address: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Health Schemas
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    environment: str
    timestamp: datetime


class ReadinessResponse(BaseModel):
    """Readiness check with dependency status."""
    status: str
    database: str
    redis: str
    celery: str
    timestamp: datetime


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Digital Twin Schemas
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

class DigitalTwinCreate(BaseModel):
    """Digital twin creation request."""
    twin_id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    species: str = Field(default="BSF", max_length=100)
    config: Optional[dict] = None
    parameters: Optional[dict] = None


class DigitalTwinUpdate(BaseModel):
    """Digital twin update request."""
    name: Optional[str] = Field(None, max_length=255)
    state: Optional[dict] = None
    config: Optional[dict] = None
    parameters: Optional[dict] = None
    is_active: Optional[bool] = None


class DigitalTwinResponse(BaseModel):
    """Digital twin response."""
    id: int
    twin_id: str
    name: str
    species: str
    state: Optional[dict]
    config: Optional[dict]
    parameters: Optional[dict]
    last_sync: Optional[datetime]
    version: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Feature Flag Schemas
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

class FeatureFlagResponse(BaseModel):
    """Feature flag response."""
    id: int
    name: str
    description: Optional[str]
    enabled: bool
    percentage_rollout: Optional[int]
    tenant_overrides: Optional[dict]
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FeatureFlagUpdate(BaseModel):
    """Feature flag update request."""
    enabled: Optional[bool] = None
    description: Optional[str] = None
    percentage_rollout: Optional[int] = Field(None, ge=0, le=100)
    tenant_overrides: Optional[dict] = None


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Export Schemas
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

class ExportRequest(BaseModel):
    """Data export request."""
    format: str = Field(default="csv", pattern=r"^(csv|json|xlsx|parquet)$")
    batch_ids: Optional[List[int]] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    include_calculations: bool = Field(default=True)


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# GDPR Schemas
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

class GdprExportResponse(BaseModel):
    """GDPR data export response."""
    user: dict
    batches: list
    calculations: list
    audit_logs: list
    api_keys: list
    webhooks: list
    export_date: datetime


class GdprAnonymizeRequest(BaseModel):
    """GDPR anonymization request."""
    user_id: int
    reason: Optional[str] = None


class GdprDeleteRequest(BaseModel):
    """GDPR hard deletion request."""
    user_id: int
    reason: Optional[str] = None
    confirm: bool = Field(..., description="Must be true to proceed")

    @field_validator("confirm")
    @classmethod
    def validate_confirm(cls, v: bool) -> bool:
        if not v:
            raise ValueError("You must set confirm=true to delete user data")
        return v


# Forward reference resolution
BatchDetailResponse.model_rebuild()

"""
BOS Pipeline v9.0 — SQLAlchemy ORM Models

All models use the shared Base from app.db and follow multi-tenant conventions:
- Every tenant-scoped model has a tenant_id column
- PostgreSQL RLS policies enforce tenant isolation at the DB level
- Temporal tables (valid_from/valid_to) support point-in-time queries
"""

from datetime import datetime, date
from typing import Optional, List, Any

from sqlalchemy import (
    Boolean,
    BigInteger,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

SQLITE_BIGINT_PK = BigInteger().with_variant(Integer, "sqlite")


# ═══════════════════════════════════════════════
# 1. Tenant
# ═══════════════════════════════════════════════


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(63), nullable=False, unique=True, index=True)
    plan: Mapped[str] = mapped_column(String(50), nullable=False, server_default="free")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    max_users: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5")
    max_batches: Mapped[int] = mapped_column(Integer, nullable=False, server_default="100")
    max_calculations: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1000")
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    settings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    users: Mapped[List["User"]] = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    batches: Mapped[List["Batch"]] = relationship("Batch", back_populates="tenant", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Tenant(id={self.id}, name='{self.name}', plan='{self.plan}')>"


# ═══════════════════════════════════════════════
# 2. User
# ═══════════════════════════════════════════════


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(150), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False, server_default="viewer", index=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", index=True)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    preferences: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="users")
    batches: Mapped[List["Batch"]] = relationship("Batch", back_populates="user", cascade="all, delete-orphan")
    calculations: Mapped[List["Calculation"]] = relationship(
        "Calculation", back_populates="user", cascade="all, delete-orphan"
    )
    api_keys: Mapped[List["ApiKey"]] = relationship("ApiKey", back_populates="user", cascade="all, delete-orphan")
    webhooks: Mapped[List["Webhook"]] = relationship("Webhook", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}', tenant_id={self.tenant_id})>"


class UserRoleGrant(Base):
    __tablename__ = "user_role_grants"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", "role", name="uq_user_role_grants_tenant_user_role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    granted_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<UserRoleGrant(id={self.id}, user_id={self.user_id}, role='{self.role}', "
            f"tenant_id={self.tenant_id}, is_active={self.is_active})>"
        )


# ═══════════════════════════════════════════════
# 3. Batch
# ═══════════════════════════════════════════════


class UserRoleGrantAuditRecord(Base):
    __tablename__ = "user_role_grant_audit_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role_grant_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("user_role_grants.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    role: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    previous_is_active: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    new_is_active: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    previous_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    previous_granted_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    new_granted_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return (
            f"<UserRoleGrantAuditRecord(id={self.id}, user_id={self.user_id}, role='{self.role}', "
            f"action='{self.action}', tenant_id={self.tenant_id})>"
        )


class Batch(Base):
    __tablename__ = "batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    species: Mapped[str] = mapped_column(String(100), nullable=False, server_default="BSF", index=True)
    substrate: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    dm_in: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dm_out: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    n_in: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    n_larvae: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    n_frass: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ash_in: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ash_out: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fat_in: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fat_out: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    moisture: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    feed_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    density: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="logged", index=True)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    operator: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    batch_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="batches")
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="batches")
    calculations: Mapped[List["Calculation"]] = relationship(
        "Calculation", back_populates="batch", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Batch(id={self.id}, batch_id='{self.batch_id}', species='{self.species}', status='{self.status}')>"


# ═══════════════════════════════════════════════
# 4. Calculation
# ═══════════════════════════════════════════════


class Calculation(Base):
    __tablename__ = "calculations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    calc_type: Mapped[str] = mapped_column(String(50), nullable=False, server_default="ser", index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="pending", index=True)
    inputs: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ser_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    passed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, index=True)
    fail_codes: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    duration_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mc_samples: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    engine_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    batch: Mapped["Batch"] = relationship("Batch", back_populates="calculations")
    user: Mapped["User"] = relationship("User", back_populates="calculations")

    def __repr__(self) -> str:
        return (
            f"<Calculation(id={self.id}, calc_type='{self.calc_type}', status='{self.status}', passed={self.passed})>"
        )


# ═══════════════════════════════════════════════
# 5. Audit Log
# ═══════════════════════════════════════════════


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(SQLITE_BIGINT_PK, primary_key=True, autoincrement=True)
    table_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    record_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resource: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    old_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    new_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    changed_fields: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action='{self.action}', table='{self.table_name}')>"


# ═══════════════════════════════════════════════
# 6. API Key
# ═══════════════════════════════════════════════


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    prefix: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    hashed_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", index=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    rate_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    scopes: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="api_keys")

    def __repr__(self) -> str:
        return f"<ApiKey(id={self.id}, name='{self.name}', prefix='{self.prefix}')>"


# Backward-compatible alias used by some routers.
APIKey = ApiKey


# ═══════════════════════════════════════════════
# 7. Webhook
# ═══════════════════════════════════════════════


class Webhook(Base):
    __tablename__ = "webhooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    events: Mapped[list] = mapped_column(JSON, nullable=False)
    secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", index=True)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_triggered: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    headers: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="webhooks")
    deliveries: Mapped[List["WebhookDelivery"]] = relationship(
        "WebhookDelivery", back_populates="webhook", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Webhook(id={self.id}, url='{self.url[:40]}...', events={self.events})>"


# ═══════════════════════════════════════════════
# 8. Webhook Delivery
# ═══════════════════════════════════════════════


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id: Mapped[int] = mapped_column(SQLITE_BIGINT_PK, primary_key=True, autoincrement=True)
    webhook_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("webhooks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    response_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_time_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    webhook: Mapped["Webhook"] = relationship("Webhook", back_populates="deliveries")

    def __repr__(self) -> str:
        return f"<WebhookDelivery(id={self.id}, event='{self.event}', success={self.success})>"


# ═══════════════════════════════════════════════
# 9. Digital Twin
# ═══════════════════════════════════════════════


class DigitalTwin(Base):
    __tablename__ = "digital_twins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    twin_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    species: Mapped[str] = mapped_column(String(100), nullable=False, server_default="BSF", index=True)
    state: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    parameters: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    last_sync: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    snapshots: Mapped[List["DigitalTwinSnapshot"]] = relationship(
        "DigitalTwinSnapshot", back_populates="twin", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<DigitalTwin(id={self.id}, twin_id='{self.twin_id}', name='{self.name}')>"


# ═══════════════════════════════════════════════
# 10. Digital Twin Snapshot
# ═══════════════════════════════════════════════


class DigitalTwinSnapshot(Base):
    __tablename__ = "digital_twin_snapshots"

    id: Mapped[int] = mapped_column(SQLITE_BIGINT_PK, primary_key=True, autoincrement=True)
    twin_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("digital_twins.id", ondelete="CASCADE"), nullable=False, index=True
    )
    state: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    parameters: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    trigger: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    twin: Mapped["DigitalTwin"] = relationship("DigitalTwin", back_populates="snapshots")

    def __repr__(self) -> str:
        return f"<DigitalTwinSnapshot(id={self.id}, twin_id={self.twin_id}, trigger='{self.trigger}')>"


# ═══════════════════════════════════════════════
# 11. Feature Flag (DB model for runtime overrides)
# ═══════════════════════════════════════════════


class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    percentage_rollout: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tenant_overrides: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    user_overrides: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<FeatureFlag(id={self.id}, name='{self.name}', enabled={self.enabled})>"


# ═══════════════════════════════════════════════
# 12. Notification Preferences
# ═══════════════════════════════════════════════


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    weekly_digest: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    ser_alerts: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    anomaly_alerts: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    batch_complete_alerts: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    webhook_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<NotificationPreference(id={self.id}, user_id={self.user_id})>"


# ═══════════════════════════════════════════════
# 13. Scheduled Report
# ═══════════════════════════════════════════════


class ScheduledReport(Base):
    __tablename__ = "scheduled_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    report_type: Mapped[str] = mapped_column(String(50), nullable=False)
    schedule_cron: Mapped[str] = mapped_column(String(100), nullable=False)
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    recipients: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", index=True)
    last_run: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    run_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<ScheduledReport(id={self.id}, name='{self.name}', type='{self.report_type}')>"


# ═══════════════════════════════════════════════
# 14. Trace (internal request tracing)
# ═══════════════════════════════════════════════


class Trace(Base):
    __tablename__ = "traces"

    id: Mapped[int] = mapped_column(SQLITE_BIGINT_PK, primary_key=True, autoincrement=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    span_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    parent_span_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    operation: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    service: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    duration_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True, index=True)
    attributes: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    events: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    def __repr__(self) -> str:
        return f"<Trace(id={self.id}, operation='{self.operation}', duration_ms={self.duration_ms})>"


# ═══════════════════════════════════════════════
# 15. GDPR Deletion Request
# ═══════════════════════════════════════════════


class GdprDeletionRequest(Base):
    __tablename__ = "gdpr_deletion_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="pending", index=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<GdprDeletionRequest(id={self.id}, user_id={self.user_id}, status='{self.status}')>"


class WechatOfficialAccount(Base):
    __tablename__ = "wechat_official_accounts"
    __table_args__ = (UniqueConstraint("account_key", name="uq_wechat_official_accounts_account_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    default_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    app_id: Mapped[str] = mapped_column(String(128), nullable=False)
    app_secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    token: Mapped[str] = mapped_column(String(255), nullable=False)
    encoding_aes_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    welcome_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", index=True)
    last_access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    access_token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    contacts: Mapped[List["WechatContactBinding"]] = relationship(
        "WechatContactBinding", back_populates="official_account", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<WechatOfficialAccount(id={self.id}, account_key='{self.account_key}', tenant_id={self.tenant_id})>"


class WechatContactBinding(Base):
    __tablename__ = "wechat_contact_bindings"
    __table_args__ = (
        UniqueConstraint("official_account_id", "openid", name="uq_wechat_contact_bindings_account_openid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    official_account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("wechat_official_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    openid: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    unionid: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    default_session_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("code_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    last_inbound_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_outbound_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    official_account: Mapped["WechatOfficialAccount"] = relationship(
        "WechatOfficialAccount", back_populates="contacts"
    )

    def __repr__(self) -> str:
        return f"<WechatContactBinding(id={self.id}, openid='{self.openid}', tenant_id={self.tenant_id})>"


from app.models_code import (  # noqa: E402,F401
    CodeAgentRuntimeState,
    CodeArtifact,
    CodeAutomationJob,
    CodeBranchState,
    CodeEvent,
    CodeLspSession,
    CodeMemorySnapshot,
    CodeMcpServer,
    CodeReflectionRun,
    CodeSession,
    CodeSkill,
    CodeSkillRevision,
    CodeSubagentRun,
    CodeTask,
    CodeToolCall,
    CodeTurn,
    CodeVerificationRun,
    CodeWorker,
    CodeWorkerEvent,
    CodeWorkspace,
    CodeWorkspaceLease,
)
from app.models_bos import (  # noqa: E402,F401
    AuditPacket,
    AssistantConfirmationRequestRecord,
    AssistantRunRecord,
    AssistantToolCallRecord,
    BatchAssayRecord,
    BenchmarkCaseRecord,
    BenchmarkRunRecord,
    BoundaryLedger,
    ControlAPIProfile,
    EvidenceItemRecord,
    EvidencePackRecord,
    ExecutorProfile,
    FinalActionAuditRecord,
    FinalActionRequestDraftRecord,
    FinalActionReviewPacketSnapshot,
    HistoricalReplayRunRecord,
    HumanApprovalRequestRecord,
    InputSnapshotRecord,
    KnowledgeRelationRecord,
    LocalityProfile,
    ModelRegistryRecord,
    ModelVersionRecord,
    PortabilityAudit,
    ReleaseDecision,
    ReleaseGateRecord,
    ReleasePacketAttachmentRecord,
    SignalBatch,
    SimulationAuditEventRecord,
    SimulationCycleRecord,
    SimulationRunRecord,
    SimulationScenarioRecord,
    SustainabilityResultRecord,
)

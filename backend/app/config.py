"""
BOS Pipeline v9.0 �� Application Configuration

Centralized settings using pydantic-settings.
All values are read from environment variables with sensible defaults.
"""

from functools import lru_cache
from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ���� Application ����
    APP_NAME: str = "BOS Pipeline"
    APP_VERSION: str = "9.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "change-me-to-a-random-64-char-string-in-production"
    ALLOWED_HOSTS: str = "localhost,127.0.0.1"

    # ���� Database ����
    DATABASE_URL: str = "sqlite+aiosqlite:///./bos.db"
    DATABASE_URL_SYNC: str = "sqlite:///./bos.db"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600
    DB_ECHO: bool = False

    # ���� Redis ����
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_MAX_CONNECTIONS: int = 50

    # ���� Celery ����
    CELERY_BROKER_URL: str = "redis://redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"

    # ���� JWT Authentication ����
    JWT_SECRET_KEY: str = "change-me-jwt-secret-key-at-least-32-chars"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ���� CORS ����
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://localhost:8080"

    # ���� Rate Limiting ����
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_BURST: int = 10

    # ���� Stripe Billing ����
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_STARTER: str = ""
    STRIPE_PRICE_PROFESSIONAL: str = ""
    STRIPE_PRICE_ENTERPRISE: str = ""

    # ���� Email (SMTP) ����
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "BOS Pipeline <noreply@bos-pipeline.com>"

    # ���� Sentry ����
    SENTRY_DSN: str = ""
    SENTRY_ENVIRONMENT: str = "development"

    # ���� OpenTelemetry ����
    OTEL_ENABLED: bool = False
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    OTEL_SERVICE_NAME: str = "bos-pipeline-backend"
    OTEL_TRACES_SAMPLER: str = "parentbased_traceidratio"
    OTEL_TRACES_SAMPLER_ARG: float = 0.2
    OTEL_CONSOLE_EXPORT: bool = False
    OTEL_ENVIRONMENT: str = "development"

    # ���� Feature Flags (env-level defaults) ����
    FF_ENABLE_MONTE_CARLO: bool = True
    FF_ENABLE_DIGITAL_TWIN: bool = True
    FF_ENABLE_AUTOML: bool = False
    FF_ENABLE_WEBSOCKET: bool = True
    FF_ENABLE_EXPORT_PARQUET: bool = True
    FF_ENABLE_BILLING: bool = True
    FF_ENABLE_MULTI_LANGUAGE: bool = True
    FF_ENABLE_DARK_MODE: bool = True

    # ���� Computed Properties ����

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS_ORIGINS string into a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def allowed_hosts_list(self) -> List[str]:
        """Parse ALLOWED_HOSTS string into a list."""
        return [host.strip() for host in self.ALLOWED_HOSTS.split(",") if host.strip()]

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.ENVIRONMENT.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.ENVIRONMENT.lower() == "development"

    @property
    def is_testing(self) -> bool:
        """Check if running in test mode."""
        return self.ENVIRONMENT.lower() == "testing"

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if v == "change-me-to-a-random-64-char-string-in-production":
            import warnings
            warnings.warn(
                "Using default SECRET_KEY. Set a proper secret in production!",
                UserWarning,
                stacklevel=2,
            )
        return v

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        if len(v) < 32:
            import warnings
            warnings.warn(
                "JWT_SECRET_KEY should be at least 32 characters for security.",
                UserWarning,
                stacklevel=2,
            )
        return v


@lru_cache()
def get_settings() -> Settings:
    """
    Cached settings factory.

    Returns the same Settings instance throughout the application lifecycle.
    Cache is invalidated on process restart.
    """
    return Settings()

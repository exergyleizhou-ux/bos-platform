"""
BOS Pipeline v9.0 application configuration.

Centralized settings using pydantic-settings.
All values are read from environment variables with sensible defaults.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application-wide configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = "BOS Pipeline"
    APP_VERSION: str = "9.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "change-me-to-a-random-64-char-string-in-production"
    ALLOWED_HOSTS: str = "localhost,127.0.0.1"

    DATABASE_URL: str = "sqlite+aiosqlite:///./bos.db"
    DATABASE_URL_SYNC: str = "sqlite:///./bos.db"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600
    DB_ECHO: bool = False

    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_MAX_CONNECTIONS: int = 50

    CELERY_BROKER_URL: str = "redis://127.0.0.1:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://127.0.0.1:6379/2"

    JWT_SECRET_KEY: str = "change-me-jwt-secret-key-at-least-32-chars"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:8080"

    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_BURST: int = 10

    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_STARTER: str = ""
    STRIPE_PRICE_PROFESSIONAL: str = ""
    STRIPE_PRICE_ENTERPRISE: str = ""

    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "BOS Pipeline <noreply@bos-pipeline.com>"

    SENTRY_DSN: str = ""
    SENTRY_ENVIRONMENT: str = "development"

    OTEL_ENABLED: bool = False
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    OTEL_SERVICE_NAME: str = "bos-pipeline-backend"
    OTEL_TRACES_SAMPLER: str = "parentbased_traceidratio"
    OTEL_TRACES_SAMPLER_ARG: float = 0.2
    OTEL_CONSOLE_EXPORT: bool = False
    OTEL_ENVIRONMENT: str = "development"

    FF_ENABLE_MONTE_CARLO: bool = True
    FF_ENABLE_DIGITAL_TWIN: bool = True
    FF_ENABLE_AUTOML: bool = False
    FF_ENABLE_WEBSOCKET: bool = True
    FF_ENABLE_EXPORT_PARQUET: bool = True
    FF_ENABLE_BILLING: bool = True
    FF_ENABLE_MULTI_LANGUAGE: bool = True
    FF_ENABLE_DARK_MODE: bool = True
    FF_ENABLE_BOS_CODE: bool = False
    FF_ENABLE_BOS_GUIDANCE: bool = False
    FF_ENABLE_BOS_PORTABILITY_RECOMMENDATION: bool = False
    FF_ENABLE_BOS_AUDIT_EXPORT: bool = False
    FF_ENABLE_BOS_LOCALITY_RELEASE: bool = False
    FF_ENABLE_BOS_SIGNAL_COMPILE: bool = False
    FF_ENABLE_BOS_TRUE_BOUNDARY_LEDGER: bool = False
    FF_ENABLE_BOS_SIMULATION_LAB: bool = False

    BOS_CODE_WORKTREE_ROOT: str = ".bos-code-worktrees"
    BOS_CODE_GIT_EXECUTABLE: str = ""
    BOS_CODE_DEFAULT_PROVIDER: str = "openai-team"
    BOS_CODE_DEFAULT_MODEL: str = "gpt-5.5"
    BOS_CODE_MAX_SESSION_TOKENS: int = 64000
    BOS_CODE_MAX_FILE_READ_BYTES: int = 262144
    BOS_CODE_MAX_FILE_WRITE_BYTES: int = 131072
    BOS_CODE_SAFE_BASH_TIMEOUT_SEC: int = 30
    BOS_CODE_LEASE_TTL_SEC: int = 300
    BOS_CODE_HEARTBEAT_INTERVAL_SEC: int = 30
    BOS_CODE_EVENT_REPLAY_LIMIT: int = 500
    BOS_CODE_ENABLE_LLM_PLANNER: bool = False
    BOS_CODE_PROVIDER_MAX_REQUESTS_PER_HOUR: int = 30
    BOS_CODE_PROVIDER_MAX_ESTIMATED_COST_PER_HOUR: float = 2.0
    BOS_CODE_PROVIDER_BUDGET_COOLDOWN_SEC: int = 900
    BOS_CODE_SUBAGENT_ASYNC_DISPATCH: bool = False
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_ORGANIZATION: str = ""
    OPENAI_PROJECT: str = ""
    OPENAI_PUBLIC_API_KEY: str = ""
    OPENAI_PUBLIC_BASE_URL: str = ""
    OPENAI_PUBLIC_ORGANIZATION: str = ""
    OPENAI_PUBLIC_PROJECT: str = ""
    OPENAI_TEAM_API_KEY: str = ""
    OPENAI_TEAM_BASE_URL: str = ""
    OPENAI_TEAM_ORGANIZATION: str = ""
    OPENAI_TEAM_PROJECT: str = ""
    BOS_CODE_OPENAI_REASONING_EFFORT: str = "medium"
    BOS_MEDIA_REMOTION_ENABLED: bool = True
    BOS_MEDIA_REMOTION_RUNTIME_DIR: str = str(REPO_ROOT / "frontend" / "remotion-runtime")
    BOS_MEDIA_REMOTION_OUTPUT_DIR: str = str(REPO_ROOT / "backend" / "generated" / "remotion")
    BOS_MEDIA_REMOTION_NODE_EXECUTABLE: str = "node"
    BOS_MEDIA_REMOTION_LOG_LEVEL: str = "error"
    BOS_MEDIA_REMOTION_ENABLE_LLM_SUGGESTIONS: bool = True
    BOS_MEDIA_REMOTION_SUGGEST_MODEL: str = "gpt-5.5"
    BOS_MEDIA_REMOTION_PRESET_STORE_PATH: str = str(
        REPO_ROOT / "backend" / "generated" / "remotion" / "presets.json"
    )
    BOS_NATIVE_MODELS_ENABLED: bool = True
    BOS_NATIVE_MODELS_CACHE_DIR: str = str(REPO_ROOT / "backend" / "generated" / "native-models")
    BOS_NATIVE_MODELS_ALLOW_REMOTE_REFERENCES: bool = True
    BOS_NATIVE_YOLO11_DSCONV_WEIGHTS_PATH: str = ""
    BOS_NATIVE_INSECTSAM_MODEL_PATH: str = ""
    BOS_NATIVE_INSECTA_MODEL_PATH: str = ""
    BOS_NATIVE_TIMER_S1_MODEL_REF: str = "bytedance-research/Timer-S1"
    BOS_NATIVE_CHRONOS_BOLT_MODEL_REF: str = "autogluon/chronos-bolt-small"
    BOS_NATIVE_TIMER_S1_ENABLE_DOWNLOAD: bool = False
    BOS_REFERENCE_INGESTION_STORAGE_DIR: str = str(REPO_ROOT / "backend" / "generated" / "reference-ingestion")
    BOS_REFERENCE_INGESTION_PROMOTION_ENABLED: bool = True
    BOS_EXTERNAL_SHARE_ALLOWED_ENDPOINTS: str = "http://127.0.0.1,http://localhost"
    BOS_EXTERNAL_SHARE_TIMEOUT_SECONDS: int = 10
    BOS_MINERU_COMMAND: str = "mineru"
    BOS_MINERU_TIMEOUT_SECONDS: int = 180
    BOS_MINERU_EXTRA_ARGS: str = "-b pipeline -m txt"
    WECHAT_ENABLE_OFFICIAL_ACCOUNTS: bool = True
    WECHAT_REPLY_TIMEOUT_SECONDS: int = 8
    WECHAT_DEFAULT_WELCOME_MESSAGE: str = "你好，这里是 BOS 助手。你可以直接发送文本消息开始对话。"
    WECHAT_DEFAULT_UNSUPPORTED_MESSAGE: str = "当前仅支持文本消息。请直接发送文字内容。"
    WECHAT_DEFAULT_ERROR_MESSAGE: str = "消息已收到，但处理时出现问题，请稍后再试。"
    WECHAT_DEFAULT_EMPTY_MESSAGE: str = "我收到了空消息，请发送文字内容。"
    WECHAT_DEFAULT_PROMPT_PREFIX: str = (
        "你现在通过微信官方号与用户对话。"
        "请默认使用简体中文回复，语气自然、直接、友好。"
        "优先给出明确可执行答案，不要空泛寒暄。"
        "除非用户要求，否则回复尽量简洁。"
        "如果信息不足，先基于现有信息给出最有帮助的下一步。"
    )
    WECHAT_WEB_BASE_URL: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS_ORIGINS string into a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def allowed_hosts_list(self) -> list[str]:
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
    def validate_secret_key(cls, value: str) -> str:
        if value == "change-me-to-a-random-64-char-string-in-production":
            import warnings

            warnings.warn(
                "Using default SECRET_KEY. Set a proper secret in production!",
                UserWarning,
                stacklevel=2,
            )
        return value

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret(cls, value: str) -> str:
        if len(value) < 32:
            import warnings

            warnings.warn(
                "JWT_SECRET_KEY should be at least 32 characters for security.",
                UserWarning,
                stacklevel=2,
            )
        return value


@lru_cache()
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed, fail-fast configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://forgerun:forgerun_dev_password@localhost:5432/forgerun",
        description="Async PostgreSQL connection URI for SQLAlchemy/asyncpg",
    )
    DATABASE_URL_SYNC: str = Field(
        default="postgresql://forgerun:forgerun_dev_password@localhost:5432/forgerun",
        description="Synchronous PostgreSQL connection URI for Alembic migrations",
    )

    # Redis
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URI",
    )

    # Kafka
    KAFKA_BROKERS: str = Field(
        default="localhost:9092",
        description="Comma-separated Kafka broker addresses",
    )
    KAFKA_TOPIC_SUBMISSION_CREATED: str = "forge.submission.created.v1"
    KAFKA_TOPIC_EXECUTION_SCHEDULED: str = "forge.execution.scheduled.v1"
    KAFKA_TOPIC_EXECUTION_STARTED: str = "forge.execution.started.v1"
    KAFKA_TOPIC_EXECUTION_COMPLETED: str = "forge.execution.completed.v1"
    KAFKA_TOPIC_EXECUTION_FAILED: str = "forge.execution.failed.v1"
    KAFKA_TOPIC_DEADLETTER: str = "forge.deadletter.v1"

    # Security
    JWT_SECRET: str = Field(
        default="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        description="Secret key for JWT signature (min 32 chars)",
    )
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_ISSUER: str = "forgerun.io"
    JWT_AUDIENCE: str = "forgerun-api"

    # Sandbox / Execution Policy
    SANDBOX_RUNTIME_CLASS: str = Field(
        default="runc",
        description="RuntimeClass for Kubernetes Jobs (runsc in production, runc in local dev)",
    )
    DEFAULT_TIME_LIMIT_MS: int = Field(default=2000, ge=100, le=60000)
    DEFAULT_MEMORY_LIMIT_MB: int = Field(default=256, ge=16, le=2048)
    MAX_OUTPUT_BYTES: int = Field(default=65536, ge=1024, le=10485760)
    MAX_CONCURRENT_ATTEMPTS: int = Field(default=50, ge=1, le=1000)

    # Observability
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    OTEL_SERVICE_NAME: str = "forgerun-api"
    LOG_LEVEL: str = "INFO"

    @field_validator("JWT_SECRET")
    @classmethod
    def validate_jwt_secret_length(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters long")
        return v


# Cached global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

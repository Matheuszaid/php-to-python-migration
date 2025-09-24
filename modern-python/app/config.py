from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Modern configuration management with environment validation."""

    # Application
    app_name: str = Field(default="Modern Billing System", alias="APP_NAME")
    app_env: Literal["dev", "test", "prod"] = Field(default="dev", alias="APP_ENV")
    app_version: str = Field(default="2.0.0", alias="APP_VERSION")
    debug: bool = Field(default=False, alias="DEBUG")

    # Database - Modern async connection
    database_url: str = Field(
        default="postgresql+asyncpg://billing_user:billing_pass@localhost:5432/billing_modern",
        alias="DATABASE_URL"
    )

    # Redis for background tasks
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # Payment Processing (securely managed)
    stripe_secret_key: str = Field(default="", alias="STRIPE_SECRET_KEY")
    paypal_client_id: str = Field(default="", alias="PAYPAL_CLIENT_ID")
    paypal_client_secret: str = Field(default="", alias="PAYPAL_CLIENT_SECRET")

    # Modern security settings
    secret_key: str = Field(default="dev-secret-change-in-prod", alias="SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30)

    # Rate limiting
    rate_limit_requests: int = Field(default=100, alias="RATE_LIMIT_REQUESTS")
    rate_limit_period: int = Field(default=60, alias="RATE_LIMIT_PERIOD")  # seconds

    # Billing configuration
    max_retry_attempts: int = Field(default=3)
    billing_batch_size: int = Field(default=100)
    billing_timeout_seconds: int = Field(default=30)

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }

    def get_masked_config(self) -> dict:
        """Get configuration with sensitive values masked for logging."""
        config = self.model_dump()
        sensitive_keys = [
            "stripe_secret_key",
            "paypal_client_secret",
            "secret_key",
            "database_url",
            "redis_url"
        ]

        for key in sensitive_keys:
            if config.get(key):
                config[key] = "***MASKED***"

        return config


def get_settings() -> Settings:
    """Get application settings singleton."""
    return Settings()


def settings_dep() -> Settings:
    """Settings dependency for FastAPI DI."""
    return get_settings()
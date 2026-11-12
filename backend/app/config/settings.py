from functools import lru_cache
from typing import Annotated, Literal

from fastapi import Depends
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_TEST_ONLY_JWT_SECRET = "testing-only-signing-key-never-used-outside-tests"  # noqa: S105
PUBLISHED_PLACEHOLDER_SECRETS = frozenset(
    {
        "replace-with-at-least-32-random-bytes",
        _TEST_ONLY_JWT_SECRET,
    }
)
PLACEHOLDER_SECRET_MARKERS = ("replace-with", "__generated__", "changeme")


class Settings(BaseSettings):
    """Application settings loaded from the environment and `.env`.

    Immutable and thread-safe once instantiated.
    """

    APP_NAME: str = "Backend API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    ENVIRONMENT: Literal["development", "production"] = Field(
        default="production",
        description=(
            "Deployment environment; development unlocks local-only conveniences "
            "such as the interactive API docs"
        ),
    )
    LOG_LEVEL: str = "INFO"

    HOST: str = "localhost"
    PORT: int = 8000
    WORKERS: int = 1

    DATABASE_URL: str | None = Field(
        default=None,
        description="PostgreSQL URL using the postgresql+asyncpg scheme",
    )
    DB_POOL_MIN_SIZE: int = 1
    DB_POOL_MAX_SIZE: int = 10
    DB_POOL_TIMEOUT: float = 30.0
    DB_POOL_RECYCLE: int = 1800
    DB_POOL_PRE_PING: bool = True
    TESTING: bool = False

    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    AUTH_JWT_SECRET: SecretStr = SecretStr("")
    AUTH_JWT_ISSUER: str = "backend-api"
    AUTH_JWT_AUDIENCE: str = "backend-web"
    AUTH_ACCESS_TTL_SECONDS: int = 900
    AUTH_SESSION_TTL_SECONDS: int = 30 * 24 * 60 * 60
    AUTH_SESSION_IDLE_TTL_SECONDS: int = 14 * 24 * 60 * 60
    AUTH_REFRESH_GRACE_SECONDS: int = 15
    AUTH_COOKIE_SECURE: bool | None = None
    AUTH_ACCESS_COOKIE: str = "app_access"
    AUTH_REFRESH_COOKIE: str = "app_refresh"
    AUTH_CSRF_COOKIE: str = "app_csrf"

    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_TRUST_FORWARDED: bool = Field(
        default=False,
        description=(
            "Read the client address from the right-most X-Forwarded-For entry; "
            "enable only behind a proxy that sets it"
        ),
    )
    RATE_LIMIT_CLIENT_IP_HEADER: str = Field(
        default="",
        description=(
            "Header the edge proxy overwrites with the client address it saw "
            "(for example X-Real-IP); takes precedence over X-Forwarded-For. "
            "Leave empty unless every request passes through that proxy"
        ),
    )
    RATE_LIMIT_LOGIN_PER_EMAIL: int = Field(default=10, ge=1)
    RATE_LIMIT_LOGIN_PER_IP: int = Field(default=50, ge=1)
    RATE_LIMIT_LOGIN_WINDOW_SECONDS: int = Field(default=900, ge=1)

    ERROR_ALERT_WEBHOOK_URL: SecretStr = Field(
        default=SecretStr(""),
        description=(
            'Webhook that receives unhandled-error alerts as JSON {"text": ...}, '
            "such as a Slack incoming webhook; empty logs the alerts instead"
        ),
    )
    ERROR_ALERT_REPEAT_WINDOW_SECONDS: int = Field(
        default=600,
        gt=0,
        description=(
            "Seconds a delivered error alert absorbs identical repeats before one "
            "summary with their count is delivered"
        ),
    )
    ERROR_ALERT_MAX_POSTS_PER_HOUR: int = Field(
        default=20,
        gt=0,
        description=(
            "Most error alert deliveries per process per hour; the excess is "
            "dropped and counted in one notice"
        ),
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        frozen=True,
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_database_configuration(self) -> "Settings":
        if not self.TESTING and not self.DATABASE_URL:
            raise ValueError(
                "DATABASE_URL is required outside explicitly isolated tests; "
                "configure a PostgreSQL postgresql+asyncpg:// URL."
            )
        return self

    @model_validator(mode="after")
    def validate_production_configuration(self) -> "Settings":
        if self.DEBUG and self.ENVIRONMENT == "production":
            raise ValueError(
                "DEBUG must be false when ENVIRONMENT is production; "
                "set ENVIRONMENT=development for local debugging."
            )
        return self

    @model_validator(mode="after")
    def validate_auth_configuration(self) -> "Settings":
        if not self.AUTH_JWT_SECRET.get_secret_value():
            if not self.TESTING:
                raise ValueError(
                    "AUTH_JWT_SECRET is required; generate one with "
                    "`python -c 'import secrets; print(secrets.token_urlsafe(48))'`. "
                    "This template ships no default signing key on purpose."
                )
            object.__setattr__(
                self, "AUTH_JWT_SECRET", SecretStr(_TEST_ONLY_JWT_SECRET)
            )
        if len(self.AUTH_JWT_SECRET.get_secret_value().encode()) < 32:
            raise ValueError("AUTH_JWT_SECRET must contain at least 256 bits")
        if not self.TESTING and _is_placeholder_secret(
            self.AUTH_JWT_SECRET.get_secret_value()
        ):
            raise ValueError(
                "AUTH_JWT_SECRET is a placeholder published in this repository; "
                "generate a real one with "
                "`python -c 'import secrets; print(secrets.token_urlsafe(48))'`."
            )
        if (
            self.AUTH_ACCESS_TTL_SECONDS <= 0
            or self.AUTH_SESSION_TTL_SECONDS <= 0
            or self.AUTH_SESSION_IDLE_TTL_SECONDS <= 0
            or self.AUTH_REFRESH_GRACE_SECONDS <= 0
        ):
            raise ValueError("Authentication TTLs must be positive")
        if self.AUTH_SESSION_IDLE_TTL_SECONDS > self.AUTH_SESSION_TTL_SECONDS:
            raise ValueError(
                "AUTH_SESSION_IDLE_TTL_SECONDS must not exceed AUTH_SESSION_TTL_SECONDS"
            )
        return self


def _is_placeholder_secret(secret: str) -> bool:
    lowered = secret.lower()
    return secret in PUBLISHED_PLACEHOLDER_SECRETS or any(
        marker in lowered for marker in PLACEHOLDER_SECRET_MARKERS
    )


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings()


settings = get_settings()
SettingsDep = Annotated[Settings, Depends(get_settings)]

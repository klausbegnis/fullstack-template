from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_TEST_ONLY_JWT_SECRET = "testing-only-signing-key-never-used-outside-tests"  # noqa: S105


class Settings(BaseSettings):
    """Application settings loaded from the environment and `.env`.

    Immutable and thread-safe once instantiated.
    """

    APP_NAME: str = "Backend API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
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

    AUTH_JWT_SECRET: str = ""
    AUTH_JWT_ISSUER: str = "backend-api"
    AUTH_JWT_AUDIENCE: str = "backend-web"
    AUTH_ACCESS_TTL_SECONDS: int = 900
    AUTH_SESSION_TTL_SECONDS: int = 30 * 24 * 60 * 60
    AUTH_COOKIE_SECURE: bool | None = None
    AUTH_ACCESS_COOKIE: str = "app_access"
    AUTH_REFRESH_COOKIE: str = "app_refresh"
    AUTH_CSRF_COOKIE: str = "app_csrf"

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
    def validate_auth_configuration(self) -> "Settings":
        if not self.AUTH_JWT_SECRET:
            if not self.TESTING:
                raise ValueError(
                    "AUTH_JWT_SECRET is required; generate one with "
                    "`python -c 'import secrets; print(secrets.token_urlsafe(48))'`. "
                    "This template ships no default signing key on purpose."
                )
            object.__setattr__(self, "AUTH_JWT_SECRET", _TEST_ONLY_JWT_SECRET)
        if len(self.AUTH_JWT_SECRET.encode()) < 32:
            raise ValueError("AUTH_JWT_SECRET must contain at least 256 bits")
        if self.AUTH_ACCESS_TTL_SECONDS <= 0 or self.AUTH_SESSION_TTL_SECONDS <= 0:
            raise ValueError("Authentication TTLs must be positive")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings()


settings = get_settings()
SettingsDep = Annotated[Settings, Depends(get_settings)]

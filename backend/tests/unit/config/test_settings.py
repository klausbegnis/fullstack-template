from pydantic import ValidationError
import pytest

from app.config import Settings


def test_idle_ttl_defaults_to_fourteen_days() -> None:
    assert Settings(TESTING=True).AUTH_SESSION_IDLE_TTL_SECONDS == 1209600


def test_idle_ttl_above_the_session_ttl_is_rejected() -> None:
    with pytest.raises(ValidationError, match="must not exceed"):
        Settings(
            TESTING=True,
            AUTH_SESSION_TTL_SECONDS=86400,
            AUTH_SESSION_IDLE_TTL_SECONDS=86401,
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"AUTH_SESSION_IDLE_TTL_SECONDS": 0},
        {"AUTH_SESSION_IDLE_TTL_SECONDS": -1},
        {"AUTH_REFRESH_GRACE_SECONDS": 0},
    ],
)
def test_non_positive_session_windows_are_rejected(overrides: dict[str, int]) -> None:
    with pytest.raises(ValidationError, match="must be positive"):
        Settings(TESTING=True, **overrides)


@pytest.mark.parametrize(
    "secret",
    [
        "replace-with-at-least-32-random-bytes",
        "testing-only-signing-key-never-used-outside-tests",
        "__generated____generated____generated__",
        "please-REPLACE-WITH-something-real-and-long",
    ],
    ids=["env-example", "test-key", "deploy-template", "marker-anywhere"],
)
def test_published_placeholder_secrets_are_rejected(secret: str) -> None:
    with pytest.raises(ValidationError, match="placeholder published"):
        Settings(
            DATABASE_URL="postgresql+asyncpg://app:app@localhost:5432/app",
            AUTH_JWT_SECRET=secret,
            TESTING=False,
            _env_file=None,
        )


def test_a_generated_secret_is_accepted() -> None:
    config = Settings(
        DATABASE_URL="postgresql+asyncpg://app:app@localhost:5432/app",
        AUTH_JWT_SECRET="k3Jx9vQ2mN8pL5rT7wY1zA4bC6dE0fG2hI8jK",
        TESTING=False,
        _env_file=None,
    )

    assert len(config.AUTH_JWT_SECRET.get_secret_value()) >= 32

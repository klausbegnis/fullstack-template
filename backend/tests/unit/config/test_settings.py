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

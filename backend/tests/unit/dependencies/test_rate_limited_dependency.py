from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
import pytest

from app.config import Settings, get_settings
from app.core.exceptions import APIException, api_exception_handler
from app.dependencies import get_rate_limit_counter, rate_limited
from app.dependencies.rate_limit import MAX_EMAIL_LENGTH
from app.schemas.api.auth import LoginRequest
from tests.support.rate_limit_fakes import InMemoryRateLimitCounter


def _app(config: Settings, counter: InMemoryRateLimitCounter) -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(APIException, api_exception_handler)  # type: ignore[arg-type]
    app.dependency_overrides[get_settings] = lambda: config
    app.dependency_overrides[get_rate_limit_counter] = lambda: counter

    @app.post("/login", dependencies=[Depends(rate_limited("login"))])
    async def login(payload: LoginRequest) -> dict[str, str]:
        return {"email": payload.email}

    return app


@pytest.fixture
def config() -> Settings:
    return Settings(
        TESTING=True, RATE_LIMIT_LOGIN_PER_EMAIL=2, RATE_LIMIT_LOGIN_PER_IP=4
    )


@pytest.fixture
def counter() -> InMemoryRateLimitCounter:
    return InMemoryRateLimitCounter()


@pytest.fixture
def client(config: Settings, counter: InMemoryRateLimitCounter) -> Iterator[TestClient]:
    with TestClient(_app(config, counter)) as test_client:
        yield test_client


def _attempt(
    client: TestClient, email: str, headers: dict[str, str] | None = None
) -> int:
    response = client.post(
        "/login", json={"email": email, "password": "x"}, headers=headers
    )
    return response.status_code


def test_email_subject_is_normalized_and_throttled_with_retry_after(
    client: TestClient,
) -> None:
    assert _attempt(client, "Member@Example.test") == 200
    assert _attempt(client, " member@example.test ") == 200

    blocked = client.post(
        "/login", json={"email": "MEMBER@example.test", "password": "x"}
    )

    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1
    assert blocked.json()["error"]["code"] == "rate_limited"
    assert blocked.json()["error"]["details"]["retry_after_seconds"] >= 1


def test_ip_subject_is_throttled_across_emails(client: TestClient) -> None:
    statuses = [_attempt(client, f"user-{index}@example.test") for index in range(5)]

    assert statuses == [200, 200, 200, 200, 429]


def test_disabled_limiter_never_throttles_nor_counts(
    config: Settings, counter: InMemoryRateLimitCounter
) -> None:
    disabled = config.model_copy(update={"RATE_LIMIT_ENABLED": False})
    with TestClient(_app(disabled, counter)) as client:
        statuses = [_attempt(client, "member@example.test") for _ in range(5)]

    assert statuses == [200] * 5
    assert counter.window_count == 0


def test_forwarded_for_splits_the_ip_bucket_only_when_trusted(
    config: Settings, counter: InMemoryRateLimitCounter
) -> None:
    trusted = config.model_copy(update={"RATE_LIMIT_TRUST_FORWARDED": True})
    with TestClient(_app(trusted, counter)) as client:
        statuses = [
            _attempt(
                client,
                f"user-{index}@example.test",
                headers={"X-Forwarded-For": f"198.51.100.{index}"},
            )
            for index in range(6)
        ]

    assert statuses == [200] * 6


def test_client_ip_header_splits_the_ip_bucket_when_configured(
    config: Settings, counter: InMemoryRateLimitCounter
) -> None:
    configured = config.model_copy(update={"RATE_LIMIT_CLIENT_IP_HEADER": "X-Real-IP"})
    with TestClient(_app(configured, counter)) as client:
        statuses = [
            _attempt(
                client,
                f"user-{index}@example.test",
                headers={"X-Real-IP": f"198.51.100.{index}"},
            )
            for index in range(6)
        ]

    assert statuses == [200] * 6


def test_forwarded_for_is_ignored_when_untrusted(client: TestClient) -> None:
    statuses = [
        _attempt(
            client,
            f"user-{index}@example.test",
            headers={"X-Forwarded-For": f"198.51.100.{index}"},
        )
        for index in range(5)
    ]

    assert statuses[-1] == 429


def test_a_body_without_an_email_is_still_counted_by_ip(client: TestClient) -> None:
    statuses = [
        client.post("/login", json={"password": "x"}).status_code for _ in range(5)
    ]

    assert statuses == [422, 422, 422, 422, 429]


def test_an_unknown_scope_fails_when_the_dependency_is_built() -> None:
    with pytest.raises(ValueError, match="Unknown rate-limit scope: signup"):
        rate_limited("signup")


def test_an_over_long_email_is_not_a_subject_but_the_ip_still_counts(
    config: Settings, counter: InMemoryRateLimitCounter
) -> None:
    roomy_ip = config.model_copy(update={"RATE_LIMIT_LOGIN_PER_IP": 100})
    over_long = f"{'a' * MAX_EMAIL_LENGTH}@example.test"
    with TestClient(_app(roomy_ip, counter)) as client:
        statuses = [_attempt(client, over_long) for _ in range(4)]

    assert statuses == [422] * 4
    assert counter.window_count == 1


def test_an_email_at_the_maximum_length_is_still_a_subject(
    config: Settings, counter: InMemoryRateLimitCounter
) -> None:
    roomy_ip = config.model_copy(update={"RATE_LIMIT_LOGIN_PER_IP": 100})
    domain = "@example.test"
    longest = f"{'a' * (MAX_EMAIL_LENGTH - len(domain))}{domain}"
    with TestClient(_app(roomy_ip, counter)) as client:
        statuses = [_attempt(client, longest) for _ in range(3)]

    assert statuses == [200, 200, 429]


def test_a_disabled_limiter_needs_no_database(config: Settings) -> None:
    disabled = config.model_copy(update={"RATE_LIMIT_ENABLED": False})
    app = FastAPI()
    app.dependency_overrides[get_settings] = lambda: disabled

    @app.post("/login", dependencies=[Depends(rate_limited("login"))])
    async def login() -> dict[str, str]:
        return {}

    with TestClient(app) as client:
        response = client.post("/login", json={"email": "member@example.test"})

    assert response.status_code == 200

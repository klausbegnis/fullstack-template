from __future__ import annotations

from fastapi import Request
import pytest

from app.config import Settings
from app.core.rate_limit import (
    RateLimitPolicy,
    client_ip,
    ensure_known_scope,
    policy_for,
)


def _request(
    *,
    client_host: str | None = "203.0.113.7",
    forwarded_for: str | None = None,
    real_ip: str | None = None,
) -> Request:
    headers = []
    if forwarded_for is not None:
        headers.append((b"x-forwarded-for", forwarded_for.encode()))
    if real_ip is not None:
        headers.append((b"x-real-ip", real_ip.encode()))
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/auth/login",
            "headers": headers,
            "client": None if client_host is None else (client_host, 50000),
        }
    )


def test_login_policy_reads_the_settings() -> None:
    config = Settings(
        TESTING=True,
        RATE_LIMIT_LOGIN_PER_EMAIL=3,
        RATE_LIMIT_LOGIN_PER_IP=7,
        RATE_LIMIT_LOGIN_WINDOW_SECONDS=120,
    )

    assert policy_for("login", config) == RateLimitPolicy(
        per_subject=3, per_ip=7, window_seconds=120
    )


def test_login_policy_defaults() -> None:
    assert policy_for("login", Settings(TESTING=True)) == RateLimitPolicy(
        per_subject=10, per_ip=50, window_seconds=900
    )


def test_an_unknown_scope_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown rate-limit scope"):
        policy_for("nonexistent", Settings(TESTING=True))


def test_ensure_known_scope_accepts_login_and_rejects_others() -> None:
    assert ensure_known_scope("login") == "login"
    with pytest.raises(ValueError, match="Unknown rate-limit scope: signup"):
        ensure_known_scope("signup")


def test_client_ip_ignores_forwarded_for_unless_trusted() -> None:
    request = _request(forwarded_for="198.51.100.1")

    assert (
        client_ip(request, trust_forwarded=False, client_ip_header="") == "203.0.113.7"
    )


def test_client_ip_uses_the_right_most_forwarded_entry_when_trusted() -> None:
    request = _request(forwarded_for="198.51.100.1, 198.51.100.2 , ")

    assert (
        client_ip(request, trust_forwarded=True, client_ip_header="") == "198.51.100.2"
    )


def test_client_ip_falls_back_to_the_peer_when_forwarded_for_is_absent() -> None:
    assert (
        client_ip(_request(), trust_forwarded=True, client_ip_header="")
        == "203.0.113.7"
    )


def test_client_ip_without_a_peer_is_unknown() -> None:
    assert (
        client_ip(
            _request(client_host=None), trust_forwarded=False, client_ip_header=""
        )
        == "unknown"
    )


def test_client_ip_prefers_the_configured_header() -> None:
    request = _request(forwarded_for="198.51.100.1, 172.18.0.5", real_ip="198.51.100.1")

    assert (
        client_ip(request, trust_forwarded=True, client_ip_header="X-Real-IP")
        == "198.51.100.1"
    )


def test_client_ip_ignores_the_header_unless_configured() -> None:
    request = _request(real_ip="198.51.100.1")

    assert (
        client_ip(request, trust_forwarded=False, client_ip_header="") == "203.0.113.7"
    )


@pytest.mark.parametrize("value", ["", "not-an-ip", "198.51.100.1, 198.51.100.2"])
def test_client_ip_falls_back_when_the_header_is_not_one_address(value: str) -> None:
    request = _request(real_ip=value)

    assert (
        client_ip(request, trust_forwarded=False, client_ip_header="X-Real-IP")
        == "203.0.113.7"
    )


def test_client_ip_accepts_an_ipv6_header_value() -> None:
    request = _request(real_ip=" 2001:db8::1 ")

    assert (
        client_ip(request, trust_forwarded=False, client_ip_header="X-Real-IP")
        == "2001:db8::1"
    )

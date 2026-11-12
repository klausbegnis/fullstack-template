"""Fixed-window rate-limit policies per scope and the client address they key on.

The counters live in the shared `iam.rate_limit_windows` table (see
`app.services.rate_limits`), so a limit holds across restarts and workers.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import ipaddress

from fastapi import Request

from app.config import Settings

FORWARDED_FOR_HEADER = "x-forwarded-for"
UNKNOWN_CLIENT = "unknown"


@dataclass(frozen=True)
class RateLimitPolicy:
    """Attempt limits for one scope: per subject (such as an email) and per IP."""

    per_subject: int
    per_ip: int
    window_seconds: int


def _login_policy(config: Settings) -> RateLimitPolicy:
    return RateLimitPolicy(
        per_subject=config.RATE_LIMIT_LOGIN_PER_EMAIL,
        per_ip=config.RATE_LIMIT_LOGIN_PER_IP,
        window_seconds=config.RATE_LIMIT_LOGIN_WINDOW_SECONDS,
    )


_POLICIES: dict[str, Callable[[Settings], RateLimitPolicy]] = {
    "login": _login_policy,
}
KNOWN_SCOPES = frozenset(_POLICIES)


def ensure_known_scope(scope: str) -> str:
    """Return `scope` if a policy exists for it; an unknown scope is a wiring error."""
    if scope not in KNOWN_SCOPES:
        raise ValueError(f"Unknown rate-limit scope: {scope}")
    return scope


def policy_for(scope: str, config: Settings) -> RateLimitPolicy:
    """Return the configured policy of a scope; an unknown scope is a wiring error."""
    return _POLICIES[ensure_known_scope(scope)](config)


IPV6_BUCKET_PREFIX = 64


def client_ip(request: Request, *, trust_forwarded: bool, client_ip_header: str) -> str:
    """Return the canonical client address, honoring proxy headers only when configured.

    `client_ip_header` names a header the edge proxy overwrites with the peer it
    saw; it wins when it holds a valid IP address. Otherwise the right-most
    `X-Forwarded-For` entry is used when trusted and valid, and then the socket
    peer. Every candidate is parsed, so two spellings of one address share a
    bucket, and an IPv6 address is reduced to its /64, the block one host
    usually controls.
    """
    candidates: list[str] = []
    if client_ip_header:
        candidates.append(request.headers.get(client_ip_header, ""))
    if trust_forwarded:
        forwarded = request.headers.get(FORWARDED_FOR_HEADER, "")
        hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
        if hops:
            candidates.append(hops[-1])
    if request.client is not None:
        candidates.append(request.client.host or "")
    for candidate in candidates:
        canonical = canonical_client_address(candidate)
        if canonical is not None:
            return canonical
    return UNKNOWN_CLIENT


def canonical_client_address(value: str) -> str | None:
    """Return the canonical rate-limit key of an address, or None when it is not one."""
    try:
        address = ipaddress.ip_address(value.strip())
    except ValueError:
        return None
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped is not None:
            return address.ipv4_mapped.compressed
        network = ipaddress.IPv6Network((address, IPV6_BUCKET_PREFIX), strict=False)
        return network.compressed
    return address.compressed

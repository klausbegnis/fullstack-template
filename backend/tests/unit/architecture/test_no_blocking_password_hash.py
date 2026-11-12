"""Keep Argon2 hashing off the event loop in every request path.

The api serves every request from one event loop, so a synchronous Argon2 hash
or verify (tens of milliseconds idle, hundreds under load) stalls all other
requests. Request-path layers call the
`*_off_loop` variants from `app.core.security`; only one-shot CLI commands may
call the synchronous `hash_password` and `verify_password`.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[3]
REQUEST_PATH_LAYERS = ("services", "routers", "dependencies")
BLOCKING_NAMES = frozenset({"hash_password", "verify_password"})


def _request_path_modules() -> list[Path]:
    return [
        path
        for layer in REQUEST_PATH_LAYERS
        for path in sorted((BACKEND_ROOT / "app" / layer).rglob("*.py"))
        if "__pycache__" not in path.parts
    ]


def _called_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def blocking_hash_calls(source: str) -> list[int]:
    """Return the line of every synchronous password hash or verify call."""
    return [
        node.lineno
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call) and _called_name(node) in BLOCKING_NAMES
    ]


def test_request_path_modules_exist() -> None:
    assert _request_path_modules(), "no request-path modules discovered to check"


def test_detector_flags_a_synchronous_hash_call() -> None:
    planted = "async def create(p):\n    return hash_password(p)\n"

    assert blocking_hash_calls(planted) == [2]


@pytest.mark.parametrize(
    "path",
    _request_path_modules(),
    ids=lambda p: p.relative_to(BACKEND_ROOT).as_posix(),
)
def test_request_path_never_hashes_passwords_on_the_event_loop(path: Path) -> None:
    lines = blocking_hash_calls(path.read_text(encoding="utf-8"))
    rendered = ", ".join(f"{path.name}:{line}" for line in lines)
    assert not lines, (
        "synchronous Argon2 call on the event loop; await "
        f"hash_password_off_loop / verify_password_off_loop instead: {rendered}"
    )

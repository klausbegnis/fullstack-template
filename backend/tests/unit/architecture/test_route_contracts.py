"""Enforce the HTTP contract every route in this application must satisfy.

The frontend's generated client, the error envelope and the authorization model
all assume the same shape: an auth dependency unless the route is deliberately
public, an async handler, a `SuccessResponse`/`PaginatedResponse` return
annotation, a predictable status code and a unique operation id. Routes are read
from the live application, so a new router is covered as soon as it is included.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
import typing
from typing import Any

from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute
import pytest

from app.main import app
from app.schemas.api import PaginatedResponse, SuccessResponse

BACKEND_ROOT = Path(__file__).resolve().parents[3]
APP_ROOT = BACKEND_ROOT / "app"

AUTH_DEPENDENCY_MODULE = "app.dependencies.auth"
TEST_ONLY_PATH_PREFIX = "/__test/"

PUBLIC_ROUTES = {("GET", "/"), ("GET", "/health")}
SYNCHRONOUS_HANDLERS: set[tuple[str, str]] = set()
ENVELOPE_EXEMPT_ROUTES = {
    ("GET", "/"),
    ("POST", "/auth/login"),
    ("GET", "/auth/me"),
    ("POST", "/auth/refresh"),
    ("POST", "/auth/logout"),
    ("DELETE", "/users/{user_id}"),
}
NO_CONTENT_ROUTES = {
    ("POST", "/auth/refresh"),
    ("POST", "/auth/logout"),
    ("DELETE", "/users/{user_id}"),
}
CREATED_STATUS = 201
NO_CONTENT_STATUS = 204
DEFAULT_STATUS = 200
ENVELOPES = (SuccessResponse, PaginatedResponse)


def _api_routes(routes: list[Any], prefix: str = "") -> list[tuple[str, APIRoute]]:
    collected: list[tuple[str, APIRoute]] = []
    for route in routes:
        if isinstance(route, APIRoute):
            collected.append((prefix + route.path, route))
            continue
        included = getattr(route, "original_router", None)
        if included is not None:
            context = getattr(route, "include_context", None)
            collected.extend(
                _api_routes(
                    included.routes, prefix + (getattr(context, "prefix", "") or "")
                )
            )
    return collected


def _route_cases() -> list[tuple[str, str, APIRoute]]:
    cases: list[tuple[str, str, APIRoute]] = []
    for path, route in _api_routes(list(app.router.routes)):
        if path.startswith(TEST_ONLY_PATH_PREFIX):
            continue
        for method in sorted(route.methods or set()):
            cases.append((method, path, route))
    return cases


ROUTE_CASES = _route_cases()
ROUTE_IDS = [f"{method} {path}" for method, path, _ in ROUTE_CASES]
ROUTE_KEYS = {(method, path) for method, path, _ in ROUTE_CASES}


def _dependency_calls(dependant: Dependant) -> list[Any]:
    calls: list[Any] = []
    for sub_dependant in dependant.dependencies:
        if sub_dependant.call is not None:
            calls.append(sub_dependant.call)
        calls.extend(_dependency_calls(sub_dependant))
    return calls


def _has_auth_dependency(route: APIRoute) -> bool:
    return any(
        getattr(call, "__module__", "") == AUTH_DEPENDENCY_MODULE
        for call in _dependency_calls(route.dependant)
    )


def _return_annotation(route: APIRoute) -> Any:
    return typing.get_type_hints(route.endpoint).get("return")


def _envelope(annotation: Any) -> tuple[Any, tuple[Any, ...]] | None:
    origin = typing.get_origin(annotation)
    if origin in ENVELOPES:
        return origin, typing.get_args(annotation)
    metadata = getattr(annotation, "__pydantic_generic_metadata__", None)
    if metadata and metadata["origin"] in ENVELOPES:
        return metadata["origin"], tuple(metadata["args"])
    return None


def _expected_status(method: str, path: str, route: APIRoute) -> int:
    if (method, path) in NO_CONTENT_ROUTES:
        return NO_CONTENT_STATUS
    if method == "POST" and route.endpoint.__name__.startswith("create"):
        return CREATED_STATUS
    return DEFAULT_STATUS


def _python_sources() -> list[Path]:
    return [APP_ROOT / "main.py", *sorted((APP_ROOT / "routers").glob("*.py"))]


def test_routes_are_discoverable() -> None:
    assert len(ROUTE_CASES) >= len(PUBLIC_ROUTES) + 1, (
        "no routes were flattened out of the application; the FastAPI router "
        "layout changed and this module's traversal needs updating"
    )


@pytest.mark.parametrize("allowlist", [PUBLIC_ROUTES, SYNCHRONOUS_HANDLERS])
def test_allowlisted_routes_still_exist(allowlist: set[tuple[str, str]]) -> None:
    assert allowlist <= ROUTE_KEYS, (
        f"allowlist entries no longer match a route: {sorted(allowlist - ROUTE_KEYS)}"
    )


@pytest.mark.parametrize("method,path,route", ROUTE_CASES, ids=ROUTE_IDS)
def test_route_declares_an_auth_dependency(
    method: str, path: str, route: APIRoute
) -> None:
    if (method, path) in PUBLIC_ROUTES:
        assert not _has_auth_dependency(route), (
            f"{method} {path} is on the public allowlist but now carries an auth "
            f"dependency; remove it from PUBLIC_ROUTES"
        )
        return
    assert _has_auth_dependency(route), (
        f"{method} {path} has no dependency from {AUTH_DEPENDENCY_MODULE}; wire "
        f"CurrentUser, RequireAdmin or SelfOrAdmin, or add it to PUBLIC_ROUTES"
    )


@pytest.mark.parametrize("method,path,route", ROUTE_CASES, ids=ROUTE_IDS)
def test_route_handler_is_a_coroutine(method: str, path: str, route: APIRoute) -> None:
    is_coroutine = inspect.iscoroutinefunction(route.endpoint)
    if (method, path) in SYNCHRONOUS_HANDLERS:
        assert not is_coroutine, (
            f"{method} {path} is now async; remove it from SYNCHRONOUS_HANDLERS"
        )
        return
    assert is_coroutine, (
        f"{method} {path} is a sync handler; the stack is async end to end and a "
        f"blocking handler occupies a threadpool worker"
    )


@pytest.mark.parametrize("method,path,route", ROUTE_CASES, ids=ROUTE_IDS)
def test_route_returns_a_response_envelope(
    method: str, path: str, route: APIRoute
) -> None:
    envelope = _envelope(_return_annotation(route))
    if (method, path) in ENVELOPE_EXEMPT_ROUTES:
        assert envelope is None, (
            f"{method} {path} now returns an envelope; remove it from "
            f"ENVELOPE_EXEMPT_ROUTES"
        )
        return
    assert envelope is not None, (
        f"{method} {path} returns {_return_annotation(route)!r}; annotate it "
        f"SuccessResponse[T] for one item or PaginatedResponse[T] for a list"
    )


@pytest.mark.parametrize("method,path,route", ROUTE_CASES, ids=ROUTE_IDS)
def test_route_does_not_nest_a_list_in_a_success_envelope(
    method: str, path: str, route: APIRoute
) -> None:
    envelope = _envelope(_return_annotation(route))
    if envelope is None or envelope[0] is not SuccessResponse:
        return
    nested_lists = [
        argument for argument in envelope[1] if typing.get_origin(argument) is list
    ]
    assert not nested_lists, (
        f"{method} {path} returns SuccessResponse[list[...]]; a collection is a "
        f"PaginatedResponse so the client gets total, page and page_size"
    )


@pytest.mark.parametrize("method,path,route", ROUTE_CASES, ids=ROUTE_IDS)
def test_route_uses_the_expected_status_code(
    method: str, path: str, route: APIRoute
) -> None:
    expected = _expected_status(method, path, route)
    actual = route.status_code or DEFAULT_STATUS
    assert actual == expected, (
        f"{method} {path} responds {actual}; expected {expected} "
        f"(create returns {CREATED_STATUS}, everything else {DEFAULT_STATUS} "
        f"unless listed in NO_CONTENT_ROUTES)"
    )


def test_operation_ids_are_unique() -> None:
    identifiers = [route.operation_id or route.unique_id for _, _, route in ROUTE_CASES]
    duplicates = sorted({name for name in identifiers if identifiers.count(name) > 1})
    assert not duplicates, (
        f"duplicate operation ids {duplicates}; orval derives one hook name per id"
    )


def test_static_paths_are_registered_before_matching_parameterized_paths() -> None:
    offenders: list[str] = []
    for index, (method, path, route) in enumerate(ROUTE_CASES):
        if "{" not in path:
            continue
        for later_method, later_path, _ in ROUTE_CASES[index + 1 :]:
            if "{" in later_path or later_method != method:
                continue
            if route.path_regex.match(later_path):
                offenders.append(f"{method} {path} shadows {later_method} {later_path}")
    assert not offenders, (
        "register static paths before the parameterized paths that would match "
        "them, so /users/me does not resolve as /users/{user_id}:\n"
        + "\n".join(offenders)
    )


@pytest.mark.parametrize(
    "path", _python_sources(), ids=lambda path: f"{path.parent.name}/{path.name}"
)
def test_include_router_does_not_add_a_prefix(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "include_router"
        and any(keyword.arg == "prefix" for keyword in node.keywords)
    ]
    assert not offenders, (
        f"{path.relative_to(BACKEND_ROOT).as_posix()} passes prefix= to "
        f"include_router at lines {offenders}; the prefix belongs on APIRouter so "
        f"the router owns its own path space"
    )

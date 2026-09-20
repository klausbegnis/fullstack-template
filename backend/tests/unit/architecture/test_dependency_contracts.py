"""Enforce the shape of the composition root in `app/dependencies`.

Every feature wires its service exactly once, as a `get_<x>_service` provider plus
an `XServiceDep` alias re-exported from `app.dependencies`. Discovering the
providers keeps the contract true for features that do not exist yet.
"""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path
import re
from typing import Any, get_args

import pytest

import app.dependencies as dependencies_package
from app.dependencies import SessionDep, get_auth_session, get_session

BACKEND_ROOT = Path(__file__).resolve().parents[3]
DEPENDENCIES_ROOT = BACKEND_ROOT / "app" / "dependencies"
PROVIDER_PATTERN = re.compile(r"^get_(?P<feature>[a-z0-9_]+)_service$")
SESSION_PARAMETER = "session"


def _alias_name(feature: str) -> str:
    return "".join(part.capitalize() for part in feature.split("_")) + "ServiceDep"


def _service_providers() -> list[tuple[str, str, Any]]:
    discovered: list[tuple[str, str, Any]] = []
    for path in sorted(DEPENDENCIES_ROOT.glob("*.py")):
        if path.name == "__init__.py":
            continue
        module = importlib.import_module(f"app.dependencies.{path.stem}")
        for name, member in vars(module).items():
            match = PROVIDER_PATTERN.match(name)
            if (
                match
                and inspect.isfunction(member)
                and member.__module__ == module.__name__
            ):
                discovered.append((path.name, match.group("feature"), member))
    return discovered


SERVICE_PROVIDERS = _service_providers()


def test_service_providers_are_discoverable() -> None:
    assert SERVICE_PROVIDERS, "no get_<x>_service provider found in app/dependencies"


@pytest.mark.parametrize(
    "module_name,feature,provider",
    SERVICE_PROVIDERS,
    ids=[f"{module}:{provider.__name__}" for module, _, provider in SERVICE_PROVIDERS],
)
def test_service_provider_exports_a_request_scoped_alias(
    module_name: str, feature: str, provider: Any
) -> None:
    alias_name = _alias_name(feature)
    assert hasattr(dependencies_package, alias_name), (
        f"{module_name} defines {provider.__name__} but app.dependencies does not "
        f"re-export {alias_name}"
    )
    assert alias_name in dependencies_package.__all__

    annotated = getattr(dependencies_package, alias_name)
    service = get_args(annotated)[0]
    assert inspect.isclass(service), f"{alias_name} must resolve to a service class"

    defaulted = [
        parameter.name
        for parameter in inspect.signature(service).parameters.values()
        if parameter.default is not inspect.Parameter.empty
    ]
    assert not defaulted, (
        f"{service.__name__}.__init__ defaults {defaulted}; a defaulted collaborator "
        f"lets a caller silently bypass the composition root"
    )

    assert SESSION_PARAMETER in provider.__annotations__, (
        f"{provider.__name__} must take the request-scoped {SESSION_PARAMETER} so "
        f"the service and its repositories share one AsyncSession"
    )


def test_every_provider_shares_one_request_scoped_session() -> None:
    assert get_args(SessionDep)[0].__name__ == "AsyncSession"
    assert get_auth_session is get_session, (
        "app.dependencies.get_auth_session must alias the single session provider "
        "so a request's services enlist in one transaction"
    )

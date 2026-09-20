"""Enforce the test-suite conventions that keep coverage honest.

A service with no unit test and a router with no integration test are the two
ways business rules ship unverified, and both are mechanically detectable. The
tier markers belong to the tier's `conftest.py`, and the unit tier uses fakes
rather than mocks, so a signature change breaks the double instead of leaving an
assertion that still passes against a `MagicMock`.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[3]
APP_ROOT = BACKEND_ROOT / "app"
TESTS_ROOT = BACKEND_ROOT / "tests"
UNIT_ROOT = TESTS_ROOT / "unit"
INTEGRATION_ROOT = TESTS_ROOT / "integration"

MOCKING_MODULES = ("unittest.mock", "pytest_mock")
TIER_MARKER_NAMES = ("skipif", "integration")
SERVICE_DEPENDENCY_SUFFIX = "ServiceDep"
PAIRED_LAYERS = (
    Path("app") / "services",
    Path("app") / "dependencies",
    Path("app") / "schemas" / "api",
)


def _modules(directory: Path) -> list[Path]:
    return [
        path
        for path in sorted(directory.glob("*.py"))
        if path.name != "__init__.py" and "__pycache__" not in path.parts
    ]


def _test_modules(root: Path) -> list[Path]:
    return [
        path
        for path in sorted(root.rglob("test_*.py"))
        if "__pycache__" not in path.parts
    ]


def _relative(path: Path) -> str:
    return path.relative_to(BACKEND_ROOT).as_posix()


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imported_modules(tree: ast.Module) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
            modules.update(f"{node.module}.{alias.name}" for alias in node.names)
    return modules


def _imported_names(tree: ast.Module) -> set[str]:
    return {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }


def _referenced_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


SERVICES = _modules(APP_ROOT / "services")
ROUTERS = _modules(APP_ROOT / "routers")
UNIT_TEST_MODULES = _test_modules(UNIT_ROOT) + [UNIT_ROOT / "conftest.py"]
INTEGRATION_TEST_MODULES = _test_modules(INTEGRATION_ROOT)


def test_application_layers_are_discoverable() -> None:
    assert SERVICES and ROUTERS and UNIT_TEST_MODULES and INTEGRATION_TEST_MODULES


@pytest.mark.parametrize("path", SERVICES, ids=lambda path: path.name)
def test_service_has_a_unit_test_module(path: Path) -> None:
    expected = UNIT_ROOT / "services" / f"test_{path.name}"
    assert expected.exists(), (
        f"{_relative(path)} has no unit test; create {_relative(expected)} covering "
        f"the happy path, every APIException it raises and every role branch"
    )


@pytest.mark.parametrize("path", ROUTERS, ids=lambda path: path.name)
def test_router_has_an_integration_test_module(path: Path) -> None:
    expected = INTEGRATION_ROOT / "api" / f"test_{path.name}"
    assert expected.exists(), (
        f"{_relative(path)} has no integration test; create "
        f"{_relative(expected)} driving it through TestClient"
    )


@pytest.mark.parametrize("path", ROUTERS, ids=lambda path: path.name)
def test_router_stem_pairs_across_the_slice(path: Path) -> None:
    tree = _parse(path)
    uses_a_service = any(
        name.endswith(SERVICE_DEPENDENCY_SUFFIX) for name in _imported_names(tree)
    )
    if not uses_a_service:
        return
    missing = [
        _relative(BACKEND_ROOT / layer / path.name)
        for layer in PAIRED_LAYERS
        if not (BACKEND_ROOT / layer / path.name).exists()
    ]
    assert not missing, (
        f"{_relative(path)} serves a resource whose slice is incomplete; the "
        f"router, service, dependencies and schemas modules share one stem so a "
        f"reader can find the slice by name. Missing: {missing}"
    )


@pytest.mark.parametrize("path", UNIT_TEST_MODULES, ids=lambda path: path.name)
def test_unit_test_uses_fakes_rather_than_mocks(path: Path) -> None:
    offenders = sorted(_imported_modules(_parse(path)).intersection(MOCKING_MODULES))
    assert not offenders, (
        f"{_relative(path)} imports {offenders}; the unit tier uses the hand "
        f"written doubles in tests/support/fakes.py so a collaborator's signature "
        f"change breaks the double instead of a silently passing assertion"
    )


@pytest.mark.parametrize("path", INTEGRATION_TEST_MODULES, ids=lambda path: path.name)
def test_integration_test_leaves_tier_markers_to_the_conftest(path: Path) -> None:
    offenders = sorted(_referenced_names(_parse(path)).intersection(TIER_MARKER_NAMES))
    assert not offenders, (
        f"{_relative(path)} declares {offenders} itself; "
        f"tests/integration/conftest.py applies the integration marker and the "
        f"DATABASE_URL skip to the whole tier"
    )

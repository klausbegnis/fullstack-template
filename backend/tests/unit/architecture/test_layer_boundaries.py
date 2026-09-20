"""Enforce the backend layering rule for every module, not for a chosen few.

`router -> service -> repository -> model` only holds if it is checked on every
file in every layer. These tests glob the layer directories, so a new feature is
covered the moment its files exist and adding one never means remembering to add
a matching architecture test.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[3]
APP_ROOT = BACKEND_ROOT / "app"

ROUTER_FORBIDDEN_IMPORTS = (
    "app.repositories",
    "app.models",
    "sqlalchemy",
    "app.core.database",
)
SERVICE_FORBIDDEN_IMPORTS = ("fastapi",)
REPOSITORY_FORBIDDEN_IMPORTS = ("app.core.exceptions",)
MODEL_FORBIDDEN_IMPORTS = (
    "app.services",
    "app.repositories",
    "app.routers",
    "app.dependencies",
    "app.schemas",
)
HTTP_EXCEPTION_NAME = "HTTPException"
CONTEXT_MANAGER_IMPORT = "asynccontextmanager"
SESSION_CONTROL_METHODS = ("commit", "rollback")
ENGINE_FACTORY_NAMES = (
    "create_async_engine",
    "create_session_factory",
    "async_sessionmaker",
)
ENGINE_FACTORY_LAYERS = ("repositories", "services", "routers", "dependencies")

KNOWN_SESSION_CONTROL_DEVIATIONS: dict[str, frozenset[str]] = {
    "app/services/auth.py": frozenset({"logout", "_logout_session"}),
}


def _layer_modules(layer: str) -> list[Path]:
    directory = APP_ROOT / layer
    return [
        path
        for path in sorted(directory.glob("*.py"))
        if path.name != "__init__.py" and "__pycache__" not in path.parts
    ]


def _module_id(path: Path) -> str:
    return f"{path.parent.name}/{path.name}"


def _relative(path: Path) -> str:
    return path.relative_to(BACKEND_ROOT).as_posix()


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _package_of(path: Path) -> str:
    parts = path.relative_to(BACKEND_ROOT).with_suffix("").parts
    return ".".join(parts[:-1])


def _imported_modules(path: Path, tree: ast.Module) -> set[str]:
    package_parts = _package_of(path).split(".")
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = ".".join(package_parts[: len(package_parts) - node.level + 1])
                modules.add(f"{base}.{node.module}" if node.module else base)
            else:
                modules.add(node.module or "")
    return modules


def _forbidden_imports(
    path: Path, tree: ast.Module, forbidden: tuple[str, ...]
) -> list[str]:
    return sorted(
        module
        for module in _imported_modules(path, tree)
        for prefix in forbidden
        if module == prefix or module.startswith(f"{prefix}.")
    )


def _imported_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(
                alias.asname or alias.name.split(".")[-1] for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
    return names


def _referenced_names(tree: ast.Module) -> set[str]:
    names = _imported_names(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


def _session_control_calls(tree: ast.Module) -> list[tuple[str, int, str]]:
    findings: list[tuple[str, int, str]] = []

    def descend(node: ast.AST, scope: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                descend(child, child.name)
                continue
            if (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and child.func.attr in SESSION_CONTROL_METHODS
            ):
                findings.append((scope, child.lineno, child.func.attr))
            descend(child, scope)

    descend(tree, "<module>")
    return findings


ROUTERS = _layer_modules("routers")
SERVICES = _layer_modules("services")
REPOSITORIES = _layer_modules("repositories")
MODELS = _layer_modules("models")
ENGINE_FACTORY_MODULES = [
    path for layer in ENGINE_FACTORY_LAYERS for path in _layer_modules(layer)
]


def test_every_layer_has_discoverable_modules() -> None:
    assert ROUTERS and SERVICES and REPOSITORIES and MODELS


@pytest.mark.parametrize("path", ROUTERS, ids=_module_id)
def test_router_does_not_reach_into_persistence(path: Path) -> None:
    offenders = _forbidden_imports(path, _parse(path), ROUTER_FORBIDDEN_IMPORTS)
    assert not offenders, (
        f"{_relative(path)} is a router: it speaks HTTP and calls one service. "
        f"Move these imports behind the service: {offenders}"
    )


@pytest.mark.parametrize("path", ROUTERS, ids=_module_id)
def test_router_does_not_raise_http_exception(path: Path) -> None:
    assert HTTP_EXCEPTION_NAME not in _referenced_names(_parse(path)), (
        f"{_relative(path)} references {HTTP_EXCEPTION_NAME}; domain errors are "
        f"APIException subclasses from app.core.exceptions"
    )


@pytest.mark.parametrize("path", SERVICES, ids=_module_id)
def test_service_does_not_import_the_web_framework(path: Path) -> None:
    offenders = _forbidden_imports(path, _parse(path), SERVICE_FORBIDDEN_IMPORTS)
    assert not offenders, (
        f"{_relative(path)} imports {offenders}; services hold domain logic and "
        f"must stay usable without an HTTP request"
    )


@pytest.mark.parametrize("path", SERVICES, ids=_module_id)
def test_service_does_not_define_its_own_transaction_helper(path: Path) -> None:
    assert CONTEXT_MANAGER_IMPORT not in _imported_names(_parse(path)), (
        f"{_relative(path)} imports {CONTEXT_MANAGER_IMPORT}; the transaction "
        f"boundary is app.core.transactions.transaction"
    )


@pytest.mark.parametrize("path", SERVICES, ids=_module_id)
def test_service_delegates_commit_and_rollback_to_the_transaction_helper(
    path: Path,
) -> None:
    allowed = KNOWN_SESSION_CONTROL_DEVIATIONS.get(_relative(path), frozenset())
    offenders = [
        f"{_relative(path)}:{line}: {scope}() calls .{method}()"
        for scope, line, method in _session_control_calls(_parse(path))
        if scope not in allowed
    ]
    assert not offenders, (
        "only app.core.transactions.transaction may commit or roll back:\n"
        + "\n".join(offenders)
    )


@pytest.mark.parametrize("path", REPOSITORIES, ids=_module_id)
def test_repository_never_ends_a_transaction(path: Path) -> None:
    offenders = [
        f"{_relative(path)}:{line}: {scope}() calls .{method}()"
        for scope, line, method in _session_control_calls(_parse(path))
    ]
    assert not offenders, (
        "repositories flush; the calling service owns the transaction:\n"
        + "\n".join(offenders)
    )


@pytest.mark.parametrize("path", REPOSITORIES, ids=_module_id)
def test_repository_raises_no_domain_exceptions(path: Path) -> None:
    offenders = _forbidden_imports(path, _parse(path), REPOSITORY_FORBIDDEN_IMPORTS)
    assert not offenders, (
        f"{_relative(path)} imports {offenders}; a repository returns rows or None "
        f"and lets the service decide what the absence means"
    )


@pytest.mark.parametrize("path", MODELS, ids=_module_id)
def test_model_never_imports_upward(path: Path) -> None:
    offenders = _forbidden_imports(path, _parse(path), MODEL_FORBIDDEN_IMPORTS)
    assert not offenders, (
        f"{_relative(path)} imports {offenders}; models are the bottom of the stack"
    )


@pytest.mark.parametrize("path", ENGINE_FACTORY_MODULES, ids=_module_id)
def test_only_core_builds_engines_and_session_factories(path: Path) -> None:
    offenders = sorted(_imported_names(_parse(path)).intersection(ENGINE_FACTORY_NAMES))
    assert not offenders, (
        f"{_relative(path)} imports {offenders}; one AsyncSession per request is "
        f"composed in app.core.database and injected through SessionDep"
    )

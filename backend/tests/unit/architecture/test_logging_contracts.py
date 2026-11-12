"""Enforce the logging rule for every module under `app/`, not for a chosen few.

`app.core.logger` renders every record as one JSON document whose top-level keys are
the `extra` fields, and attaches the request ID from the context var. That only pays
off while every module goes through `get_logger`, keeps its message constant, puts
variable data in stable snake_case `extra` keys, keeps secrets out of those keys and
logs from the layers that own an event. These tests walk the whole package, so a new
module is covered the moment it exists.
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path
import re

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[3]
APP_ROOT = BACKEND_ROOT / "app"
LOGGER_MODULE = APP_ROOT / "core" / "logger.py"
REQUEST_ID_OWNER = APP_ROOT / "core"

LOGGER_FACTORY = "get_logger"
LOGGER_NAME_PREFIX = "app."
LOG_METHODS = frozenset(
    {"debug", "info", "warning", "error", "exception", "critical", "log"}
)
FAILURE_METHODS = frozenset({"error", "exception", "critical"})
SILENT_LAYERS = (
    "routers",
    "repositories",
    "models",
    "schemas",
    "dependencies",
    "config",
)
SENSITIVE_KEY_PARTS = frozenset(
    {
        "authorization",
        "cookie",
        "cookies",
        "credential",
        "credentials",
        "email",
        "passwd",
        "password",
        "phone",
        "secret",
        "ssn",
        "token",
    }
)
RESERVED_EXTRA_KEYS = frozenset(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__
) | {"message", "asctime"}
SNAKE_CASE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
API_EXCEPTION_BASE = "APIException"


def _app_modules() -> list[Path]:
    return [
        path
        for path in sorted(APP_ROOT.rglob("*.py"))
        if "__pycache__" not in path.parts
    ]


def _relative(path: Path) -> str:
    return path.relative_to(BACKEND_ROOT).as_posix()


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _is_factory_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == LOGGER_FACTORY
    return isinstance(func, ast.Attribute) and func.attr == LOGGER_FACTORY


def _logger_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _is_factory_call(node.value):
            names.update(
                target.id for target in node.targets if isinstance(target, ast.Name)
            )
        elif (
            isinstance(node, ast.AnnAssign)
            and node.value is not None
            and _is_factory_call(node.value)
            and isinstance(node.target, ast.Name)
        ):
            names.add(node.target.id)
    return names


def _log_calls(tree: ast.AST, loggers: set[str]) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in LOG_METHODS
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id in loggers
    ]


def _message_argument(call: ast.Call) -> ast.expr | None:
    assert isinstance(call.func, ast.Attribute)
    positional = call.args[1:] if call.func.attr == "log" else call.args
    return positional[0] if positional else None


def _interpolation_arguments(call: ast.Call) -> list[ast.expr]:
    assert isinstance(call.func, ast.Attribute)
    return call.args[2:] if call.func.attr == "log" else call.args[1:]


def _extra_argument(call: ast.Call) -> ast.expr | None:
    return next(
        (keyword.value for keyword in call.keywords if keyword.arg == "extra"), None
    )


def _extra_keys(call: ast.Call) -> list[str]:
    extra = _extra_argument(call)
    if not isinstance(extra, ast.Dict):
        return []
    return [
        key.value
        for key in extra.keys
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    ]


def _is_failure_log(call: ast.Call) -> bool:
    assert isinstance(call.func, ast.Attribute)
    if call.func.attr in FAILURE_METHODS:
        return True
    return any(keyword.arg == "exc_info" for keyword in call.keywords)


def _handler_catches(handler: ast.ExceptHandler) -> set[str]:
    if handler.type is None:
        return set()
    nodes = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    names: set[str] = set()
    for node in nodes:
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


def _handler_reraises(handler: ast.ExceptHandler) -> bool:
    return any(isinstance(node, ast.Raise) for node in ast.walk(handler))


def _api_exception_names() -> frozenset[str]:
    bases: dict[str, set[str]] = {}
    for path in APP_MODULES:
        for node in ast.walk(_parse(path)):
            if isinstance(node, ast.ClassDef):
                bases[node.name] = {
                    base.id if isinstance(base, ast.Name) else base.attr
                    for base in node.bases
                    if isinstance(base, ast.Name | ast.Attribute)
                }
    found = {API_EXCEPTION_BASE}
    changed = True
    while changed:
        changed = False
        for name, parents in bases.items():
            if name not in found and parents & found:
                found.add(name)
                changed = True
    return frozenset(found)


def _findings(path: Path, calls: list[ast.Call], problem: str) -> list[str]:
    return [f"{_relative(path)}:{call.lineno}: {problem}" for call in calls]


APP_MODULES = _app_modules()
LOGGING_MODULES = [path for path in APP_MODULES if _logger_names(_parse(path))]
SILENT_MODULES = [
    path for path in APP_MODULES if path.relative_to(APP_ROOT).parts[0] in SILENT_LAYERS
]


def test_logging_is_discoverable() -> None:
    assert LOGGER_MODULE.exists()
    assert LOGGING_MODULES, "no module obtains a logger through get_logger"
    assert SILENT_MODULES


@pytest.mark.parametrize("path", APP_MODULES, ids=_relative)
def test_only_the_logger_module_imports_stdlib_logging(path: Path) -> None:
    if path == LOGGER_MODULE:
        return
    offenders = [
        node.lineno
        for node in ast.walk(_parse(path))
        if (
            isinstance(node, ast.Import)
            and any(alias.name.split(".")[0] == "logging" for alias in node.names)
        )
        or (
            isinstance(node, ast.ImportFrom)
            and (node.module or "").split(".")[0] == "logging"
        )
    ]
    assert not offenders, (
        f"{_relative(path)} imports `logging` at lines {offenders}; obtain a logger "
        "with app.core.logger.get_logger(__name__) and leave handlers, levels and "
        "formatters to setup_logging()"
    )


@pytest.mark.parametrize("path", APP_MODULES, ids=_relative)
def test_loggers_are_named_after_their_module(path: Path) -> None:
    offenders: list[str] = []
    for node in ast.walk(_parse(path)):
        if not _is_factory_call(node) or path == LOGGER_MODULE:
            continue
        assert isinstance(node, ast.Call)
        argument = node.args[0] if node.args else None
        if isinstance(argument, ast.Name) and argument.id == "__name__":
            continue
        if (
            isinstance(argument, ast.Constant)
            and isinstance(argument.value, str)
            and argument.value.startswith(LOGGER_NAME_PREFIX)
        ):
            continue
        offenders.append(f"{_relative(path)}:{node.lineno}")
    assert not offenders, (
        "get_logger takes __name__, or a literal `app.<channel>` name for a "
        f"dedicated stream such as app.access: {offenders}"
    )


@pytest.mark.parametrize("path", LOGGING_MODULES, ids=_relative)
def test_log_messages_are_constant_strings(path: Path) -> None:
    tree = _parse(path)
    offenders: list[ast.Call] = []
    for call in _log_calls(tree, _logger_names(tree)):
        message = _message_argument(call)
        constant = isinstance(message, ast.Constant) and isinstance(message.value, str)
        if not constant or _interpolation_arguments(call):
            offenders.append(call)
    findings = _findings(path, offenders, "message is not a constant string")
    assert not findings, (
        "a log message is a constant string and every variable value goes into "
        "`extra`, so the same event always has the same message and its data is "
        "queryable by key:\n" + "\n".join(findings)
    )


@pytest.mark.parametrize("path", LOGGING_MODULES, ids=_relative)
def test_log_extra_is_a_literal_dict_of_stable_snake_case_keys(path: Path) -> None:
    tree = _parse(path)
    findings: list[str] = []
    for call in _log_calls(tree, _logger_names(tree)):
        extra = _extra_argument(call)
        if extra is None:
            continue
        if not isinstance(extra, ast.Dict) or len(_extra_keys(call)) != len(extra.keys):
            findings.append(f"{_relative(path)}:{call.lineno}: `extra` is not literal")
            continue
        findings.extend(
            f"{_relative(path)}:{call.lineno}: `{key}`"
            for key in _extra_keys(call)
            if not SNAKE_CASE.match(key) or key in RESERVED_EXTRA_KEYS
        )
    assert not findings, (
        "`extra` is a dict literal whose keys are snake_case strings and never a "
        "LogRecord attribute (those collide or are dropped by JSONFormatter):\n"
        + "\n".join(findings)
    )


@pytest.mark.parametrize("path", LOGGING_MODULES, ids=_relative)
def test_log_extra_keys_never_name_secrets_or_personal_data(path: Path) -> None:
    tree = _parse(path)
    findings = [
        f"{_relative(path)}:{call.lineno}: `{key}`"
        for call in _log_calls(tree, _logger_names(tree))
        for key in _extra_keys(call)
        if set(key.split("_")) & SENSITIVE_KEY_PARTS
    ]
    assert not findings, (
        "log keys name a secret, a credential or personal data; log the owning "
        "record's ID instead:\n" + "\n".join(findings)
    )


@pytest.mark.parametrize("path", LOGGING_MODULES, ids=_relative)
def test_request_id_is_left_to_the_filter(path: Path) -> None:
    if REQUEST_ID_OWNER in path.parents:
        return
    tree = _parse(path)
    offenders = [
        call
        for call in _log_calls(tree, _logger_names(tree))
        if "request_id" in _extra_keys(call)
    ]
    findings = _findings(path, offenders, "passes request_id")
    assert not findings, (
        "RequestIdFilter attaches request_id from the request context; only "
        "app/core, whose handlers can run outside that context, passes it:\n"
        + "\n".join(findings)
    )


@pytest.mark.parametrize("path", SILENT_MODULES, ids=_relative)
def test_silent_layers_do_not_log(path: Path) -> None:
    tree = _parse(path)
    imports_logger = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "app.core.logger"
        or isinstance(node, ast.ImportFrom)
        and node.module == "app.core"
        and any(alias.name == LOGGER_FACTORY for alias in node.names)
        for node in ast.walk(tree)
    )
    assert not imports_logger and not _logger_names(tree), (
        f"{_relative(path)} logs, but {', '.join(SILENT_LAYERS)} do not: a router's "
        "request is already in the access log, a repository's failure propagates "
        "to the service, and models, schemas, dependencies and config "
        "hold no events of their own"
    )


@pytest.mark.parametrize("path", LOGGING_MODULES, ids=_relative)
def test_a_failure_is_not_logged_and_reraised(path: Path) -> None:
    tree = _parse(path)
    loggers = _logger_names(tree)
    findings = [
        f"{_relative(path)}:{call.lineno}"
        for handler in ast.walk(tree)
        if isinstance(handler, ast.ExceptHandler) and _handler_reraises(handler)
        for call in _log_calls(handler, loggers)
        if _is_failure_log(call)
    ]
    assert not findings, (
        "an exception logged as a failure and re-raised is logged again by the "
        "boundary that finally handles it; log it where it stops, once:\n"
        + "\n".join(findings)
    )


@pytest.mark.parametrize("path", LOGGING_MODULES, ids=_relative)
def test_expected_domain_errors_are_not_logged_as_failures(path: Path) -> None:
    tree = _parse(path)
    loggers = _logger_names(tree)
    domain_errors = _api_exception_names()
    findings = [
        f"{_relative(path)}:{call.lineno}"
        for handler in ast.walk(tree)
        if isinstance(handler, ast.ExceptHandler)
        and _handler_catches(handler) & domain_errors
        for call in _log_calls(handler, loggers)
        if _is_failure_log(call)
    ]
    assert not findings, (
        "an APIException is an expected outcome that api_exception_handler "
        "already logs at warning; do not log it as an error:\n" + "\n".join(findings)
    )

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import get_args

from app.dependencies import UserServiceDep, get_user_service
from app.services.users import UserService


def test_user_router_does_not_import_persistence_details() -> None:
    router_path = Path(__file__).parents[3] / "app" / "routers" / "users.py"
    tree = ast.parse(router_path.read_text())
    forbidden = ("app.repositories", "app.models", "sqlalchemy", "app.core.database")

    imported_modules = {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    imported_modules.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    assert not any(
        module == prefix or module.startswith(f"{prefix}.")
        for module in imported_modules
        for prefix in forbidden
    )


def test_user_service_dependency_is_non_optional_and_request_scoped() -> None:
    assert get_args(UserServiceDep)[0] is UserService
    assert all(
        parameter.default is inspect.Parameter.empty
        for parameter in inspect.signature(UserService).parameters.values()
    )
    assert "session" in get_user_service.__annotations__

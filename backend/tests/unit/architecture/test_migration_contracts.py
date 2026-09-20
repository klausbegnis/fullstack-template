"""Enforce the invariants of the Alembic revision history.

Two heads mean `alembic upgrade head` picks one and the other silently never
runs; the condition appears when two branches each autogenerate a revision. A
`sa.Enum` that Alembic is allowed to create implicitly emits `CREATE TYPE` twice
and the migration fails on the second table that uses it. Neither check needs a
database.
"""

from __future__ import annotations

import ast
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"
VERSIONS_ROOT = BACKEND_ROOT / "alembic" / "versions"
PLACEHOLDER_DATABASE_URL = "postgresql+asyncpg://unused:unused@localhost:5432/unused"
ENUM_CALL_NAME = "Enum"
CREATE_TYPE_KEYWORD = "create_type"


def _script_directory() -> ScriptDirectory:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", PLACEHOLDER_DATABASE_URL)
    return ScriptDirectory.from_config(config)


def _revisions() -> list[Path]:
    return [
        path
        for path in sorted(VERSIONS_ROOT.glob("*.py"))
        if "__pycache__" not in path.parts
    ]


def _implicit_enum_calls(tree: ast.Module) -> list[int]:
    offenders: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        is_enum = (
            isinstance(function, ast.Attribute) and function.attr == ENUM_CALL_NAME
        ) or (isinstance(function, ast.Name) and function.id == ENUM_CALL_NAME)
        if not is_enum:
            continue
        declared = {
            keyword.arg: keyword.value
            for keyword in node.keywords
            if keyword.arg is not None
        }
        value = declared.get(CREATE_TYPE_KEYWORD)
        if not (isinstance(value, ast.Constant) and value.value is False):
            offenders.append(node.lineno)
    return offenders


REVISIONS = _revisions()


def test_revisions_are_discoverable() -> None:
    assert REVISIONS, "no Alembic revisions found under alembic/versions"


def test_revision_history_has_exactly_one_head() -> None:
    heads = _script_directory().get_heads()
    assert len(heads) == 1, (
        f"the revision history has {len(heads)} heads {heads}; merge them with "
        f"`alembic merge` so `alembic upgrade head` runs every revision"
    )


@pytest.mark.parametrize("path", REVISIONS, ids=lambda path: path.name)
def test_revision_never_creates_an_enum_type_implicitly(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders = _implicit_enum_calls(tree)
    assert not offenders, (
        f"{path.name} calls Enum(...) without {CREATE_TYPE_KEYWORD}=False at lines "
        f"{offenders}; create and drop the type explicitly so a second column "
        f"using it does not re-emit CREATE TYPE"
    )

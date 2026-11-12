"""Every `LIKE` search in a repository escapes what the user typed.

Without `escape=`, a `%` or `_` in a search box becomes a wildcard, so a search
for `50%` also matches `500`. The shared helper is
`app.repositories.search.like_contains_pattern`, passed with
`escape=LIKE_ESCAPE`.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPOSITORIES_ROOT = Path(__file__).resolve().parents[3] / "app" / "repositories"
LIKE_METHODS = frozenset({"like", "ilike", "not_like", "not_ilike"})
REPOSITORY_MODULES = sorted(
    path for path in REPOSITORIES_ROOT.glob("*.py") if path.name != "__init__.py"
)


def _unescaped_like_calls(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in LIKE_METHODS
        and not any(keyword.arg == "escape" for keyword in node.keywords)
    ]


def test_repositories_are_discoverable() -> None:
    assert REPOSITORY_MODULES


@pytest.mark.parametrize("path", REPOSITORY_MODULES, ids=lambda path: path.name)
def test_every_repository_ilike_passes_escape(path: Path) -> None:
    offenders = _unescaped_like_calls(path)
    assert not offenders, (
        f"app/repositories/{path.name} lines {offenders} call like/ilike without "
        f"escape=; build the pattern with like_contains_pattern and pass "
        f"escape=LIKE_ESCAPE"
    )

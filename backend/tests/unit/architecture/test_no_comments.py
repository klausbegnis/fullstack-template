"""Enforce the project rule that code carries no explanatory comments.

Intent belongs in names, structure and docstrings. A comment that felt necessary is a
design signal: rename the thing or extract a well-named function instead. Only
functional directives survive.
"""

from pathlib import Path
import tokenize

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[3]
SEARCH_ROOTS = ("app", "alembic", "tests")
ALLOWED_PREFIXES = ("#!", "# noqa", "# type:", "# pragma:", "# ruff:", "# mypy:")


def _python_files() -> list[Path]:
    files: list[Path] = []
    for root in SEARCH_ROOTS:
        for path in sorted((BACKEND_ROOT / root).rglob("*.py")):
            if "__pycache__" not in path.parts:
                files.append(path)
    return files


def _disallowed_comments(path: Path) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    with path.open("rb") as handle:
        for token in tokenize.tokenize(handle.readline):
            if token.type != tokenize.COMMENT:
                continue
            text = token.string.strip()
            if not text.startswith(ALLOWED_PREFIXES):
                findings.append((token.start[0], text))
    return findings


def test_python_sources_exist() -> None:
    assert _python_files(), "no Python sources discovered to check"


@pytest.mark.parametrize("path", _python_files(), ids=lambda p: str(p.name))
def test_file_has_no_explanatory_comments(path: Path) -> None:
    findings = _disallowed_comments(path)
    rendered = "\n".join(f"  {path}:{line}: {text}" for line, text in findings)
    assert not findings, (
        f"explanatory comments are not allowed; express intent in names, "
        f"structure or a docstring instead:\n{rendered}"
    )

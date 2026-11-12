"""Build `LIKE` patterns that match what a user typed, wildcards included."""

from __future__ import annotations

LIKE_ESCAPE = "\\"


def like_contains_pattern(search: str) -> str:
    """Return a `%…%` pattern in which `\\`, `%` and `_` from `search` match literally.

    Pass it with `escape=LIKE_ESCAPE` so the database honours the escapes.
    """
    escaped = (
        search.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
        .replace("%", f"{LIKE_ESCAPE}%")
        .replace("_", f"{LIKE_ESCAPE}_")
    )
    return f"%{escaped}%"

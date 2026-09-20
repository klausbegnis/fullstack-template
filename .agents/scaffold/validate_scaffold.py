"""Validate a proposed scaffold artifact list before anything is written.

The generators under `.agents/scaffold/` never write a path this module has not
cleared. A path clears when it is repo-relative, free of traversal, shaped like
one of the vertical slice's layers, and present in the frozen list the user
approved after reading the `--plan` output.
"""

from __future__ import annotations

import argparse
import json
from pathlib import PurePosixPath
import re
import sys

BACKEND_ARTIFACT_DIRS = (
    "backend/app/models",
    "backend/app/repositories",
    "backend/app/services",
    "backend/app/routers",
    "backend/app/schemas/api",
    "backend/app/dependencies",
    "backend/tests/unit/services",
    "backend/tests/integration/api",
)

BACKEND_PATCH_TARGETS = (
    "backend/app/models/__init__.py",
    "backend/app/models/db_schemas.py",
    "backend/app/dependencies/__init__.py",
    "backend/app/routers/__init__.py",
    "backend/app/schemas/api/__init__.py",
    "backend/app/main.py",
)

FRONTEND_FEATURE_ROOT = "frontend/src/features"
FRONTEND_ROUTE_ROOT = "frontend/src/app/(app)"

MODULE_NAME = re.compile(r"^[a-z][a-z0-9_]*\.py$")
FEATURE_NAME = re.compile(r"^[a-z][a-z0-9-]*$")
FRONTEND_SUFFIXES = (".ts", ".tsx")


class ScaffoldError(Exception):
    """Raised when a proposed path may not be written."""


def _reject_unsafe(path: str) -> str:
    """Return the path in canonical form, or explain why it is unsafe."""
    if not path or path.strip() != path:
        return "path is empty or padded with whitespace"
    if path.startswith("/") or re.match(r"^[A-Za-z]:", path):
        return "absolute paths are never written by a scaffold"
    if "\\" in path:
        return "backslashes are not repo-relative separators"
    parts = PurePosixPath(path).parts
    if any(part in ("..", ".", "") for part in parts):
        return "path traversal segments are not allowed"
    if path.endswith("/"):
        return "a directory is not an artifact"
    return ""


def _backend_reason(path: str) -> str:
    """Explain why a `backend/` path is outside the allowed slice, if it is."""
    if path in BACKEND_PATCH_TARGETS:
        return ""
    parent = str(PurePosixPath(path).parent)
    name = PurePosixPath(path).name
    if parent not in BACKEND_ARTIFACT_DIRS:
        return f"{parent}/ is not one of the slice's backend directories"
    if not MODULE_NAME.match(name):
        return f"{name} is not a lower_snake_case Python module"
    if parent.startswith("backend/tests/") and not name.startswith("test_"):
        return f"{name} is in a test directory but is not a test module"
    return ""


def _frontend_reason(path: str, feature: str | None) -> str:
    """Explain why a `frontend/` path is outside the allowed slice, if it is."""
    roots = (FRONTEND_FEATURE_ROOT, FRONTEND_ROUTE_ROOT)
    root = next((candidate for candidate in roots if path.startswith(candidate + "/")), None)
    if root is None:
        return "only features/<f>/** and app/(app)/<f>/** belong to a frontend slice"
    remainder = PurePosixPath(path[len(root) + 1 :])
    segment = remainder.parts[0]
    if len(remainder.parts) < 2:
        return "a slice writes files inside its feature or route directory, not beside it"
    if not FEATURE_NAME.match(segment):
        return f"{segment} is not a kebab-case feature name"
    if feature is not None and segment != feature:
        return f"{segment} does not belong to the {feature} feature"
    if remainder.suffix not in FRONTEND_SUFFIXES:
        return f"{remainder.name} is not a .ts or .tsx module"
    return ""


def check_path(path: str, *, feature: str | None = None) -> str:
    """Return an empty string when the path may be written, else the reason."""
    unsafe = _reject_unsafe(path)
    if unsafe:
        return unsafe
    if path.startswith("backend/"):
        return _backend_reason(path)
    if path.startswith("frontend/"):
        return _frontend_reason(path, feature)
    return "a scaffold only writes under backend/ or frontend/"


def validate(
    proposed: list[str],
    approved: list[str] | None = None,
    *,
    feature: str | None = None,
    strict: bool = False,
) -> dict[str, object]:
    """Check every proposed path and, when given, the approved list it must match."""
    errors: list[str] = []
    seen: set[str] = set()
    for path in proposed:
        if path in seen:
            errors.append(f"{path}: listed twice")
            continue
        seen.add(path)
        reason = check_path(path, feature=feature)
        if reason:
            errors.append(f"{path}: {reason}")
    if approved is not None:
        approved_set = set(approved)
        for path in proposed:
            if path not in approved_set:
                errors.append(f"{path}: not present in the approved artifact list")
        if strict:
            for path in approved:
                if path not in seen:
                    errors.append(f"{path}: approved but not produced by the plan")
    return {"ok": not errors, "checked": len(proposed), "errors": errors}


def _read_list(source: str) -> list[str]:
    """Read a newline- or JSON-array-delimited path list from a file or stdin."""
    raw = sys.stdin.read() if source == "-" else open(source, encoding="utf-8").read()
    stripped = raw.strip()
    if stripped.startswith("["):
        loaded = json.loads(stripped)
        return [str(item) for item in loaded]
    return [line.strip() for line in stripped.splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    """Run the validator as a command and print its JSON verdict."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposed", required=True)
    parser.add_argument("--approved")
    parser.add_argument("--feature")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    proposed = _read_list(args.proposed)
    approved = _read_list(args.approved) if args.approved else None
    result = validate(proposed, approved, feature=args.feature, strict=args.strict)
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

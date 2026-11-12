"""Plant and remove the deliberate rule violations that test the enforcement layer.

Every probe is one rule from `.agents/rules/**` that is supposed to be mechanical.
Planting it and watching the named check go red is the only evidence that the check
still works; a rule that nothing catches is prose, whatever the `Enforced by:` line
says.

Probe files are named `__probe*` so `--clean` can remove them without a git operation,
and `--plant` refuses to overwrite a file that already exists.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

PROBE_MARKER = "__probe"


def repo_root() -> Path:
    """Return the working tree the probes are planted in."""
    result = subprocess.run(  # noqa: S603
        ["git", "rev-parse", "--show-toplevel"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        sys.stderr.write("not inside a git working tree\n")
        raise SystemExit(2)
    return Path(result.stdout.strip())


PROBES: dict[str, dict[str, str]] = {
    "model-imports-tanstack": {
        "path": "frontend/src/features/users/model/__probe-query.ts",
        "expect": "npm run lint (boundaries/external: model may not import @tanstack/*)",
        "content": """import { queryOptions } from "@tanstack/react-query";

export const probeOptions = queryOptions({ queryKey: ["probe"] });
""",
    },
    "component-is-client": {
        "path": "frontend/src/features/users/components/__probe-view.tsx",
        "expect": "npm run lint (no-restricted-syntax: 'use client' banned under features/*/components)",
        "content": """"use client";

import { useState } from "react";

export function ProbeView() {
  const [open, setOpen] = useState(false);
  return <button onClick={() => setOpen(!open)}>{String(open)}</button>;
}
""",
    },
    "feature-show-modal": {
        "path": "frontend/src/features/users/hooks/__probe-dialog.ts",
        "expect": "npm run lint (no-restricted-properties: showModal outside components/ui)",
        "content": """export function openProbeDialog(dialog: HTMLDialogElement) {
  dialog.showModal();
}
""",
    },
    "barrel-file": {
        "path": "frontend/src/features/users/index.ts",
        "expect": "npm run test:fast (src/testing/architecture.node.test.ts: no barrels outside the generated client)",
        "content": """export { toUser } from "@/features/users/api/user-mapper";
""",
    },
    "async-page-without-loading": {
        "path": "frontend/src/app/(app)/__probe/page.tsx",
        "expect": "npm run test:fast (src/testing/architecture.node.test.ts: every async page has loading.tsx and error.tsx)",
        "content": """export default async function Page() {
  await Promise.resolve();
  return <p>probe</p>;
}
""",
    },
    "router-imports-model": {
        "path": "backend/app/routers/__probe.py",
        "expect": "uv run pytest tests/unit/architecture/test_layer_boundaries.py (routers may not import app.models)",
        "content": '''"""Probe router that reaches past the service layer."""

from fastapi import APIRouter

from app.models.user import User

router = APIRouter(prefix="/__probe", tags=["probe"])


@router.get("")
async def probe() -> dict[str, str]:
    """Return the model name the router should never have imported."""
    return {"model": User.__name__}
''',
    },
    "repository-commits": {
        "path": "backend/app/repositories/__probe.py",
        "expect": "uv run pytest tests/unit/architecture/test_layer_boundaries.py (repositories flush, never commit)",
        "content": '''"""Probe repository that owns a transaction it does not own."""

from sqlalchemy.ext.asyncio import AsyncSession


class ProbeRepository:
    """Repository that commits, which only a service's transaction() may do."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self) -> None:
        """Commit from the wrong layer."""
        await self._session.commit()
''',
    },
    "route-without-auth": {
        "path": "backend/app/routers/__probe_open.py",
        "expect": "uv run pytest tests/unit/architecture/test_route_contracts.py (every route declares an auth dependency)",
        "content": '''"""Probe router whose route is open to the world."""

from fastapi import APIRouter

from app.schemas.api import SuccessResponse

router = APIRouter(prefix="/__probe-open", tags=["probe"])


@router.get("")
async def probe_open() -> SuccessResponse[str]:
    """Answer without asking who is calling."""
    return SuccessResponse(data="open")
''',
        "register": True,
    },
    "service-without-test": {
        "path": "backend/app/services/__probe.py",
        "expect": "uv run pytest tests/unit/architecture/test_test_conventions.py (every service has a unit test module)",
        "content": '''"""Probe service with no paired test module."""

from sqlalchemy.ext.asyncio import AsyncSession


class ProbeService:
    """Service that ships without tests/unit/services/test___probe.py."""

    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session
''',
    },
}

REGISTRATION = "app.include_router(probe_open_router, responses=ERROR_RESPONSES)"
REGISTRATION_IMPORT = "from .routers.__probe_open import router as probe_open_router"


def _register(root: Path) -> None:
    """Include the open probe router so the live-route contract test can see it."""
    main = root / "backend/app/main.py"
    source = main.read_text(encoding="utf-8")
    if REGISTRATION in source:
        return
    source = source.replace(
        "from .schemas.api.errors import ERROR_RESPONSES",
        f"from .schemas.api.errors import ERROR_RESPONSES\n{REGISTRATION_IMPORT}",
        1,
    )
    includes = list(re.finditer(r"^app\.include_router\([^\n]*\)\n", source, re.MULTILINE))
    cut = includes[-1].end()
    main.write_text(source[:cut] + REGISTRATION + "\n" + source[cut:], encoding="utf-8")


def _unregister(root: Path) -> None:
    """Undo `_register`."""
    main = root / "backend/app/main.py"
    source = main.read_text(encoding="utf-8")
    source = source.replace(REGISTRATION + "\n", "").replace(REGISTRATION_IMPORT + "\n", "")
    main.write_text(source, encoding="utf-8")


def plant(root: Path, names: list[str]) -> list[dict[str, str]]:
    """Write each named probe and return what is expected to catch it."""
    planted = []
    for name in names:
        probe = PROBES[name]
        target = root / probe["path"]
        if target.exists():
            sys.stderr.write(f"{probe['path']} already exists; refusing to overwrite\n")
            raise SystemExit(2)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(probe["content"], encoding="utf-8")
        if probe.get("register"):
            _register(root)
        planted.append(
            {"probe": name, "path": probe["path"], "expected_failure": probe["expect"]}
        )
    return planted


def clean(root: Path) -> list[str]:
    """Remove every planted probe and the registration edit."""
    removed = []
    for probe in PROBES.values():
        target = root / probe["path"]
        if not target.exists():
            continue
        if target.read_text(encoding="utf-8") != probe["content"]:
            sys.stderr.write(f"{probe['path']} is not the planted probe; left in place\n")
            continue
        target.unlink()
        removed.append(probe["path"])
    _unregister(root)
    for directory in {
        (root / probe["path"]).parent for probe in PROBES.values() if PROBE_MARKER in probe["path"]
    }:
        if directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()
    return removed


def main(argv: list[str] | None = None) -> int:
    """Plant, list or clean the probe set."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plant", action="store_true")
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--probe", action="append", default=[])
    args = parser.parse_args(argv)

    if args.list:
        print(
            json.dumps(
                [
                    {"probe": name, "path": p["path"], "expected_failure": p["expect"]}
                    for name, p in PROBES.items()
                ],
                indent=2,
            )
        )
        return 0

    root = repo_root()
    if args.clean:
        print(json.dumps({"removed": clean(root)}, indent=2))
        return 0
    if args.plant:
        unknown = [name for name in args.probe if name not in PROBES]
        if unknown:
            sys.stderr.write(f"unknown probes: {unknown}\n")
            return 2
        names = args.probe or list(PROBES)
        print(json.dumps({"planted": plant(root, names)}, indent=2))
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

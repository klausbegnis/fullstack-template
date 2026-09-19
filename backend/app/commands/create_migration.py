"""Create an Alembic revision that already complies with the project's style rules.

Wraps ``alembic revision --autogenerate``, strips the banner comments Alembic injects
into the generated body, and formats the result, so a new migration needs no manual
cleanup before it passes the repository's checks.
"""

import argparse
from pathlib import Path
import re
import subprocess
import sys

_BANNER = re.compile(r"^\s*#\s*###.*###\s*$")
_GENERATED_PATH = re.compile(r"Generating (.+?\.py)\s")


def _strip_banners(path: Path) -> None:
    lines = path.read_text().splitlines(keepends=True)
    kept = [line for line in lines if not _BANNER.match(line.rstrip("\n"))]
    path.write_text("".join(kept))


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a fixed developer tool, passing arguments as argv rather than a shell.

    Only ``alembic`` and ``ruff`` are invoked here and no shell is involved, so a
    revision message cannot escape into command execution.
    """
    return subprocess.run(  # noqa: S603
        command, capture_output=True, text=True, check=False
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-m", "--message", required=True)
    parser.add_argument("--empty", action="store_true")
    args = parser.parse_args()

    command = ["alembic", "revision", "-m", args.message]
    if not args.empty:
        command.append("--autogenerate")

    result = _run(command)
    sys.stderr.write(result.stderr)
    sys.stdout.write(result.stdout)
    if result.returncode != 0:
        return result.returncode

    match = _GENERATED_PATH.search(result.stdout + result.stderr)
    if match is None:
        sys.stderr.write("could not determine the generated revision path\n")
        return 1

    revision_path = Path(match.group(1))
    _strip_banners(revision_path)
    _run(["ruff", "check", "--fix", str(revision_path)])
    _run(["ruff", "format", str(revision_path)])

    sys.stdout.write(f"ready: {revision_path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

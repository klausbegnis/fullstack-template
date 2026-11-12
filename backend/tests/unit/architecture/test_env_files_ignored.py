"""Keep real environment files out of git while the examples stay tracked.

A `.env.production` or `deploy/vps/.env.api` holds live secrets; the root
`.gitignore` must ignore every `.env.*` variant, and the `*.env.example` files
that document the settings must stay addable.
"""

from pathlib import Path
import shutil
import subprocess

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
GIT = shutil.which("git") or "git"

SECRET_ENV_FILES = (
    ".env",
    ".env.production",
    "backend/.env",
    "backend/.env.local",
    "deploy/vps/.env",
    "deploy/vps/.env.api",
    "deploy/vps/.env.prod",
)
EXAMPLE_ENV_FILES = (
    "backend/.env.example",
    "deploy/vps/.env.example",
    "deploy/vps/.env.api.example",
    "frontend/.env.example",
)


def _is_ignored(path: str) -> bool:
    result = subprocess.run(
        [GIT, "check-ignore", "--quiet", "--no-index", path],
        cwd=REPO_ROOT,
        check=False,
    )
    return result.returncode == 0


@pytest.mark.parametrize("path", SECRET_ENV_FILES)
def test_secret_env_file_is_ignored(path: str) -> None:
    assert _is_ignored(path)


@pytest.mark.parametrize("path", EXAMPLE_ENV_FILES)
def test_example_env_file_is_not_ignored(path: str) -> None:
    assert (REPO_ROOT / path).is_file()
    assert not _is_ignored(path)

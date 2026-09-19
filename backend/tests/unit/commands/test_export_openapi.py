import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

EXPECTED_PATHS = {
    "/auth/login",
    "/auth/refresh",
    "/auth/logout",
    "/auth/me",
    "/users",
    "/users/{user_id}",
    "/health",
}


@pytest.mark.unit
def test_export_openapi_runs_without_database(tmp_path: Path) -> None:
    output_path = tmp_path / "openapi.json"
    environment = {
        key: value for key, value in os.environ.items() if key not in {"DATABASE_URL"}
    }
    environment["TESTING"] = "true"
    environment["AUTH_JWT_SECRET"] = "unit-test-only-secret-of-32-bytes!!"

    subprocess.run(
        [
            sys.executable,
            "-m",
            "app.commands.export_openapi",
            "--output",
            str(output_path),
        ],
        check=True,
        env=environment,
        cwd=Path(__file__).resolve().parents[3],
    )

    schema = json.loads(output_path.read_text())
    assert schema["paths"].keys() >= EXPECTED_PATHS

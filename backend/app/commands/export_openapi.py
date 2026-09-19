"""Export the application's OpenAPI schema without a database or server."""

import argparse
import json
import os
from pathlib import Path
from typing import Any

os.environ.setdefault("TESTING", "true")

from app.main import app  # noqa: E402

DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parents[2] / "openapi.json"


def export_schema(output_path: Path = DEFAULT_OUTPUT_PATH) -> dict[str, Any]:
    """Write the application's OpenAPI schema to `output_path` and return it."""
    schema = app.openapi()
    output_path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    return schema


def main() -> None:
    """Run the OpenAPI export from the command line."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Path to write the OpenAPI schema JSON to",
    )
    args = parser.parse_args()
    export_schema(args.output)


if __name__ == "__main__":
    main()

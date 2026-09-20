"""Apply the integration tier's marker and database precondition in one place.

Repeating `pytestmark` per module drifts: a file that forgets the skip fails the
whole run on a machine without PostgreSQL. The tier owns both decisions.
"""

import os
from pathlib import Path

import pytest

TIER_ROOT = Path(__file__).parent
REQUIRES_DATABASE = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="PostgreSQL DATABASE_URL is not configured",
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark every test under `tests/integration` and skip it without a database."""
    for item in items:
        if TIER_ROOT in Path(item.path).parents:
            item.add_marker(pytest.mark.integration)
            item.add_marker(REQUIRES_DATABASE)

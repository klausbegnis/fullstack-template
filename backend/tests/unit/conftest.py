"""Apply the unit tier's marker to everything collected beneath this directory."""

from pathlib import Path

import pytest

TIER_ROOT = Path(__file__).parent


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark every test under `tests/unit` so the tier can be selected by marker."""
    for item in items:
        if TIER_ROOT in Path(item.path).parents:
            item.add_marker(pytest.mark.unit)

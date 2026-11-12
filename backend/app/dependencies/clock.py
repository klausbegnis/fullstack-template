"""The injectable wall clock; tests override `get_clock` to move time by hand."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.core.clock import Clock, utc_now


def get_clock() -> Clock:
    """Provide the wall clock."""
    return utc_now


ClockDep = Annotated[Clock, Depends(get_clock)]

__all__ = ["ClockDep", "get_clock"]

"""Shared rule for display names a user types."""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator

from app.core.text import contains_control_characters

CONTROL_CHARACTERS_MESSAGE = "must not contain control or formatting characters"


def reject_control_characters(value: str) -> str:
    """Return `value`, or reject it when it holds a control or bidi character."""
    if contains_control_characters(value):
        raise ValueError(CONTROL_CHARACTERS_MESSAGE)
    return value


DisplayName = Annotated[str, AfterValidator(reject_control_characters)]

"""Detect and drop control and formatting characters in user-supplied names.

Unicode categories `Cc` (control, such as BEL or a raw newline) and `Cf`
(formatting, such as the U+202E right-to-left override) never belong in a
person's name: they can hide or reorder what a reader sees.
"""

from __future__ import annotations

import unicodedata

HIDDEN_CATEGORIES = frozenset({"Cc", "Cf"})


def _is_hidden(character: str) -> bool:
    return unicodedata.category(character) in HIDDEN_CATEGORIES


def contains_control_characters(value: str) -> bool:
    """Return whether `value` holds any `Cc` or `Cf` character."""
    return any(_is_hidden(character) for character in value)


def strip_control_characters(value: str) -> str:
    """Return `value` without its `Cc` and `Cf` characters."""
    return "".join(character for character in value if not _is_hidden(character))

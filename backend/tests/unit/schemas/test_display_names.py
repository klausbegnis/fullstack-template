from pydantic import ValidationError
import pytest

from app.schemas.api.names import CONTROL_CHARACTERS_MESSAGE
from app.schemas.api.users import UserCreate, UserUpdate


def _create(name: str) -> UserCreate:
    return UserCreate(name=name, email="ada@example.com", password="long enough")


@pytest.mark.parametrize(
    "name",
    ["Ada‮ecalovoL", "Ada\nLovelace", "Ada\x07", "Ada​Lovelace"],
    ids=["rtl-override", "newline", "bell", "zero-width-space"],
)
def test_create_rejects_control_and_formatting_characters(name: str) -> None:
    with pytest.raises(ValidationError, match=CONTROL_CHARACTERS_MESSAGE):
        _create(name)


def test_update_rejects_control_and_formatting_characters() -> None:
    with pytest.raises(ValidationError, match=CONTROL_CHARACTERS_MESSAGE):
        UserUpdate(name="Ada‮")


def test_ordinary_names_pass() -> None:
    assert _create("Ada Lovelace-Byron O'Neil").name == "Ada Lovelace-Byron O'Neil"


def test_create_requires_an_eight_character_password() -> None:
    with pytest.raises(ValidationError):
        UserCreate(name="Ada", email="ada@example.com", password="short")

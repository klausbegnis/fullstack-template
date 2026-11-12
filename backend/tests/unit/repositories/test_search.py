from app.repositories.search import LIKE_ESCAPE, like_contains_pattern


def test_like_contains_pattern_escapes_backslash_percent_and_underscore() -> None:
    assert LIKE_ESCAPE == "\\"
    assert like_contains_pattern("50%") == "%50\\%%"
    assert like_contains_pattern("snake_case") == "%snake\\_case%"
    assert like_contains_pattern("a\\b") == "%a\\\\b%"
    assert like_contains_pattern("plain") == "%plain%"

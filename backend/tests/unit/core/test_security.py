from starlette.responses import Response

from app.config import Settings
from app.core.security import set_auth_cookies


def _set_cookie_header(response: Response, name: str) -> str:
    [header] = [
        value
        for value in response.headers.getlist("set-cookie")
        if value.startswith(f"{name}=")
    ]
    return header


def test_refresh_and_csrf_cookies_last_the_idle_limit() -> None:
    config = Settings(TESTING=True)
    response = Response()

    set_auth_cookies(response, "access", "refresh", "csrf", config=config)

    assert "Max-Age=900" in _set_cookie_header(response, config.AUTH_ACCESS_COOKIE)
    assert "Max-Age=1209600" in _set_cookie_header(response, config.AUTH_REFRESH_COOKIE)
    assert "Max-Age=1209600" in _set_cookie_header(response, config.AUTH_CSRF_COOKIE)

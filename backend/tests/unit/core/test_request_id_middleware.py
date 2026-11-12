"""Verify the inbound X-Request-ID is echoed only when it is a safe token."""

import uuid

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
import pytest

from app.core.middleware import REQUEST_ID_HEADER, RequestIDMiddleware


def _client() -> TestClient:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/probe")
    async def probe(request: Request) -> dict[str, str]:
        return {"bound": request.state.request_id}

    return TestClient(app)


def _is_uuid4(value: str) -> bool:
    return uuid.UUID(value).version == 4


def test_inbound_uuid_is_kept_and_echoed() -> None:
    inbound = str(uuid.uuid4())

    response = _client().get("/probe", headers={REQUEST_ID_HEADER: inbound})

    assert response.headers[REQUEST_ID_HEADER] == inbound
    assert response.json()["bound"] == inbound


def test_inbound_token_of_64_safe_characters_is_kept() -> None:
    inbound = "a.b_c-" + "9" * 58

    response = _client().get("/probe", headers={REQUEST_ID_HEADER: inbound})

    assert response.headers[REQUEST_ID_HEADER] == inbound


@pytest.mark.parametrize(
    "inbound",
    ["x" * 65, "<script>", "two words", "id;drop", "../etc"],
    ids=["too-long", "markup", "space", "semicolon", "slash"],
)
def test_unsafe_inbound_id_is_replaced_with_a_fresh_uuid(inbound: str) -> None:
    response = _client().get("/probe", headers={REQUEST_ID_HEADER: inbound})

    echoed = response.headers[REQUEST_ID_HEADER]
    assert echoed != inbound
    assert _is_uuid4(echoed)
    assert response.json()["bound"] == echoed


def test_missing_inbound_id_gets_a_fresh_uuid() -> None:
    response = _client().get("/probe")

    assert _is_uuid4(response.headers[REQUEST_ID_HEADER])

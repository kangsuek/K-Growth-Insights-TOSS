import time

import pytest
import respx
from httpx import Response

from app.services import toss_client as toss_client_module
from app.services.toss_client import TossAuthError, TossClient

BASE_URL = "https://openapi.tossinvest.com"


@pytest.fixture(autouse=True)
def _credentials(monkeypatch):
    monkeypatch.setattr(toss_client_module, "TOSS_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(toss_client_module, "TOSS_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setattr(toss_client_module, "TOSS_API_BASE_URL", BASE_URL)


@respx.mock
async def test_get_fetches_token_and_calls_api():
    token_route = respx.post(f"{BASE_URL}/oauth2/token").mock(
        return_value=Response(200, json={"access_token": "tok1", "expires_in": 100})
    )
    stocks_route = respx.get(f"{BASE_URL}/api/v1/stocks").mock(
        return_value=Response(200, json={"result": [{"symbol": "005930"}]})
    )

    client = TossClient()
    data = await client.get("/api/v1/stocks", params={"symbols": "005930"})

    assert data == {"result": [{"symbol": "005930"}]}
    assert token_route.call_count == 1
    assert stocks_route.calls.last.request.headers["Authorization"] == "Bearer tok1"


@respx.mock
async def test_token_is_cached_across_calls():
    token_route = respx.post(f"{BASE_URL}/oauth2/token").mock(
        return_value=Response(200, json={"access_token": "tok1", "expires_in": 100})
    )
    respx.get(f"{BASE_URL}/api/v1/stocks").mock(
        return_value=Response(200, json={"result": []})
    )

    client = TossClient()
    await client.get("/api/v1/stocks")
    await client.get("/api/v1/stocks")

    assert token_route.call_count == 1


@respx.mock
async def test_token_refreshes_after_expiry(monkeypatch):
    responses = iter([
        Response(200, json={"access_token": "tok1", "expires_in": 100}),
        Response(200, json={"access_token": "tok2", "expires_in": 100}),
    ])
    token_route = respx.post(f"{BASE_URL}/oauth2/token").mock(
        side_effect=lambda request: next(responses)
    )
    stocks_route = respx.get(f"{BASE_URL}/api/v1/stocks").mock(
        return_value=Response(200, json={"result": []})
    )

    client = TossClient()
    await client.get("/api/v1/stocks")

    # 만료 시각을 이미 지난 것처럼 조작해 재발급을 강제한다.
    client._expires_at = time.monotonic() - 1
    await client.get("/api/v1/stocks")

    assert token_route.call_count == 2
    assert stocks_route.calls.last.request.headers["Authorization"] == "Bearer tok2"


async def test_missing_credentials_raises(monkeypatch):
    monkeypatch.setattr(toss_client_module, "TOSS_CLIENT_ID", None)
    monkeypatch.setattr(toss_client_module, "TOSS_CLIENT_SECRET", None)

    client = TossClient()
    with pytest.raises(TossAuthError):
        await client.get("/api/v1/stocks")

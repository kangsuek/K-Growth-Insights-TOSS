import asyncio

import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response

from app.database import get_connection
from app.main import app
from app.services import toss_client as toss_client_module
from app.services import watchlist

BASE_URL = "https://openapi.tossinvest.com"

CANDLES_RESPONSE = {
    "result": {
        "candles": [
            {
                "timestamp": "2026-09-04T00:00:00.000+09:00",
                "openPrice": "251000",
                "highPrice": "259000",
                "lowPrice": "251000",
                "closePrice": "257000",
                "volume": "21429660",
                "currency": "KRW",
            }
        ],
        "nextBefore": None,
    }
}


@pytest.fixture(autouse=True)
def _credentials(monkeypatch):
    monkeypatch.setattr(toss_client_module, "TOSS_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(toss_client_module, "TOSS_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setattr(toss_client_module, "TOSS_API_BASE_URL", BASE_URL)
    monkeypatch.setattr(toss_client_module, "MIN_REQUEST_INTERVAL_SECONDS", 0.0)
    monkeypatch.setattr(toss_client_module.toss_client, "_access_token", None)
    monkeypatch.setattr(toss_client_module.toss_client, "_expires_at", 0.0)


def _seed_catalog(symbol="005930", name="삼성전자", market="KOSPI", security_type="STOCK"):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO stock_catalog (symbol, name, market, security_type, is_common_share, isin_code)
            VALUES (?, ?, ?, ?, 1, 'KR0000000000')
            """,
            (symbol, name, market, security_type),
        )


def _mock_candles_endpoint():
    respx.post(f"{BASE_URL}/oauth2/token").mock(
        return_value=Response(200, json={"access_token": "tok1", "expires_in": 100})
    )
    respx.get(f"{BASE_URL}/api/v1/candles").mock(return_value=Response(200, json=CANDLES_RESPONSE))


client = TestClient(app)


@respx.mock
def test_add_stock_requires_catalog_entry():
    response = client.post("/api/watchlist", json={"symbol": "999999"})
    assert response.status_code == 404


@respx.mock
def test_add_stock_saves_watchlist_and_candles():
    _seed_catalog()
    _mock_candles_endpoint()

    response = client.post("/api/watchlist", json={"symbol": "005930"})
    assert response.status_code == 201
    body = response.json()
    assert body["symbol"] == "005930"
    assert body["name"] == "삼성전자"
    assert body["sort_order"] == 1

    candles = client.get("/api/watchlist/005930/candles").json()
    assert len(candles) == 1
    assert candles[0]["trade_date"] == "2026-09-04"


@respx.mock
def test_add_duplicate_stock_returns_400():
    _seed_catalog()
    _mock_candles_endpoint()

    client.post("/api/watchlist", json={"symbol": "005930"})
    response = client.post("/api/watchlist", json={"symbol": "005930"})

    assert response.status_code == 400


@respx.mock
def test_list_and_reorder():
    _seed_catalog("005930", "삼성전자")
    _seed_catalog("000660", "SK하이닉스")
    _mock_candles_endpoint()

    client.post("/api/watchlist", json={"symbol": "005930"})
    client.post("/api/watchlist", json={"symbol": "000660"})

    listed = client.get("/api/watchlist").json()
    assert [s["symbol"] for s in listed] == ["005930", "000660"]

    reorder_response = client.post("/api/watchlist/reorder", json=["000660", "005930"])
    assert reorder_response.status_code == 200

    listed = client.get("/api/watchlist").json()
    assert [s["symbol"] for s in listed] == ["000660", "005930"]


@respx.mock
def test_add_stock_survives_candle_sync_failure():
    _seed_catalog()
    respx.post(f"{BASE_URL}/oauth2/token").mock(
        return_value=Response(200, json={"access_token": "tok1", "expires_in": 100})
    )
    respx.get(f"{BASE_URL}/api/v1/candles").mock(return_value=Response(500))

    response = client.post("/api/watchlist", json={"symbol": "005930"})

    assert response.status_code == 201
    assert client.get("/api/watchlist").json()[0]["symbol"] == "005930"
    assert client.get("/api/watchlist/005930/candles").json() == []


@respx.mock
async def test_concurrent_add_same_symbol_only_one_succeeds():
    _seed_catalog()
    _mock_candles_endpoint()

    results = await asyncio.gather(
        watchlist.add_stock("005930"),
        watchlist.add_stock("005930"),
        return_exceptions=True,
    )

    successes = [r for r in results if not isinstance(r, Exception)]
    duplicate_errors = [r for r in results if isinstance(r, watchlist.DuplicateSymbolError)]
    assert len(successes) == 1
    assert len(duplicate_errors) == 1


@respx.mock
def test_reorder_rejects_partial_list():
    _seed_catalog("005930", "삼성전자")
    _seed_catalog("000660", "SK하이닉스")
    _mock_candles_endpoint()
    client.post("/api/watchlist", json={"symbol": "005930"})
    client.post("/api/watchlist", json={"symbol": "000660"})

    response = client.post("/api/watchlist/reorder", json=["005930"])

    assert response.status_code == 400


@respx.mock
def test_remove_stock():
    _seed_catalog()
    _mock_candles_endpoint()
    client.post("/api/watchlist", json={"symbol": "005930"})

    response = client.delete("/api/watchlist/005930")
    assert response.status_code == 200

    response = client.delete("/api/watchlist/005930")
    assert response.status_code == 404

    assert client.get("/api/watchlist").json() == []

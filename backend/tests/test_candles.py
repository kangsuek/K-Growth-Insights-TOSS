import pytest
import respx
from httpx import Response

from app.database import get_connection
from app.services import toss_client as toss_client_module
from app.services.candles import sync_daily_candles

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
            },
            {
                "timestamp": "2026-09-03T00:00:00.000+09:00",
                "openPrice": "252000",
                "highPrice": "255500",
                "lowPrice": "243000",
                "closePrice": "248000",
                "volume": "21475989",
                "currency": "KRW",
            },
        ],
        "nextBefore": "2026-09-02T00:00:00.000+09:00",
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


@respx.mock
async def test_sync_daily_candles_converts_and_saves():
    respx.post(f"{BASE_URL}/oauth2/token").mock(
        return_value=Response(200, json={"access_token": "tok1", "expires_in": 100})
    )
    respx.get(f"{BASE_URL}/api/v1/candles").mock(return_value=Response(200, json=CANDLES_RESPONSE))

    result = await sync_daily_candles("005930", count=2)

    assert result == {"symbol": "005930", "saved_count": 2}

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT trade_date, open_price, close_price, volume FROM prices WHERE symbol = ? ORDER BY trade_date",
            ("005930",),
        ).fetchall()

    assert [dict(r) for r in rows] == [
        {"trade_date": "2026-09-03", "open_price": 252000.0, "close_price": 248000.0, "volume": 21475989},
        {"trade_date": "2026-09-04", "open_price": 251000.0, "close_price": 257000.0, "volume": 21429660},
    ]


@respx.mock
async def test_sync_daily_candles_upserts_same_date():
    respx.post(f"{BASE_URL}/oauth2/token").mock(
        return_value=Response(200, json={"access_token": "tok1", "expires_in": 100})
    )
    respx.get(f"{BASE_URL}/api/v1/candles").mock(return_value=Response(200, json=CANDLES_RESPONSE))

    await sync_daily_candles("005930", count=2)
    await sync_daily_candles("005930", count=2)  # 재실행해도 중복 삽입되지 않아야 한다.

    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) AS n FROM prices WHERE symbol = ?", ("005930",)).fetchone()["n"]

    assert count == 2

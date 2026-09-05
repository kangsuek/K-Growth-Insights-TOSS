import json

import pytest
import respx
from httpx import Response

from app.database import get_connection
from app.services import toss_client as toss_client_module
from app.services.trading_flow import sync_trading_flow

BASE_URL = "https://openapi.tossinvest.com"


def _record(
    date,
    individual_net,
    foreigner_net,
    institution_net,
    other_net,
    holding_rate="0.4673",
    breakdown="default",
    foreigner_holding="default",
):
    if breakdown == "default":
        breakdown = {
            "financialInvestment": {"buyVolume": "1", "sellVolume": "1", "netBuyVolume": "100"},
            "insurance": {"buyVolume": "1", "sellVolume": "1", "netBuyVolume": "10"},
            "trust": {"buyVolume": "1", "sellVolume": "1", "netBuyVolume": "20"},
            "privateEquityFund": {"buyVolume": "1", "sellVolume": "1", "netBuyVolume": "-5"},
            "bank": {"buyVolume": "1", "sellVolume": "1", "netBuyVolume": "1"},
            "otherFinancialInstitution": {"buyVolume": "1", "sellVolume": "1", "netBuyVolume": "2"},
            "pensionFund": {"buyVolume": "1", "sellVolume": "1", "netBuyVolume": "50"},
        }
    if foreigner_holding == "default":
        foreigner_holding = {
            "holdingQuantity": "1",
            "limitQuantity": "1",
            "holdingRate": holding_rate,
        }
    return {
        "date": date,
        "updatedAt": f"{date}T06:00:00.000+09:00",
        "individual": {"buyVolume": "1", "sellVolume": "1", "netBuyVolume": str(individual_net)},
        "foreigner": {"buyVolume": "1", "sellVolume": "1", "netBuyVolume": str(foreigner_net)},
        "institution": {
            "buyVolume": "1",
            "sellVolume": "1",
            "netBuyVolume": str(institution_net),
            "breakdown": breakdown,
        },
        "otherCorporation": {"buyVolume": "1", "sellVolume": "1", "netBuyVolume": str(other_net)},
        "foreignerHolding": foreigner_holding,
        "cfd": {"buyBalanceQuantity": "0", "buyBalanceRate": "0", "sellBalanceQuantity": "0", "sellBalanceRate": "0"},
    }


INVESTOR_TRADING_RESPONSE = {
    "result": {
        "nextUntil": "2026-09-01",
        "records": [
            _record("2026-09-04", -5789578, 697460, 3060648, 2016327),
            _record("2026-09-03", -1248264, 114341, -860563, 500000),
        ],
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


def _mock_investor_trading():
    respx.post(f"{BASE_URL}/oauth2/token").mock(
        return_value=Response(200, json={"access_token": "tok1", "expires_in": 100})
    )
    respx.get(f"{BASE_URL}/api/v1/stocks/005930/investor-trading").mock(
        return_value=Response(200, json=INVESTOR_TRADING_RESPONSE)
    )


@respx.mock
async def test_sync_trading_flow_converts_and_saves():
    _mock_investor_trading()

    result = await sync_trading_flow("005930", count=2)

    assert result == {"symbol": "005930", "saved_count": 2}

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM trading_flow WHERE symbol = ? AND trade_date = ?",
            ("005930", "2026-09-04"),
        ).fetchone()

    assert row["individual_net"] == -5789578
    assert row["foreigner_net"] == 697460
    assert row["institution_net"] == 3060648
    assert row["other_corporation_net"] == 2016327
    assert row["foreigner_holding_rate"] == pytest.approx(0.4673)

    breakdown = json.loads(row["institution_breakdown"])
    assert breakdown["financialInvestment"] == 100
    assert breakdown["pensionFund"] == 50


@respx.mock
async def test_sync_trading_flow_upserts_same_date():
    _mock_investor_trading()

    await sync_trading_flow("005930", count=2)
    await sync_trading_flow("005930", count=2)

    with get_connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM trading_flow WHERE symbol = ?", ("005930",)
        ).fetchone()["n"]

    assert count == 2


@respx.mock
async def test_sync_trading_flow_handles_null_breakdown_and_holding():
    respx.post(f"{BASE_URL}/oauth2/token").mock(
        return_value=Response(200, json={"access_token": "tok1", "expires_in": 100})
    )
    respx.get(f"{BASE_URL}/api/v1/stocks/005930/investor-trading").mock(
        return_value=Response(
            200,
            json={
                "result": {
                    "nextUntil": None,
                    "records": [
                        _record(
                            "2026-09-04",
                            -100,
                            200,
                            300,
                            400,
                            breakdown=None,
                            foreigner_holding=None,
                        )
                    ],
                }
            },
        )
    )

    result = await sync_trading_flow("005930", count=1)

    assert result == {"symbol": "005930", "saved_count": 1}
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM trading_flow WHERE symbol = ? AND trade_date = ?",
            ("005930", "2026-09-04"),
        ).fetchone()

    assert row["foreigner_holding_rate"] is None
    assert json.loads(row["institution_breakdown"]) == {}


@respx.mock
async def test_sync_trading_flow_handles_sentinel_holding_rate():
    respx.post(f"{BASE_URL}/oauth2/token").mock(
        return_value=Response(200, json={"access_token": "tok1", "expires_in": 100})
    )
    respx.get(f"{BASE_URL}/api/v1/stocks/005930/investor-trading").mock(
        return_value=Response(
            200,
            json={
                "result": {
                    "nextUntil": None,
                    "records": [_record("2026-09-04", -100, 200, 300, 400, holding_rate="-")],
                }
            },
        )
    )

    result = await sync_trading_flow("005930", count=1)

    assert result == {"symbol": "005930", "saved_count": 1}
    with get_connection() as conn:
        row = conn.execute(
            "SELECT foreigner_holding_rate FROM trading_flow WHERE symbol = ? AND trade_date = ?",
            ("005930", "2026-09-04"),
        ).fetchone()

    assert row["foreigner_holding_rate"] is None

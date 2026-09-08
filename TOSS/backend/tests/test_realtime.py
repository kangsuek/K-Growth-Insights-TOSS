import asyncio
import json
from unittest.mock import AsyncMock

import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response

from app.database import get_connection
from app.main import app
from app.services import realtime as realtime_module
from app.services import toss_client as toss_client_module
from app.services.realtime import TossRealtimeManager

BASE_URL = "https://openapi.tossinvest.com"


class FakeClient:
    def __init__(self, fail=False):
        self.fail = fail
        self.sent = []

    async def send_text(self, message):
        if self.fail:
            raise RuntimeError("연결 끊김")
        self.sent.append(message)


@pytest.fixture
def manager():
    return TossRealtimeManager()


@pytest.fixture(autouse=True)
def _toss_credentials(monkeypatch):
    monkeypatch.setattr(toss_client_module, "TOSS_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(toss_client_module, "TOSS_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setattr(toss_client_module, "TOSS_API_BASE_URL", BASE_URL)
    monkeypatch.setattr(toss_client_module, "MIN_REQUEST_INTERVAL_SECONDS", 0.0)
    monkeypatch.setattr(toss_client_module.toss_client, "_access_token", None)
    monkeypatch.setattr(toss_client_module.toss_client, "_expires_at", 0.0)


def _seed_price(symbol, trade_date, close_price):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO prices (symbol, trade_date, open_price, high_price, low_price, close_price, volume)
            VALUES (?, ?, ?, ?, ?, ?, 0)
            """,
            (symbol, trade_date, close_price, close_price, close_price, close_price),
        )


def _mock_token():
    respx.post(f"{BASE_URL}/oauth2/token").mock(
        return_value=Response(200, json={"access_token": "tok1", "expires_in": 100})
    )


def _mock_candle(symbol, trade_date, open_price, high_price, low_price, close_price):
    respx.get(f"{BASE_URL}/api/v1/candles", params={"symbol": symbol}).mock(
        return_value=Response(
            200,
            json={
                "result": {
                    "candles": [
                        {
                            "timestamp": f"{trade_date}T09:00:00.000+09:00",
                            "openPrice": str(open_price),
                            "highPrice": str(high_price),
                            "lowPrice": str(low_price),
                            "closePrice": str(close_price),
                            "volume": "1",
                            "currency": "KRW",
                        }
                    ],
                    "nextBefore": None,
                }
            },
        )
    )


async def test_handle_trade_message_updates_history_and_quote_and_broadcasts(manager):
    client = FakeClient()
    manager.register(client)

    raw = json.dumps(
        {
            "type": "message",
            "topic": "trade:kr:005930",
            "data": {"price": "257000", "volume": "120", "timestamp": "2026-09-04T09:30:42.000+09:00", "currency": "KRW"},
        }
    )
    await manager.handle_message(AsyncMock(), raw)

    record = {
        "symbol": "005930",
        "price": 257000.0,
        "volume": 120,
        "timestamp": "2026-09-04T09:30:42.000+09:00",
    }
    assert list(manager.trade_history["005930"]) == [record]
    assert manager.quotes["005930"]["open"] == 257000.0
    assert manager.quotes["005930"]["high"] == 257000.0
    assert manager.quotes["005930"]["low"] == 257000.0
    assert manager.quotes["005930"]["last"] == 257000.0

    assert len(client.sent) == 2
    assert json.loads(client.sent[0]) == {"type": "trade", "data": record}
    assert json.loads(client.sent[1])["type"] == "quote"


async def test_quote_tracks_running_high_low_across_ticks(manager):
    ws = AsyncMock()
    prices = ["100", "105", "95", "102"]
    for price in prices:
        raw = json.dumps(
            {"type": "message", "topic": "trade:kr:005930", "data": {"price": price, "volume": "1", "timestamp": "t"}}
        )
        await manager.handle_message(ws, raw)

    quote = manager.quotes["005930"]
    assert quote["open"] == 100.0
    assert quote["high"] == 105.0
    assert quote["low"] == 95.0
    assert quote["last"] == 102.0


async def test_trade_history_trims_to_maxlen(manager):
    ws = AsyncMock()
    for i in range(realtime_module.TRADE_HISTORY_MAXLEN + 10):
        raw = json.dumps(
            {"type": "message", "topic": "trade:kr:005930", "data": {"price": str(i), "volume": "1", "timestamp": str(i)}}
        )
        await manager.handle_message(ws, raw)

    history = manager.trade_history["005930"]
    assert len(history) == realtime_module.TRADE_HISTORY_MAXLEN
    assert history[0]["price"] == 10.0  # 앞의 10개는 잘려나가야 한다.
    assert history[-1]["price"] == float(realtime_module.TRADE_HISTORY_MAXLEN + 9)


async def test_broadcast_removes_dead_clients(manager):
    good = FakeClient()
    bad = FakeClient(fail=True)
    manager.register(good)
    manager.register(bad)

    await manager.broadcast({"type": "trade", "data": {}})

    assert good.sent
    assert bad not in manager._clients
    assert good in manager._clients


async def test_server_shutdown_error_closes_connection(manager):
    ws = AsyncMock()
    raw = json.dumps({"type": "error", "error": {"code": "server-shutdown", "message": "재연결 필요"}})

    await manager.handle_message(ws, raw)

    ws.close.assert_awaited_once()


async def test_rate_limit_error_redeclares_subscriptions(manager, monkeypatch):
    async def fast_sleep(_seconds):
        return None

    monkeypatch.setattr("app.services.realtime.asyncio.sleep", fast_sleep)
    manager._current_symbols = {"005930"}
    ws = AsyncMock()
    raw = json.dumps({"type": "error", "error": {"code": "rate-limit-exceeded", "message": "..."}})

    await manager.handle_message(ws, raw)

    ws.send.assert_awaited_once_with(json.dumps([{"type": "trade:kr", "codes": ["005930"]}]))


async def test_subscriptions_ack_does_not_raise(manager):
    raw = json.dumps({"type": "subscriptions", "subscribed": ["trade:kr:005930"], "rejected": []})
    await manager.handle_message(AsyncMock(), raw)  # 예외만 안 나면 통과


async def test_malformed_json_is_ignored(manager):
    await manager.handle_message(AsyncMock(), "not json")  # 예외 없이 무시되어야 함


@respx.mock
async def test_seed_quote_adopts_todays_candle_ohlc(manager, monkeypatch):
    _mock_token()
    monkeypatch.setattr(realtime_module, "_today_kst", lambda: "2026-09-05")
    _seed_price("005930", "2026-09-04", 250000.0)
    _mock_candle("005930", "2026-09-05", 251000, 259000, 249000, 257000)

    await manager.seed_quote("005930")

    quote = manager.quotes["005930"]
    assert quote["prev_close"] == 250000.0
    assert quote["open"] == 251000.0
    assert quote["high"] == 259000.0
    assert quote["low"] == 249000.0
    assert quote["last"] == 257000.0


@respx.mock
async def test_seed_quote_skips_ohlc_when_candle_is_not_today(manager, monkeypatch):
    _mock_token()
    monkeypatch.setattr(realtime_module, "_today_kst", lambda: "2026-09-05")
    _seed_price("005930", "2026-09-04", 250000.0)
    _mock_candle("005930", "2026-09-04", 251000, 259000, 249000, 257000)  # 어제 봉(오늘자 미확정 봉 없음)

    await manager.seed_quote("005930")

    quote = manager.quotes["005930"]
    assert quote["prev_close"] == 250000.0
    assert quote["open"] is None
    assert quote["high"] is None
    assert quote["low"] is None
    assert quote["last"] is None


@respx.mock
async def test_seed_quote_reconciliation_overwrites_tick_derived_ohlc(manager, monkeypatch):
    _mock_token()
    monkeypatch.setattr(realtime_module, "_today_kst", lambda: "2026-09-05")
    _seed_price("005930", "2026-09-04", 250000.0)

    # 서버 재시작 등으로 늦게 구독을 시작해 틱만으로는 실제보다 좁은 범위를 관찰했다고 가정.
    manager.quotes["005930"] = {
        "symbol": "005930", "open": 255000.0, "high": 256000.0, "low": 254000.0,
        "last": 255500.0, "prev_close": 250000.0, "updated_at": "t1",
    }
    _mock_candle("005930", "2026-09-05", 251000, 259000, 249000, 257000)

    await manager.seed_quote("005930")

    quote = manager.quotes["005930"]
    assert quote["open"] == 251000.0
    assert quote["high"] == 259000.0
    assert quote["low"] == 249000.0
    assert quote["last"] == 255500.0  # 이미 틱으로 받은 최신가는 REST 값으로 덮어쓰지 않는다.


@respx.mock
async def test_seed_quote_never_narrows_high_low_from_lagging_rest_snapshot(manager, monkeypatch):
    """REST 스냅샷이 그 사이 들어온 틱보다 지연되어 있어 더 좁은 범위를 보고하더라도,
    이미 틱으로 관측한 고가/저가를 후퇴시키면 안 된다(항상 더 넓은 범위로 병합)."""
    _mock_token()
    monkeypatch.setattr(realtime_module, "_today_kst", lambda: "2026-09-05")
    _seed_price("005930", "2026-09-04", 250000.0)

    # 틱으로 이미 REST 스냅샷보다 넓은 고가/저가를 관측한 상태.
    manager.quotes["005930"] = {
        "symbol": "005930", "open": 251000.0, "high": 261000.0, "low": 248000.0,
        "last": 255500.0, "prev_close": 250000.0, "updated_at": "t1",
    }
    _mock_candle("005930", "2026-09-05", 251000, 259000, 249000, 257000)  # 더 좁은 범위(지연된 스냅샷)

    await manager.seed_quote("005930")

    quote = manager.quotes["005930"]
    assert quote["high"] == 261000.0  # REST(259000)보다 넓으므로 그대로 유지.
    assert quote["low"] == 248000.0  # REST(249000)보다 넓으므로 그대로 유지.


@respx.mock
async def test_seed_quote_safe_broadcasts_only_on_change(manager, monkeypatch):
    _mock_token()
    monkeypatch.setattr(realtime_module, "_today_kst", lambda: "2026-09-05")
    _mock_candle("005930", "2026-09-05", 251000, 259000, 249000, 257000)
    client = FakeClient()
    manager.register(client)

    await manager._seed_quote_safe("005930")
    assert len(client.sent) == 1

    await manager._seed_quote_safe("005930")  # 값이 그대로면 재브로드캐스트하지 않는다.
    assert len(client.sent) == 1


@respx.mock
async def test_seed_quote_safe_survives_rest_failure(manager):
    _mock_token()
    respx.get(f"{BASE_URL}/api/v1/candles", params={"symbol": "005930"}).mock(return_value=Response(500))
    client = FakeClient()
    manager.register(client)

    await manager._seed_quote_safe("005930")  # 예외가 전파되지 않아야 한다.

    assert client.sent == []


def test_websocket_route_sends_initial_snapshot(monkeypatch):
    from app.services.realtime import realtime_manager

    monkeypatch.setattr(realtime_manager, "trade_history", {"005930": [{"symbol": "005930", "price": 257000.0}]})
    monkeypatch.setattr(
        realtime_manager,
        "quotes",
        {"005930": {"symbol": "005930", "open": 251000.0, "high": 259000.0, "low": 249000.0, "last": 257000.0, "prev_close": 250000.0, "updated_at": "t"}},
    )

    client = TestClient(app)
    with client.websocket_connect("/ws/realtime") as ws:
        message = ws.receive_json()

    assert message["type"] == "snapshot"
    assert message["data"]["trades"] == {"005930": [{"symbol": "005930", "price": 257000.0}]}
    assert message["data"]["quotes"]["005930"]["last"] == 257000.0


class _FakeRunningTask:
    def done(self):
        return False


def test_start_ignores_second_call_while_already_running(manager, monkeypatch):
    monkeypatch.setattr(realtime_module, "TOSS_CLIENT_ID", "test-id")
    monkeypatch.setattr(realtime_module, "TOSS_CLIENT_SECRET", "test-secret")
    sentinel = _FakeRunningTask()
    manager._task = sentinel

    manager.start()

    assert manager._task is sentinel  # 새 태스크로 교체되지 않아야 한다(중복 커넥션 방지).


async def test_stop_cancels_pending_fire_and_forget_seed_tasks(manager, monkeypatch):
    async def slow_seed(_symbol):
        await asyncio.sleep(10)

    monkeypatch.setattr(manager, "_seed_quote_safe", slow_seed)
    manager._spawn_seed_task("005930")
    assert len(manager._seed_tasks) == 1

    await manager.stop()

    assert manager._seed_tasks == set()


async def test_spawn_seed_task_removes_itself_from_registry_on_completion(manager):
    async def instant_seed(_symbol):
        return None

    original = manager._seed_quote_safe
    manager._seed_quote_safe = instant_seed
    try:
        manager._spawn_seed_task("005930")
        task = next(iter(manager._seed_tasks))
        await task
        await asyncio.sleep(0)  # done_callback이 이벤트 루프에서 실행되도록 한 틱 양보.
    finally:
        manager._seed_quote_safe = original

    assert manager._seed_tasks == set()


def test_get_quotes_rest_returns_all(monkeypatch):
    from app.services.realtime import realtime_manager

    monkeypatch.setattr(
        realtime_manager, "quotes", {"005930": {"symbol": "005930", "last": 257000.0}}
    )

    response = TestClient(app).get("/api/realtime/quotes")

    assert response.status_code == 200
    assert response.json() == {"005930": {"symbol": "005930", "last": 257000.0}}


def test_get_quote_rest_returns_single_symbol(monkeypatch):
    from app.services.realtime import realtime_manager

    monkeypatch.setattr(
        realtime_manager, "quotes", {"005930": {"symbol": "005930", "last": 257000.0}}
    )

    response = TestClient(app).get("/api/realtime/quotes/005930")

    assert response.status_code == 200
    assert response.json() == {"symbol": "005930", "last": 257000.0}


def test_get_quote_rest_404_when_unknown_symbol(monkeypatch):
    from app.services.realtime import realtime_manager

    monkeypatch.setattr(realtime_manager, "quotes", {})

    response = TestClient(app).get("/api/realtime/quotes/999999")

    assert response.status_code == 404


def test_get_trades_rest_returns_recent_history(monkeypatch):
    from app.services.realtime import realtime_manager

    history = [{"symbol": "005930", "price": float(i)} for i in range(5)]
    monkeypatch.setattr(realtime_manager, "trade_history", {"005930": history})

    response = TestClient(app).get("/api/realtime/trades/005930", params={"limit": 3})

    assert response.status_code == 200
    assert response.json() == history[-3:]


def test_get_trades_rest_returns_empty_list_for_unknown_symbol(monkeypatch):
    from app.services.realtime import realtime_manager

    monkeypatch.setattr(realtime_manager, "trade_history", {})

    response = TestClient(app).get("/api/realtime/trades/999999")

    assert response.status_code == 200
    assert response.json() == []

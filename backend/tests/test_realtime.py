import json
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import realtime as realtime_module
from app.services.realtime import TossRealtimeManager


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


async def test_handle_trade_message_updates_cache_and_broadcasts(manager):
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

    assert manager.latest_trades["005930"] == {
        "symbol": "005930",
        "price": 257000.0,
        "volume": 120,
        "timestamp": "2026-09-04T09:30:42.000+09:00",
    }
    assert len(client.sent) == 1
    assert json.loads(client.sent[0]) == {"type": "trade", "data": manager.latest_trades["005930"]}


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


def test_websocket_route_sends_initial_snapshot(monkeypatch):
    from app.services.realtime import realtime_manager

    monkeypatch.setattr(
        realtime_manager, "latest_trades", {"005930": {"symbol": "005930", "price": 257000.0}}
    )

    client = TestClient(app)
    with client.websocket_connect("/ws/realtime") as ws:
        message = ws.receive_json()

    assert message == {"type": "snapshot", "data": [{"symbol": "005930", "price": 257000.0}]}


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

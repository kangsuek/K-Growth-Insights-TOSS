"""실시간 매니저: 목표가 판정 대상 제한·체결 중계 범위·연결 상태."""
import asyncio
import json

from fastapi.testclient import TestClient

from app.database import get_connection
from app.main import app
from app.services import realtime
from app.services.realtime import TossRealtimeManager


def _trade_frame(symbol, price):
    return json.dumps({
        "type": "message",
        "topic": f"trade:kr:{symbol}",
        "data": {"price": str(price), "volume": "10", "timestamp": "2026-10-02T10:00:00.000+09:00"},
    })


def _run_trades(manager, frames):
    async def go():
        for frame in frames:
            await manager.handle_message(None, frame)
        # fire-and-forget 판정 태스크가 끝날 때까지 기다린다.
        await asyncio.gather(*list(manager._seed_tasks))
    asyncio.run(go())


def test_trade_broadcasts_quote_only(monkeypatch):
    manager = TossRealtimeManager()
    sent = []

    async def capture(payload):
        sent.append(payload["type"])

    monkeypatch.setattr(manager, "broadcast", capture)
    _run_trades(manager, [_trade_frame("000660", 1820)])

    assert sent == ["quote"]  # 원시 체결(trade) 메시지는 보내지 않는다
    assert set(manager.snapshot()) == {"quotes"}
    assert manager.last_trade_at == "2026-10-02T10:00:00.000+09:00"


def test_alert_check_only_for_tickers_with_price_rules(monkeypatch):
    manager = TossRealtimeManager()
    monkeypatch.setattr(manager, "broadcast", lambda payload: asyncio.sleep(0))
    checked = []
    monkeypatch.setattr(
        realtime.alerts, "check_price_rules_for_ticker", lambda t, p: checked.append((t, p))
    )
    with get_connection() as conn:
        conn.execute("DELETE FROM alert_rules")
        conn.execute(
            "INSERT INTO alert_rules (ticker, rule_type, target_price) VALUES ('000660', 'price_above', 2000)"
        )
        conn.execute("INSERT INTO alert_rules (ticker, rule_type) VALUES ('005930', 'rsi_zone')")
    manager.refresh_price_alert_tickers()

    _run_trades(manager, [_trade_frame("000660", 1820), _trade_frame("005930", 70000)])

    # 목표가 규칙이 없는 종목(신호 규칙만 있는 005930 포함)은 판정하지 않는다.
    assert checked == [("000660", 1820.0)]


def test_alert_check_skips_while_previous_check_in_flight(monkeypatch):
    manager = TossRealtimeManager()
    manager._price_alert_tickers = {"000660"}
    manager._alert_checks_inflight = {"000660"}
    spawned = []
    monkeypatch.setattr(manager, "_check_price_alerts_safe", lambda s, p: spawned.append(s))

    manager._spawn_alert_check("000660", 1820.0)

    assert spawned == []


def test_status_endpoint_reports_manager_state(monkeypatch):
    monkeypatch.setattr(realtime.realtime_manager, "status", "auth_failed")
    monkeypatch.setattr(realtime.realtime_manager, "last_error", "토스 토큰 발급 실패")
    body = TestClient(app).get("/api/realtime/status").json()
    assert body["status"] == "auth_failed"
    assert body["last_error"] == "토스 토큰 발급 실패"
    assert "last_trade_at" in body

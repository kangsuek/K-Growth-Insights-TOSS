"""실시간 시세 매니저: 날짜 전환 초기화·기준가(prev_close) 재계산·재계산 요청 테스트.

토스 WS/REST는 호출하지 않는다 — toss_client.get을 가짜로 바꾸고 handle_message를 직접 부른다.
"""
import asyncio
import json

import pytest

from app.database import get_connection
from app.services import realtime
from app.services.realtime import TossRealtimeManager

TODAY = "2026-10-02"
YESTERDAY = "2026-10-01"


@pytest.fixture(autouse=True)
def _fixed_today(monkeypatch):
    monkeypatch.setattr(realtime, "_today_kst", lambda: TODAY)


def _fake_candles(monkeypatch, candles):
    calls = []

    async def fake_get(path, params=None):
        calls.append((path, params))
        return {"result": {"candles": candles}}

    monkeypatch.setattr(realtime.toss_client, "get", fake_get)
    return calls


def _candle(day, open_=100.0, high=110.0, low=90.0, close=105.0):
    return {
        "timestamp": f"{day}T00:00:00.000+09:00",
        "openPrice": str(open_), "highPrice": str(high), "lowPrice": str(low), "closePrice": str(close),
    }


def _insert_price(ticker, day, close, change_pct):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO prices (ticker, date, close_price, change_pct) VALUES (?, ?, ?, ?)",
            (ticker, day, close, change_pct),
        )


def _trade_frame(symbol, price):
    return json.dumps({
        "type": "message",
        "topic": f"trade:kr:{symbol}",
        "data": {"price": str(price), "volume": "10", "timestamp": f"{TODAY}T10:00:00.000+09:00"},
    })


def _manager_without_side_effects(monkeypatch):
    manager = TossRealtimeManager()
    monkeypatch.setattr(manager, "broadcast", lambda payload: asyncio.sleep(0))
    monkeypatch.setattr(manager, "_spawn_alert_check", lambda symbol, price: None)
    return manager


# --- 날짜 전환 -------------------------------------------------------------------

def test_trade_on_new_day_resets_yesterdays_quote(monkeypatch):
    manager = _manager_without_side_effects(monkeypatch)
    manager.quotes["000660"] = {
        "symbol": "000660", "trade_date": YESTERDAY,
        "open": 1700.0, "high": 1900.0, "low": 1600.0, "last": 1800.0,
        "prev_close": 1650.0, "updated_at": f"{YESTERDAY}T15:30:00+09:00",
    }
    manager.trade_history["000660"] = realtime.deque([{"price": 1800.0}], maxlen=5)

    asyncio.run(manager.handle_message(None, _trade_frame("000660", 1820)))

    quote = manager.quotes["000660"]
    assert quote["trade_date"] == TODAY
    # 어제 시가·고가·저가·기준가가 남지 않고 오늘 첫 체결로 새로 시작한다.
    assert (quote["open"], quote["high"], quote["low"], quote["last"]) == (1820.0, 1820.0, 1820.0, 1820.0)
    assert quote["prev_close"] is None
    # 체결 이력도 오늘 것만 남는다(방금 받은 체결은 지워지지 않는다).
    assert [r["price"] for r in manager.trade_history["000660"]] == [1820.0]


def test_trade_on_same_day_accumulates(monkeypatch):
    manager = _manager_without_side_effects(monkeypatch)
    asyncio.run(manager.handle_message(None, _trade_frame("000660", 1820)))
    asyncio.run(manager.handle_message(None, _trade_frame("000660", 1850)))
    asyncio.run(manager.handle_message(None, _trade_frame("000660", 1810)))
    quote = manager.quotes["000660"]
    assert (quote["open"], quote["high"], quote["low"], quote["last"]) == (1820.0, 1850.0, 1810.0, 1810.0)
    assert len(manager.trade_history["000660"]) == 3


# --- 기준가 우선순위 ---------------------------------------------------------------

def test_prev_close_prefers_db_today_base(monkeypatch):
    # 오늘자 행(종가 1845, +0.65%)이 있으면 KRX 기준가로 역산한 값을 쓴다.
    _insert_price("000660", TODAY, 1845.0, 0.65)
    _insert_price("000660", "2026-09-30", 1783.0, 1.02)
    _fake_candles(monkeypatch, [_candle(TODAY, close=1845.0), _candle(YESTERDAY, close=1828.0)])
    manager = TossRealtimeManager()
    asyncio.run(manager.seed_quote("000660"))
    assert manager.quotes["000660"]["prev_close"] == pytest.approx(1845.0 / 1.0065)


def test_prev_close_uses_toss_previous_candle_when_db_is_stale(monkeypatch):
    # 앱이 꺼져 있어 DB에 10/1·10/2가 없다(9/30만 있음) — 토스 전일봉 10/1 종가를 써야 한다.
    _insert_price("000660", "2026-09-30", 1783.0, 1.02)
    _fake_candles(monkeypatch, [_candle(TODAY, close=1845.0), _candle(YESTERDAY, close=1828.0)])
    manager = TossRealtimeManager()
    asyncio.run(manager.seed_quote("000660"))
    assert manager.quotes["000660"]["prev_close"] == 1828.0


def test_prev_close_before_open_uses_latest_confirmed_candle(monkeypatch):
    # 장 시작 전: 오늘 봉이 아직 없으면 최신 봉 자체가 전일 확정 종가다(시가/고가/저가는 비움).
    _fake_candles(monkeypatch, [_candle(YESTERDAY, close=1828.0), _candle("2026-09-30", close=1783.0)])
    manager = TossRealtimeManager()
    asyncio.run(manager.seed_quote("000660"))
    quote = manager.quotes["000660"]
    assert quote["prev_close"] == 1828.0
    assert quote["open"] is None and quote["last"] is None


def test_prev_close_falls_back_to_db_when_no_candles(monkeypatch):
    _insert_price("000660", "2026-09-30", 1783.0, 1.02)
    _fake_candles(monkeypatch, [])
    manager = TossRealtimeManager()
    asyncio.run(manager.seed_quote("000660"))
    assert manager.quotes["000660"]["prev_close"] == 1783.0


def test_prev_close_is_recomputed_after_catch_up(monkeypatch):
    # 기동 직후엔 DB가 비어 토스 전일봉 기준, 보충 수집으로 오늘자 행이 생기면 KRX 기준가로 바뀐다.
    _fake_candles(monkeypatch, [_candle(TODAY, close=1845.0), _candle(YESTERDAY, close=1828.0)])
    manager = TossRealtimeManager()
    asyncio.run(manager.seed_quote("000660"))
    assert manager.quotes["000660"]["prev_close"] == 1828.0

    _insert_price("000660", TODAY, 1845.0, 0.65)
    asyncio.run(manager.seed_quote("000660"))
    assert manager.quotes["000660"]["prev_close"] == pytest.approx(1845.0 / 1.0065)


def test_seed_merges_today_candle_without_retreating_ticks(monkeypatch):
    _fake_candles(monkeypatch, [_candle(TODAY, open_=1800, high=1850, low=1790, close=1840),
                                _candle(YESTERDAY, close=1828.0)])
    manager = TossRealtimeManager()
    manager.quotes["000660"] = {
        "symbol": "000660", "trade_date": TODAY, "open": 1805.0, "high": 1860.0, "low": 1795.0,
        "last": 1845.0, "prev_close": None, "updated_at": f"{TODAY}T10:00:01+09:00",
    }
    asyncio.run(manager.seed_quote("000660"))
    quote = manager.quotes["000660"]
    assert quote["open"] == 1800.0             # 시가는 REST 값으로 고정
    assert quote["high"] == 1860.0             # 틱으로 본 더 높은 고가 유지
    assert quote["low"] == 1790.0              # REST의 더 낮은 저가 반영
    assert quote["last"] == 1845.0             # 틱 현재가 유지
    assert quote["updated_at"] == f"{TODAY}T10:00:01+09:00"


def test_seed_on_new_day_resets_stale_quote(monkeypatch):
    _fake_candles(monkeypatch, [_candle(YESTERDAY, close=1828.0)])
    manager = TossRealtimeManager()
    manager.quotes["000660"] = {
        "symbol": "000660", "trade_date": YESTERDAY, "open": 1700.0, "high": 1900.0, "low": 1600.0,
        "last": 1828.0, "prev_close": 1650.0, "updated_at": f"{YESTERDAY}T15:30:00+09:00",
    }
    asyncio.run(manager.seed_quote("000660"))
    quote = manager.quotes["000660"]
    assert quote["trade_date"] == TODAY
    assert quote["last"] is None and quote["high"] is None
    assert quote["prev_close"] == 1828.0


# --- 재계산 요청 -------------------------------------------------------------------

def test_request_reconcile_is_noop_when_not_started():
    TossRealtimeManager().request_reconcile()  # 예외 없이 무시


def test_request_reconcile_wakes_loop_from_other_thread():
    async def scenario():
        manager = TossRealtimeManager()
        manager._loop = asyncio.get_running_loop()
        manager._reconcile_event = asyncio.Event()
        await asyncio.to_thread(manager.request_reconcile)
        await asyncio.wait_for(manager._reconcile_event.wait(), timeout=1)
        return manager._reconcile_event.is_set()

    assert asyncio.run(scenario())

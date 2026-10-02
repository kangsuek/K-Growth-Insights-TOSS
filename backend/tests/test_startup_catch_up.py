"""앱 기동 보충 수집 테스트: 판정·공백일수·실행 순서·중복 수집 방지.

이 앱은 켤 때만 백엔드가 떠 있어, 꺼져 있던 동안 놓친 수집을 기동 시 채운다.
"""
import threading
import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app import config
from app.database import get_connection
from app.models import CollectResult
from app.services import jobs, scheduler
from app.services.realtime import realtime_manager
from tests.conftest import seed_stock

KST = ZoneInfo("Asia/Seoul")


def _insert_price(ticker: str, day: str, close: float = 100.0):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO prices (ticker, date, close_price, change_pct, updated_at) "
            "VALUES (?, ?, ?, 0, datetime('now'))",
            (ticker, day, close),
        )


# --- 판정 ----------------------------------------------------------------------

def test_needs_catch_up_when_no_history():
    assert scheduler.needs_catch_up(datetime(2026, 10, 2, 10, 0, tzinfo=KST), None)


def test_needs_catch_up_during_market_hours_checks_previous_close():
    now = datetime(2026, 10, 2, 10, 0, tzinfo=KST)  # 금 장중 → 기준은 10/1 15:40
    assert scheduler.needs_catch_up(now, "2026-09-30T17:57:23+09:00")
    assert not scheduler.needs_catch_up(now, "2026-10-01T15:45:00+09:00")


def test_needs_catch_up_after_close_requires_todays_close():
    now = datetime(2026, 10, 2, 19, 0, tzinfo=KST)  # 금 장 마감 후 → 기준은 10/2 15:40
    assert scheduler.needs_catch_up(now, "2026-10-02T14:00:00+09:00")
    assert not scheduler.needs_catch_up(now, "2026-10-02T15:41:00+09:00")


def test_needs_catch_up_on_weekend_uses_friday_close():
    now = datetime(2026, 10, 4, 12, 0, tzinfo=KST)  # 일요일 → 기준은 10/2(금) 15:40
    assert not scheduler.needs_catch_up(now, "2026-10-02T15:40:30+09:00")
    assert scheduler.needs_catch_up(now, "2026-10-01T15:41:00+09:00")


def test_needs_catch_up_when_some_ticker_is_still_behind():
    # 보충 도중 앱을 껐거나 일부 종목이 실패: 수집 시각은 최신이지만 한 종목이 9/30에 멈춤.
    now = datetime(2026, 10, 2, 19, 0, tzinfo=KST)
    assert scheduler.needs_catch_up(now, "2026-10-02T15:45:00+09:00", "2026-09-30")
    assert not scheduler.needs_catch_up(now, "2026-10-02T15:45:00+09:00", "2026-10-02")
    # 장중: 기대 거래일은 전일(10/1)
    during = datetime(2026, 10, 2, 10, 0, tzinfo=KST)
    assert not scheduler.needs_catch_up(during, "2026-10-01T15:45:00+09:00", "2026-10-01")
    assert scheduler.needs_catch_up(during, "2026-10-01T15:45:00+09:00", "2026-09-30")
    # 시세가 하나도 없으면 수집 시각 기준만 본다
    assert not scheduler.needs_catch_up(during, "2026-10-01T15:45:00+09:00", None)


def test_needs_catch_up_accepts_db_utc_format():
    # DB 원문(UTC naive) 형식도 해석한다: 2026-10-02 06:41 UTC = 15:41 KST
    now = datetime(2026, 10, 2, 19, 0, tzinfo=KST)
    assert not scheduler.needs_catch_up(now, "2026-10-02 06:41:00")


# --- 공백일수 ------------------------------------------------------------------

def test_catch_up_days_uses_stalest_watchlist_ticker():
    seed_stock("000660", "SK하이닉스")
    seed_stock("005930", "삼성전자")
    _insert_price("000660", "2026-10-01")
    _insert_price("005930", "2026-09-20")  # 더 오래 비어 있는 종목 기준
    _insert_price("999999", "2026-01-01")  # 관심종목이 아닌 행은 무시
    assert scheduler.catch_up_days(date(2026, 10, 2)) == 12 + scheduler.CATCH_UP_MARGIN_DAYS


def test_catch_up_days_bounds_and_empty():
    assert scheduler.catch_up_days(date(2026, 10, 2)) is None  # 시세 없음
    seed_stock("000660", "SK하이닉스")
    _insert_price("000660", "2026-10-02")
    assert scheduler.catch_up_days(date(2026, 10, 2)) == scheduler.CATCH_UP_MARGIN_DAYS
    _insert_price("000660", "2020-01-01")  # MAX(date)는 그대로 10/2
    assert scheduler.catch_up_days(date(2026, 10, 2)) == scheduler.CATCH_UP_MARGIN_DAYS
    with get_connection() as conn:
        conn.execute("DELETE FROM prices WHERE date = '2026-10-02'")
    assert scheduler.catch_up_days(date(2026, 10, 2)) == scheduler.CATCH_UP_MAX_DAYS


# --- 실행 ----------------------------------------------------------------------

def test_startup_catch_up_collects_daily_then_intraday_and_wakes_realtime(monkeypatch):
    calls = []
    monkeypatch.setattr(scheduler, "needs_catch_up", lambda now, last, oldest: True)
    monkeypatch.setattr(scheduler, "catch_up_days", lambda today: 7)
    monkeypatch.setattr(jobs, "collect_all_sync", lambda days=None: calls.append(("daily", days)))
    monkeypatch.setattr(scheduler, "run_collect_intraday_all", lambda reason: calls.append(("intraday", reason)))
    monkeypatch.setattr(realtime_manager, "request_reconcile", lambda: calls.append(("reconcile",)))

    scheduler._startup_catch_up()
    assert calls == [("daily", 7), ("intraday", "startup"), ("reconcile",)]


def test_startup_catch_up_skips_daily_when_fresh(monkeypatch):
    calls = []
    monkeypatch.setattr(scheduler, "needs_catch_up", lambda now, last, oldest: False)
    monkeypatch.setattr(jobs, "collect_all_sync", lambda days=None: calls.append("daily"))
    monkeypatch.setattr(scheduler, "run_collect_intraday_all", lambda reason: calls.append("intraday"))
    monkeypatch.setattr(realtime_manager, "request_reconcile", lambda: calls.append("reconcile"))

    scheduler._startup_catch_up()
    assert calls == ["intraday", "reconcile"]


def test_startup_catch_up_failure_still_wakes_realtime(monkeypatch):
    calls = []
    monkeypatch.setattr(scheduler, "needs_catch_up", lambda now, last, oldest: True)
    monkeypatch.setattr(scheduler, "catch_up_days", lambda today: 3)

    def boom(days=None):
        raise RuntimeError("network down")

    monkeypatch.setattr(jobs, "collect_all_sync", boom)
    monkeypatch.setattr(realtime_manager, "request_reconcile", lambda: calls.append("reconcile"))
    scheduler._startup_catch_up()  # 예외가 밖으로 새지 않는다
    assert calls == ["reconcile"]


def test_run_startup_catch_up_respects_scheduler_disabled(monkeypatch):
    monkeypatch.setattr(config, "SCHEDULER_ENABLED", False)
    assert scheduler.run_startup_catch_up() is None


# --- 중복 수집 방지 --------------------------------------------------------------

def test_collect_all_runs_are_serialized(monkeypatch):
    seed_stock("000660", "SK하이닉스")
    active = []
    overlap = []
    started = threading.Event()

    def slow_collect(ticker, days=None):
        started.set()
        active.append(ticker)
        if len(active) > 1:
            overlap.append(True)
        time.sleep(0.2)
        active.pop()
        return CollectResult(ticker=ticker)

    monkeypatch.setattr(jobs.collectors, "collect_stock", slow_collect)
    monkeypatch.setattr(jobs.alerts, "check_signal_rules_after_daily_collect", lambda t: None)

    threads = [threading.Thread(target=jobs.collect_all_sync) for _ in range(2)]
    for t in threads:
        t.start()
    assert started.wait(timeout=5)
    assert jobs.is_running()
    for t in threads:
        t.join()
    assert not overlap
    assert not jobs.is_running()


def test_interval_job_skips_while_collect_all_running(monkeypatch):
    called = []
    monkeypatch.setattr(scheduler, "_in_market_hours_at_minute", lambda: True)
    monkeypatch.setattr(scheduler, "run_collect_all", lambda reason: called.append(reason))
    with jobs.exclusive():
        scheduler._interval_job()
    assert called == []
    scheduler._interval_job()
    assert called == ["interval"]

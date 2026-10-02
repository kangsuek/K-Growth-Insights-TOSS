"""종목 발굴 '금일 지속 상승' — 장중 추세 지표·검색 필터·분봉 수집 테스트."""
import sqlite3
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import database
from app.database import get_connection
from app.main import app
from app.services import metrics, naver_client, scanner

client = TestClient(app)


def _bars(prices, day="2026-10-02", start_minute=0, open_price=None):
    """09:00부터 1분 간격 분봉(시간순)."""
    rows = []
    for i, p in enumerate(prices):
        total = 9 * 60 + start_minute + i
        rows.append({
            "datetime": f"{day}T{total // 60:02d}:{total % 60:02d}:00",
            "open_price": (open_price if i == 0 and open_price is not None else p),
            "high_price": p, "low_price": p, "price": p, "volume": 10,
        })
    return rows


# --- 지표 -----------------------------------------------------------------------

def test_steady_rise_passes_every_condition():
    bars = _bars([100 + i * 0.1 for i in range(60)])
    m = metrics.intraday_trend_metrics(bars)
    assert m["intraday_return"] > 0
    assert m["intraday_r2"] > 95
    assert m["intraday_mdd"] == 0
    assert m["intraday_above_open"] > 95


def test_spike_then_fade_has_large_drawdown():
    # 장 초반 +10% 급등 후 +2%까지 밀림 → 등락률은 +지만 고점 대비 -7%대
    prices = [100 + i for i in range(10)] + [110 - i * 0.4 for i in range(20)] + [102] * 10
    m = metrics.intraday_trend_metrics(_bars(prices))
    assert m["intraday_return"] > 0
    assert m["intraday_mdd"] < -2


def test_v_shape_rebound_spends_little_time_above_open():
    prices = [100 - i * 0.2 for i in range(30)] + [94 + i * 0.25 for i in range(30)]
    m = metrics.intraday_trend_metrics(_bars(prices))
    assert m["intraday_return"] > 0
    assert m["intraday_above_open"] < 70


def test_downtrend_has_no_r2():
    m = metrics.intraday_trend_metrics(_bars([100 - i * 0.1 for i in range(60)]))
    assert m["intraday_r2"] is None
    assert m["intraday_return"] < 0


def test_too_few_bars_returns_none():
    m = metrics.intraday_trend_metrics(_bars([100 + i for i in range(10)]))
    assert set(m.values()) == {None}


def test_after_hours_bars_are_ignored():
    # 정규장 60봉 꾸준한 상승 + 15:31 이후 NXT 급락 봉 → 시간외는 판정에서 빠진다
    regular = _bars([100 + i * 0.1 for i in range(60)])
    after = [{"datetime": "2026-10-02T16:10:00", "open_price": 80, "price": 80}]
    m = metrics.intraday_trend_metrics(regular + after)
    assert m["intraday_mdd"] == 0
    assert m["intraday_return"] > 0


def test_return_uses_first_bar_open_price():
    bars = _bars([100 + i * 0.1 for i in range(40)], open_price=99)
    m = metrics.intraday_trend_metrics(bars)
    assert round(m["intraday_return"], 4) == round((bars[-1]["price"] - 99) / 99 * 100, 4)


# --- 검색 필터 --------------------------------------------------------------------

def _seed_catalog(rows):
    with get_connection() as conn:
        for t, day, ret, r2, mdd, above in rows:
            conn.execute(
                """INSERT INTO stock_catalog
                   (ticker, name, type, market, is_active, intraday_date, intraday_return,
                    intraday_r2, intraday_mdd, intraday_above_open)
                   VALUES (?, ?, 'ETF', 'ETF', 1, ?, ?, ?, ?, ?)""",
                (t, t, day, ret, r2, mdd, above),
            )


def _search_tickers(**extra):
    res = scanner.search({"type": "ETF", "intraday_uptrend": True, "page_size": 50, **extra})
    return {i["ticker"] for i in res["items"]}


def test_search_intraday_uptrend_applies_all_conditions():
    _seed_catalog([
        ("GOOD", "2026-10-02", 1.5, 80, -0.5, 90),
        ("FADE", "2026-10-02", 1.5, 80, -3.0, 90),     # 고점 대비 -3%
        ("WEAK", "2026-10-02", 1.5, 40, -0.5, 90),     # 추세선 R² 낮음
        ("BELOW", "2026-10-02", 1.5, 80, -0.5, 50),    # 시가 아래 체류가 많음
        ("DOWN", "2026-10-02", -0.2, None, -1.0, 30),  # 시가 대비 하락
        ("FLAT", "2026-10-02", 0.0, 80, 0.0, 90),      # 보합은 상승이 아님
    ])
    assert _search_tickers() == {"GOOD"}


def test_search_intraday_uptrend_excludes_stale_session():
    _seed_catalog([
        ("TODAY", "2026-10-02", 1.0, 80, -0.5, 90),
        ("OLD", "2026-10-01", 3.0, 95, 0.0, 99),  # 어제 갱신 후 멈춤 → 제외
    ])
    assert _search_tickers() == {"TODAY"}


def test_search_exposes_intraday_fields_and_sorts_by_intraday_return():
    _seed_catalog([
        ("A", "2026-10-02", 1.0, 80, -0.5, 90),
        ("B", "2026-10-02", 2.0, 85, -0.2, 95),
    ])
    res = scanner.search({"type": "ETF", "sort_by": "intraday_return", "sort_dir": "desc"})
    assert [i["ticker"] for i in res["items"]] == ["B", "A"]
    assert res["items"][0]["intraday_r2"] == 85
    assert res["items"][0]["intraday_date"] == "2026-10-02"
    assert res["intraday_session"]["date"] == "2026-10-02"


def test_search_reports_intraday_session_even_when_no_match():
    _seed_catalog([("FADE", "2026-10-02", 1.5, 80, -3.0, 90)])
    res = scanner.search({"type": "ETF", "intraday_uptrend": True})
    assert res["items"] == []
    assert res["intraday_session"]["date"] == "2026-10-02"


def test_search_endpoint_accepts_intraday_uptrend():
    _seed_catalog([("GOOD", "2026-10-02", 1.5, 80, -0.5, 90)])
    res = client.get("/api/scanner", params={"type": "ETF", "intraday_uptrend": True})
    assert res.status_code == 200
    assert [i["ticker"] for i in res.json()["items"]] == ["GOOD"]


# --- 분봉 수집 --------------------------------------------------------------------

def test_update_intraday_metrics_stores_latest_session(monkeypatch):
    _seed_catalog([("069500", None, None, None, None, None)])
    bars = _bars([100] * 5, day="2026-10-01") + _bars([100 + i * 0.1 for i in range(40)])
    monkeypatch.setattr(naver_client, "fetch_intraday", lambda code: bars)
    assert scanner._update_intraday_metrics("069500")
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM stock_catalog WHERE ticker='069500'").fetchone()
    assert row["intraday_date"] == "2026-10-02"
    assert row["intraday_return"] > 0 and row["intraday_r2"] > 95
    assert row["intraday_updated_at"] is not None


def test_collect_intraday_trend_updates_targets_and_reports_progress(monkeypatch):
    _seed_catalog([("AAA", None, None, None, None, None), ("BBB", None, None, None, None, None)])
    calls = []

    def fake_fetch(code):
        calls.append(code)
        return _bars([100 + i * 0.1 for i in range(40)])

    monkeypatch.setattr(naver_client, "fetch_intraday", fake_fetch)
    result = scanner.collect_intraday_trend()
    assert sorted(calls) == ["AAA", "BBB"]
    assert result["status"] == "completed"
    assert result["items_collected"] == 2
    assert "금일 추세" in result["message"]


def test_collect_intraday_one_tolerates_failure(monkeypatch):
    _seed_catalog([("AAA", None, None, None, None, None)])

    def boom(code):
        raise RuntimeError("timeout")

    monkeypatch.setattr(naver_client, "fetch_intraday", boom)
    result = scanner.collect_intraday_trend()
    assert result["status"] == "completed"
    assert result["items_collected"] == 0


def test_collect_data_intraday_mode_starts_without_freshness_guard():
    with patch.object(scanner, "check_freshness") as fresh, \
         patch.object(scanner, "collect_intraday_trend") as collect:
        res = client.post("/api/scanner/collect-data", params={"mode": "intraday"})
    assert res.status_code == 200
    assert res.json()["status"] == "started"
    fresh.assert_not_called()
    collect.assert_called_once()


def test_collect_data_rejects_unknown_mode():
    assert client.post("/api/scanner/collect-data", params={"mode": "bogus"}).status_code == 422


# --- 마이그레이션 ---------------------------------------------------------------------

def test_migration_adds_intraday_columns_to_old_catalog(tmp_path, monkeypatch):
    db_file = tmp_path / "old.db"
    conn = sqlite3.connect(db_file)
    conn.execute("CREATE TABLE stock_catalog (ticker TEXT PRIMARY KEY, name TEXT NOT NULL, "
                 "type TEXT NOT NULL DEFAULT 'STOCK')")
    conn.commit()
    conn.close()
    monkeypatch.setattr(database, "DATABASE_PATH", str(db_file))
    database.init_db()
    with get_connection() as c:
        cols = {r["name"] for r in c.execute("PRAGMA table_info(stock_catalog)")}
    assert {"intraday_date", "intraday_return", "intraday_r2", "intraday_mdd",
            "intraday_above_open", "intraday_updated_at"} <= cols


# --- 리뷰 반영: 동시 시작·장 초반 세션 선택 ----------------------------------------------

def test_try_start_is_atomic_and_records_mode():
    assert scanner.try_start("intraday")
    assert scanner.get_progress()["mode"] == "intraday"
    assert scanner.get_progress()["status"] == "in_progress"
    assert not scanner.try_start("full")          # 진행 중엔 두 번째 시작 거부
    assert scanner.get_progress()["mode"] == "intraday"


def test_second_button_while_running_returns_already_running():
    with patch.object(scanner, "collect_intraday_trend"), \
         patch.object(scanner, "collect_catalog_data") as deep, \
         patch.object(scanner, "check_freshness", return_value={"fresh": False, "missing": 0}):
        first = client.post("/api/scanner/collect-data", params={"mode": "intraday"})
        # 백그라운드 작업이 mock이라 상태가 in_progress로 남아 있다 = 진행 중 상황
        second = client.post("/api/scanner/collect-data", params={"mode": "full", "force": True})
    assert first.json()["status"] == "started"
    assert second.json()["status"] == "already_running"
    deep.assert_not_called()


def test_session_keeps_previous_day_until_enough_regular_bars(monkeypatch):
    # 09:10: NXT 프리마켓 + 정규장 10봉뿐 → 직전 세션(10/01, 60봉)으로 판정을 유지한다
    _seed_catalog([("069500", None, None, None, None, None)])
    prev = _bars([100 + i * 0.1 for i in range(60)], day="2026-10-01")
    pre_market = [{"datetime": "2026-10-02T08:30:00", "open_price": 101, "price": 101}]
    early = _bars([101 + i * 0.1 for i in range(10)], day="2026-10-02")
    monkeypatch.setattr(naver_client, "fetch_intraday", lambda code: prev + pre_market + early)
    assert scanner._update_intraday_metrics("069500")
    with get_connection() as conn:
        row = conn.execute("SELECT intraday_date, intraday_r2 FROM stock_catalog WHERE ticker='069500'").fetchone()
    assert row["intraday_date"] == "2026-10-01"
    assert row["intraday_r2"] > 95


def test_session_falls_back_to_latest_day_and_skips_bad_dates():
    bars = [{"datetime": "None--T::", "price": 1}] + _bars([100] * 5, day="2026-10-02")
    day, session = scanner._pick_intraday_session(bars)
    assert day == "2026-10-02" and len(session) == 5
    assert scanner._pick_intraday_session([]) == (None, [])

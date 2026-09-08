from fastapi.testclient import TestClient

from app.database import get_connection
from app.main import app

client = TestClient(app)


def _seed_catalog(symbol="005930", name="삼성전자", market="KOSPI", security_type="STOCK"):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO stock_catalog (symbol, name, market, security_type, is_common_share, isin_code)
            VALUES (?, ?, ?, ?, 1, 'KR0000000000')
            """,
            (symbol, name, market, security_type),
        )


def _seed_watchlist(symbol="005930", name="삼성전자", market="KOSPI", security_type="STOCK"):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO stocks (symbol, name, market, security_type, sort_order) VALUES (?, ?, ?, ?, 1)",
            (symbol, name, market, security_type),
        )


def _seed_price(symbol="005930", trade_date="2026-09-04"):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO prices (symbol, trade_date, open_price, high_price, low_price, close_price, volume)
            VALUES (?, ?, 100, 110, 90, 105, 1000)
            """,
            (symbol, trade_date),
        )


def _seed_trading_flow(symbol="005930", trade_date="2026-09-04"):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO trading_flow
                (symbol, trade_date, individual_net, foreigner_net, institution_net, other_corporation_net)
            VALUES (?, ?, 1, 2, 3, 4)
            """,
            (symbol, trade_date),
        )


def test_stats_counts_each_table_independently():
    _seed_catalog("005930")
    _seed_catalog("000660", "SK하이닉스")
    _seed_watchlist("005930")
    _seed_price("005930", "2026-09-03")
    _seed_price("005930", "2026-09-04")
    _seed_trading_flow("005930", "2026-09-04")

    response = client.get("/api/data/stats")

    assert response.status_code == 200
    assert response.json() == {
        "watchlist_count": 1,
        "catalog_count": 2,
        "price_rows": 2,
        "trading_flow_rows": 1,
    }


def test_stats_zero_when_empty():
    response = client.get("/api/data/stats")

    assert response.json() == {
        "watchlist_count": 0,
        "catalog_count": 0,
        "price_rows": 0,
        "trading_flow_rows": 0,
    }


def test_reset_deletes_only_prices_and_trading_flow():
    _seed_catalog("005930")
    _seed_watchlist("005930")
    _seed_price("005930")
    _seed_trading_flow("005930")

    response = client.delete("/api/data/reset")

    assert response.status_code == 200
    assert response.json() == {"deleted_price_rows": 1, "deleted_trading_flow_rows": 1}

    stats = client.get("/api/data/stats").json()
    assert stats == {
        "watchlist_count": 1,  # 관심종목은 유지
        "catalog_count": 1,  # 카탈로그도 유지
        "price_rows": 0,
        "trading_flow_rows": 0,
    }


def test_reset_is_idempotent_when_already_empty():
    response = client.delete("/api/data/reset")

    assert response.status_code == 200
    assert response.json() == {"deleted_price_rows": 0, "deleted_trading_flow_rows": 0}

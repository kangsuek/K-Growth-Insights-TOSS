"""저장 데이터 통계/초기화 라우터."""
from __future__ import annotations

from fastapi import APIRouter

from app.database import get_connection

router = APIRouter(prefix="/api/data", tags=["data"])

_COUNT_TABLES = {
    "watchlist_count": "stocks",
    "catalog_count": "stock_catalog",
    "price_rows": "prices",
    "trading_flow_rows": "trading_flow",
}


@router.get("/stats")
def get_stats() -> dict:
    with get_connection() as conn:
        return {
            key: conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
            for key, table in _COUNT_TABLES.items()
        }


@router.delete("/reset")
def reset_data() -> dict:
    """확정/실시간 수집 데이터(캔들·매매동향)만 초기화한다.

    관심종목(stocks)과 카탈로그(stock_catalog)는 사용자가 직접 관리하는 데이터라 유지한다.
    """
    with get_connection() as conn:
        price_rows = conn.execute("SELECT COUNT(*) AS n FROM prices").fetchone()["n"]
        trading_flow_rows = conn.execute("SELECT COUNT(*) AS n FROM trading_flow").fetchone()["n"]
        conn.execute("DELETE FROM prices")
        conn.execute("DELETE FROM trading_flow")
    return {"deleted_price_rows": price_rows, "deleted_trading_flow_rows": trading_flow_rows}

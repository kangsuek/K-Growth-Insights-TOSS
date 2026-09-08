"""일봉 캔들 조회/재수집 라우터."""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.database import get_connection
from app.services.candles import sync_daily_candles

router = APIRouter(prefix="/api/candles", tags=["candles"])


@router.get("/{symbol}")
def get_candles(symbol: str, limit: int = Query(120, ge=1, le=500)) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM (
                SELECT trade_date, open_price, high_price, low_price, close_price, volume
                FROM prices WHERE symbol = ? ORDER BY trade_date DESC LIMIT ?
            ) ORDER BY trade_date ASC
            """,
            (symbol, limit),
        ).fetchall()
    return [dict(row) for row in rows]


@router.post("/{symbol}/sync")
async def sync_candles(symbol: str, count: int = Query(120, ge=1, le=200)) -> dict:
    return await sync_daily_candles(symbol, count=count)

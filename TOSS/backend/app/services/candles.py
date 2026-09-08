"""토스 일봉/분봉 캔들 수집.

GET /api/v1/candles 응답의 가격/거래량은 문자열로 오므로 저장 전 숫자로 변환한다.
"""
from __future__ import annotations

from app.database import get_connection
from app.services.toss_client import toss_client


async def sync_daily_candles(symbol: str, count: int = 120) -> dict:
    payload = await toss_client.get(
        "/api/v1/candles",
        params={"symbol": symbol, "interval": "1d", "count": count},
    )
    candles = payload["result"]["candles"]

    with get_connection() as conn:
        for candle in candles:
            trade_date = candle["timestamp"][:10]
            conn.execute(
                """
                INSERT INTO prices
                    (symbol, trade_date, open_price, high_price, low_price, close_price, volume, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(symbol, trade_date) DO UPDATE SET
                    open_price = excluded.open_price,
                    high_price = excluded.high_price,
                    low_price = excluded.low_price,
                    close_price = excluded.close_price,
                    volume = excluded.volume,
                    updated_at = excluded.updated_at
                """,
                (
                    symbol,
                    trade_date,
                    float(candle["openPrice"]),
                    float(candle["highPrice"]),
                    float(candle["lowPrice"]),
                    float(candle["closePrice"]),
                    int(candle["volume"]),
                ),
            )

    return {"symbol": symbol, "saved_count": len(candles)}

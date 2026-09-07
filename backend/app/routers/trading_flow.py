"""투자자별 매매동향 조회/재수집 라우터."""
from __future__ import annotations

import json

from fastapi import APIRouter, Query

from app.database import get_connection
from app.services.trading_flow import sync_trading_flow

router = APIRouter(prefix="/api/trading-flow", tags=["trading-flow"])


@router.get("/{symbol}")
def get_trading_flow(symbol: str, limit: int = Query(60, ge=1, le=200)) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM (
                SELECT trade_date, individual_net, foreigner_net, institution_net,
                       other_corporation_net, foreigner_holding_rate, institution_breakdown
                FROM trading_flow WHERE symbol = ? ORDER BY trade_date DESC LIMIT ?
            ) ORDER BY trade_date ASC
            """,
            (symbol, limit),
        ).fetchall()

    result = []
    for row in rows:
        item = dict(row)
        item["institution_breakdown"] = (
            json.loads(item["institution_breakdown"]) if item["institution_breakdown"] else {}
        )
        result.append(item)
    return result


@router.post("/{symbol}/sync")
async def sync_trading_flow_route(symbol: str, count: int = Query(60, ge=1, le=200)) -> dict:
    return await sync_trading_flow(symbol, count=count)

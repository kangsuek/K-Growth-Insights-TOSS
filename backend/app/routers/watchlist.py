"""관심종목 CRUD + 캔들/매매동향 조회·재수집 라우터."""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.database import get_connection
from app.services import watchlist
from app.services.candles import sync_daily_candles
from app.services.trading_flow import sync_trading_flow

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


class AddStockRequest(BaseModel):
    symbol: str


@router.get("")
def list_stocks() -> list[dict]:
    return watchlist.list_stocks()


@router.post("", status_code=201)
async def add_stock(body: AddStockRequest) -> dict:
    try:
        return await watchlist.add_stock(body.symbol)
    except watchlist.SymbolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except watchlist.DuplicateSymbolError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{symbol}")
def remove_stock(symbol: str) -> dict:
    try:
        watchlist.remove_stock(symbol)
    except watchlist.SymbolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"symbol": symbol, "deleted": True}


@router.post("/reorder")
def reorder(symbols: list[str]) -> dict:
    try:
        watchlist.reorder(symbols)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"symbols": symbols}


@router.get("/{symbol}/candles")
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


@router.post("/{symbol}/candles/sync")
async def sync_candles(symbol: str, count: int = Query(120, ge=1, le=200)) -> dict:
    return await sync_daily_candles(symbol, count=count)


@router.get("/{symbol}/trading-flow")
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


@router.post("/{symbol}/trading-flow/sync")
async def sync_trading_flow_route(symbol: str, count: int = Query(60, ge=1, le=200)) -> dict:
    return await sync_trading_flow(symbol, count=count)

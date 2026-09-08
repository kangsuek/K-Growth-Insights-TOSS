"""관심종목 CRUD 라우터."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import watchlist

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

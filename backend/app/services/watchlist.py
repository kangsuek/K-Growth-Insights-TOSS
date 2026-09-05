"""관심종목(watchlist) CRUD.

stock_catalog(전체 유니버스)와 별개의 테이블이다. 종목 추가 시 카탈로그에 실제로
존재하는 심볼인지 서버에서 검증해, 존재하지 않는 심볼로 캔들 API를 낭비 호출하지 않게 한다.
"""
from __future__ import annotations

import logging
import sqlite3

from app.database import get_connection
from app.services.candles import sync_daily_candles
from app.services.trading_flow import sync_trading_flow

logger = logging.getLogger(__name__)


class SymbolNotFoundError(LookupError):
    """카탈로그에 존재하지 않는 symbol."""


class DuplicateSymbolError(ValueError):
    """이미 관심종목에 등록된 symbol."""


def list_stocks() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM stocks ORDER BY sort_order").fetchall()
    return [dict(row) for row in rows]


async def add_stock(symbol: str) -> dict:
    with get_connection() as conn:
        catalog_row = conn.execute(
            "SELECT name, market, security_type FROM stock_catalog WHERE symbol = ?", (symbol,)
        ).fetchone()
        if catalog_row is None:
            raise SymbolNotFoundError(f"카탈로그에 없는 symbol입니다: {symbol}")

        existing = conn.execute("SELECT 1 FROM stocks WHERE symbol = ?", (symbol,)).fetchone()
        if existing is not None:
            raise DuplicateSymbolError(f"이미 관심종목에 등록되어 있습니다: {symbol}")

        next_order = conn.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 AS n FROM stocks").fetchone()["n"]
        try:
            conn.execute(
                """
                INSERT INTO stocks (symbol, name, market, security_type, sort_order, updated_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
                """,
                (symbol, catalog_row["name"], catalog_row["market"], catalog_row["security_type"], next_order),
            )
        except sqlite3.IntegrityError as exc:
            # 동시에 같은 symbol을 추가하는 요청이 겹친 경우 — 뒤늦게 들어온 쪽을 중복으로 처리한다.
            raise DuplicateSymbolError(f"이미 관심종목에 등록되어 있습니다: {symbol}") from exc

    try:
        await sync_daily_candles(symbol)
    except Exception:
        # 캔들 수집 실패가 관심종목 등록 자체를 막지는 않는다. 나중에 /candles/sync로 재수집 가능.
        logger.warning("관심종목 %s 캔들 수집 실패(등록은 유지됨)", symbol, exc_info=True)

    try:
        await sync_trading_flow(symbol)
    except Exception:
        # 매매동향 수집도 캔들과 마찬가지로 실패해도 등록을 막지 않는다.
        logger.warning("관심종목 %s 매매동향 수집 실패(등록은 유지됨)", symbol, exc_info=True)

    with get_connection() as conn:
        row = conn.execute("SELECT * FROM stocks WHERE symbol = ?", (symbol,)).fetchone()
    return dict(row)


def remove_stock(symbol: str) -> None:
    with get_connection() as conn:
        existing = conn.execute("SELECT 1 FROM stocks WHERE symbol = ?", (symbol,)).fetchone()
        if existing is None:
            raise SymbolNotFoundError(f"관심종목에 없는 symbol입니다: {symbol}")
        conn.execute("DELETE FROM stocks WHERE symbol = ?", (symbol,))
        conn.execute("DELETE FROM prices WHERE symbol = ?", (symbol,))
        conn.execute("DELETE FROM trading_flow WHERE symbol = ?", (symbol,))


def reorder(symbols: list[str]) -> None:
    with get_connection() as conn:
        existing = {row["symbol"] for row in conn.execute("SELECT symbol FROM stocks")}
        if set(symbols) != existing:
            raise ValueError("reorder 목록은 현재 관심종목 전체와 정확히 일치해야 합니다.")
        for order, symbol in enumerate(symbols, start=1):
            conn.execute("UPDATE stocks SET sort_order = ? WHERE symbol = ?", (order, symbol))

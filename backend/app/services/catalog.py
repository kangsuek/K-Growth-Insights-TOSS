"""토스 종목 카탈로그(KOSPI/KOSDAQ 전체 유니버스) 동기화.

GET /api/v1/stocks/all은 페이지네이션이 없어 시장별 1회 호출로 전체가 반환된다.
이번 동기화에서 보지 못한 symbol은 상장폐지/변경 등으로 간주해 삭제(prune)한다.
"""
from __future__ import annotations

import asyncio

from app.database import get_connection
from app.services.toss_client import toss_client

MARKETS = ("KOSPI", "KOSDAQ")

# 동시에 두 번 트리거돼도(중복 클릭 등) SQLite 쓰기가 겹치지 않도록 직렬화한다.
_sync_lock = asyncio.Lock()


async def sync_catalog() -> dict:
    async with _sync_lock:
        return await _sync_catalog()


async def _sync_catalog() -> dict:
    counts: dict[str, int] = {}
    seen_symbols: set[str] = set()

    with get_connection() as conn:
        for market in MARKETS:
            payload = await toss_client.get("/api/v1/stocks/all", params={"market": market})
            items = payload["result"]
            counts[market.lower() + "_count"] = len(items)

            for item in items:
                symbol = item["symbol"]
                seen_symbols.add(symbol)
                conn.execute(
                    """
                    INSERT INTO stock_catalog
                        (symbol, name, market, security_type, is_common_share, isin_code, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                    ON CONFLICT(symbol) DO UPDATE SET
                        name = excluded.name,
                        market = excluded.market,
                        security_type = excluded.security_type,
                        is_common_share = excluded.is_common_share,
                        isin_code = excluded.isin_code,
                        updated_at = excluded.updated_at
                    """,
                    (
                        symbol,
                        item["name"],
                        market,
                        item["securityType"],
                        1 if item.get("isCommonShare") else 0,
                        item.get("isinCode"),
                    ),
                )

        existing_symbols = {row["symbol"] for row in conn.execute("SELECT symbol FROM stock_catalog")}
        stale_symbols = existing_symbols - seen_symbols
        if stale_symbols:
            placeholders = ",".join("?" for _ in stale_symbols)
            conn.execute(
                f"DELETE FROM stock_catalog WHERE symbol IN ({placeholders})",
                tuple(stale_symbols),
            )

    return {
        **counts,
        "total_collected": len(seen_symbols),
        "removed_count": len(stale_symbols),
    }

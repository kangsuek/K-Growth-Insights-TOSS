"""종목 카탈로그 수집/조회 라우터."""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.database import get_connection
from app.services.catalog import sync_catalog

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


@router.post("/sync")
async def sync() -> dict:
    return await sync_catalog()


@router.get("")
async def list_catalog(
    market: str | None = None,
    security_type: str | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict:
    conditions = []
    params: list = []

    if market:
        conditions.append("market = ?")
        params.append(market)
    if security_type:
        conditions.append("security_type = ?")
        params.append(security_type)
    if q:
        conditions.append("name LIKE ?")
        params.append(f"%{q}%")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    offset = (page - 1) * page_size

    with get_connection() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) AS count FROM stock_catalog {where_clause}", params
        ).fetchone()["count"]
        rows = conn.execute(
            f"""
            SELECT symbol, name, market, security_type, is_common_share, isin_code, updated_at
            FROM stock_catalog {where_clause}
            ORDER BY symbol
            LIMIT ? OFFSET ?
            """,
            (*params, page_size, offset),
        ).fetchall()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [dict(row) for row in rows],
    }

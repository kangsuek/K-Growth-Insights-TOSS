"""토스 투자자별 매매동향(개인/외국인/기관/기타법인) 수집.

GET /api/v1/stocks/{symbol}/investor-trading 응답의 수치는 문자열로 오므로
저장 전 숫자로 변환한다. 기관 7세부(financialInvestment 등)는 컬럼을 늘리지
않고 JSON 텍스트 한 컬럼에 순매수만 담아 저장한다.
"""
from __future__ import annotations

import json

from app.database import get_connection
from app.services.toss_client import toss_client

INSTITUTION_BREAKDOWN_KEYS = (
    "financialInvestment",
    "insurance",
    "trust",
    "privateEquityFund",
    "bank",
    "otherFinancialInstitution",
    "pensionFund",
)


def _parse_optional_float(value) -> float | None:
    """토스 API가 해당 없음을 null 대신 "-"/"" 같은 문자열로 보내는 경우까지 안전하게 처리한다."""
    if value is None or value == "" or value == "-":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def sync_trading_flow(symbol: str, count: int = 60) -> dict:
    payload = await toss_client.get(
        f"/api/v1/stocks/{symbol}/investor-trading", params={"count": count}
    )
    records = payload["result"]["records"]

    with get_connection() as conn:
        for record in records:
            # institution.breakdown / foreignerHolding이 키 자체가 없는 경우뿐 아니라
            # 명시적으로 null로 오는 경우도 있어 `or {}`로 두 상황 모두 방어한다.
            breakdown = record["institution"].get("breakdown") or {}
            breakdown_net = {
                key: int(breakdown[key]["netBuyVolume"])
                for key in INSTITUTION_BREAKDOWN_KEYS
                if key in breakdown
            }
            holding_rate = _parse_optional_float(
                (record.get("foreignerHolding") or {}).get("holdingRate")
            )

            conn.execute(
                """
                INSERT INTO trading_flow
                    (symbol, trade_date, individual_net, foreigner_net, institution_net,
                     other_corporation_net, foreigner_holding_rate, institution_breakdown, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(symbol, trade_date) DO UPDATE SET
                    individual_net = excluded.individual_net,
                    foreigner_net = excluded.foreigner_net,
                    institution_net = excluded.institution_net,
                    other_corporation_net = excluded.other_corporation_net,
                    foreigner_holding_rate = excluded.foreigner_holding_rate,
                    institution_breakdown = excluded.institution_breakdown,
                    updated_at = excluded.updated_at
                """,
                (
                    symbol,
                    record["date"],
                    int(record["individual"]["netBuyVolume"]),
                    int(record["foreigner"]["netBuyVolume"]),
                    int(record["institution"]["netBuyVolume"]),
                    int(record["otherCorporation"]["netBuyVolume"]),
                    holding_rate,
                    json.dumps(breakdown_net),
                ),
            )

    return {"symbol": symbol, "saved_count": len(records)}

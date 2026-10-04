"""종목 비교(Comparison) — 정규화 가격·통계·상관관계.

원본 /etfs/compare 응답을 재현한다(순수 파이썬 계산):
{normalized_prices:{dates,data}, statistics:{ticker:{...}}, correlation_matrix:{tickers,matrix}}
"""
from __future__ import annotations

import math
from datetime import date, timedelta

from app.services import metrics, repository

# 연환산 기준 거래일 수는 metrics와 같은 값을 쓴다(지표가 화면마다 어긋나지 않게).
TRADING_DAYS_PER_YEAR = metrics.TRADING_DAYS_PER_YEAR
RISK_FREE_RATE = 3.0

# 연환산(annualized)은 표본이 짧으면 극단적으로 증폭된다(20거래일 +39% → 연환산 +8043%).
# 화면도 '3개월 이상 데이터만 연환산 표시, 3개월 미만은 N/A'로 안내하므로, 그 미만은
# 계산하지 않고 None을 준다.
#
# 기준은 60거래일. 이론값 252/4=63이 아니라 실제 거래일 수를 쓴다 — 달력 3개월
# 구간에는 공휴일이 끼어 60일 안팎이 나오므로(예: 2026-04-26~07-26이 60거래일),
# 63으로 두면 사용자가 '3개월'을 골라도 '3개월 미만'으로 표시된다.
MIN_POINTS_FOR_ANNUALIZED = 60


def _daily_returns(values: list[float]) -> list[float]:
    return [(values[i] / values[i - 1] - 1) for i in range(1, len(values)) if values[i - 1]]


def _correlation(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n < 2:
        return 0.0
    a, b = a[:n], b[:n]
    ma, mb = sum(a) / n, sum(b) / n
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    da = math.sqrt(sum((x - ma) ** 2 for x in a))
    db = math.sqrt(sum((x - mb) ** 2 for x in b))
    if da == 0 or db == 0:
        return 0.0
    return cov / (da * db)


def _statistics(closes: list[float]) -> dict:
    """기간·연환산 수익률, 변동성, 최대낙폭, 샤프."""
    n = len(closes)
    if n < 2 or not closes[0]:
        return {"period_return": None, "annualized_return": None, "volatility": None,
                "max_drawdown": None, "sharpe_ratio": None, "data_points": n}
    period_return = (closes[-1] / closes[0] - 1) * 100
    rets = _daily_returns(closes)
    # 변동성은 표본표준편차(n-1) 기준 연환산. rets는 비율이므로 퍼센트로 바꿔 넘긴다.
    volatility = metrics.annualized_volatility([r * 100 for r in rets]) if rets else None
    # 표본이 3개월 미만이면 연환산은 의미가 없어 계산하지 않는다.
    annualized = (
        ((closes[-1] / closes[0]) ** (TRADING_DAYS_PER_YEAR / max(n - 1, 1)) - 1) * 100
        if n >= MIN_POINTS_FOR_ANNUALIZED else None
    )
    # 최대 낙폭
    peak = closes[0]
    max_dd = 0.0
    for c in closes:
        peak = max(peak, c)
        if peak:
            max_dd = min(max_dd, (c - peak) / peak * 100)
    # 샤프는 연환산 수익률에 기반하므로 연환산이 없으면 함께 None.
    sharpe = None
    if annualized is not None and volatility and volatility > 0:
        sharpe = round((annualized - RISK_FREE_RATE) / volatility, 2)
    return {
        "period_return": round(period_return, 2),
        "annualized_return": round(annualized, 2) if annualized is not None else None,
        "volatility": round(volatility, 2) if volatility is not None else None,
        "max_drawdown": round(max_dd, 2),
        "sharpe_ratio": sharpe,
        "data_points": n,
    }


def compare(ticker_list: list[str], start: str | None, end: str | None) -> dict:
    """여러 종목의 정규화 가격·통계·상관관계를 계산."""
    today = date.today()
    end = end or today.isoformat()
    start = start or (today - timedelta(days=30)).isoformat()

    # 종목별 {date: close}. get_prices(days=N)는 "N개 행(거래일)"이라 보유
    # 이력이 길면 요청한 start보다 늦게 잘릴 수 있어(52주 버그와 동일 패턴),
    # 캘린더 범위를 그대로 쿼리하는 get_prices_range를 쓴다.
    series: dict[str, dict] = {}
    for t in ticker_list:
        prices = repository.get_prices_range(t, start, end)  # 오래된→최신, 이미 범위 필터됨
        m = {p["date"]: p["close_price"] for p in prices if p.get("close_price")}
        if m:
            series[t] = m

    valid = list(series.keys())
    # 선택한 기간에 시세가 하나도 없어 통째로 빠진 종목(예: 추적 시작일이 늦은 종목을
    # 그보다 이른 기간으로 비교하는 경우). 화면에서 말없이 사라지지 않도록 알려준다.
    excluded = [t for t in ticker_list if t not in valid]
    if not valid:
        return {"normalized_prices": {"dates": [], "data": {}},
                "statistics": {}, "correlation_matrix": {"tickers": [], "matrix": []},
                "excluded_tickers": excluded}

    # 통계(수익률·변동성·MDD·샤프)는 종목마다 '기간 안의 자기 시세 전체'로 계산한다.
    # 예전엔 전 종목 공통 날짜(교집합)만 썼는데, 상장한 지 얼마 안 된 종목이 하나라도
    # 섞이면 계산 시작일이 그 종목 상장일로 잘려 6개월·YTD·1년이 모두 같은 값이 됐다.
    # 실제 계산 구간이 요청보다 짧은 종목은 start_date로 화면에서 알린다.
    #
    # 정규화 차트는 전 종목 날짜 합집합을 축으로, 각 종목의 첫 거래일을 100으로 둔다
    # (데이터가 없는 날은 None) — 마지막 값이 period_return과 일치한다.
    all_dates = sorted(set().union(*[set(series[t]) for t in valid]))

    normalized: dict[str, list[float | None]] = {}
    statistics: dict[str, dict] = {}
    for t in valid:
        own_dates = sorted(series[t])
        closes = [series[t][d] for d in own_dates]
        base = closes[0]
        normalized[t] = [
            round(series[t][d] / base * 100, 2) if d in series[t] else None
            for d in all_dates
        ]
        statistics[t] = {**_statistics(closes),
                         "start_date": own_dates[0], "end_date": own_dates[-1]}

    # 상관관계 행렬(일일 수익률 기준) — 같은 날끼리 비교해야 하므로 종목 쌍마다
    # 두 종목의 공통 날짜로 계산한다(한 종목의 짧은 이력이 다른 쌍까지 자르지 않게).
    matrix = []
    for a in valid:
        row = []
        for b in valid:
            if a == b:
                row.append(1.0)
                continue
            pair = sorted(set(series[a]) & set(series[b]))
            row.append(round(_correlation(
                _daily_returns([series[a][d] for d in pair]),
                _daily_returns([series[b][d] for d in pair]),
            ), 2))
        matrix.append(row)

    return {
        "normalized_prices": {"dates": all_dates, "data": normalized},
        "statistics": statistics,
        "correlation_matrix": {"tickers": valid, "matrix": matrix},
        "excluded_tickers": excluded,
    }

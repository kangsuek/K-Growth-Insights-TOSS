"""토스 실시간 체결(WebSocket) 매니저.

토스 access_token은 서버 자격증명이라 브라우저에 노출할 수 없다. 이 매니저가
프로세스당 단일 커넥션으로 토스 WS(wss://openapi-ws.tossinvest.com/ws/v1)에
접속해 관심종목을 구독하고, 수신한 체결을 프론트엔드가 연결하는 /ws/realtime
클라이언트들에 그대로 중계(broadcast)한다.

구독 선언은 배열이어야 한다: [{"type":"trade:kr","codes":[...]}] — 객체 하나만
보내면 wrong-format 에러가 난다(2026-09-05 실계정 연결로 확인, 킥오프 문서와 다름).

/ws/realtime 자체 프로토콜(우리 백엔드↔프론트엔드, 토스 프로토콜과 별개):
- 연결 시 1회: {"type":"snapshot","data":{"trades":{symbol:[record,...]},"quotes":{symbol:quote}}}
- 체결마다: {"type":"trade","data":{symbol,price,volume,timestamp}} (라인차트용 원시 틱)
- 체결/정합보정마다: {"type":"quote","data":{symbol,open,high,low,last,prev_close,updated_at}}
  (카드/헤더용 집계값 — WS가 시가/고가/저가를 안 주므로 틱 누적 + REST 정합 보정으로 계산.
  자세한 설계는 KICKOFF 마일스톤 9 계획 참고)
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from collections import deque
from datetime import datetime, timedelta, timezone

import websockets

from app.config import TOSS_CLIENT_ID, TOSS_CLIENT_SECRET
from app.database import get_connection
from app.services.toss_client import toss_client

logger = logging.getLogger(__name__)

WS_URL = "wss://openapi-ws.tossinvest.com/ws/v1"
PING_INTERVAL_SECONDS = 60
SUBSCRIPTION_REFRESH_SECONDS = 10
RECV_POLL_TIMEOUT_SECONDS = 5
MAX_BACKOFF_SECONDS = 30
TRADE_HISTORY_MAXLEN = 200
QUOTE_RECONCILE_INTERVAL_SECONDS = 30

# 시장 지수(코스피/코스닥)는 종목과 달리 WS 푸시가 없어 REST 폴링으로 quotes에 합류시킨다.
INDEX_SYMBOLS = ("KOSPI", "KOSDAQ")
MARKET_INDICATOR_POLL_SECONDS = 3

KST = timezone(timedelta(hours=9))


def _load_watchlist_symbols() -> set[str]:
    # 관심종목뿐 아니라 그 ETF들의 구성종목(etf_holdings.item_code)도 함께 구독한다 —
    # 상세페이지 "ETF 주요 구성자산" 표의 전일대비를 실시간으로 보여주기 위함. ETF당
    # 구성종목은 최대 10개(네이버 응답 자체가 Top10만 제공)라 관심종목이 늘어도 토스
    # 연결당 구독 100건 제한을 넘길 걱정은 적다.
    with get_connection() as conn:
        stock_rows = conn.execute("SELECT ticker FROM stocks").fetchall()
        holding_rows = conn.execute(
            "SELECT DISTINCT item_code FROM etf_holdings "
            "WHERE item_code IS NOT NULL AND item_code != ''"
        ).fetchall()
    symbols = {row["ticker"] for row in stock_rows}
    symbols.update(row["item_code"] for row in holding_rows)
    return symbols


def _load_prev_close(symbol: str) -> float | None:
    # 스케줄러가 장중에도 오늘자 행을 계속 upsert하므로(collectors.collect_prices),
    # 오늘 날짜를 제외하고 그 이전 중 가장 최근 확정 종가를 가져와야 한다. 그냥
    # ORDER BY date DESC LIMIT 1만 쓰면 "오늘 장중 현재까지 종가"가 섞여 등락률이
    # 왜곡된다(2026-09-08 실측: prev_close가 당일 last와 거의 같아지는 현상으로 발견).
    with get_connection() as conn:
        row = conn.execute(
            "SELECT close_price FROM prices WHERE ticker = ? AND date < ? "
            "ORDER BY date DESC LIMIT 1",
            (symbol, _today_kst()),
        ).fetchone()
    return row["close_price"] if row else None


def _today_kst() -> str:
    return datetime.now(KST).date().isoformat()


def _empty_quote(symbol: str) -> dict:
    return {
        "symbol": symbol,
        "open": None,
        "high": None,
        "low": None,
        "last": None,
        "prev_close": None,
        "updated_at": None,
    }


class TossRealtimeManager:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._quote_task: asyncio.Task | None = None
        self._market_indicator_task: asyncio.Task | None = None
        self._seed_tasks: set[asyncio.Task] = set()
        self._clients: set = set()
        self._current_symbols: set[str] = set()
        self._stopping = False
        self.trade_history: dict[str, deque] = {}
        self.quotes: dict[str, dict] = {}

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            logger.warning("실시간 시세 매니저가 이미 실행 중입니다 — 중복 시작을 무시합니다.")
            return
        if not (TOSS_CLIENT_ID and TOSS_CLIENT_SECRET):
            logger.info("토스 자격증명이 없어 실시간 시세 매니저를 시작하지 않습니다.")
            return
        self._stopping = False
        self._task = asyncio.create_task(self._run())
        self._quote_task = asyncio.create_task(self._quote_reconciliation_loop())
        self._market_indicator_task = asyncio.create_task(self._market_indicator_loop())

    async def stop(self) -> None:
        self._stopping = True
        for attr in ("_task", "_quote_task", "_market_indicator_task"):
            task = getattr(self, attr)
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                setattr(self, attr, None)

        pending = list(self._seed_tasks)
        for task in pending:
            task.cancel()
        for task in pending:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._seed_tasks.clear()

    def _spawn_seed_task(self, symbol: str) -> None:
        """새로 추가된 심볼의 quote를 백그라운드로 시딩한다.

        참조를 self._seed_tasks에 보관해 GC 대상이 되지 않게 하고, 완료 시
        자동으로 정리하며, stop()에서 취소·대기할 수 있게 한다.
        """
        task = asyncio.create_task(self._seed_quote_safe(symbol))
        self._seed_tasks.add(task)
        task.add_done_callback(self._seed_tasks.discard)

    def register(self, websocket) -> None:
        self._clients.add(websocket)

    def unregister(self, websocket) -> None:
        self._clients.discard(websocket)

    async def broadcast(self, payload: dict) -> None:
        message = json.dumps(payload)
        dead = []
        for client in list(self._clients):
            try:
                await client.send_text(message)
            except Exception:
                dead.append(client)
        for client in dead:
            self._clients.discard(client)

    def snapshot(self) -> dict:
        return {
            "trades": {symbol: list(history) for symbol, history in self.trade_history.items()},
            "quotes": dict(self.quotes),
        }

    async def seed_quote(self, symbol: str) -> None:
        """전일종가 + (있다면) 오늘자 봉의 시가/고가/저가로 quote를 채우거나 정합 보정한다.

        관심종목(stocks)은 로컬 DB(prices)에 전일종가가 있지만, ETF 구성종목처럼 watchlist에는
        없는 심볼은 DB에 아무 이력이 없어 _load_prev_close가 항상 None을 준다. 이 경우 캔들을
        2개(count=2) 요청해 두 번째 봉(전일 확정 종가)을 대신 prev_close로 쓴다.
        """
        quote = self.quotes.setdefault(symbol, _empty_quote(symbol))

        if quote["prev_close"] is None:
            prev_close = await asyncio.to_thread(_load_prev_close, symbol)
            if prev_close is not None:
                quote["prev_close"] = prev_close

        payload = await toss_client.get(
            "/api/v1/candles", params={"symbol": symbol, "interval": "1d", "count": 2}
        )
        candles = payload["result"]["candles"]
        if not candles:
            return

        candle = candles[0]
        if candle["timestamp"][:10] != _today_kst():
            # 오늘자 미확정 봉을 안 주는 경우 — 시가/고가/저가는 틱으로만 채운다(핸들러 쪽 로직).
            # DB에도 전일종가가 없었다면(watchlist 밖 심볼), 이 봉 자체가 가장 최근 확정
            # 종가이므로 그걸 prev_close로 쓴다.
            if quote["prev_close"] is None:
                quote["prev_close"] = float(candle["closePrice"])
            return

        # 시가는 하루 중 유일하게 고정된 값이라 그대로 덮어써도 안전하다. 반면 고가/저가는
        # REST 스냅샷이 그 사이 들어온 틱보다 지연되어 있을 수 있어, 무조건 덮어쓰면 이미
        # 관측한 고가/저가를 후퇴시킬 수 있다 — 항상 더 넓은 범위로만 병합(max/min)한다.
        quote["open"] = float(candle["openPrice"])
        rest_high = float(candle["highPrice"])
        rest_low = float(candle["lowPrice"])
        quote["high"] = rest_high if quote["high"] is None else max(quote["high"], rest_high)
        quote["low"] = rest_low if quote["low"] is None else min(quote["low"], rest_low)
        if quote["last"] is None:
            quote["last"] = float(candle["closePrice"])
        quote["updated_at"] = candle["timestamp"]

        if quote["prev_close"] is None and len(candles) >= 2:
            quote["prev_close"] = float(candles[1]["closePrice"])

    async def _seed_quote_safe(self, symbol: str) -> None:
        before = dict(self.quotes.get(symbol, {}))
        try:
            await self.seed_quote(symbol)
        except Exception:
            logger.warning("종목 %s 실시간 시세 시딩 실패", symbol, exc_info=True)
            return
        after = self.quotes.get(symbol)
        if after and after != before:
            await self.broadcast({"type": "quote", "data": dict(after)})

    async def _quote_reconciliation_loop(self) -> None:
        while not self._stopping:
            for symbol in list(self._current_symbols):
                if self._stopping:
                    break
                await self._seed_quote_safe(symbol)
            await asyncio.sleep(QUOTE_RECONCILE_INTERVAL_SECONDS)

    async def _load_index_prev_close(self, symbol: str) -> float | None:
        """지수의 전일 확정 종가를 캔들 2개(count=2)로 구한다.

        seed_quote()와 동일한 패턴: 최신 봉이 오늘자면 두 번째 봉이 전일 종가, 오늘자가
        아니면(장 시작 전 등) 그 봉 자체가 전일 종가다.
        """
        payload = await toss_client.get(
            f"/api/v1/market-indicators/{symbol}/candles", params={"interval": "1d", "count": 2}
        )
        candles = payload["result"]["candles"]
        if not candles:
            return None
        if candles[0]["timestamp"][:10] != _today_kst():
            return float(candles[0]["closePrice"])
        if len(candles) >= 2:
            return float(candles[1]["closePrice"])
        return None

    async def _market_indicator_loop(self) -> None:
        """시장 지수(코스피/코스닥)는 WS 푸시가 없어 REST를 3초마다 폴링해 quotes에 합류시킨다.

        "KOSPI"/"KOSDAQ" 키는 6자리 종목코드와 절대 겹치지 않으므로 기존 quotes 딕셔너리에
        안전하게 함께 둘 수 있다 — 그러면 기존 broadcast()/REST/WS 경로를 전혀 안 고쳐도
        프론트가 이미 3초 주기로 반영하는 quotes에 지수도 자연히 나타난다.
        """
        while not self._stopping:
            try:
                payload = await toss_client.get(
                    "/api/v1/market-indicators/prices",
                    params={"symbols": ",".join(INDEX_SYMBOLS)},
                )
                rows = payload.get("result", [])
            except Exception:
                logger.warning("시장 지수 시세 조회 실패", exc_info=True)
                rows = []

            for row in rows:
                symbol = row.get("symbol")
                if symbol not in INDEX_SYMBOLS or row.get("lastPrice") is None:
                    continue
                # 한 심볼(주로 prev_close 조회) 실패가 나머지 심볼 처리를 막지 않도록
                # 심볼별로 개별 try/except로 감싼다 — 안 그러면 KOSPI가 실패할 때마다
                # 같은 사이클의 KOSDAQ도 매번 함께 건너뛰어진다(순서상 KOSPI가 먼저 옴).
                try:
                    quote = self.quotes.setdefault(symbol, _empty_quote(symbol))
                    quote["last"] = float(row["lastPrice"])
                    quote["updated_at"] = row.get("timestamp")
                    if quote["prev_close"] is None:
                        quote["prev_close"] = await self._load_index_prev_close(symbol)
                    await self.broadcast({"type": "quote", "data": dict(quote)})
                except Exception:
                    logger.warning("시장 지수 %s 시세 갱신 실패", symbol, exc_info=True)

            await asyncio.sleep(MARKET_INDICATOR_POLL_SECONDS)

    async def _declare_subscriptions(self, ws, symbols: set[str]) -> None:
        added = symbols - self._current_symbols
        payload = [{"type": "trade:kr", "codes": sorted(symbols)}] if symbols else []
        await ws.send(json.dumps(payload))
        self._current_symbols = set(symbols)
        for symbol in added:
            self._spawn_seed_task(symbol)

    async def handle_message(self, ws, raw: str) -> None:
        """수신 프레임 1건을 파싱해 분기 처리한다(재연결/재선언 등 부수효과 포함)."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("실시간 시세 프레임 파싱 실패: %s", raw[:200])
            return

        msg_type = data.get("type")

        if msg_type == "message":
            topic = data.get("topic") or ""
            symbol = topic.split(":")[-1] if topic else None
            trade = data.get("data") or {}
            if not symbol or "price" not in trade:
                return
            price = float(trade["price"])
            record = {
                "symbol": symbol,
                "price": price,
                "volume": int(trade.get("volume", 0)),
                "timestamp": trade.get("timestamp"),
            }
            self.trade_history.setdefault(symbol, deque(maxlen=TRADE_HISTORY_MAXLEN)).append(record)
            await self.broadcast({"type": "trade", "data": record})

            quote = self.quotes.setdefault(symbol, _empty_quote(symbol))
            quote["open"] = price if quote["open"] is None else quote["open"]
            quote["high"] = price if quote["high"] is None else max(quote["high"], price)
            quote["low"] = price if quote["low"] is None else min(quote["low"], price)
            quote["last"] = price
            quote["updated_at"] = record["timestamp"]
            await self.broadcast({"type": "quote", "data": dict(quote)})

        elif msg_type == "error":
            error = data.get("error") or {}
            code = error.get("code")
            if code == "server-shutdown":
                logger.info("토스 서버 재시작 통보 수신 — 재연결합니다.")
                await ws.close()
            elif code == "rate-limit-exceeded":
                await asyncio.sleep(1)
                await self._declare_subscriptions(ws, self._current_symbols)
            else:
                logger.warning("토스 실시간 에러 프레임: %s", error)

        elif msg_type == "subscriptions":
            logger.info(
                "실시간 구독 확정: %s, 거부: %s", data.get("subscribed"), data.get("rejected")
            )
        # type == "pong"은 keepalive 확인용이라 별도 처리 불필요.

    async def _run(self) -> None:
        attempt = 0
        while not self._stopping:
            try:
                token = await toss_client.get_access_token()
                async with websockets.connect(
                    WS_URL, additional_headers={"Authorization": f"Bearer {token}"}
                ) as ws:
                    attempt = 0
                    symbols = await asyncio.to_thread(_load_watchlist_symbols)
                    await self._declare_subscriptions(ws, symbols)

                    last_ping = time.monotonic()
                    last_refresh = time.monotonic()
                    while not self._stopping:
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=RECV_POLL_TIMEOUT_SECONDS)
                            await self.handle_message(ws, raw)
                        except asyncio.TimeoutError:
                            pass

                        now = time.monotonic()
                        if now - last_ping >= PING_INTERVAL_SECONDS:
                            await ws.send("PING")
                            last_ping = now
                        if now - last_refresh >= SUBSCRIPTION_REFRESH_SECONDS:
                            new_symbols = await asyncio.to_thread(_load_watchlist_symbols)
                            if new_symbols != self._current_symbols:
                                await self._declare_subscriptions(ws, new_symbols)
                            last_refresh = now
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("토스 실시간 연결이 끊겼습니다. 재연결을 시도합니다: %s", exc)

            if self._stopping:
                break
            attempt += 1
            backoff = min(MAX_BACKOFF_SECONDS, 2 ** (attempt - 1)) + random.uniform(0, 1)
            await asyncio.sleep(backoff)


realtime_manager = TossRealtimeManager()

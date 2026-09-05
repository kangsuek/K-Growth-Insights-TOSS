"""토스 실시간 체결(WebSocket) 매니저.

토스 access_token은 서버 자격증명이라 브라우저에 노출할 수 없다. 이 매니저가
프로세스당 단일 커넥션으로 토스 WS(wss://openapi-ws.tossinvest.com/ws/v1)에
접속해 관심종목을 구독하고, 수신한 체결을 프론트엔드가 연결하는 /ws/realtime
클라이언트들에 그대로 중계(broadcast)한다.

구독 선언은 배열이어야 한다: [{"type":"trade:kr","codes":[...]}] — 객체 하나만
보내면 wrong-format 에러가 난다(2026-09-05 실계정 연결로 확인, 킥오프 문서와 다름).
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import time

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


def _load_watchlist_symbols() -> set[str]:
    with get_connection() as conn:
        rows = conn.execute("SELECT symbol FROM stocks").fetchall()
    return {row["symbol"] for row in rows}


class TossRealtimeManager:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._clients: set = set()
        self._current_symbols: set[str] = set()
        self._stopping = False
        self.latest_trades: dict[str, dict] = {}

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            logger.warning("실시간 시세 매니저가 이미 실행 중입니다 — 중복 시작을 무시합니다.")
            return
        if not (TOSS_CLIENT_ID and TOSS_CLIENT_SECRET):
            logger.info("토스 자격증명이 없어 실시간 시세 매니저를 시작하지 않습니다.")
            return
        self._stopping = False
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stopping = True
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

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

    async def _declare_subscriptions(self, ws, symbols: set[str]) -> None:
        payload = [{"type": "trade:kr", "codes": sorted(symbols)}] if symbols else []
        await ws.send(json.dumps(payload))
        self._current_symbols = set(symbols)

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
            record = {
                "symbol": symbol,
                "price": float(trade["price"]),
                "volume": int(trade.get("volume", 0)),
                "timestamp": trade.get("timestamp"),
            }
            self.latest_trades[symbol] = record
            await self.broadcast({"type": "trade", "data": record})

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

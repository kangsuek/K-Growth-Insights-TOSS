"""공유 API 키 인증(선택, API_KEY 미설정 시 완전 비활성)."""
from __future__ import annotations

import secrets
import threading
import time

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from app import config

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(key: str | None = Security(_api_key_header)) -> None:
    if not config.API_KEY:
        return
    if key != config.API_KEY:
        raise HTTPException(status_code=401, detail="유효하지 않은 API 키입니다")


# --- WebSocket 1회용 접속 티켓 -------------------------------------------------
#
# 브라우저 네이티브 WebSocket은 커스텀 헤더를 못 붙여 쿼리파라미터로 인증해야 하는데,
# 장기 비밀키(API_KEY)를 그대로 쓰면 리버스 프록시 접근 로그·브라우저 히스토리에
# 평문으로 남는다. 그래서 연결 직전 이 짧은 TTL의 1회용 토큰을 발급받아 그것만 쿼리에
# 싣는다 — 개인용 단일 프로세스 앱이라 DB/Redis 없이 인메모리로 충분하다.

WS_TICKET_TTL_SECONDS = 30
_tickets: dict[str, float] = {}
_tickets_lock = threading.Lock()


def issue_ws_ticket() -> dict:
    """1회용 WS 접속 티켓 발급. 짧은 TTL 후 자동 만료, 사용 시 즉시 소모."""
    token = secrets.token_urlsafe(32)
    expires_at = time.monotonic() + WS_TICKET_TTL_SECONDS
    with _tickets_lock:
        now = time.monotonic()
        for expired in [t for t, exp in _tickets.items() if exp < now]:
            del _tickets[expired]
        _tickets[token] = expires_at
    return {"ticket": token, "expires_in": WS_TICKET_TTL_SECONDS}


def consume_ws_ticket(token: str | None) -> bool:
    """티켓을 검증하고 즉시 제거(1회용)한다. 유효했으면 True."""
    if not token:
        return False
    with _tickets_lock:
        expires_at = _tickets.pop(token, None)
    return expires_at is not None and expires_at >= time.monotonic()

"""토스증권 Open API 클라이언트.

인증: POST /oauth2/token (client_credentials) → access_token 발급, 만료 전까지 캐싱.
2026-09-05 실제 계정으로 토큰 발급·/api/v1/stocks 호출 검증 완료.
"""
from __future__ import annotations

import asyncio
import time

import httpx

from app.config import TOSS_API_BASE_URL, TOSS_CLIENT_ID, TOSS_CLIENT_SECRET

# 만료 시각 이 값(초) 이내로 남으면 미리 재발급한다.
TOKEN_REFRESH_MARGIN_SECONDS = 30

# 토스 API 레이트리밋(2026-09-05 실측: x-ratelimit-limit=1, 즉 초당 1회)에 맞춘 최소 요청 간격.
MIN_REQUEST_INTERVAL_SECONDS = 1.0
# 그럼에도 429가 오면 Retry-After만큼 대기 후 재시도할 최대 횟수.
MAX_RETRIES_ON_RATE_LIMIT = 2


class TossAuthError(RuntimeError):
    """토스 API 자격증명 미설정 또는 토큰 발급 실패."""


def _parse_retry_after(value: str | None) -> float:
    """Retry-After 헤더를 초 단위로 파싱한다.

    HTTP 스펙상 delta-seconds 또는 HTTP-date 둘 다 허용되는데, 날짜 형식이 오면
    float() 파싱이 실패하므로 안전하게 기본 간격으로 대체한다.
    """
    if value is None:
        return MIN_REQUEST_INTERVAL_SECONDS
    try:
        return float(value)
    except ValueError:
        return MIN_REQUEST_INTERVAL_SECONDS


class TossClient:
    def __init__(self) -> None:
        self._access_token: str | None = None
        self._expires_at: float = 0.0
        self._lock = asyncio.Lock()
        self._rate_lock = asyncio.Lock()
        self._last_request_at: float = 0.0

    async def _throttle(self) -> None:
        """직전 요청과 MIN_REQUEST_INTERVAL_SECONDS 이상 간격을 두도록 대기한다."""
        async with self._rate_lock:
            wait = MIN_REQUEST_INTERVAL_SECONDS - (time.monotonic() - self._last_request_at)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request_at = time.monotonic()

    async def _send(self, method: str, path: str, **kwargs) -> httpx.Response:
        """스로틀링 + 429 재시도를 적용해 요청을 보낸다."""
        response: httpx.Response | None = None
        for attempt in range(MAX_RETRIES_ON_RATE_LIMIT + 1):
            await self._throttle()
            async with httpx.AsyncClient(base_url=TOSS_API_BASE_URL, timeout=10.0) as client:
                response = await client.request(method, path, **kwargs)
            if response.status_code == 429 and attempt < MAX_RETRIES_ON_RATE_LIMIT:
                retry_after = _parse_retry_after(response.headers.get("Retry-After"))
                await asyncio.sleep(retry_after)
                continue
            return response
        assert response is not None
        return response

    async def _fetch_token(self) -> None:
        if not (TOSS_CLIENT_ID and TOSS_CLIENT_SECRET):
            raise TossAuthError("TOSS_CLIENT_ID/TOSS_CLIENT_SECRET이 설정되지 않았습니다.")

        response = await self._send(
            "POST",
            "/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": TOSS_CLIENT_ID,
                "client_secret": TOSS_CLIENT_SECRET,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            response.raise_for_status()
            payload = response.json()
            self._access_token = payload["access_token"]
            self._expires_at = time.monotonic() + payload["expires_in"]
        except (httpx.HTTPStatusError, KeyError, ValueError) as exc:
            raise TossAuthError(f"토스 토큰 발급 실패: {exc}") from exc

    async def _ensure_token(self) -> str:
        async with self._lock:
            if (
                self._access_token is None
                or time.monotonic() >= self._expires_at - TOKEN_REFRESH_MARGIN_SECONDS
            ):
                await self._fetch_token()
        assert self._access_token is not None
        return self._access_token

    async def get(self, path: str, params: dict | None = None) -> dict:
        """토스 API에 인증된 GET 요청을 보내고 JSON 응답을 반환한다."""
        token = await self._ensure_token()
        response = await self._send(
            "GET",
            path,
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        return response.json()


toss_client = TossClient()

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


class TossAuthError(RuntimeError):
    """토스 API 자격증명 미설정 또는 토큰 발급 실패."""


class TossClient:
    def __init__(self) -> None:
        self._access_token: str | None = None
        self._expires_at: float = 0.0
        self._lock = asyncio.Lock()

    async def _fetch_token(self) -> None:
        if not (TOSS_CLIENT_ID and TOSS_CLIENT_SECRET):
            raise TossAuthError("TOSS_CLIENT_ID/TOSS_CLIENT_SECRET이 설정되지 않았습니다.")

        async with httpx.AsyncClient(base_url=TOSS_API_BASE_URL, timeout=10.0) as client:
            response = await client.post(
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
        async with httpx.AsyncClient(base_url=TOSS_API_BASE_URL, timeout=10.0) as client:
            response = await client.get(
                path,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
        response.raise_for_status()
        return response.json()


toss_client = TossClient()

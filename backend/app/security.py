"""공유 API 키 인증(선택, API_KEY 미설정 시 완전 비활성)."""
from __future__ import annotations

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from app import config

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(key: str | None = Security(_api_key_header)) -> None:
    if not config.API_KEY:
        return
    if key != config.API_KEY:
        raise HTTPException(status_code=401, detail="유효하지 않은 API 키입니다")

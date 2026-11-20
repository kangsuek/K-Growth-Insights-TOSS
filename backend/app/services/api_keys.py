"""API 키(토스증권 Open API·네이버 검색) 저장·조회·런타임 적용.

키는 DB와 같은 디렉터리(config.APP_DATA_DIR)의 api_keys.json에 저장하고, 저장 시
os.environ과 config 모듈 속성에 즉시 반영해 실행 중인 서비스(naver_client)가 바로
사용하도록 한다.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from app import config

logger = logging.getLogger(__name__)

_KEYS_PATH = Path(config.APP_DATA_DIR) / "api_keys.json"
_MANAGED = ("NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET", "TOSS_CLIENT_ID", "TOSS_CLIENT_SECRET")
_TOSS_KEYS = ("TOSS_CLIENT_ID", "TOSS_CLIENT_SECRET")
# 원문 조회(raw=True, 수정 화면용)에도 돌려주지 않는 키. 토스 Secret은 실계정 거래 API
# 자격증명이라 화면에 다시 띄울 이유가 없다 — 바꿀 때는 새 값을 입력한다.
_NEVER_RAW = ("TOSS_CLIENT_SECRET",)


def _load() -> dict:
    if not _KEYS_PATH.exists():
        return {}
    try:
        with _KEYS_PATH.open(encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _save(keys: dict) -> None:
    _KEYS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _KEYS_PATH.open("w", encoding="utf-8") as fh:
        json.dump(keys, fh, ensure_ascii=False, indent=2)
    # 평문 API 키 파일이라 같은 기기의 다른 사용자 계정이 읽지 못하도록
    # 소유자만 읽고 쓸 수 있게 제한한다(Windows에서는 영향 없음, 무해).
    try:
        os.chmod(_KEYS_PATH, 0o600)
    except OSError:
        logger.warning("api_keys.json 권한 설정 실패", exc_info=True)


def _apply(key: str, value: str) -> None:
    """런타임 반영: 환경변수 + config 모듈 속성."""
    os.environ[key] = value
    if key in _MANAGED:
        setattr(config, key, value)


def load_to_runtime() -> None:
    """저장된 키를 기동 시 런타임에 적용한다."""
    if _KEYS_PATH.exists():
        # 이 보호가 생기기 전에 만들어진 파일은 권한이 더 느슨할 수 있어 기동 시 바로잡는다.
        try:
            os.chmod(_KEYS_PATH, 0o600)
        except OSError:
            logger.warning("api_keys.json 권한 설정 실패", exc_info=True)
    for key, value in _load().items():
        if value and not value.startswith("your_"):
            _apply(key, value)


def _mask(value: str) -> str:
    return value[:4] + "*" * max(0, len(value) - 4) if value else ""


def get_keys(raw: bool = False) -> dict:
    """저장/환경의 키를 마스킹(raw=False) 또는 원본(raw=True)으로 반환."""
    stored = _load()
    result: dict[str, str] = {}
    for key in _MANAGED:
        value = stored.get(key) or os.getenv(key, "") or ""
        if value and not value.startswith("your_"):
            result[key] = value if raw and key not in _NEVER_RAW else _mask(value)
        else:
            result[key] = ""
    return {
        "keys": result,
        "configured": {
            "naver": bool(result["NAVER_CLIENT_ID"] and result["NAVER_CLIENT_SECRET"]),
            "toss": bool(result["TOSS_CLIENT_ID"] and result["TOSS_CLIENT_SECRET"]),
        },
    }


def update_keys(data: dict) -> dict:
    """제공된 키만 갱신·저장·런타임 반영. 마스킹된 현황 반환."""
    keys = _load()
    toss_changed = False
    for key, value in data.items():
        if key in _MANAGED and value is not None:
            keys[key] = value
            if value and not value.startswith("your_"):
                _apply(key, value)
                toss_changed = toss_changed or key in _TOSS_KEYS
    _save(keys)
    if toss_changed:
        # 새 토스 키로 토큰을 다시 받고 실시간 연결을 처음부터 맺는다(앱 재시작 불필요).
        from app.services.realtime import realtime_manager
        from app.services.toss_client import toss_client
        toss_client.reset_token()
        realtime_manager.request_restart()
    return get_keys(raw=False)

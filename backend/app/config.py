"""환경변수(.env 포함)로부터 로드되는 애플리케이션 설정."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
PROJECT_ROOT = BASE_DIR.parent
DATA_DIR = BASE_DIR / "data"


def _resolve_path(value: str) -> str:
    """상대 경로를 프로젝트 루트 기준으로 고정 해석한다."""
    path = Path(value)
    return str(path if path.is_absolute() else (PROJECT_ROOT / path).resolve())


DATABASE_PATH = _resolve_path(os.getenv("DATABASE_PATH", str(DATA_DIR / "kgrowth_toss.db")))

# CORS: Vite 개발 서버 기본 포트. 쉼표 뒤 공백이 섞여도 Origin 매칭이 깨지지 않도록 trim한다.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]

# 토스증권 Open API 자격증명
TOSS_API_BASE_URL = os.getenv("TOSS_API_BASE_URL", "https://openapi.tossinvest.com")
TOSS_CLIENT_ID = os.getenv("TOSS_CLIENT_ID")
TOSS_CLIENT_SECRET = os.getenv("TOSS_CLIENT_SECRET")


def toss_credentials_configured() -> bool:
    """토스 API client_id/client_secret이 모두 설정되어 있으면 True."""
    return bool(TOSS_CLIENT_ID and TOSS_CLIENT_SECRET)

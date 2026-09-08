"""환경변수(.env 포함)로부터 로드되는 애플리케이션 설정."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent  # TOSS/backend/
PROJECT_ROOT = BASE_DIR.parent  # TOSS/ — DATABASE_PATH 같은 상대경로 해석 기준
REPO_ROOT = PROJECT_ROOT.parent  # 저장소 루트 — .env가 있는 곳
DATA_DIR = BASE_DIR / "data"

# 인자 없이 호출하면 이 파일 위치에서 상위로 올라가며 암묵적으로 .env를 탐색하는데,
# 폴더 구조가 한 단계 더 깊어져도(TOSS/backend/) 안 깨지도록 저장소 루트를 명시적으로 지정한다.
load_dotenv(REPO_ROOT / ".env")


def _resolve_path(value: str) -> str:
    """상대 경로를 PROJECT_ROOT(TOSS/) 기준으로 고정 해석한다."""
    path = Path(value)
    return str(path if path.is_absolute() else (PROJECT_ROOT / path).resolve())


DATABASE_PATH = _resolve_path(os.getenv("DATABASE_PATH", str(DATA_DIR / "kgrowth_toss.db")))

# CORS: Vite 개발 서버 기본 포트(5273 — K-Growth-Insights V2의 5173과 겹치지 않게 분리).
# 쉼표 뒤 공백이 섞여도 Origin 매칭이 깨지지 않도록 trim한다.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:5273,http://127.0.0.1:5273"
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

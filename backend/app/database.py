"""SQLite 연결/초기화."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from app.config import DATABASE_PATH


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """데이터 디렉터리를 생성하고 DB 파일 연결을 확인한다.

    실제 테이블 스키마는 카탈로그 수집 파이프라인 구현 시(마일스톤 4) 추가한다.
    """
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    conn.close()

"""공용 픽스처: 각 테스트를 격리된 임시 SQLite DB로 실행한다.

app.database.DATABASE_PATH를 임시 파일로 바꿔치기하여 실제 데이터에
영향을 주지 않고 collectors/repository/catalog/엔드포인트를 검증한다.
"""
import sqlite3

import pytest

from app import config, database
from app.services import realtime as realtime_module


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """테스트마다 새 임시 DB 파일을 생성하고 스키마를 초기화한다."""
    db_file = tmp_path / "test.db"
    monkeypatch.setattr(database, "DATABASE_PATH", str(db_file))
    database.init_db()
    yield db_file


@pytest.fixture(autouse=True)
def _no_real_realtime_connection(monkeypatch):
    """TestClient가 lifespan을 실행하더라도 실제 토스 WS에 접속하지 않게 막는다."""
    monkeypatch.setattr(realtime_module, "TOSS_CLIENT_ID", None)
    monkeypatch.setattr(realtime_module, "TOSS_CLIENT_SECRET", None)


@pytest.fixture(autouse=True)
def _api_key_disabled_by_default(monkeypatch):
    """개발자 로컬 .env에 실제 API_KEY가 설정돼 있어도 테스트는 항상 인증 비활성
    상태로 시작한다(그렇지 않으면 헤더를 안 보내는 다른 모든 테스트가 401로 깨진다).
    인증 켠 상태를 검증하는 테스트는 이 값을 개별적으로 monkeypatch한다."""
    monkeypatch.setattr(config, "API_KEY", None)


def seed_stock(ticker: str, name: str, type_: str = "STOCK", theme: str | None = None):
    """stocks 테이블에 종목 1건을 삽입하는 헬퍼."""
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO stocks (ticker, name, type, theme) VALUES (?, ?, ?, ?)",
            (ticker, name, type_, theme),
        )

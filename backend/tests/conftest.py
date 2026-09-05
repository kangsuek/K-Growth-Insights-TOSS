"""공용 픽스처: 각 테스트를 격리된 임시 SQLite DB로 실행한다.

app.database.DATABASE_PATH를 임시 파일로 바꿔치기하여 실제 데이터에
영향을 주지 않고 검증한다.
"""
import pytest

from app import database


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """테스트마다 새 임시 DB 파일을 생성하고 초기화한다."""
    db_file = tmp_path / "test.db"
    monkeypatch.setattr(database, "DATABASE_PATH", str(db_file))
    database.init_db()
    yield db_file

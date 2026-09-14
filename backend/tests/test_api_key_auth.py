"""공유 API 키 인증(선택) 테스트.

API_KEY 미설정(기본값)이면 완전히 비활성 상태로 기존과 동일하게 동작해야 한다 —
그 회귀 여부는 이 파일 자체보다도, 헤더 없이 요청하는 나머지 전체 테스트 스위트가
그대로 통과하는지로 증명된다.
"""
import pytest
from starlette.websockets import WebSocketDisconnect

from app import config
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_rest_succeeds_without_header_when_api_key_unset():
    assert config.API_KEY is None  # 기본값(테스트 환경에 API_KEY가 설정돼 있지 않음)
    resp = client.get("/api/etfs/")
    assert resp.status_code == 200


def test_rest_rejects_missing_or_wrong_key_when_enabled(monkeypatch):
    monkeypatch.setattr(config, "API_KEY", "secret123")

    resp_no_header = client.get("/api/etfs/")
    assert resp_no_header.status_code == 401

    resp_wrong = client.get("/api/etfs/", headers={"X-API-Key": "wrong"})
    assert resp_wrong.status_code == 401


def test_rest_succeeds_with_correct_key_when_enabled(monkeypatch):
    monkeypatch.setattr(config, "API_KEY", "secret123")
    resp = client.get("/api/etfs/", headers={"X-API-Key": "secret123"})
    assert resp.status_code == 200


def test_health_stays_open_even_when_api_key_enabled(monkeypatch):
    """/api/health는 모니터링용이라 인증 대상에서 의도적으로 제외했다."""
    monkeypatch.setattr(config, "API_KEY", "secret123")
    resp = client.get("/api/health")
    assert resp.status_code == 200


def test_ws_rejects_without_api_key_when_enabled(monkeypatch):
    monkeypatch.setattr(config, "API_KEY", "secret123")
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/realtime"):
            pass


def test_ws_accepts_with_correct_api_key_when_enabled(monkeypatch):
    monkeypatch.setattr(config, "API_KEY", "secret123")
    with client.websocket_connect("/ws/realtime?api_key=secret123"):
        pass  # 연결(accept)이 성공하면 이 블록에 들어온다 — 그 자체가 검증.

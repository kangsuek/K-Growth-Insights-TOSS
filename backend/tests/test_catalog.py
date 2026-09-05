import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response

from app.main import app
from app.services import toss_client as toss_client_module
from app.services.catalog import sync_catalog

BASE_URL = "https://openapi.tossinvest.com"

KOSPI_ITEMS = [
    {"symbol": "005930", "name": "삼성전자", "securityType": "STOCK", "isCommonShare": True, "isinCode": "KR7005930003"},
    {"symbol": "069500", "name": "KODEX 200", "securityType": "ETF", "isCommonShare": False, "isinCode": "KR7069500007"},
]
KOSDAQ_ITEMS = [
    {"symbol": "247540", "name": "에코프로비엠", "securityType": "STOCK", "isCommonShare": True, "isinCode": "KR7247540008"},
]


@pytest.fixture(autouse=True)
def _credentials(monkeypatch):
    monkeypatch.setattr(toss_client_module, "TOSS_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(toss_client_module, "TOSS_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setattr(toss_client_module, "TOSS_API_BASE_URL", BASE_URL)
    monkeypatch.setattr(toss_client_module, "MIN_REQUEST_INTERVAL_SECONDS", 0.0)
    # 모듈 전역 싱글턴 토큰 캐시가 테스트 간에 새지 않도록 초기화한다.
    monkeypatch.setattr(toss_client_module.toss_client, "_access_token", None)
    monkeypatch.setattr(toss_client_module.toss_client, "_expires_at", 0.0)


def _mock_catalog_endpoints(kospi=KOSPI_ITEMS, kosdaq=KOSDAQ_ITEMS):
    respx.post(f"{BASE_URL}/oauth2/token").mock(
        return_value=Response(200, json={"access_token": "tok1", "expires_in": 100})
    )
    respx.get(f"{BASE_URL}/api/v1/stocks/all", params={"market": "KOSPI"}).mock(
        return_value=Response(200, json={"result": kospi})
    )
    respx.get(f"{BASE_URL}/api/v1/stocks/all", params={"market": "KOSDAQ"}).mock(
        return_value=Response(200, json={"result": kosdaq})
    )


@respx.mock
async def test_sync_catalog_upserts_all_markets():
    _mock_catalog_endpoints()

    result = await sync_catalog()

    assert result["kospi_count"] == 2
    assert result["kosdaq_count"] == 1
    assert result["total_collected"] == 3
    assert result["removed_count"] == 0


@respx.mock
async def test_sync_catalog_prunes_stale_symbols():
    _mock_catalog_endpoints()
    await sync_catalog()

    respx.clear()
    # 두 번째 동기화에서는 KODEX 200이 더 이상 보이지 않는다 → 삭제되어야 한다.
    _mock_catalog_endpoints(kospi=[KOSPI_ITEMS[0]], kosdaq=KOSDAQ_ITEMS)

    result = await sync_catalog()

    assert result["removed_count"] == 1

    client = TestClient(app)
    response = client.get("/api/catalog", params={"q": "KODEX"})
    assert response.json()["total"] == 0


@respx.mock
async def test_list_catalog_filters_by_market_and_query():
    _mock_catalog_endpoints()
    await sync_catalog()

    client = TestClient(app)
    response = client.get("/api/catalog", params={"market": "KOSDAQ"})
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["symbol"] == "247540"

    response = client.get("/api/catalog", params={"q": "삼성"})
    assert response.json()["items"][0]["name"] == "삼성전자"

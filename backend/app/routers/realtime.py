"""실시간 시세 WebSocket 릴레이 + REST 조회 라우터.

quotes/trade_history는 원래 WS 연결이 있어야만 접근 가능했는데, curl/테스트 스크립트 등
일반 REST 클라이언트에서도 조회할 수 있도록 REST 엔드포인트를 함께 제공한다.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect

from app import config, security
from app.security import require_api_key
from app.services.realtime import realtime_manager

router = APIRouter()


@router.websocket("/ws/realtime")
async def realtime_ws(websocket: WebSocket, ticket: str | None = None) -> None:
    # 브라우저 네이티브 WebSocket은 커스텀 헤더를 못 붙이므로, 장기 비밀키 대신
    # 연결 직전 발급받은 1회용 티켓을 쿼리파라미터로 검사한다(app.security 참고).
    if config.API_KEY and not security.consume_ws_ticket(ticket):
        await websocket.close(code=1008)  # policy violation
        return
    await websocket.accept()
    realtime_manager.register(websocket)
    try:
        snapshot = realtime_manager.snapshot()
        if snapshot["trades"] or snapshot["quotes"]:
            await websocket.send_text(json.dumps({"type": "snapshot", "data": snapshot}))
        while True:
            # 클라이언트가 보내는 메시지는 쓰지 않지만, disconnect를 감지하려면 계속 대기해야 한다.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        realtime_manager.unregister(websocket)


@router.post("/api/realtime/ws-ticket", dependencies=[Depends(require_api_key)])
async def issue_ws_ticket() -> dict:
    """WS 연결용 1회용 단기 토큰 발급(연결 직전 호출). API_KEY 미설정이면 이 엔드포인트도
    인증 없이 열려 있지만, 그 상태에선 프론트가 애초에 이 엔드포인트를 호출하지 않는다."""
    return security.issue_ws_ticket()


@router.get("/api/realtime/quotes", dependencies=[Depends(require_api_key)])
async def get_quotes() -> dict:
    # realtime_manager는 이벤트 루프 위 백그라운드 태스크에서 quotes/trade_history를 계속
    # 변경한다. FastAPI는 동기 def 라우트를 별도 스레드풀에서 돌리는데, 그러면 이 딕셔너리를
    # 읽는 도중 다른 스레드(사실은 이벤트 루프 스레드)가 값을 바꿔 레이스가 날 수 있다.
    # async def로 두면 이 핸들러도 이벤트 루프에서만 실행되어(await 지점 전까지는 다른
    # 코루틴이 끼어들 수 없음) 안전하게 스냅샷을 뜰 수 있다.
    return dict(realtime_manager.quotes)


@router.get("/api/realtime/quotes/{symbol}", dependencies=[Depends(require_api_key)])
async def get_quote(symbol: str) -> dict:
    quote = realtime_manager.quotes.get(symbol)
    if quote is None:
        raise HTTPException(status_code=404, detail=f"아직 실시간 시세가 없는 symbol입니다: {symbol}")
    return dict(quote)


@router.get("/api/realtime/trades/{symbol}", dependencies=[Depends(require_api_key)])
async def get_trades(symbol: str, limit: int = Query(200, ge=1, le=200)) -> list[dict]:
    history = realtime_manager.trade_history.get(symbol)
    if not history:
        return []
    return list(history)[-limit:]

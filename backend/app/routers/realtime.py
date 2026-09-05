"""실시간 시세 WebSocket 릴레이 라우터."""
from __future__ import annotations

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.realtime import realtime_manager

router = APIRouter()


@router.websocket("/ws/realtime")
async def realtime_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    realtime_manager.register(websocket)
    try:
        if realtime_manager.latest_trades:
            await websocket.send_text(
                json.dumps({"type": "snapshot", "data": list(realtime_manager.latest_trades.values())})
            )
        while True:
            # 클라이언트가 보내는 메시지는 쓰지 않지만, disconnect를 감지하려면 계속 대기해야 한다.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        realtime_manager.unregister(websocket)

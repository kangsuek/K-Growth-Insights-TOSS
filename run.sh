#!/usr/bin/env bash
# K-Growth Insights TOSS — 프론트엔드(:5173)를 실행하고, Docker 백엔드(:8000)가
# 떠 있는지 확인합니다(없으면 기동). 백엔드는 웹앱과 데스크톱 앱이 공유하는 상시
# 서비스라 이 스크립트가 직접 관리하지 않는다 — 자세한 관리는 docker-backend.sh 참고.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT/.run"
LOG_DIR="$ROOT/logs"
FRONTEND_LOG_DIR="$LOG_DIR/frontend"
mkdir -p "$RUN_DIR" "$FRONTEND_LOG_DIR"

BACKEND_PORT=8000
FRONTEND_PORT=5173
HEALTH_URL="http://127.0.0.1:$BACKEND_PORT/api/health"

# 이미 실행 중이면 먼저 정리(프론트엔드만 — 백엔드는 그대로 둔다)
"$ROOT/stop.sh" >/dev/null 2>&1 || true

FRONTEND_LOG="$FRONTEND_LOG_DIR/frontend.log"

echo "▶ Docker 백엔드 확인"
if curl -sf "$HEALTH_URL" >/dev/null 2>&1; then
  echo "  ✔ 이미 실행 중 (:$BACKEND_PORT)"
else
  echo "  응답 없음 — 기동합니다"
  "$ROOT/docker-backend.sh" start
fi

echo "▶ 프론트엔드 시작 (:$FRONTEND_PORT)"
(
  cd "$ROOT/frontend"
  npm run dev -- --port "$FRONTEND_PORT"
) >"$FRONTEND_LOG" 2>&1 &
echo $! >"$RUN_DIR/frontend.pid"

echo ""
echo "✔ 실행 완료"
echo "  - 백엔드(Docker): http://localhost:$BACKEND_PORT   (관리: ./docker-backend.sh logs|stop)"
echo "  - 프론트엔드:      http://localhost:$FRONTEND_PORT   (로그: logs/frontend/frontend.log)"
echo ""
echo "종료하려면(프론트엔드만): ./stop.sh"

#!/usr/bin/env bash
# K-Growth Insights TOSS — 백엔드(:8000)와 프론트엔드(:5173)를 함께 실행합니다.
# 저장소 루트의 backend/, frontend/는 V2(K-Growth-Insights) 소스코드를 복사해
# 토스 API 실시간 기능을 이식한 앱이며, V2 원래 기본 포트를 그대로 쓴다.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT/.run"
LOG_DIR="$ROOT/logs"
BACKEND_LOG_DIR="$LOG_DIR/backend"
FRONTEND_LOG_DIR="$LOG_DIR/frontend"
mkdir -p "$RUN_DIR" "$BACKEND_LOG_DIR" "$FRONTEND_LOG_DIR"

BACKEND_PORT=8000
FRONTEND_PORT=5173
# 기본은 이 기기에서만 접근 가능한 127.0.0.1. 이 앱은 API에 인증이 없어서,
# 0.0.0.0으로 띄우면 같은 네트워크의 누구나 데이터를 읽고 쓸 수 있다.
# 같은 네트워크의 다른 기기(휴대폰 등)에서 테스트해야 할 때만
# `BACKEND_HOST=0.0.0.0 ./run.sh`처럼 명시적으로 켠다.
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"

# 이미 실행 중이면 먼저 정리
"$ROOT/stop.sh" >/dev/null 2>&1 || true

BACKEND_LOG="$BACKEND_LOG_DIR/backend.log"
FRONTEND_LOG="$FRONTEND_LOG_DIR/frontend.log"

if [ "$BACKEND_HOST" != "127.0.0.1" ]; then
  echo "⚠ 백엔드를 $BACKEND_HOST 로 띄웁니다 — 인증이 없는 API라 같은 네트워크의 누구나 접근할 수 있습니다."
fi

echo "▶ 백엔드 시작 (:$BACKEND_PORT)"
(
  cd "$ROOT/backend"
  uv run uvicorn app.main:app --reload --host "$BACKEND_HOST" --port "$BACKEND_PORT"
) >"$BACKEND_LOG" 2>&1 &
echo $! >"$RUN_DIR/backend.pid"

echo "▶ 프론트엔드 시작 (:$FRONTEND_PORT)"
(
  cd "$ROOT/frontend"
  npm run dev -- --port "$FRONTEND_PORT"
) >"$FRONTEND_LOG" 2>&1 &
echo $! >"$RUN_DIR/frontend.pid"

echo ""
echo "✔ 실행 완료"
echo "  - 백엔드:    http://localhost:$BACKEND_PORT   (로그: logs/backend/backend.log)"
echo "  - 프론트엔드: http://localhost:$FRONTEND_PORT   (로그: logs/frontend/frontend.log)"
echo ""
echo "로그 실시간 보기: tail -f logs/backend/backend.log"
echo "종료하려면:       ./stop.sh"

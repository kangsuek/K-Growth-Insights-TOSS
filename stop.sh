#!/usr/bin/env bash
# K-Growth Insights TOSS — 백엔드/프론트엔드 프로세스를 종료합니다.
# 실제 V2 원본 프로젝트도 동일한 "uvicorn app.main:app"/"vite" 명령을 쓰므로,
# 이 프로젝트의 포트 번호가 포함된 프로세스만 종료해 다른 프로젝트에 영향을 주지 않는다.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT/.run"

BACKEND_PORT=8000
FRONTEND_PORT=5173

killed=0

for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
  pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
  if [ -n "$pids" ]; then
    echo "▶ :$port 포트 프로세스 종료: $pids"
    kill $pids 2>/dev/null || true
    killed=1
  fi
done

pkill -f "uvicorn app.main:app.*--port $BACKEND_PORT" 2>/dev/null && killed=1 || true
pkill -f "vite.*--port $FRONTEND_PORT" 2>/dev/null && killed=1 || true

rm -f "$RUN_DIR/backend.pid" "$RUN_DIR/frontend.pid" 2>/dev/null || true

if [ "$killed" -eq 1 ]; then
  echo "✔ 모든 백엔드/프론트엔드 프로세스를 종료했습니다."
else
  echo "실행 중인 백엔드/프론트엔드 프로세스가 없습니다."
fi

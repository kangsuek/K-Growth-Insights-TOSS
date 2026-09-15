#!/usr/bin/env bash
# K-Growth Insights TOSS — 프론트엔드 프로세스를 종료합니다.
# 백엔드는 웹앱과 데스크톱 앱이 공유하는 Docker 상시 서비스라 이 스크립트가 건드리지
# 않는다(잘못 죽이면 docker-proxy까지 종료될 수 있음) — 끄려면 ./docker-backend.sh stop.
# 실제 V2 원본 프로젝트도 동일한 "vite" 명령을 쓰므로, 이 프로젝트의 포트 번호가
# 포함된 프로세스만 종료해 다른 프로젝트에 영향을 주지 않는다.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT/.run"

FRONTEND_PORT=5173

killed=0

pids="$(lsof -ti tcp:"$FRONTEND_PORT" 2>/dev/null || true)"
if [ -n "$pids" ]; then
  echo "▶ :$FRONTEND_PORT 포트 프로세스 종료: $pids"
  kill $pids 2>/dev/null || true
  killed=1
fi

pkill -f "vite.*--port $FRONTEND_PORT" 2>/dev/null && killed=1 || true

rm -f "$RUN_DIR/frontend.pid" 2>/dev/null || true

if [ "$killed" -eq 1 ]; then
  echo "✔ 프론트엔드 프로세스를 종료했습니다."
else
  echo "실행 중인 프론트엔드 프로세스가 없습니다."
fi

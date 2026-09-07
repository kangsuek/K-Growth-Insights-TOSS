#!/usr/bin/env bash
# K-Growth Insights TOSS — 모든 백엔드/프론트엔드 프로세스를 종료합니다.
# K-Growth-Insights(V2)도 동일한 "uvicorn app.main:app"/"vite" 명령을 쓰므로,
# 다른 경로(V2)의 프로세스까지 죽이지 않도록 이 프로젝트 경로가 포함된 프로세스만 종료한다.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT/.run"

BACKEND_PORT=8100
FRONTEND_PORT=5273

killed=0

# 포트를 점유한 프로세스 종료 (가장 확실한 방법)
for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
  pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
  if [ -n "$pids" ]; then
    echo "▶ :$port 포트 프로세스 종료: $pids"
    kill $pids 2>/dev/null || true
    killed=1
  fi
done

# 이름으로 남은 프로세스 정리(reload 워커 등) — 커맨드라인에 이 프로젝트 포트 번호가
# 포함된 것만 대상으로 해 V2(다른 포트)의 동일한 이름 프로세스는 건드리지 않는다.
pkill -f "uvicorn app.main:app.*--port $BACKEND_PORT" 2>/dev/null && killed=1 || true
pkill -f "vite.*--port $FRONTEND_PORT" 2>/dev/null && killed=1 || true

# PID 파일 정리
rm -f "$RUN_DIR/backend.pid" "$RUN_DIR/frontend.pid" 2>/dev/null || true

if [ "$killed" -eq 1 ]; then
  echo "✔ 모든 백엔드/프론트엔드 프로세스를 종료했습니다."
else
  echo "실행 중인 백엔드/프론트엔드 프로세스가 없습니다."
fi

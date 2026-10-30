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
# 기본은 이 기기에서만 접근 가능한 127.0.0.1. 이 앱은 기본적으로 API 인증이 없어서,
# 0.0.0.0으로 띄우면 같은 네트워크의 누구나 데이터를 읽고 쓸 수 있다.
# 같은 네트워크의 다른 기기(휴대폰 등)에서 테스트해야 할 때만
# `BACKEND_HOST=0.0.0.0 ./run.sh`처럼 명시적으로 켠다.
# 터널/클라우드로 외부에 노출하려면 .env에 API_KEY를 설정해 인증을 켜고(선택,
# .env.example 참고), 프론트엔드 VITE_API_KEY도 같은 값으로 맞춘다.
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"

# 이미 실행 중이면 먼저 정리
"$ROOT/stop.sh" >/dev/null 2>&1 || true

BACKEND_LOG="$BACKEND_LOG_DIR/backend.log"
FRONTEND_LOG="$FRONTEND_LOG_DIR/frontend.log"

if [ "$BACKEND_HOST" != "127.0.0.1" ]; then
  echo "⚠ 백엔드를 $BACKEND_HOST 로 띄웁니다 — .env에 API_KEY를 설정하지 않았다면 같은 네트워크의 누구나 접근할 수 있습니다."
fi

# --- 사전 점검: 필요한 도구와 의존성이 없으면 설치한다 ---
INSTALL_LOG="$LOG_DIR/install.log"
: >"$INSTALL_LOG"

# uv 기본 설치 위치(~/.local/bin)가 PATH에 없는 셸에서도 찾을 수 있게 한다.
if ! command -v uv >/dev/null 2>&1; then
  export PATH="$HOME/.local/bin:$PATH"
fi
if ! command -v uv >/dev/null 2>&1; then
  echo "✖ uv가 설치되어 있지 않습니다. 설치 후 다시 실행하세요: brew install uv" >&2
  echo "  (또는 https://docs.astral.sh/uv/getting-started/installation/ 참고)" >&2
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "✖ node/npm이 설치되어 있지 않습니다. Node.js를 설치한 뒤 다시 실행하세요." >&2
  exit 1
fi

# 대상 디렉터리가 없거나, 의존성 명세 파일이 설치 결과보다 새로우면 설치가 필요하다.
needs_install() {
  local marker="$1"; shift
  [ ! -e "$marker" ] && return 0
  local spec
  for spec in "$@"; do
    [ "$spec" -nt "$marker" ] && return 0
  done
  return 1
}

if needs_install "$ROOT/backend/.venv" "$ROOT/backend/pyproject.toml" "$ROOT/backend/uv.lock"; then
  echo "▶ 백엔드 의존성 설치 (uv sync) — 로그: logs/install.log"
  (cd "$ROOT/backend" && uv sync --extra dev) >>"$INSTALL_LOG" 2>&1 || {
    echo "✖ 백엔드 의존성 설치 실패 — logs/install.log 확인" >&2; exit 1; }
  touch "$ROOT/backend/.venv"
fi
if needs_install "$ROOT/frontend/node_modules" "$ROOT/frontend/package.json" "$ROOT/frontend/package-lock.json"; then
  echo "▶ 프론트엔드 의존성 설치 (npm install) — 로그: logs/install.log"
  (cd "$ROOT/frontend" && npm install) >>"$INSTALL_LOG" 2>&1 || {
    echo "✖ 프론트엔드 의존성 설치 실패 — logs/install.log 확인" >&2; exit 1; }
  touch "$ROOT/frontend/node_modules"
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

# 기동 확인: 프로세스가 곧바로 죽었는데 "실행 완료"로 끝나는 일을 막는다.
echo "▶ 기동 확인 중..."
ok=0
for _ in $(seq 1 60); do
  if curl -fs "http://127.0.0.1:$BACKEND_PORT/api/health" >/dev/null 2>&1 \
     && curl -fs -o /dev/null "http://127.0.0.1:$FRONTEND_PORT" 2>&1; then
    ok=1; break
  fi
  sleep 1
done
if [ "$ok" -ne 1 ]; then
  echo "✖ 60초 안에 서버가 응답하지 않았습니다. 로그를 확인하세요." >&2
  echo "--- backend.log (tail) ---" >&2; tail -n 15 "$BACKEND_LOG" >&2 || true
  echo "--- frontend.log (tail) ---" >&2; tail -n 15 "$FRONTEND_LOG" >&2 || true
  exit 1
fi

echo ""
echo "✔ 실행 완료"
echo "  - 백엔드:    http://localhost:$BACKEND_PORT   (로그: logs/backend/backend.log)"
echo "  - 프론트엔드: http://localhost:$FRONTEND_PORT   (로그: logs/frontend/frontend.log)"
echo ""
echo "로그 실시간 보기: tail -f logs/backend/backend.log"
echo "종료하려면:       ./stop.sh"

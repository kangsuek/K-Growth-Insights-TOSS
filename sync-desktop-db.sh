#!/usr/bin/env bash
# K-Growth Insights TOSS — 설치된 데스크톱 앱의 kgrowth.db를 개발 환경
# (backend/data/kgrowth.db)으로 가져옵니다. 반대 방향(개발 DB를 앱에 넣기)은
# 이 스크립트의 범위가 아니다 — 필요하면 직접 cp 하세요.
#
# 사용법:
#   ./sync-desktop-db.sh
set -euo pipefail
trap 'echo "" >&2; echo "✘ 실패 (sync-desktop-db.sh:${LINENO})" >&2' ERR

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEV_DATA_DIR="$ROOT/backend/data"
DEV_DB="$DEV_DATA_DIR/kgrowth.db"
APP_SUPPORT="$HOME/Library/Application Support/kgrowth-insights-toss-desktop"
APP_DB="$APP_SUPPORT/data/kgrowth.db"

echo "=== 데스크톱 앱 DB → 개발 환경 DB 동기화 ==="
echo "  원본(설치된 앱): $APP_DB"
echo "  대상(개발 환경): $DEV_DB"
echo ""

# ── 0. 사전 확인 ──────────────────────────────────────────────────────────
if [ ! -f "$APP_DB" ]; then
  echo "ERROR: 설치된 앱의 DB가 없습니다: $APP_DB" >&2
  echo "  앱을 한 번 이상 실행했는지 확인하세요." >&2
  exit 1
fi

if pgrep -f "K-Growth Insights TOSS.app" >/dev/null 2>&1; then
  echo "⚠ 데스크톱 앱이 실행 중입니다 — DB가 WAL 모드로 열려 있으면 최근 변경분이"
  echo "  아직 -wal 파일에만 있어 그대로 복사 시 누락될 수 있습니다."
  read -r -p "  앱을 종료하지 않고 계속할까요? [y/N] " ans
  case "$ans" in
    y|Y) ;;
    *) echo "취소했습니다. 앱을 종료한 뒤 다시 실행하세요."; exit 1 ;;
  esac
fi

if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "ERROR: 백엔드(포트 8000)가 실행 중입니다. ./docker-backend.sh stop 으로 먼저 종료하세요." >&2
  exit 1
fi

# ── 1. 백업 ───────────────────────────────────────────────────────────────
mkdir -p "$DEV_DATA_DIR/backup"
if [ -f "$DEV_DB" ]; then
  TS="$(date +%Y%m%d_%H%M%S)"
  BACKUP="$DEV_DATA_DIR/backup/kgrowth.db.bak_${TS}"
  cp "$DEV_DB" "$BACKUP"
  echo "▶ 기존 개발 DB 백업: $BACKUP"
fi

# ── 2. 복사 ───────────────────────────────────────────────────────────────
echo "▶ 앱 DB → 개발 DB 복사"
cp "$APP_DB" "$DEV_DB"
rm -f "$DEV_DB-wal" "$DEV_DB-shm"

# ── 3. 무결성 검증 ────────────────────────────────────────────────────────
echo "▶ 무결성 검사"
command -v sqlite3 >/dev/null 2>&1 || { echo "ERROR: sqlite3 명령이 없습니다." >&2; exit 1; }
RESULT="$(sqlite3 "$DEV_DB" "PRAGMA integrity_check;")"
if [ "$RESULT" != "ok" ]; then
  echo "ERROR: 무결성 검사 실패: $RESULT" >&2
  exit 1
fi
echo "  ✔ ok"

echo ""
echo "=== 완료 ==="
echo "  $(du -h "$DEV_DB" | cut -f1 | tr -d ' ')  $DEV_DB"
echo "  ./run.sh 로 개발 서버를 다시 시작하면 앱의 최신 데이터로 확인할 수 있습니다."

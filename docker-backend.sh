#!/usr/bin/env bash
# K-Growth Insights TOSS — Docker Desktop에서 백엔드 컨테이너를 관리합니다.
# 웹앱(run.sh)과 데스크톱 앱이 공유하는 상시 백엔드라, run.sh/stop.sh와 별개로
# 이 스크립트로 직접 켜고 끈다.
#
# 사용법:
#   ./docker-backend.sh start     # 빌드 후 백그라운드로 기동 + 헬스체크 대기
#   ./docker-backend.sh stop      # 종료
#   ./docker-backend.sh restart   # 재빌드 후 재기동
#   ./docker-backend.sh logs      # 로그 실시간 보기
#   ./docker-backend.sh status    # 헬스체크 결과만 확인
set -euo pipefail
trap 'echo "" >&2; echo "✘ 실패 (docker-backend.sh:${LINENO})" >&2' ERR

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

HEALTH_URL="http://127.0.0.1:8000/api/health"
HEALTH_TIMEOUT_S=60

require_docker() {
  command -v docker >/dev/null 2>&1 || {
    echo "ERROR: 'docker' 명령이 없습니다. Docker Desktop을 설치한 뒤 다시 실행하세요." >&2
    exit 1
  }
  docker info >/dev/null 2>&1 || {
    echo "ERROR: Docker 데몬에 연결할 수 없습니다. Docker Desktop을 실행한 뒤 다시 시도하세요." >&2
    exit 1
  }
}

wait_for_health() {
  echo "▶ 헬스체크 대기 ($HEALTH_URL)"
  local start
  start="$(date +%s)"
  while true; do
    if curl -sf "$HEALTH_URL" >/dev/null 2>&1; then
      echo "  ✔ 백엔드 준비됨"
      return 0
    fi
    if [ "$(( $(date +%s) - start ))" -ge "$HEALTH_TIMEOUT_S" ]; then
      echo "ERROR: ${HEALTH_TIMEOUT_S}초 안에 백엔드가 응답하지 않았습니다. 'docker compose logs backend'로 확인하세요." >&2
      return 1
    fi
    sleep 1
  done
}

cmd="${1:-start}"

case "$cmd" in
  start)
    require_docker
    echo "▶ Docker 백엔드 빌드/기동"
    docker compose up -d --build backend
    wait_for_health
    echo ""
    echo "=== 완료 ==="
    echo "  백엔드: http://localhost:8000"
    echo "  로그:   ./docker-backend.sh logs"
    echo "  종료:   ./docker-backend.sh stop"
    ;;
  stop)
    require_docker
    echo "▶ Docker 백엔드 종료"
    docker compose stop backend
    ;;
  restart)
    require_docker
    echo "▶ Docker 백엔드 재빌드/재기동"
    docker compose up -d --build backend
    wait_for_health
    ;;
  logs)
    require_docker
    docker compose logs -f backend
    ;;
  status)
    if curl -sf "$HEALTH_URL" >/dev/null 2>&1; then
      echo "✔ 백엔드 정상 응답: $HEALTH_URL"
    else
      echo "✘ 백엔드가 응답하지 않습니다: $HEALTH_URL"
      exit 1
    fi
    ;;
  *)
    echo "사용법: $0 {start|stop|restart|logs|status}" >&2
    exit 2
    ;;
esac

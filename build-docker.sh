#!/usr/bin/env bash
# K-Growth Insights TOSS — 백엔드 Docker 이미지를 빌드합니다.
#
# 사용법:
#   ./build-docker.sh                                  # 기본 태그(kgrowth-backend:latest)
#   ./build-docker.sh --tag myrepo/kgrowth-backend:0.1.0
#   ./build-docker.sh --skip-tests                     # 테스트 없이 빌드(빠름, 배포용으로는 비권장)
set -euo pipefail
trap 'echo "" >&2; echo "✘ 빌드 실패 (build-docker.sh:${LINENO})" >&2' ERR

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"

TAG="kgrowth-backend:latest"
RUN_TESTS=1

while [ $# -gt 0 ]; do
  case "$1" in
    --tag) TAG="${2:-}"; shift 2 ;;
    --skip-tests) RUN_TESTS=0; shift ;;
    -h|--help) sed -n '2,7p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "알 수 없는 옵션: $1 (--help 참고)" >&2; exit 2 ;;
  esac
done

echo "=== K-Growth Insights TOSS 백엔드 Docker 이미지 빌드 ==="
echo "  프로젝트: $ROOT"
echo "  태그: $TAG"
echo ""

# ── 0. 사전 확인 ──────────────────────────────────────────────────────────
command -v docker >/dev/null 2>&1 || {
  echo "ERROR: 'docker' 가 없습니다. Docker Desktop(또는 colima 등)을 설치한 뒤 다시 실행하세요." >&2
  exit 1
}
docker info >/dev/null 2>&1 || {
  echo "ERROR: Docker 데몬에 연결할 수 없습니다. Docker Desktop을 실행한 뒤 다시 시도하세요." >&2
  exit 1
}

# ── 1. 테스트 ─────────────────────────────────────────────────────────────
# 이미지에 굽기 전에 실패를 잡는다 — 컨테이너로 배포한 뒤에야 버그를 발견하는 것보다 낫다.
if [ "$RUN_TESTS" -eq 1 ]; then
  echo "▶ 백엔드 테스트 (--skip-tests 로 생략 가능)"
  (cd "$BACKEND" && uv sync --extra dev --quiet && uv run pytest -q)
fi

# ── 2. 이미지 빌드 ────────────────────────────────────────────────────────
# 빌드 컨텍스트는 backend/ 디렉터리(Dockerfile·.dockerignore가 여기 있음).
echo "▶ Docker 이미지 빌드"
docker build -t "$TAG" "$BACKEND"

# ── 3. 검증 ───────────────────────────────────────────────────────────────
echo ""
echo "▶ 이미지 확인"
SIZE="$(docker image inspect "$TAG" --format '{{.Size}}' | awk '{printf "%.0f MB", $1/1024/1024}')"
echo "  ✔ $TAG  ($SIZE)"

echo ""
echo "=== 빌드 완료 ==="
echo "  이미지: $TAG"
echo ""
echo "  실행 예시:"
echo "    docker run --rm -p 8000:8000 \\"
echo "      -e TOSS_CLIENT_ID=<값> -e TOSS_CLIENT_SECRET=<값> -e API_KEY=<값> \\"
echo "      -v kgrowth-data:/data $TAG"
echo ""
echo "  확인:"
echo "    curl http://localhost:8000/api/health"
echo ""
echo "  레지스트리에 올리려면:"
echo "    docker tag $TAG <registry>/<repo>:<태그>"
echo "    docker push <registry>/<repo>:<태그>"

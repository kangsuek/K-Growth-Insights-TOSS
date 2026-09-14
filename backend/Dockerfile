FROM python:3.11-slim-bookworm

# uv 공식 배포 바이너리를 그대로 복사(빌드 도구 설치 없이 재현 가능한 설치)
COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /uvx /usr/local/bin/

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# 의존성 레이어를 코드 레이어보다 먼저 캐시(코드만 바뀌면 재설치 안 함)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 런타임에 필요한 코드/자산만 복사(.dockerignore가 data/·.venv/·tests/ 등을 제외)
COPY app ./app
COPY config ./config
COPY prompt ./prompt
RUN uv sync --frozen --no-dev

RUN useradd -m -u 1000 appuser \
 && mkdir -p /data \
 && chown -R appuser:appuser /app /data
USER appuser

ENV PATH="/app/.venv/bin:$PATH" \
    DATABASE_PATH=/data/kgrowth.db \
    STOCKS_CONFIG_PATH=/app/config/stocks.json

VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/api/health', timeout=3)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

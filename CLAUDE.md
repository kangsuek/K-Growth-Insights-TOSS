# CLAUDE.md

이 파일은 Claude Code가 이 저장소에서 작업할 때 참고하는 가이드입니다.

## 프로젝트

한국 ETF·주식 분석 앱. K-Growth-Insights(V2, 네이버 API 단일 소스)와 별개의 새 프로젝트로,
**토스증권 Open API를 주 데이터 소스**로 사용한다. V2 폴더는 읽기 참고만 하고 절대 수정하지 않는다.
킥오프 배경·데이터 소스 분담 전체 표는 [KICKOFF_PROMPT.md](./KICKOFF_PROMPT.md) 참고.

## 저장소 구조 (2026-09-08 변경)

이 저장소에는 서로 다른 두 앱이 공존한다.

- **`TOSS/backend`, `TOSS/frontend`** — 토스 API 기반으로 새로 개발 중인 앱(위 "프로젝트" 설명 대상).
  포트 `:8100`/`:5273`, `./run.sh`/`./stop.sh`.
- **루트 `backend/`, `frontend/`** — V2(`K-Growth-Insights`) 소스코드를 그대로 복사해 온 사본.
  원본 V2 폴더는 절대 수정하지 않는다는 규칙에 따라, 필요한 기능을 이 저장소 안에서 독립적으로
  돌리기 위해 통째로 복사했다. V2 원래 기본 포트 `:8000`/`:5173` 그대로 쓰며, `./run-v2.sh`/
  `./stop-v2.sh`로 기동/종료한다. 공유 `.env`는 두 앱이 쓰는 키가 겹치지 않아 그대로 둬도 충돌 없다.
  **계획**: 이 V2 사본이 정상 동작을 확인되면, 이후 단계로 토스 API 기반 기능(실시간 시세 등)을
  이 사본 쪽으로 이식할 예정 — 즉 장기적으로는 `TOSS/` 대신 이 루트 앱이 주력이 될 수 있다. V2
  자체 CI/랜딩페이지(`.github/`, `site/`, `justfile`)는 "기능이 정상 동작"과 무관해 복사하지
  않았다.
- **`desktop/`, `build-dmg.sh`(2026-09-09 추가)** — 루트 `backend/`+`frontend/`를 macOS 데스크톱
  앱(dmg)으로 패키징하는 Electron 셸. V2의 `desktop/`을 이식하되, 나중에 같은 Mac에 V2 실제
  데스크톱 앱을 설치해도 서로 덮어쓰지 않도록 식별자를 분리했다: appId
  `com.kgrowth.insights.toss`(V2는 `com.kgrowth.insights`), productName
  `K-Growth Insights TOSS`(V2는 `K-Growth Insights`), Electron 내부 백엔드 포트 `18100`(V2는
  `18000`). `./build-dmg.sh --arch arm64|x64|both`로 빌드하며, 산출물은 `desktop/release/`
  (gitignore 대상, 커밋 안 됨).

## 데이터 소스 분담

- **토스**: 종목 기본정보/카탈로그, 실시간 시세(WebSocket), 현재가 REST, 호가, 캔들, 투자자별 매매동향
- **네이버 유지**: 펀더멘털(PER/PBR/EPS/BPS/배당/52주), ETF NAV/괴리율/총보수/구성종목, 뉴스, 시장 지수(코스피/코스닥)
- 공매도 데이터는 범위 제외

## 스택

- 백엔드: **uv** + FastAPI + **SQLite 전용** (`TOSS/backend/`)
- 프론트엔드: **npm** + React + Vite + recharts + TanStack Query (`TOSS/frontend/`)

## 명령어

```bash
cd TOSS/backend && uv sync --extra dev              # 백엔드 의존성 설치
cd TOSS/backend && uv run pytest -q                 # 백엔드 테스트 전체
cd TOSS/backend && uv run uvicorn app.main:app --reload --port 8100  # API(:8100)

cd TOSS/frontend && npm install                     # 프론트 의존성 설치
cd TOSS/frontend && npm run dev                      # Vite 개발 서버(:5273)
```

포트는 K-Growth-Insights(V2, :8000/:5173)와 겹치지 않도록 :8100/:5273으로 분리했다(`./run.sh`/`./stop.sh` 사용 권장).

## 아키텍처 (현재)

```
FastAPI (TOSS/backend/app) ──/api──▶ React+Vite (TOSS/frontend/src)
  services/toss_client.py — 토스 Open API 인증(OAuth2 client_credentials, 토큰 캐싱) + GET 헬퍼
  database.py — SQLite 연결/초기화(스키마는 카탈로그 구현 시 추가)
```

라우터/서비스는 마일스톤 단위로 늘어난다. 현재는 `/health`만 존재.

## 작업 규칙

- **주석·커밋 메시지는 한글로 작성한다.** (conventional-commits 접두사는 영어 유지)
- 사용자에게 보여지는 모든 숫자는 천 단위 구분 기호를 사용한다(`toLocaleString('ko-KR')`).
- 백엔드는 **실제 사용하는 엔드포인트만** 유지한다. 미사용 라우트·래퍼는 만들지 않는다.
- **기능 개선/버그 수정은 소스 수정 전 Plan Mode로 계획하고 승인받는다.** 단순 조회성 질문에는 적용하지 않는다.
- **큰 작업은 마일스톤 단위로 쪼갠다.** 구현 → 실제 동작 검증 → 사용자 확인 → 다음 단계.
- **기능 수정 후에는 유닛테스트만으로 끝내지 않고 실제 화면을 띄워 검증한다.** 브라우저 자동화는 Playwright(Electron이면 `_electron`)를 쓰고 osascript는 쓰지 않는다.
- 검증이 끝나면 diff를 리뷰한 뒤 승인 없이 바로 commit + push한다. 단, force push·destructive 작업·민감정보 포함 가능성이 있는 커밋은 예외로 반드시 확인받는다.
- **K-Growth-Insights(V2) 폴더는 절대 수정하지 않는다.** 필요한 로직은 복사해서 이 저장소에 새로 작성한다.
- 커밋 메시지 끝에 다음을 추가한다:
  `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`

## 범위 (현재)

백엔드/프론트엔드 기본 골격 + 토스 OAuth2 인증 클라이언트(`toss_client.py`)까지 구현 완료.

다음: `GET /api/v1/stocks/all` 카탈로그 수집 파이프라인(네이버 카탈로그 수집 대체) → 캔들/실시간 WS/매매동향 순으로 확장 예정.

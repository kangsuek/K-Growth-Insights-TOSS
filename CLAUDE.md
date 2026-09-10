# CLAUDE.md

이 파일은 Claude Code가 이 저장소에서 작업할 때 참고하는 가이드입니다.

## 프로젝트

한국 ETF·주식 분석 앱. K-Growth-Insights(V2, 네이버 API 단일 소스)와 별개의 새 프로젝트로,
**토스증권 Open API를 주 데이터 소스**로 사용한다. V2 폴더는 읽기 참고만 하고 절대 수정하지 않는다.
킥오프 배경·데이터 소스 분담 전체 표는 [KICKOFF_PROMPT.md](./KICKOFF_PROMPT.md) 참고.

## 저장소 구조 (2026-09-10 변경)

- **`backend/`, `frontend/`** — 이 저장소의 유일한 앱. V2(`K-Growth-Insights`) 소스코드를 그대로
  복사해 온 뒤(원본 V2 폴더는 절대 수정하지 않는다는 규칙에 따라 복사해서 독립적으로 발전시킴),
  대시보드/ETF상세/포트폴리오/알림 등 전역에 **토스증권 Open API 실시간 시세**를 이식해 주력
  앱이 됐다. V2 원래 기본 포트 `:8000`/`:5173`을 그대로 쓰며, `./run.sh`/`./stop.sh`로 기동/종료한다.
  V2 자체 CI/랜딩페이지(`.github/`, `site/`, `justfile`)는 복사하지 않았다.
  (한때 별도로 `TOSS/backend`, `TOSS/frontend`라는 초기 스캐폴딩이 공존했으나, 실제 기능은 전부
  이 루트 앱 쪽으로 이식이 끝나 2026-09-10 삭제했다 — 더 이상 참고할 필요 없음.)
- **`desktop/`, `build-dmg.sh`** — 루트 `backend/`+`frontend/`를 macOS 데스크톱 앱(dmg)으로
  패키징하는 Electron 셸. V2의 `desktop/`을 이식하되, 나중에 같은 Mac에 V2 실제 데스크톱 앱을
  설치해도 서로 덮어쓰지 않도록 식별자를 분리했다: appId `com.kgrowth.insights.toss`(V2는
  `com.kgrowth.insights`), productName `K-Growth Insights TOSS`(V2는 `K-Growth Insights`),
  Electron 내부 백엔드 포트 `18100`(V2는 `18000`). `./build-dmg.sh --arch arm64|x64|both`로
  빌드하며, 산출물은 `desktop/release/`(gitignore 대상, 커밋 안 됨).

## 데이터 소스 분담

- **토스**: 종목 기본정보/카탈로그, 실시간 시세(WebSocket), 현재가 REST, 호가, 캔들, 투자자별 매매동향
- **네이버 유지**: 펀더멘털(PER/PBR/EPS/BPS/배당/52주), ETF NAV/괴리율/총보수/구성종목, 뉴스, 시장 지수(코스피/코스닥)
- 공매도 데이터는 범위 제외

## 스택

- 백엔드: **uv** + FastAPI + **SQLite 전용** (`backend/`)
- 프론트엔드: **npm** + React + Vite + recharts + TanStack Query (`frontend/`)

## 명령어

```bash
cd backend && uv sync --extra dev                   # 백엔드 의존성 설치
cd backend && uv run pytest -q                       # 백엔드 테스트 전체
cd backend && uv run uvicorn app.main:app --reload --port 8000  # API(:8000)

cd frontend && npm install                           # 프론트 의존성 설치
cd frontend && npm run dev                            # Vite 개발 서버(:5173)
```

백엔드+프론트엔드를 한 번에 띄우려면 루트의 `./run.sh`(종료는 `./stop.sh`)를 쓴다.

## 아키텍처 (현재)

```
FastAPI (backend/app) ──/api──▶ React+Vite (frontend/src)
  routers/    — etfs, market, scanner, simulation, alerts, settings, news, realtime, data
  services/
    toss_client.py — 토스 Open API 인증(OAuth2 client_credentials, 토큰 캐싱) + REST/WS 헬퍼
    realtime.py     — TossRealtimeManager: WS 구독·체결 브로드캐스트·실시간 목표가 알림 트리거
    naver_client.py — 펀더멘털/뉴스/지수 등 네이버 유지 데이터
    alerts.py, scanner.py, simulation.py, scheduler.py, repository.py 등
```

프론트엔드는 대시보드/ETF상세/포트폴리오/스캐너/비교/시뮬레이션/알림/설정 8개 페이지로 구성되며,
`useRealtimeMarket()` 훅(WS 기반, 3초 렌더 주기)을 대시보드·ETF상세·포트폴리오·알림 등에서 공유해
확정 배치 시세를 라이브 시세로 우선 대체하는 패턴을 쓴다.

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

V2 전체 기능(대시보드/ETF상세/포트폴리오/스캐너/비교/시뮬레이션/알림/설정) 위에 토스 실시간 시세를
순차 이식 완료: 시장 현황(코스피/코스닥), 오늘의 가격 흐름, ETF 상세 주요 구성자산·최근 가격 정보,
포트폴리오 평가금액/비중/기여도, 목표가 알림(WS 체결 기반 즉시 트리거, 폴백으로 분봉 1분 주기 유지)까지
3초 주기로 실시간 갱신된다. macOS 데스크톱 앱(dmg) 패키징도 완료.

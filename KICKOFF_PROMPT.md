# K-Growth Insights TOSS 개발 시작

## 배경

K-Growth-Insights(V2, `/Users/kangsuek/pythonProject/K-Growth-Insights`)는 네이버 모바일 API
단일 소스로 동작하는 한국 ETF·주식 분석 앱이다. 조사 결과 토스증권 Open API가 실시간 시세·
종목정보·캔들·투자자별 매매동향까지 제공함을 확인했고, 이를 활용해 K-Growth Insights TOSS를
완전히 새로운 프로젝트/저장소로 개발하기로 했다.

**중요: TOSS는 V2와 완전히 별도의 폴더/GitHub 저장소다.**
- 새 폴더: `/Users/kangsuek/pythonProject/K-Growth-Insights-TOSS`
- V2 폴더(`/Users/kangsuek/pythonProject/K-Growth-Insights`)의 파일은 **절대 열람 외 수정하지 않는다**(읽기 참고만).
- 이 새 폴더 자체를 새 GitHub 저장소로 생성해 관리한다(저장소 이름·공개범위는 이 세션에서 사용자와 먼저 확정할 것 — 아직 미정).

## 데이터 소스 분담 (킥오프 당시 계획 — 원칙: 토스로 가능한 건 전부 토스, 나머지만 네이버)

| 데이터 | 소스 | 엔드포인트 |
|---|---|---|
| 종목 기본정보 | 토스 | `GET /api/v1/stocks?symbols=...` (최대 200개) |
| 전체 종목 카탈로그 | 토스 | `GET /api/v1/stocks/all?market=KOSPI\|KOSDAQ&status=&securityType=` |
| 현재가(실시간) | 토스 WebSocket | `wss://openapi-ws.tossinvest.com/ws/v1`, 구독 `{"type":"trade:kr","codes":["005930"]}` |
| 현재가(REST 스냅샷) | 토스 | `GET /api/v1/prices?symbols=...` |
| 호가 | 토스 | `GET /api/v1/orderbook?symbol=...` |
| 캔들(일봉/분봉) | 토스 | `GET /api/v1/candles?symbol=&interval=1m\|1d&count=1-200&before=` |
| 투자자별 매매동향 | 토스 | `GET /api/v1/stocks/{symbol}/investor-trading?count=&until=` (개인/외국인/기관 7세부/기타법인) |
| 펀더멘털(PER/PBR/EPS/BPS/배당/52주) | **네이버 유지** | 기존 `naver_client.fetch_stock_fundamentals` 로직 이식 |
| ETF NAV/괴리율/총보수/구성종목 | **네이버 유지** | 기존 `naver_client.fetch_etf_fundamentals/holdings` 로직 이식 |
| 뉴스 | **네이버 유지** | 기존 `naver_client.fetch_news` 로직 이식 |
| 시장 지수(코스피/코스닥) | **네이버 유지** | 토스 문서에 지수 엔드포인트 미확인. 기존 `naver_client.fetch_index_*` 로직 이식 |

> **실제로는 이 계획대로 되지 않았다.** 실측 결과 토스 API 레이트리밋이 계정당 초당 1회
> (`x-ratelimit-limit: 1`, 2026-09-05 확인 — `backend/app/services/toss_client.py`
> `MIN_REQUEST_INTERVAL_SECONDS` 참고)로 매우 낮아, 수천 종목을 순회해야 하는 카탈로그·
> 일별시세·매매동향 수집을 토스로 옮기는 건 현실적이지 않았다. 최종적으로 토스는 아래
> 세 가지 실시간 경로에만 쓰고, 그 외(종목 기본정보·전체 카탈로그·호가·투자자별 매매동향·
> 일별시세·분봉)는 계획과 달리 전부 네이버에 남았다.
>
> - 실시간 체결 WebSocket(`trade:kr`)
> - quote 시가/고가/저가 시딩·정합용 캔들(`GET /api/v1/candles`, `interval=1d`, `count=2`만 사용 — 분봉은 미사용)
> - 시장 지수(코스피/코스닥) 실시간가 폴링·캔들(`GET /api/v1/market-indicators/*`)
>
> 최신 정확한 분담 기준은 `CLAUDE.md`의 "데이터 소스 분담" 섹션을 참고할 것 — 위 표는
> 구현 전 조사 시점의 계획 스냅샷으로만 남긴다.

## 토스 인증 · WebSocket 프로토콜

- 토큰 발급: `POST /oauth2/token` (Content-Type: `application/x-www-form-urlencoded`, `grant_type=client_credentials`, `client_id`, `client_secret`) → `access_token`/`expires_in`.
- REST: 매 요청 `Authorization: Bearer {token}` 헤더.
- WebSocket: 핸드셰이크 시 1회만 `Authorization: Bearer {token}` 헤더 인증(연결 유지 중 토큰 만료돼도 끊기지 않음).
- 구독은 "선언형 full-replace" — 새 배열을 보내면 이전 구독 전체를 대체(`[]`=전체 해제), subscribe/unsubscribe 액션 구분 없음.
  - **실계정 검증 결과 정정(2026-09-05):** 구독 선언은 반드시 **배열**이어야 한다 —
    `[{"type":"trade:kr","codes":["005930"]}]`. 위 원칙 설명과 달리 객체 하나만 보내면
    (`{"type":"trade:kr","codes":[...]}`) `wrong-format` 에러가 난다.
- Keepalive: 순수 텍스트 `PING`(대문자) 60초 간격 권장, 서버는 `{"type":"pong"}` 응답. 180초 무응답 시 서버가 연결 종료.
- 재연결: `server-shutdown` 에러 시 즉시 재연결, 그 외엔 지수 백오프. 재연결 전 기존 연결을 먼저 닫을 것.
- 레이트리밋(2026-09-05 실측): `x-ratelimit-limit: 1` — 계정당 REST 초당 1회. 위 데이터
  소스 분담 계획이 카탈로그·매매동향까지 토스로 옮기지 못한 주된 원인이다.
- ~~다음 세션 첫 마일스톤에서 실제 계정으로 토큰 발급을 직접 검증할 것~~ — **완료(2026-09-05,
  `backend/app/services/toss_client.py` 참고).** 이 표는 OpenAPI/AsyncAPI 문서
  (`https://openapi.tossinvest.com/openapi-docs/latest/openapi.json`, `.../asyncapi.json`)를
  조사한 킥오프 시점 스냅샷이며, 위 정정 사항 외 나머지는 실제 응답과 일치함을 확인했다.

## V2에서 그대로 참고/이식할 코드 (읽기 전용 참고 — V2 파일은 수정 금지)

- `K-Growth-Insights/backend/app/services/naver_client.py` — 펀더멘털·ETF·뉴스·지수 조회 로직. **복사해서** 새 저장소에 붙여넣고 그대로 사용.
- `K-Growth-Insights/backend/app/timeutil.py` — KST 변환·장중 판정(`is_market_hours`/`is_close_confirmed`) 로직. 복사해서 재사용.
- `K-Growth-Insights/backend/tests/conftest.py` — 임시 DB 격리(`temp_db`) 테스트 패턴. 동일 구조로 이식.
- `K-Growth-Insights/CLAUDE.md` — 컨벤션(한글 주석/커밋, 천단위 구분, 실사용 엔드포인트만 유지 등). TOSS 저장소에도 이 프로젝트만의 CLAUDE.md를 별도로 만들어 유사 규칙을 명시할 것(자동 상속되지 않음).

## 스택 (V2와 동일하게 유지)

- 백엔드: uv + FastAPI + SQLite
- 프론트엔드: npm + React + Vite + recharts + TanStack Query

## 작업 규칙 (V2와 동일하게 적용)

- 기능 개선/신규 기능은 소스 수정 전 Plan Mode로 계획하고 승인받는다.
- 마일스톤 단위로 구현 → 실제 동작 검증(브라우저로 직접 확인) → 사용자 확인 → 다음 단계.
- 커밋 메시지는 한글, `Co-Authored-By` 트레일러 포함.

## 이번 세션에서 가장 먼저 할 일 (제안)

1. ✅ 새 GitHub 저장소 이름·공개범위를 사용자와 확정하고 로컬 폴더에 `git init` + `gh repo create` (또는 사용자가 먼저 만든 저장소에 연결). — `github.com/kangsuek/K-Growth-Insights-TOSS`로 완료.
2. ✅ 백엔드/프론트엔드 기본 골격 생성(V2 pyproject.toml/package.json 참고해 동일 스택으로). — 완료.
3. ✅ `toss_client.py`: OAuth2 토큰 발급을 실제 계정으로 연동해 성공 여부부터 검증(가장 중요한 선행 검증 — 여기서 막히면 전체 계획 재검토 필요). — 완료(2026-09-05).
4. ❌ `GET /api/v1/stocks/all`로 카탈로그 수집 파이프라인 구현(네이버 카탈로그 수집을 대체). — **미실행.** 위 "데이터 소스 분담" 정정 사항 참고 — 토스 레이트리밋(초당 1회) 때문에 카탈로그 수집은 계획을 접고 네이버(`naver_client.fetch_market_catalog`, `services/catalog.py`)에 그대로 남았다.
5. 이후 마일스톤(캔들/실시간 WS/매매동향 → 화면별 재구현)은 4번까지 검증 후 사용자와 다시 논의. — 결과적으로 실시간 WS·시장지수 폴링만 토스로 이식되고, 캔들 기반 일별시세·매매동향 재구현은 4번과 같은 이유로 진행하지 않았다.

## MCP / 스킬

- 별도 MCP 서버 불필요 — 토스 API도 네이버처럼 백엔드 코드(`toss_client.py`)에서 직접 HTTP/WS로 처리.
- 별도 스킬 파일도 아직 불필요. 반복 작업 패턴이 확인되면 그때 추가 검토.

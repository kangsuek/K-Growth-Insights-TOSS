"""APScheduler 기반 자동 수집 스케줄러.

- 정기 수집: 평일 09:00:05부터 15:40 KST까지, 별도 주기(설정의 '데이터 자동
  수집 주기', 기본 10분)로 종목관리 등록 종목의 일별 시세·수급·펀더멘털을
  수집하는 interval_collect 잡이 전담한다(분봉은 여기서 수집하지 않는다 —
  collectors.collect_stock이 분봉을 호출하지 않으므로). 서버 기동 시각이 아니라
  CronTrigger로 정각+5초에 정렬한다.
- 분봉 수집: 평일 09:00:10부터 15:40 KST까지, 별도 주기(설정의 '분봉 자동 수집
  주기', 기본 1분)로 분봉만 수집하는 intraday_collect 잡이 전담한다. 다른 잡과
  중복 수집하지 않는다(분봉은 일별 데이터보다 훨씬 자주 바뀌므로
  COLLECT_INTERVAL_MINUTES와 분리하며, 서버 기동 시각이 아니라 CronTrigger로
  정각+10초에 정렬한다)
- 마감 수집: 평일 15:40 KST 종가 확정 시점 전체 수집(분봉 제외)
- 기동 보충 수집: 이 앱은 서버가 아니라 켤 때만 백엔드가 떠 있다. 꺼져 있던 동안 놓친
  수집(마감 수집 포함 — APScheduler는 놓친 실행을 건너뛴다)을 앱을 켤 때 한 번 채운다
  (run_startup_catch_up).

collectors가 동기(httpx.Client)이므로 이벤트 루프를 막지 않도록 스레드 기반
BackgroundScheduler를 사용한다. 서버 lifespan에서 start/shutdown 한다.
"""
from __future__ import annotations

import logging
import threading
from datetime import date, datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app import config
from app.database import get_connection
from app.services import alerts, collectors, jobs, repository
from app.timeutil import (  # noqa: F401
    KST, MARKET_CLOSE, MARKET_OPEN, is_market_hours, last_market_close, parse_db_timestamp,
)

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def run_collect_all(reason: str) -> dict:
    """추적 전체 종목을 수집하고 성공/실패 요약을 로깅·반환한다."""
    stocks = repository.list_stocks()
    succeeded = 0
    for s in stocks:
        result = collectors.collect_stock(s["ticker"])
        if result.ok:
            succeeded += 1
            try:
                alerts.check_signal_rules_after_daily_collect(s["ticker"])
            except Exception:  # noqa: BLE001 - 알림 판정 실패가 수집 자체를 막지 않게
                logger.warning("[scheduler:%s] 신호 알림 판정 실패: %s", reason, s["ticker"])
    summary = {"total": len(stocks), "succeeded": succeeded}
    logger.info("[scheduler:%s] 수집 완료 %d/%d", reason, succeeded, len(stocks))
    return summary


def run_collect_intraday_all(reason: str) -> dict:
    """추적 전체 종목의 분봉만 수집하고 성공/실패 요약을 로깅·반환한다."""
    stocks = repository.list_stocks()
    succeeded = 0
    for s in stocks:
        try:
            collectors.collect_intraday(s["ticker"])
            succeeded += 1
            alerts.check_price_rules_after_intraday_collect(s["ticker"])
        except Exception:  # noqa: BLE001 - 한 종목 실패가 나머지를 막지 않게
            logger.warning("[scheduler:%s] 분봉 수집 실패: %s", reason, s["ticker"])
    summary = {"total": len(stocks), "succeeded": succeeded}
    logger.info("[scheduler:%s] 분봉 수집 완료 %d/%d", reason, succeeded, len(stocks))
    return summary


def _in_market_hours_at_minute() -> bool:
    """CronTrigger가 정각+N초에 실행되므로, 초 단위를 잘라 비교해 장 마감 정각
    (15:40:00)과의 초 단위 오차로 마지막 15:40 수집이 걸러지지 않게 한다."""
    now = datetime.now(KST).replace(second=0, microsecond=0)
    return is_market_hours(now)


def _interval_job() -> None:
    if not _in_market_hours_at_minute():
        return
    # 기동 보충 수집·수동 전체 수집·마감 수집이 진행 중이면 같은 데이터를 다시 받을 필요가
    # 없다. 확인과 실행 사이에 다른 수집이 끼어들지 않게 락을 비차단으로 잡는다.
    lock = jobs.exclusive()
    if not lock.acquire(blocking=False):
        logger.info("[scheduler:interval] 전체 수집 진행 중 — 이번 회차 건너뜀")
        return
    try:
        run_collect_all("interval")
    finally:
        lock.release()


def _intraday_interval_job() -> None:
    if not _in_market_hours_at_minute():
        return
    run_collect_intraday_all("intraday-interval")


def _daily_close_job() -> None:
    # 마감 수집은 확정 종가를 받는 유일한 회차라 건너뛰지 않는다 — 다른 전체 수집이
    # 진행 중이면 끝날 때까지 기다렸다가 이어서 실행한다(그 수집은 장중 값일 수 있음).
    with jobs.exclusive():
        run_collect_all("daily-close")


# --- 기동 보충 수집 ---------------------------------------------------------

# 보충할 일별 시세 일수 상한(네이버 일별 시세 페이지네이션 기준 약 7페이지).
CATCH_UP_MAX_DAYS = 365
# 공백 경계(휴장일·기준일 여유)용 추가 일수.
CATCH_UP_MARGIN_DAYS = 5


def _oldest_latest_price_date() -> str | None:
    """관심종목별 최신 시세일 중 가장 이른 날짜(가장 오래 비어 있는 종목 기준). 시세가 없으면 None."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT MIN(latest) AS oldest FROM (
                SELECT MAX(p.date) AS latest FROM stocks s
                JOIN prices p ON p.ticker = s.ticker
                GROUP BY s.ticker
            )
            """
        ).fetchone()
    return row["oldest"] if row else None


def needs_catch_up(now: datetime, last_collection, oldest_latest: str | None = None) -> bool:
    """밀린 수집이 있으면 True. 둘 중 하나라도 해당하면 보충한다.

    1. 가장 최근 장 마감(확정) 이후에 수집한 적이 없다(last_collection).
       장중에 켰다면 '전일 마감분을 가졌는가', 장 마감 후·주말이면 '그날 마감분'을 본다.
    2. 관심종목 중 하나라도 최신 시세일이 마지막 마감 거래일보다 이르다(oldest_latest).
       1번(MAX(updated_at))만 보면, 보충 도중 앱을 끄거나 일부 종목이 실패해도 한 종목만
       저장되면 '수집함'으로 판정돼 남은 종목의 공백이 영영 채워지지 않는다.
       (공휴일엔 그날 시세가 없어 매 기동마다 보충이 돌 수 있지만, 새 데이터가 없을 뿐
       값은 틀어지지 않는다.)
    """
    expected = last_market_close(now)
    last = parse_db_timestamp(last_collection)
    if last is None or last < expected:
        return True
    return oldest_latest is not None and oldest_latest < expected.date().isoformat()


def catch_up_days(today: date) -> int | None:
    """보충할 일별 시세 일수. 관심종목 중 가장 오래 비어 있는 종목 기준(최신 시세일).

    며칠·몇 주 앱을 안 켰어도 시세·수급 이력이 빈칸 없이 채워지게 공백만큼 받는다.
    시세가 하나도 없으면 None(수집기 기본 범위)을 돌려준다.
    """
    oldest = _oldest_latest_price_date()
    if not oldest:
        return None
    try:
        gap = (today - date.fromisoformat(oldest)).days
    except ValueError:
        return None
    return max(1, min(CATCH_UP_MAX_DAYS, gap + CATCH_UP_MARGIN_DAYS))


def _startup_catch_up() -> None:
    now = datetime.now(KST)
    try:
        if needs_catch_up(now, repository.last_collection_time(), _oldest_latest_price_date()):
            days = catch_up_days(now.date())
            logger.info("[scheduler:startup] 밀린 데이터 보충 수집 시작(days=%s)", days)
            jobs.collect_all_sync(days=days)
        else:
            logger.info("[scheduler:startup] 최근 마감 이후 수집분이 있어 일별 보충 생략")
        # 분봉은 항상 채운다(종목당 1요청) — 직전 세션 분봉 + 목표가 알림 폴백 판정.
        run_collect_intraday_all("startup")
    except Exception:  # noqa: BLE001 - 보충 실패가 앱 동작을 막지 않게
        logger.warning("[scheduler:startup] 보충 수집 실패", exc_info=True)
    finally:
        # 새로 채운 시세로 실시간 기준가(prev_close)를 즉시 다시 계산하게 한다.
        from app.services.realtime import realtime_manager
        realtime_manager.request_reconcile()


def run_startup_catch_up() -> threading.Thread | None:
    """앱 기동 시 밀린 수집을 백그라운드 스레드로 한 번 실행한다(기동·헬스체크를 막지 않음).

    SCHEDULER_ENABLED=false면 자동 수집 전체를 끈 것으로 보고 실행하지 않는다.
    """
    if not config.SCHEDULER_ENABLED:
        return None
    thread = threading.Thread(target=_startup_catch_up, name="startup-catch-up", daemon=True)
    thread.start()
    return thread


def _market_cron(minutes: int, second: int) -> CronTrigger:
    """장중(평일 09:00~15:59) 정각+`second`초부터 매 `minutes`분마다 도는 트리거."""
    return CronTrigger(
        day_of_week="mon-fri",
        hour="9-15",
        minute=f"*/{minutes}",
        second=second,
        timezone=KST,
    )


def start() -> BackgroundScheduler | None:
    """스케줄러를 기동한다. 비활성화 상태면 None 반환."""
    global _scheduler
    if not config.SCHEDULER_ENABLED:
        logger.info("스케줄러 비활성화(SCHEDULER_ENABLED=false)")
        return None
    if _scheduler and _scheduler.running:
        return _scheduler

    scheduler = BackgroundScheduler(timezone=KST)
    scheduler.add_job(
        _interval_job,
        # 09:00:05부터 매 N분마다 실행(서버 기동 시각이 아닌 정각+5초 기준 정렬).
        # 분봉 잡(정각+10초)보다 5초 앞서 실행해 시세·수급을 먼저 채운다.
        _market_cron(config.COLLECT_INTERVAL_MINUTES, second=5),
        id="interval_collect",
        replace_existing=True,
        max_instances=1,  # 이전 실행이 안 끝났으면 중복 실행 금지
        coalesce=True,     # 밀린 실행은 1회로 합침
    )
    scheduler.add_job(
        _intraday_interval_job,
        # 09:00:10부터 매 N분마다 실행(서버 기동 시각이 아닌 정각+10초 기준 정렬).
        # 09:00:00 정각 대신 10초 여유를 둬 개장 직후 네이버 분봉이 아직
        # 생성되지 않은 시점에 빈 응답을 받는 것을 피한다.
        _market_cron(config.INTRADAY_COLLECT_INTERVAL_MINUTES, second=10),
        id="intraday_collect",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _daily_close_job,
        CronTrigger(day_of_week="mon-fri", hour=15, minute=40, timezone=KST),
        id="daily_close_collect",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info(
        "스케줄러 시작: 장중 %d분 간격(일별) + %d분 간격(분봉) + 평일 15:40 KST 마감 수집",
        config.COLLECT_INTERVAL_MINUTES,
        config.INTRADAY_COLLECT_INTERVAL_MINUTES,
    )
    return scheduler


def update_intraday_interval(minutes: int) -> None:
    """분봉 수집 주기를 변경한다. 실행 중인 스케줄러가 있으면 해당 잡을 즉시 재등록한다.

    스케줄러가 아직 기동 전(설정 로드 시점)이면 config 값만 갱신되고,
    이후 start()가 이 값으로 잡을 등록한다.
    """
    config.INTRADAY_COLLECT_INTERVAL_MINUTES = minutes
    if _scheduler and _scheduler.running:
        _scheduler.reschedule_job("intraday_collect", trigger=_market_cron(minutes, second=10))
        logger.info("분봉 수집 잡 재등록: %d분 간격", minutes)


def update_collect_interval(minutes: int) -> None:
    """일별 시세·수급·펀더멘털 수집 주기를 변경한다. 실행 중인 스케줄러가 있으면
    해당 잡을 즉시 재등록한다.

    스케줄러가 아직 기동 전(설정 로드 시점)이면 config 값만 갱신되고,
    이후 start()가 이 값으로 잡을 등록한다.
    """
    config.COLLECT_INTERVAL_MINUTES = minutes
    if _scheduler and _scheduler.running:
        _scheduler.reschedule_job("interval_collect", trigger=_market_cron(minutes, second=5))
        logger.info("데이터 자동 수집 잡 재등록: %d분 간격", minutes)


def shutdown() -> None:
    """스케줄러를 정리한다(진행 중 작업은 대기하지 않음)."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("스케줄러 종료")
    _scheduler = None

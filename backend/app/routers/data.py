"""Data collection endpoints (Naver mobile API -> SQLite)."""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.services import jobs, repository, scheduler

router = APIRouter(prefix="/api/data", tags=["data"])


@router.post("/collect-all")
def collect_all(days: int = Query(1, ge=1, le=365, description="수집할 일수(기본 1)")):
    """전체 종목 수집을 백그라운드로 시작하고 즉시 반환한다.

    진행률과 완료 후 집계(result)는 /collect-progress 폴링으로 받는다. 이미 진행 중이면
    새로 시작하지 않고 already_running을 돌려준다(화면은 그 수집의 결과를 기다리면 된다).
    """
    if not jobs.start_collect_all(days=days):
        return {"message": "이미 전체 수집이 진행 중입니다", "status": "already_running"}
    return {"message": "전체 수집을 시작했습니다", "status": "started"}


# 내부 상태 → 프론트 진행률 status 매핑.
_PROGRESS_STATUS = {"idle": "idle", "running": "collecting", "done": "completed", "error": "error"}


@router.get("/collect-progress")
def collect_progress():
    """수집 진행률(폴링용). 프론트 collectAllProgress 계약."""
    snap = jobs.snapshot()
    return {
        "status": _PROGRESS_STATUS.get(snap["status"], snap["status"]),
        "is_collecting": snap["status"] == "running",
        "total": snap["total"],
        "completed": snap["completed"],
        "current": snap["current"],
        "message": f"{snap['completed']}/{snap['total']}" if snap["total"] else "",
        # 완료 시 집계(성공/실패 수·레코드 수), 실패 시 사유. 진행 중엔 둘 다 None.
        "result": snap.get("result"),
        "error": snap.get("error"),
    }


@router.get("/scheduler-status")
def scheduler_status():
    """스케줄러 상태 + 마지막 수집 시각(프론트 대시보드/푸터용)."""
    running = scheduler._scheduler is not None and scheduler._scheduler.running
    next_run = None
    if running:
        for job in scheduler._scheduler.get_jobs():
            if job.id == "interval_collect" and job.next_run_time:
                next_run = job.next_run_time.isoformat()
    return {
        "scheduler": {
            "is_running": running,
            "last_collection_time": repository.last_collection_time(),
            "next_collection_time": next_run,
        }
    }


@router.delete("/reset")
def reset_data():
    """수집 데이터 초기화(종목 목록은 유지)."""
    deleted = repository.reset_collected_data()
    return {"reset": True, "deleted": deleted}


@router.get("/stats")
def stats():
    return repository.data_stats()

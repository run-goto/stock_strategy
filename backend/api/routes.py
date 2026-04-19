from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Request

from backend.api.schemas import (
    BacktestCreatedResponse,
    BacktestRequest,
    BacktestResultResponse,
    HealthResponse,
    JobResponse,
    ScanCreatedResponse,
    ScanJobResponse,
    ScanRequest,
    StrategyInfo,
    StrategyResultResponse,
    SyncCreatedResponse,
    SyncRequest,
    SyncResultResponse,
    SyncScheduleResponse,
    SyncScheduleUpdateRequest,
)
from backend.application.interfaces import TaskExecutionService
from backend.application.strategy import load_strategies_from_config
from backend.application.sync import SyncScheduleService

router = APIRouter(prefix="/api/v1")


def get_job_service(request: Request):
    return request.app.state.job_service


def get_config(request: Request):
    return request.app.state.config


def get_sync_schedule_service(request: Request):
    service = getattr(request.app.state, "sync_schedule_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="定时同步服务不可用")
    return service


ConfigDep = Annotated[dict, Depends(get_config)]
JobServiceDep = Annotated[TaskExecutionService, Depends(get_job_service)]
SyncScheduleServiceDep = Annotated[SyncScheduleService, Depends(get_sync_schedule_service)]
JobIdPath = Annotated[str, Path()]
JobTypeQuery = Annotated[str | None, Query(alias="type")]
JobLimitQuery = Annotated[int, Query(ge=1, le=200)]


@router.get("/health", response_model=HealthResponse)
def health(config: ConfigDep):
    return {
        "status": "ok",
        "duckdb_path": config.get("storage", {}).get("duckdb_path", "stock_data.duckdb"),
        "current_time": datetime.now().isoformat(),
    }


@router.get("/strategies", response_model=list[StrategyInfo])
def strategies():
    return [
        {"class_name": s.__class__.__name__, "name": s.name}
        for s in load_strategies_from_config()
    ]


@router.post("/scans", response_model=ScanCreatedResponse, status_code=202)
def create_scan(
    request_body: Annotated[ScanRequest, Body()],
    job_service: JobServiceDep,
):
    try:
        job = job_service.submit_scan(
            start_date=request_body.start,
            end_date=request_body.end,
            target_dates=request_body.targets,
            strategy_classes=request_body.strategy_classes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return job


@router.post("/syncs", response_model=SyncCreatedResponse, status_code=202)
def create_sync(
    request_body: Annotated[SyncRequest, Body()],
    job_service: JobServiceDep,
):
    try:
        return job_service.submit_sync(
            scope=request_body.scope,
            start_date=request_body.start,
            end_date=request_body.end,
            stock_codes=request_body.stock_codes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/sync-schedules/default", response_model=SyncScheduleResponse)
def get_default_sync_schedule(sync_schedule_service: SyncScheduleServiceDep):
    return sync_schedule_service.get_default_schedule()


@router.put("/sync-schedules/default", response_model=SyncScheduleResponse)
def update_default_sync_schedule(
    request_body: Annotated[SyncScheduleUpdateRequest, Body()],
    sync_schedule_service: SyncScheduleServiceDep,
):
    update_data = (
        request_body.model_dump(exclude_unset=True)
        if hasattr(request_body, "model_dump")
        else request_body.dict(exclude_unset=True)
    )
    try:
        return sync_schedule_service.update_default_schedule(**update_data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sync-schedules/default/run", response_model=SyncCreatedResponse, status_code=202)
def run_default_sync_schedule(sync_schedule_service: SyncScheduleServiceDep):
    try:
        return sync_schedule_service.run_default_now()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/backtests", response_model=BacktestCreatedResponse, status_code=202)
def create_backtest(
    request_body: Annotated[BacktestRequest, Body()],
    job_service: JobServiceDep,
):
    try:
        return job_service.submit_backtest(
            strategy=request_body.strategy,
            start_date=request_body.start,
            end_date=request_body.end,
            stock_codes=request_body.stock_codes,
            scan_job_id=request_body.scan_job_id,
            initial_cash=request_body.initial_cash,
            commission=request_body.commission,
            slippage=request_body.slippage,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/jobs", response_model=list[JobResponse])
def list_jobs(
    job_service: JobServiceDep,
    job_type: JobTypeQuery = None,
    limit: JobLimitQuery = 50,
):
    try:
        return job_service.list_unified_jobs(job_type=job_type, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: JobIdPath, job_service: JobServiceDep):
    getter = getattr(job_service, "get_unified_job", job_service.get_job)
    job = getter(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job


@router.get("/scans/{job_id}", response_model=ScanJobResponse)
def get_scan(job_id: JobIdPath, job_service: JobServiceDep):
    getter = getattr(job_service, "get_scan_job", job_service.get_job)
    job = getter(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="扫描任务不存在")
    return job


@router.get("/scans/{job_id}/results", response_model=list[StrategyResultResponse])
def get_scan_results(job_id: JobIdPath, job_service: JobServiceDep):
    getter = getattr(job_service, "get_scan_job", job_service.get_job)
    if getter(job_id) is None:
        raise HTTPException(status_code=404, detail="扫描任务不存在")
    return job_service.get_results(job_id)


@router.get("/syncs/{job_id}/results", response_model=list[SyncResultResponse])
def get_sync_results(job_id: JobIdPath, job_service: JobServiceDep):
    if job_service.get_unified_job(job_id) is None:
        raise HTTPException(status_code=404, detail="同步任务不存在")
    return job_service.get_sync_results(job_id)


@router.get("/backtests/{job_id}/results", response_model=list[BacktestResultResponse])
def get_backtest_results(job_id: JobIdPath, job_service: JobServiceDep):
    if job_service.get_unified_job(job_id) is None:
        raise HTTPException(status_code=404, detail="回测任务不存在")
    return job_service.get_backtest_results(job_id)

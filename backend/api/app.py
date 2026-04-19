from contextlib import asynccontextmanager

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router
from backend.application.backtest_service import BacktestService
from backend.application.interfaces import TaskExecutionService
from backend.application.sync import DataSyncService, InProcessSyncScheduler, SyncScheduleService
from backend.application.tasks import ResearchJobService
from backend.infrastructure.data_sources import create_data_source
from backend.infrastructure.config import configure_logging, load_app_config, get_duckdb_path
from backend.infrastructure.persistence.duckdb_repository import (
    DuckDBJobRepository,
    DuckDBScanJobRepository,
    DuckDBStockRepository,
)

logger = logging.getLogger(__name__)


def create_app(
    app_config: dict | None = None,
    repository: DuckDBStockRepository | None = None,
    job_repository: DuckDBScanJobRepository | None = None,
    unified_job_repository: DuckDBJobRepository | None = None,
    job_service: TaskExecutionService | None = None,
    sync_schedule_service: SyncScheduleService | None = None,
) -> FastAPI:
    config = app_config or load_app_config()
    configure_logging(config)
    db_path = get_duckdb_path(config)
    repository = repository or DuckDBStockRepository(db_path)
    job_repository = job_repository or DuckDBScanJobRepository(db_path)
    unified_job_repository = unified_job_repository or DuckDBJobRepository(db_path)
    if job_service is None:
        data_config = config.get("data_source", {})
        data_source = create_data_source(
            data_config.get("provider", "tencent"),
            timeout=data_config.get("timeout"),
        )
        sync_service = DataSyncService(
            stock_repository=repository,
            job_repository=unified_job_repository,
            data_source=data_source,
            stock_fetch_timeout=data_config.get("stock_fetch_timeout", data_config.get("timeout", 10.0)),
            daily_fetch_workers=data_config.get("daily_fetch_workers", 8),
        )
        backtest_service = BacktestService(
            stock_repository=repository,
            job_repository=unified_job_repository,
        )
        job_service = ResearchJobService(
            stock_repository=repository,
            job_repository=unified_job_repository,
            app_config=config,
            sync_service=sync_service,
            backtest_service=backtest_service,
        )
    if sync_schedule_service is None and hasattr(job_service, "submit_sync"):
        sync_schedule_service = SyncScheduleService(
            schedule_repository=unified_job_repository,
            job_service=job_service,
        )
    scheduler = None
    if sync_schedule_service is not None:
        schedule_config = config.get("sync_schedule", {})
        scheduler = InProcessSyncScheduler(
            sync_schedule_service,
            poll_interval_seconds=schedule_config.get("poll_interval_seconds", 60),
        )
    if hasattr(job_service, "recover_unfinished_jobs"):
        recovered_count = job_service.recover_unfinished_jobs()
        if recovered_count:
            logger.info("已恢复未完成任务: count=%s", recovered_count)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if app.state.sync_scheduler is not None:
            app.state.sync_scheduler.start()
        try:
            yield
        finally:
            if app.state.sync_scheduler is not None:
                app.state.sync_scheduler.stop()
            app.state.job_service.shutdown()

    app = FastAPI(title="A股策略分析系统", version="2.0.0", lifespan=lifespan)
    app.state.config = config
    app.state.repository = repository
    app.state.scan_job_repository = job_repository
    app.state.unified_job_repository = unified_job_repository
    app.state.job_service = job_service
    app.state.sync_schedule_service = sync_schedule_service
    app.state.sync_scheduler = scheduler
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["null"],
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    return app


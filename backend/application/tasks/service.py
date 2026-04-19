"""Unified async job service for sync, scan, and backtest workflows."""

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from uuid import uuid4

from backend.application.interfaces import (
    DATA_SYNC_SCOPES,
    BacktestRunner,
    DataSyncRunner,
    StrategyScanRunner,
    TaskExecutionService,
    TradeCalendarProvider,
)
from backend.application.strategy.calendar import ConfigTradeCalendarProvider, resolve_scan_dates, validate_date
from backend.application.tasks.handlers import BacktestJobHandler, JobDispatcher, ScanJobHandler, SyncJobHandler
from backend.domain.models import Job, JobStatus, JobType
from backend.domain.ports import JobRepository, StockRepository

logger = logging.getLogger(__name__)


class ResearchJobService(TaskExecutionService):
    """Single-process queue for local research jobs."""

    def __init__(
        self,
        stock_repository: StockRepository,
        job_repository: JobRepository,
        app_config: dict,
        sync_service: DataSyncRunner,
        backtest_service: BacktestRunner,
        scan_runner: StrategyScanRunner | None = None,
        dispatcher: JobDispatcher | None = None,
        calendar_provider: TradeCalendarProvider | None = None,
        auto_start: bool = True,
    ):
        self.stock_repository = stock_repository
        self.job_repository = job_repository
        self.app_config = app_config
        self.sync_service = sync_service
        self.backtest_service = backtest_service
        self.scan_runner = scan_runner or self._default_scan_runner
        self.dispatcher = dispatcher or JobDispatcher({
            JobType.SYNC: SyncJobHandler(sync_service),
            JobType.SCAN: ScanJobHandler(self.scan_runner),
            JobType.BACKTEST: BacktestJobHandler(backtest_service),
        })
        self.calendar_provider = calendar_provider or ConfigTradeCalendarProvider(app_config)
        self.auto_start = auto_start
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="research-job")

    def submit_sync(
        self,
        scope: str,
        start_date: str | None = None,
        end_date: str | None = None,
        stock_codes: list[str] | None = None,
    ) -> dict:
        if scope not in DATA_SYNC_SCOPES:
            raise ValueError(f"不支持的数据同步范围: {scope}")
        if scope in {"daily", "all"}:
            if not start_date or not end_date:
                raise ValueError("同步日线数据时 start 和 end 必须同时提供")
            validate_date(start_date)
            validate_date(end_date)

        job = self._create_job(
            JobType.SYNC,
            {
                "scope": scope,
                "start_date": start_date,
                "end_date": end_date,
                "stock_codes": stock_codes,
            },
        )
        return job.to_dict()

    def submit_scan(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        target_dates: list[str] | None = None,
        strategy_classes: list[str] | None = None,
    ) -> dict:
        start_date, end_date, target_dates = resolve_scan_dates(
            self.app_config,
            start_date,
            end_date,
            target_dates,
            calendar_provider=self.calendar_provider,
        )
        strategy_classes = self._resolve_strategy_classes(strategy_classes)
        job = self._create_job(
            JobType.SCAN,
            {
                "start_date": start_date,
                "end_date": end_date,
                "target_dates": target_dates,
                "strategy_classes": strategy_classes,
            },
        )
        return self._scan_job_payload(job)

    def submit_backtest(
        self,
        strategy: str,
        start_date: str,
        end_date: str,
        stock_codes: list[str] | None = None,
        scan_job_id: str | None = None,
        initial_cash: float = 100000,
        commission: float = 0.0003,
        slippage: float = 0.0,
    ) -> dict:
        validate_date(start_date)
        validate_date(end_date)
        supported_strategies = self._supported_backtest_strategies()
        if strategy not in supported_strategies:
            raise ValueError(f"当前仅支持回测策略: {', '.join(supported_strategies)}")
        if not stock_codes and not scan_job_id:
            raise ValueError("回测必须提供 stock_codes 或 scan_job_id")

        job = self._create_job(
            JobType.BACKTEST,
            {
                "strategy": strategy,
                "start_date": start_date,
                "end_date": end_date,
                "stock_codes": stock_codes,
                "scan_job_id": scan_job_id,
                "initial_cash": initial_cash,
                "commission": commission,
                "slippage": slippage,
            },
        )
        return job.to_dict()

    def run_job(self, job_id: str) -> None:
        job = self.job_repository.get(job_id)
        if job is None:
            logger.error("任务不存在: %s", job_id)
            return

        logger.info("任务开始: job_id=%s type=%s params=%s", job.job_id, job.type.value, job.params)
        job.mark_running()
        self.job_repository.save(job)
        try:
            summary = self.dispatcher.run(job)
            job.mark_completed(**summary)
            self.job_repository.save(job)
            logger.info(
                "任务完成: job_id=%s type=%s total_items=%s success_count=%s failed_count=%s",
                job.job_id,
                job.type.value,
                job.total_items,
                job.success_count,
                job.failed_count,
            )
        except Exception as exc:
            logger.exception("任务失败: %s", job_id)
            job.mark_failed(error=str(exc))
            self.job_repository.save(job)

    def get_unified_job(self, job_id: str) -> dict | None:
        job = self.job_repository.get(job_id)
        return job.to_dict() if job else None

    def recover_unfinished_jobs(self, reason: str = "服务重启，任务执行上下文已丢失") -> int:
        recovered_count = 0
        for job in self.job_repository.list_jobs(limit=10000):
            if job.status not in {JobStatus.QUEUED, JobStatus.RUNNING}:
                continue
            previous_status = job.status.value
            job.status = JobStatus.FAILED
            job.error = reason
            job.finished_at = datetime.now().isoformat()
            self.job_repository.save(job)
            recovered_count += 1
            logger.info(
                "恢复未完成任务状态: job_id=%s type=%s previous_status=%s",
                job.job_id,
                job.type.value,
                previous_status,
            )
        return recovered_count

    def list_unified_jobs(self, job_type: str | None = None, limit: int = 100) -> list[dict]:
        if job_type is not None and job_type not in {item.value for item in JobType}:
            raise ValueError(f"不支持的任务类型: {job_type}")

        if job_type is not None:
            jobs = self.job_repository.list_jobs(limit=10000)
            jobs = [job for job in jobs if job.type.value == job_type]
            jobs = jobs[:limit]
        else:
            jobs = self.job_repository.list_jobs(limit=limit)
        return [job.to_dict() for job in jobs]

    def get_scan_job(self, job_id: str) -> dict | None:
        job = self.job_repository.get(job_id)
        if job is None or job.type != JobType.SCAN:
            return None

        return self._scan_job_payload(job)

    def get_job(self, job_id: str) -> dict | None:
        return self.get_scan_job(job_id)

    def get_results(self, job_id: str) -> list[dict]:
        return [hit.to_dict() for hit in self.stock_repository.get_strategy_results(job_id)]

    def get_sync_results(self, job_id: str) -> list[dict]:
        return [item.to_dict() for item in self.job_repository.get_sync_results(job_id)]

    def get_backtest_results(self, job_id: str) -> list[dict]:
        return [item.to_dict() for item in self.job_repository.get_backtest_results(job_id)]

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=False)

    def _create_job(self, job_type: JobType, params: dict) -> Job:
        job = Job(job_id=uuid4().hex, type=job_type, status=JobStatus.QUEUED, params=params)
        self.job_repository.save(job)
        logger.info("任务已提交: job_id=%s type=%s params=%s", job.job_id, job.type.value, job.params)
        if self.auto_start:
            self.executor.submit(self.run_job, job.job_id)
        return job

    def _default_scan_runner(
        self,
        start_date: str,
        end_date: str,
        target_dates: list[str],
        job_id: str | None = None,
        strategy_classes: list[str] | None = None,
    ) -> list[dict]:
        from backend.application.strategy.loader import load_strategies_from_config
        from backend.application.strategy.execution import StrategyExecutor, TradeDataService
        from backend.infrastructure.data_sources import create_data_source

        data_config = self.app_config.get("data_source", {})
        data_source = create_data_source(
            data_config.get("provider", "tencent"),
            timeout=data_config.get("timeout"),
        )
        trade_data_service = TradeDataService(
            repository=self.stock_repository,
            data_source=data_source,
            allow_online_fetch=False,
        )
        strategies = load_strategies_from_config(
            config=self.app_config,
            strategy_classes=strategy_classes,
        )
        executor = StrategyExecutor(
            trade_data_service=trade_data_service,
            repository=self.stock_repository,
            strategies=strategies,
            max_workers=self.app_config["defaults"]["max_workers"],
        )
        return executor.run(start_date, end_date, target_dates, job_id=job_id)

    def _resolve_strategy_classes(self, strategy_classes: list[str] | None) -> list[str] | None:
        if strategy_classes is None:
            return None

        from backend.application.strategy.loader import load_strategies_from_config

        strategies = load_strategies_from_config(
            config=self.app_config,
            strategy_classes=strategy_classes,
        )
        return [strategy.__class__.__name__ for strategy in strategies]

    def _supported_backtest_strategies(self) -> list[str]:
        lister = getattr(self.backtest_service, "list_supported_strategies", None)
        if lister is not None:
            return list(lister())

        supported = getattr(self.backtest_service, "SUPPORTED_STRATEGIES", None)
        if isinstance(supported, dict):
            return list(supported)
        if supported:
            return list(supported)

        return ["DualMATrendStrategyBT"]

    @staticmethod
    def _scan_job_payload(job: Job) -> dict:
        params = job.params
        return {
            "job_id": job.job_id,
            "type": job.type.value,
            "status": job.status.value,
            "start_date": params["start_date"],
            "end_date": params["end_date"],
            "target_dates": params["target_dates"],
            "total_results": job.success_count,
            "total_items": job.total_items,
            "success_count": job.success_count,
            "failed_count": job.failed_count,
            "error": job.error,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
        }

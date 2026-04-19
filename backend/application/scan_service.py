"""Legacy scan job facade.

New code should use backend.application.tasks.ResearchJobService. This module
keeps the old scan-only service import path working for tests and integrations.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from backend.application.strategy.calendar import resolve_scan_dates, validate_date
from backend.domain.models import JobStatus, ScanJob
from backend.domain.ports import ScanJobRepository, StockRepository

logger = logging.getLogger(__name__)


class ScanJobService:
    """Legacy scan-only job service."""

    def __init__(
        self,
        stock_repository: StockRepository,
        job_repository: ScanJobRepository,
        app_config: dict,
        runner=None,
        auto_start: bool = True,
    ):
        self.stock_repository = stock_repository
        self.job_repository = job_repository
        self.app_config = app_config
        self.runner = runner or self._default_runner
        self.auto_start = auto_start
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="scan-job")

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
        )
        if strategy_classes is not None:
            self._resolve_strategy_classes(strategy_classes)
        job = ScanJob(
            job_id=uuid4().hex,
            status=JobStatus.QUEUED,
            start_date=start_date,
            end_date=end_date,
            target_dates=target_dates,
        )
        self.job_repository.save(job)
        if self.auto_start:
            self.executor.submit(self.run_job, job.job_id, strategy_classes)
        return job.to_dict()

    def run_job(self, job_id: str, strategy_classes: list[str] | None = None):
        job = self.job_repository.get(job_id)
        if job is None:
            logger.error("扫描任务不存在: %s", job_id)
            return

        job.mark_running()
        self.job_repository.save(job)
        try:
            if strategy_classes is None:
                results = self.runner(job.start_date, job.end_date, job.target_dates)
            else:
                results = self.runner(
                    job.start_date,
                    job.end_date,
                    job.target_dates,
                    strategy_classes=strategy_classes,
                )
            job.mark_completed(total_results=len(results))
            self.job_repository.save(job)
        except Exception as exc:
            logger.exception("扫描任务失败: %s", job_id)
            job.mark_failed(error=str(exc))
            self.job_repository.save(job)

    def get_job(self, job_id: str) -> dict | None:
        job = self.job_repository.get(job_id)
        return job.to_dict() if job else None

    def get_results(self, job_id: str) -> list[dict]:
        job = self.job_repository.get(job_id)
        if job is None:
            return []
        hits = self.job_repository.get_results(job)
        return [h.to_dict() for h in hits]

    def shutdown(self):
        self.executor.shutdown(wait=False, cancel_futures=False)

    def _default_runner(
        self,
        start_date: str,
        end_date: str,
        target_dates: list[str],
        strategy_classes: list[str] | None = None,
    ) -> list[dict]:
        from backend.application.strategy.execution import StrategyExecutor, TradeDataService
        from backend.application.strategy.loader import load_strategies_from_config
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
        return executor.run(start_date, end_date, target_dates)

    def _resolve_strategy_classes(self, strategy_classes: list[str]) -> list[str]:
        from backend.application.strategy.loader import load_strategies_from_config

        strategies = load_strategies_from_config(
            config=self.app_config,
            strategy_classes=strategy_classes,
        )
        return [strategy.__class__.__name__ for strategy in strategies]


__all__ = ["ScanJobService", "resolve_scan_dates", "validate_date"]

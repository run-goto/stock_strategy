"""Job handlers and type-based dispatch."""

from backend.application.interfaces import BacktestRunner, DataSyncRunner, JobHandler, StrategyScanRunner
from backend.domain.models import Job, JobType


class SyncJobHandler(JobHandler):
    """Execute a persisted data synchronization job."""

    def __init__(self, sync_service: DataSyncRunner):
        self.sync_service = sync_service

    def run(self, job: Job) -> dict:
        params = job.params
        return self.sync_service.run(
            job_id=job.job_id,
            scope=params["scope"],
            start_date=params.get("start_date"),
            end_date=params.get("end_date"),
            stock_codes=params.get("stock_codes"),
        )


class ScanJobHandler(JobHandler):
    """Execute a persisted strategy scan job."""

    def __init__(self, scan_runner: StrategyScanRunner):
        self.scan_runner = scan_runner

    def run(self, job: Job) -> dict:
        params = job.params
        if params.get("strategy_classes") is None:
            results = self.scan_runner(
                params["start_date"],
                params["end_date"],
                params["target_dates"],
                job_id=job.job_id,
            )
        else:
            results = self.scan_runner(
                params["start_date"],
                params["end_date"],
                params["target_dates"],
                job_id=job.job_id,
                strategy_classes=params["strategy_classes"],
            )
        return {
            "total_items": len(results),
            "success_count": len(results),
            "failed_count": 0,
        }


class BacktestJobHandler(JobHandler):
    """Execute a persisted backtest job."""

    def __init__(self, backtest_service: BacktestRunner):
        self.backtest_service = backtest_service

    def run(self, job: Job) -> dict:
        params = job.params
        return self.backtest_service.run(
            job_id=job.job_id,
            strategy=params["strategy"],
            start_date=params["start_date"],
            end_date=params["end_date"],
            stock_codes=params.get("stock_codes"),
            scan_job_id=params.get("scan_job_id"),
            initial_cash=params.get("initial_cash", 100000),
            commission=params.get("commission", 0.0003),
            slippage=params.get("slippage", 0.0),
        )


class JobDispatcher:
    """Dispatch jobs to handlers by JobType."""

    def __init__(self, handlers: dict[JobType, JobHandler]):
        self.handlers = handlers

    def run(self, job: Job) -> dict:
        handler = self.handlers.get(job.type)
        if handler is None:
            raise ValueError(f"不支持的任务类型: {job.type}")
        return handler.run(job)

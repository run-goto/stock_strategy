import tempfile
from pathlib import Path

from backend.application.interfaces import TradeCalendarProvider
from backend.application.tasks import JobDispatcher, ResearchJobService
from backend.domain.models import Job, JobStatus, JobType
from backend.infrastructure.persistence.duckdb_repository import DuckDBJobRepository, DuckDBStockRepository


class FakeCalendarProvider(TradeCalendarProvider):
    def recent_range(self, n_days: int = 60) -> tuple[str, str]:
        return "20260101", "20260102"

    def normalize_targets(self, target_dates: list[str]) -> list[str]:
        return target_dates


class RecordingSyncService:
    def __init__(self):
        self.calls = []

    def run(self, job_id, scope, start_date, end_date, stock_codes=None):
        self.calls.append((job_id, scope, start_date, end_date, stock_codes))
        return {"total_items": 1, "success_count": 1, "failed_count": 0}


class RecordingBacktestService:
    def __init__(self):
        self.calls = []

    def list_supported_strategies(self):
        return ["DualMATrendStrategyBT"]

    def run(
        self,
        job_id,
        strategy,
        start_date,
        end_date,
        stock_codes=None,
        scan_job_id=None,
        initial_cash=100000,
        commission=0.0003,
        slippage=0.0,
    ):
        self.calls.append((job_id, strategy, start_date, end_date, stock_codes, scan_job_id))
        return {"total_items": 1, "success_count": 1, "failed_count": 0}


class ExplodingSyncService(RecordingSyncService):
    def run(self, job_id, scope, start_date, end_date, stock_codes=None):
        raise RuntimeError("sync exploded")


def test_research_job_service_dispatches_each_job_type_to_handler():
    with tempfile.TemporaryDirectory() as temp_dir:
        stock_repository, job_repository = _repositories(temp_dir)
        sync_service = RecordingSyncService()
        backtest_service = RecordingBacktestService()
        scan_calls = []

        def scan_runner(start_date, end_date, target_dates, job_id=None, strategy_classes=None):
            scan_calls.append((job_id, start_date, end_date, target_dates, strategy_classes))
            return [{"code": "000001"}]

        service = ResearchJobService(
            stock_repository=stock_repository,
            job_repository=job_repository,
            app_config=_config(),
            sync_service=sync_service,
            backtest_service=backtest_service,
            scan_runner=scan_runner,
            calendar_provider=FakeCalendarProvider(),
            auto_start=False,
        )

        sync_job_id = service.submit_sync("daily", "20260101", "20260102", ["000001"])["job_id"]
        scan_job_id = service.submit_scan(target_dates=["20260102"])["job_id"]
        backtest_job_id = service.submit_backtest(
            "DualMATrendStrategyBT",
            "20260101",
            "20260102",
            stock_codes=["000001"],
        )["job_id"]

        service.run_job(sync_job_id)
        service.run_job(scan_job_id)
        service.run_job(backtest_job_id)

        assert job_repository.get(sync_job_id).status == JobStatus.COMPLETED
        assert job_repository.get(scan_job_id).status == JobStatus.COMPLETED
        assert job_repository.get(backtest_job_id).status == JobStatus.COMPLETED
        assert sync_service.calls[0][1:] == ("daily", "20260101", "20260102", ["000001"])
        assert scan_calls[0][1:] == ("20260101", "20260102", ["20260102"], None)
        assert backtest_service.calls[0][1:] == (
            "DualMATrendStrategyBT",
            "20260101",
            "20260102",
            ["000001"],
            None,
        )


def test_research_job_service_marks_failed_when_handler_raises():
    with tempfile.TemporaryDirectory() as temp_dir:
        stock_repository, job_repository = _repositories(temp_dir)
        service = ResearchJobService(
            stock_repository=stock_repository,
            job_repository=job_repository,
            app_config=_config(),
            sync_service=ExplodingSyncService(),
            backtest_service=RecordingBacktestService(),
            calendar_provider=FakeCalendarProvider(),
            auto_start=False,
        )
        job_id = service.submit_sync("daily", "20260101", "20260102")["job_id"]

        service.run_job(job_id)

        job = job_repository.get(job_id)
        assert job.status == JobStatus.FAILED
        assert job.error == "sync exploded"


def test_job_dispatcher_rejects_unsupported_job_type():
    dispatcher = JobDispatcher({})
    job = Job(job_id="job-1", type=JobType.SYNC, status=JobStatus.RUNNING, params={"scope": "stocks"})

    try:
        dispatcher.run(job)
    except ValueError as exc:
        assert "不支持的任务类型" in str(exc)
    else:
        raise AssertionError("dispatcher should reject missing handler")


def test_legacy_import_paths_reexport_new_implementations():
    from backend.application.job_service import ResearchJobService as LegacyResearchJobService
    from backend.application.screening import StrategyExecutor as LegacyStrategyExecutor
    from backend.application.sync_service import DataSyncService as LegacyDataSyncService
    from backend.infrastructure.persistence.duckdb import DuckDBJobRepository as NewDuckDBJobRepository
    from backend.infrastructure.persistence.duckdb_repository import DuckDBJobRepository as LegacyDuckDBJobRepository

    assert LegacyResearchJobService is ResearchJobService
    assert LegacyDataSyncService.__module__ == "backend.application.sync.service"
    assert LegacyStrategyExecutor.__module__ == "backend.application.strategy.execution"
    assert LegacyDuckDBJobRepository is NewDuckDBJobRepository


def test_application_layer_no_longer_imports_duckdb_or_infra_market_helper():
    app_root = Path(__file__).resolve().parents[1] / "backend" / "application"
    scanned = []
    for path in app_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        scanned.append(path)
        assert "duckdb_repository" not in text
        assert "infrastructure.data_sources.base import get_market_code" not in text

    assert scanned


def _repositories(temp_dir):
    db_path = str(Path(temp_dir) / "test.duckdb")
    return DuckDBStockRepository(db_path), DuckDBJobRepository(db_path)


def _config():
    return {
        "data_source": {"provider": "tencent", "timeout": 10.0},
        "defaults": {"check_days": 60, "max_workers": 1},
        "strategies": {},
    }

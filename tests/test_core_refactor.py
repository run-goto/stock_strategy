import tempfile
import unittest
from pathlib import Path
import logging
import time
import threading

import pandas as pd

from backend.infrastructure.config import configure_logging, load_app_config
from backend.infrastructure.data_sources import create_data_source
from backend.infrastructure.data_sources.base import DataSourceBase, normalize_stock_data
from backend.infrastructure.data_sources.tencent import _decode_response_text
from backend.infrastructure.persistence.duckdb_repository import DuckDBJobRepository, DuckDBStockRepository
from backend.application.backtest_service import BacktestService
from backend.application.interfaces import (
    BacktestRunner,
    DataSyncRunner,
    StrategyExecutionRunner,
    TaskExecutionService,
    TradeDataProvider,
)
from backend.application.job_service import ResearchJobService
from backend.application.screening import StrategyExecutor
from backend.application.sync_service import DataSyncService
from backend.backtrader_integration.data_feed import load_stock_data_from_duckdb
from backend.domain.models import BacktestResultRecord, Job, JobStatus, JobType, SyncResult, SyncSchedule
from backend.application.screening import scan_stock_data
from backend.application.sync_schedule_service import SyncScheduleService
from backend.application.strategy_loader import load_strategies_from_config
from backend.application.screening import TradeDataService
from backend.domain.strategy import BaseStrategy


class StubDataSource(DataSourceBase):
    def __init__(self, data):
        super().__init__(timeout=None)
        self.data = data
        self.calls = 0

    def do_fetch(self, stock_code, market_code, start_date, end_date):
        self.calls += 1
        return self.data


class ParallelTrackingDataSource(DataSourceBase):
    def __init__(self, data, delay=0.05):
        super().__init__(timeout=None)
        self.data = data
        self.delay = delay
        self.calls = 0
        self.active_calls = 0
        self.max_active_calls = 0
        self.lock = threading.Lock()

    def do_fetch(self, stock_code, market_code, start_date, end_date):
        with self.lock:
            self.calls += 1
            self.active_calls += 1
            self.max_active_calls = max(self.max_active_calls, self.active_calls)
        try:
            time.sleep(self.delay)
            return self.data
        finally:
            with self.lock:
                self.active_calls -= 1


class AlwaysHitStrategy(BaseStrategy):
    def __init__(self):
        super().__init__("测试命中")

    def check(self, hist_data: pd.DataFrame) -> bool:
        return True


class CoreRefactorTest(unittest.TestCase):
    def test_application_implementations_follow_service_interfaces(self):
        self.assertTrue(issubclass(DataSyncService, DataSyncRunner))
        self.assertTrue(issubclass(TradeDataService, TradeDataProvider))
        self.assertTrue(issubclass(StrategyExecutor, StrategyExecutionRunner))
        self.assertTrue(issubclass(BacktestService, BacktestRunner))
        self.assertTrue(issubclass(ResearchJobService, TaskExecutionService))

    def test_config_has_default_duckdb_path(self):
        config = load_app_config()
        self.assertEqual(config["storage"]["duckdb_path"], "stock_data.duckdb")

    def test_configure_logging_writes_info_log_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "logs"
            try:
                log_file = configure_logging({
                    "logging": {
                        "level": "INFO",
                        "format": "%(levelname)s:%(message)s",
                        "dir": str(log_dir),
                        "file": "app.log",
                    }
                })
                logging.getLogger("tests.logging").info("info log smoke test")
                for handler in logging.getLogger().handlers:
                    handler.flush()

                self.assertEqual(log_file, log_dir / "app.log")
                self.assertTrue(log_file.exists())
                self.assertIn("INFO:info log smoke test", log_file.read_text(encoding="utf-8"))
            finally:
                for handler in list(logging.getLogger().handlers):
                    if getattr(handler, "name", None) == "stock-strategy-file":
                        logging.getLogger().removeHandler(handler)
                        handler.close()

    def test_create_data_source_from_provider(self):
        data_source = create_data_source("tencent", timeout=1.5)
        self.assertEqual(data_source.timeout, 1.5)
        self.assertEqual(data_source.name, "腾讯证券")

    def test_tencent_response_decoder_falls_back_to_gb18030(self):
        class Response:
            content = "国际实业".encode("gb18030")

        self.assertEqual(_decode_response_text(Response()), "国际实业")

    def test_normalize_stock_data_returns_standard_columns(self):
        raw_data = pd.DataFrame(
            [
                {
                    "stock_code": "000001",
                    "date": "20260102",
                    "open": "1.0",
                    "close": "1.2",
                    "high": "1.3",
                    "low": "0.9",
                    "volume": "100",
                }
            ]
        )

        normalized = normalize_stock_data(raw_data)

        self.assertEqual(
            list(normalized.columns),
            ["stock_code", "date", "open", "close", "high", "low", "volume", "amount"],
        )
        self.assertEqual(normalized.iloc[0]["date"].strftime("%Y%m%d"), "20260102")
        self.assertEqual(normalized.iloc[0]["volume"], 100)

    def test_duckdb_repository_upserts_daily_data_and_results(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = DuckDBStockRepository(str(Path(temp_dir) / "test.duckdb"))
            repository.upsert_stocks([{"code": "000001", "name": "平安银行"}])
            repository.upsert_daily_data(_sample_daily_data())
            repository.upsert_strategy_results(
                [
                    {
                        "code": "000001",
                        "name": "平安银行",
                        "strategy": "测试命中",
                        "target_date": "20260102",
                        "current_price": 1.2,
                        "current_volume": 100,
                    }
                ]
            )
            repository.upsert_strategy_results(
                [
                    {
                        "code": "000001",
                        "name": "平安银行",
                        "strategy": "测试命中",
                        "target_date": "20260102",
                        "current_price": 1.3,
                        "current_volume": 120,
                    }
                ]
            )

            stocks = repository.list_stocks()
            history = repository.get_stock_history("000001", "20260101", "20260103")

            self.assertEqual(stocks[0].name, "平安银行")
            self.assertEqual(len(history), 2)
            self.assertEqual(history.iloc[-1]["close"], 1.2)
            with repository.connection() as conn:
                row = conn.execute(
                    """
                    SELECT COUNT(*), MAX(current_price)
                    FROM strategy_results
                    WHERE code = '000001'
                    """
                ).fetchone()
            self.assertEqual(row, (1, 1.3))

    def test_duckdb_repository_persists_scan_jobs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            from backend.infrastructure.persistence.duckdb_repository import DuckDBScanJobRepository
            from backend.domain.models import ScanJob, JobStatus

            db_path = str(Path(temp_dir) / "test.duckdb")
            job_repo = DuckDBScanJobRepository(db_path)

            job = ScanJob(
                job_id="job-1",
                status=JobStatus.QUEUED,
                start_date="20260101",
                end_date="20260102",
                target_dates=["20260102"],
            )
            job_repo.save(job)

            loaded = job_repo.get("job-1")
            self.assertEqual(loaded.status, JobStatus.QUEUED)

            loaded.mark_running()
            loaded.mark_completed(total_results=2)
            job_repo.save(loaded)

            updated = job_repo.get("job-1")
            self.assertEqual(updated.status, JobStatus.COMPLETED)
            self.assertEqual(updated.target_dates, ["20260102"])
            self.assertEqual(updated.total_results, 2)
            self.assertIsNotNone(updated.started_at)
            self.assertIsNotNone(updated.finished_at)

    def test_duckdb_repository_persists_unified_jobs_and_results(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = str(Path(temp_dir) / "test.duckdb")
            stock_repository = DuckDBStockRepository(db_path)
            job_repository = DuckDBJobRepository(db_path)

            job = Job(
                job_id="job-sync",
                type=JobType.SYNC,
                status=JobStatus.QUEUED,
                params={"scope": "daily", "start_date": "20260101"},
            )
            job_repository.save(job)
            job.mark_running()
            job.mark_completed(total_items=1, success_count=1, failed_count=0)
            job_repository.save(job)
            job_repository.save_sync_results([
                SyncResult(
                    job_id="job-sync",
                    scope="daily",
                    code="000001",
                    status="completed",
                    rows_written=2,
                )
            ])
            job_repository.save_backtest_results([
                BacktestResultRecord(
                    job_id="job-backtest",
                    stock_code="000001",
                    strategy_name="DualMATrendStrategyBT",
                    start_date="20260101",
                    end_date="20260102",
                    final_value=100100,
                    total_return=0.001,
                    annualized_return=0.1,
                    sharpe_ratio=1.2,
                    max_drawdown=0.02,
                    total_trades=1,
                    win_rate=1.0,
                )
            ])
            stock_repository.upsert_strategy_results(
                [
                    {
                        "code": "000001",
                        "name": "平安银行",
                        "strategy": "测试命中",
                        "target_date": "20260102",
                        "current_price": 1.2,
                        "current_volume": 100,
                    }
                ],
                job_id="job-a",
            )
            stock_repository.upsert_strategy_results(
                [
                    {
                        "code": "000001",
                        "name": "平安银行",
                        "strategy": "测试命中",
                        "target_date": "20260102",
                        "current_price": 1.3,
                        "current_volume": 120,
                    }
                ],
                job_id="job-b",
            )

            loaded_job = job_repository.get("job-sync")
            self.assertEqual(loaded_job.status, JobStatus.COMPLETED)
            self.assertEqual(job_repository.get_sync_results("job-sync")[0].rows_written, 2)
            self.assertEqual(job_repository.get_backtest_results("job-backtest")[0].win_rate, 1.0)
            self.assertEqual(stock_repository.get_strategy_results("job-a")[0].current_price, 1.2)
            self.assertEqual(stock_repository.get_strategy_results("job-b")[0].current_price, 1.3)

    def test_duckdb_repository_persists_sync_schedule(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = str(Path(temp_dir) / "test.duckdb")
            job_repository = DuckDBJobRepository(db_path)

            schedule = SyncSchedule(
                schedule_id="default",
                name="默认数据同步",
                enabled=True,
                scope="all",
                run_time="18:30",
                lookback_days=7,
                stock_codes=["000001"],
                last_job_id="job-1",
                last_run_at="2026-01-02T18:30:00",
                next_run_at="2026-01-03T18:30:00",
            )
            job_repository.save_sync_schedule(schedule)

            loaded = job_repository.get_sync_schedule("default")

            self.assertTrue(loaded.enabled)
            self.assertEqual(loaded.scope, "all")
            self.assertEqual(loaded.stock_codes, ["000001"])
            self.assertEqual(loaded.last_job_id, "job-1")

    def test_job_service_recovers_unfinished_jobs_after_restart(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = str(Path(temp_dir) / "test.duckdb")
            stock_repository = DuckDBStockRepository(db_path)
            job_repository = DuckDBJobRepository(db_path)
            running_job = Job(
                job_id="running-job",
                type=JobType.SYNC,
                status=JobStatus.RUNNING,
                params={"scope": "stocks"},
            )
            queued_job = Job(
                job_id="queued-job",
                type=JobType.SYNC,
                status=JobStatus.QUEUED,
                params={"scope": "stocks"},
            )
            completed_job = Job(
                job_id="completed-job",
                type=JobType.SYNC,
                status=JobStatus.COMPLETED,
                params={"scope": "stocks"},
            )
            job_repository.save(running_job)
            job_repository.save(queued_job)
            job_repository.save(completed_job)

            class StubSyncService:
                pass

            class StubBacktestService:
                pass

            service = ResearchJobService(
                stock_repository=stock_repository,
                job_repository=job_repository,
                app_config={"defaults": {"max_workers": 1}},
                sync_service=StubSyncService(),
                backtest_service=StubBacktestService(),
                auto_start=False,
            )

            recovered_count = service.recover_unfinished_jobs(reason="restart")

            self.assertEqual(recovered_count, 2)
            self.assertEqual(job_repository.get("running-job").status, JobStatus.FAILED)
            self.assertEqual(job_repository.get("queued-job").status, JobStatus.FAILED)
            self.assertEqual(job_repository.get("completed-job").status, JobStatus.COMPLETED)
            self.assertEqual(job_repository.get("running-job").error, "restart")

    def test_sync_schedule_service_triggers_due_schedule_once_per_day(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = str(Path(temp_dir) / "test.duckdb")
            job_repository = DuckDBJobRepository(db_path)
            submitted_jobs = []

            class StubJobService:
                def submit_sync(self, scope, start_date=None, end_date=None, stock_codes=None):
                    submitted_jobs.append(
                        {
                            "scope": scope,
                            "start_date": start_date,
                            "end_date": end_date,
                            "stock_codes": stock_codes,
                        }
                    )
                    return {"job_id": f"job-{len(submitted_jobs)}", "status": "queued"}

            service = SyncScheduleService(
                schedule_repository=job_repository,
                job_service=StubJobService(),
                clock=lambda: pd.Timestamp("2026-01-02 18:31:00").to_pydatetime(),
            )
            self.assertFalse(service.get_default_schedule()["enabled"])
            service.update_default_schedule(enabled=True, run_time="18:30", lookback_days=7)

            first_job = service.tick()
            second_job = service.tick()
            schedule = job_repository.get_sync_schedule("default")

            self.assertEqual(first_job["job_id"], "job-1")
            self.assertIsNone(second_job)
            self.assertEqual(len(submitted_jobs), 1)
            self.assertEqual(submitted_jobs[0]["scope"], "all")
            self.assertEqual(submitted_jobs[0]["start_date"], "20251226")
            self.assertEqual(submitted_jobs[0]["end_date"], "20260102")
            self.assertEqual(schedule.last_job_id, "job-1")
            self.assertEqual(schedule.next_run_at, "2026-01-03T18:30:00")

    def test_trade_data_service_fetches_missing_target_and_writes_to_duckdb(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = DuckDBStockRepository(str(Path(temp_dir) / "test.duckdb"))
            data_source = StubDataSource(_sample_daily_data())
            service = TradeDataService(repository=repository, data_source=data_source)

            history = service.get_history_for_scan(
                code="000001",
                name="平安银行",
                start_date="20260101",
                end_date="20260103",
                target_dates=["20260102"],
            )

            self.assertEqual(data_source.calls, 1)
            self.assertEqual(len(history), 2)
            self.assertEqual(
                repository.get_available_dates("000001", "20260101", "20260103"),
                {"20260101", "20260102"},
            )

    def test_trade_data_service_can_read_local_data_without_online_fetch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = DuckDBStockRepository(str(Path(temp_dir) / "test.duckdb"))
            repository.upsert_stocks([{"code": "000001", "name": "平安银行"}])
            repository.upsert_daily_data(_sample_daily_data())
            data_source = StubDataSource(_sample_daily_data())
            service = TradeDataService(
                repository=repository,
                data_source=data_source,
                allow_online_fetch=False,
            )

            history = service.get_history_for_scan(
                code="000001",
                name="平安银行",
                start_date="20260101",
                end_date="20260103",
                target_dates=["20260103"],
            )

            self.assertEqual(data_source.calls, 0)
            self.assertEqual(len(history), 2)
            self.assertEqual(history.iloc[-1]["date"].strftime("%Y%m%d"), "20260102")

    def test_trade_data_service_does_not_fetch_stock_list_when_online_fetch_disabled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = DuckDBStockRepository(str(Path(temp_dir) / "test.duckdb"))
            data_source = StubDataSource(_sample_daily_data())
            service = TradeDataService(
                repository=repository,
                data_source=data_source,
                allow_online_fetch=False,
            )

            stocks = service.list_stocks()

            self.assertEqual(list(stocks.columns), ["code", "name"])
            self.assertTrue(stocks.empty)
            self.assertEqual(data_source.calls, 0)

    def test_data_sync_service_uses_stub_source_and_records_results(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = str(Path(temp_dir) / "test.duckdb")
            stock_repository = DuckDBStockRepository(db_path)
            job_repository = DuckDBJobRepository(db_path)
            data_source = StubDataSource(_sample_daily_data())
            service = DataSyncService(
                stock_repository=stock_repository,
                job_repository=job_repository,
                data_source=data_source,
                stock_fetcher=lambda: pd.DataFrame([{"code": "000001", "name": "平安银行"}]),
            )

            summary = service.run(
                job_id="sync-1",
                scope="all",
                start_date="20260101",
                end_date="20260102",
                stock_codes=["000001"],
            )

            self.assertEqual(summary, {"total_items": 2, "success_count": 2, "failed_count": 0})
            self.assertEqual(data_source.calls, 1)
            self.assertEqual(len(stock_repository.get_stock_history("000001", "20260101", "20260102")), 2)
            self.assertEqual(len(job_repository.get_sync_results("sync-1")), 2)

    def test_data_sync_service_fetches_daily_data_in_parallel(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = str(Path(temp_dir) / "test.duckdb")
            stock_repository = DuckDBStockRepository(db_path)
            job_repository = DuckDBJobRepository(db_path)
            stock_repository.upsert_stocks([
                {"code": "000001", "name": "平安银行"},
                {"code": "000002", "name": "万科A"},
                {"code": "600000", "name": "浦发银行"},
            ])
            data_source = ParallelTrackingDataSource(_sample_daily_data())
            service = DataSyncService(
                stock_repository=stock_repository,
                job_repository=job_repository,
                data_source=data_source,
                daily_fetch_workers=3,
            )

            summary = service.run(
                job_id="sync-parallel",
                scope="daily",
                start_date="20260101",
                end_date="20260102",
            )

            self.assertEqual(summary, {"total_items": 3, "success_count": 3, "failed_count": 0})
            self.assertEqual(data_source.calls, 3)
            self.assertGreater(data_source.max_active_calls, 1)
            self.assertEqual(len(job_repository.get_sync_results("sync-parallel")), 3)

    def test_data_sync_service_times_out_stock_list_fetcher(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = str(Path(temp_dir) / "test.duckdb")
            stock_repository = DuckDBStockRepository(db_path)
            job_repository = DuckDBJobRepository(db_path)
            data_source = StubDataSource(_sample_daily_data())

            def slow_fetcher():
                time.sleep(0.2)
                return pd.DataFrame([{"code": "000001", "name": "平安银行"}])

            service = DataSyncService(
                stock_repository=stock_repository,
                job_repository=job_repository,
                data_source=data_source,
                stock_fetcher=slow_fetcher,
                stock_fetch_timeout=0.01,
            )

            with self.assertRaises(TimeoutError):
                service.run(
                    job_id="sync-timeout",
                    scope="stocks",
                    start_date=None,
                    end_date=None,
                )

    def test_backtrader_data_feed_uses_repository_standard_date_column(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = DuckDBStockRepository(str(Path(temp_dir) / "test.duckdb"))
            repository.upsert_stocks([{"code": "000001", "name": "平安银行"}])
            repository.upsert_daily_data(_sample_daily_data())

            data = load_stock_data_from_duckdb(repository, "000001", "20260101", "20260102")

            self.assertEqual(list(data.columns), ["date", "open", "high", "low", "close", "volume", "amount"])
            self.assertEqual(data.iloc[-1]["close"], 1.2)

    def test_scan_stock_data_returns_result_payload(self):
        results = scan_stock_data(
            code="000001",
            name="平安银行",
            hist_data=normalize_stock_data(_sample_daily_data()),
            target_dates=["20260102"],
            strategies=[AlwaysHitStrategy()],
        )

        self.assertEqual(
            results,
            [
                {
                    "code": "000001",
                    "name": "平安银行",
                    "strategy": "测试命中",
                    "target_date": "20260102",
                    "current_price": 1.2,
                    "current_volume": 100,
                }
            ],
        )

    def test_strategy_loader_uses_enabled_config_entries(self):
        strategies = load_strategies_from_config()
        strategy_names = {strategy.__class__.__name__ for strategy in strategies}

        self.assertIn("HighVolumeStrategy", strategy_names)
        self.assertIn("ContinuationGapStrategy", strategy_names)
        self.assertIn("TwoDayUpStrategy", strategy_names)


def _sample_daily_data():
    return pd.DataFrame(
        [
            {
                "stock_code": "000001",
                "date": "20260101",
                "open": 1.0,
                "close": 1.1,
                "high": 1.2,
                "low": 0.9,
                "volume": 90,
                "amount": 1000,
            },
            {
                "stock_code": "000001",
                "date": "20260102",
                "open": 1.1,
                "close": 1.2,
                "high": 1.3,
                "low": 1.0,
                "volume": 100,
                "amount": 1200,
            },
        ]
    )


if __name__ == "__main__":
    unittest.main()


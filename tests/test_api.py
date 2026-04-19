from contextlib import contextmanager
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.application.job_service import ResearchJobService
from backend.application.scan_service import ScanJobService
from backend.domain.models import BacktestResultRecord, SyncResult
from backend.infrastructure.persistence.duckdb_repository import (
    DuckDBJobRepository,
    DuckDBScanJobRepository,
    DuckDBStockRepository,
)


class ApiTest(unittest.TestCase):
    def test_health_and_strategies(self):
        with _test_client() as client:
            health = client.get("/api/v1/health")
            strategies = client.get("/api/v1/strategies")

            self.assertEqual(health.status_code, 200)
            self.assertEqual(health.json()["status"], "ok")
            self.assertTrue(health.json()["duckdb_path"].endswith("test.duckdb"))
            self.assertEqual(strategies.status_code, 200)
            self.assertIn("class_name", strategies.json()[0])
            self.assertIn("name", strategies.json()[0])

    def test_local_frontend_cors_preflight(self):
        with _test_client() as client:
            response = client.options(
                "/api/v1/syncs",
                headers={
                    "Origin": "http://127.0.0.1:8080",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type",
                },
            )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.headers["access-control-allow-origin"],
                "http://127.0.0.1:8080",
            )

    def test_create_scan_read_job_and_results(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = str(Path(temp_dir) / "test.duckdb")
            repository = DuckDBStockRepository(db_path)
            job_repository = DuckDBScanJobRepository(db_path)

            def runner(start_date, end_date, target_dates):
                results = [
                    {
                        "code": "000001",
                        "name": "平安银行",
                        "strategy": "测试命中",
                        "target_date": target_dates[0],
                        "current_price": 1.2,
                        "current_volume": 100,
                    }
                ]
                repository.upsert_strategy_results(results)
                return results

            job_service = ScanJobService(
                stock_repository=repository,
                job_repository=job_repository,
                app_config=_test_config(db_path),
                runner=runner,
                auto_start=False,
            )
            app = create_app(
                app_config=_test_config(db_path),
                repository=repository,
                job_repository=job_repository,
                job_service=job_service,
            )

            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/scans",
                    json={
                        "start": "20260101",
                        "end": "20260102",
                        "targets": ["20260102"],
                    },
                )
                self.assertEqual(response.status_code, 202)
                job_id = response.json()["job_id"]
                self.assertEqual(response.json()["status"], "queued")

                job_service.run_job(job_id)

                job_response = client.get(f"/api/v1/scans/{job_id}")
                result_response = client.get(f"/api/v1/scans/{job_id}/results")

                self.assertEqual(job_response.status_code, 200)
                self.assertEqual(job_response.json()["status"], "completed")
                self.assertEqual(job_response.json()["total_results"], 1)
                self.assertEqual(result_response.status_code, 200)
                self.assertEqual(result_response.json()[0]["code"], "000001")

    def test_invalid_scan_date_returns_400(self):
        with _test_client() as client:
            response = client.post(
                "/api/v1/scans",
                json={"start": "2026-01-01", "end": "20260102", "targets": ["20260102"]},
            )
            self.assertEqual(response.status_code, 400)

    def test_v2_sync_scan_backtest_job_routes(self):
        with _v2_test_client() as (client, job_service):
            sync_response = client.post(
                "/api/v1/syncs",
                json={"scope": "daily", "start": "20260101", "end": "20260102", "stock_codes": ["000001"]},
            )
            self.assertEqual(sync_response.status_code, 202)
            sync_job_id = sync_response.json()["job_id"]
            job_service.run_job(sync_job_id)

            sync_job = client.get(f"/api/v1/jobs/{sync_job_id}")
            sync_results = client.get(f"/api/v1/syncs/{sync_job_id}/results")
            sync_jobs = client.get("/api/v1/jobs", params={"type": "sync"})
            self.assertEqual(sync_job.json()["status"], "completed")
            self.assertEqual(sync_results.json()[0]["rows_written"], 2)
            self.assertEqual(sync_jobs.status_code, 200)
            self.assertEqual(sync_jobs.json()[0]["job_id"], sync_job_id)

            invalid_jobs = client.get("/api/v1/jobs", params={"type": "unknown"})
            self.assertEqual(invalid_jobs.status_code, 400)

            schedule = client.get("/api/v1/sync-schedules/default")
            self.assertEqual(schedule.status_code, 200)
            self.assertFalse(schedule.json()["enabled"])
            self.assertEqual(schedule.json()["scope"], "all")

            schedule_update = client.put(
                "/api/v1/sync-schedules/default",
                json={
                    "enabled": True,
                    "run_time": "18:30",
                    "lookback_days": 7,
                    "stock_codes": ["000001"],
                },
            )
            self.assertEqual(schedule_update.status_code, 200)
            self.assertTrue(schedule_update.json()["enabled"])
            self.assertEqual(schedule_update.json()["stock_codes"], ["000001"])

            scheduled_run = client.post("/api/v1/sync-schedules/default/run")
            self.assertEqual(scheduled_run.status_code, 202)
            scheduled_job_id = scheduled_run.json()["job_id"]
            job_service.run_job(scheduled_job_id)
            scheduled_results = client.get(f"/api/v1/syncs/{scheduled_job_id}/results")
            self.assertEqual(scheduled_results.json()[0]["rows_written"], 2)

            scan_response = client.post(
                "/api/v1/scans",
                json={"start": "20260101", "end": "20260102", "targets": ["20260102"]},
            )
            self.assertEqual(scan_response.status_code, 202)
            scan_job_id = scan_response.json()["job_id"]
            job_service.run_job(scan_job_id)

            scan_results = client.get(f"/api/v1/scans/{scan_job_id}/results")
            self.assertEqual(scan_results.json()[0]["job_id"], scan_job_id)

            scan_jobs = client.get("/api/v1/jobs", params={"type": "scan", "limit": 20})
            self.assertEqual(scan_jobs.status_code, 200)
            self.assertEqual(scan_jobs.json()[0]["job_id"], scan_job_id)
            self.assertEqual(scan_jobs.json()[0]["params"]["start_date"], "20260101")
            self.assertEqual(scan_jobs.json()[0]["params"]["target_dates"], ["20260102"])
            self.assertIsNone(scan_jobs.json()[0]["params"]["strategy_classes"])
            self.assertIsNone(job_service.seen_scan_strategy_classes[-1])

            selected_scan_response = client.post(
                "/api/v1/scans",
                json={
                    "start": "20260101",
                    "end": "20260102",
                    "targets": ["20260102"],
                    "strategy_classes": ["HighVolumeStrategy"],
                },
            )
            self.assertEqual(selected_scan_response.status_code, 202)
            selected_scan_job_id = selected_scan_response.json()["job_id"]
            selected_scan_job = client.get(f"/api/v1/jobs/{selected_scan_job_id}")
            self.assertEqual(
                selected_scan_job.json()["params"]["strategy_classes"],
                ["HighVolumeStrategy"],
            )
            job_service.run_job(selected_scan_job_id)
            self.assertEqual(job_service.seen_scan_strategy_classes[-1], ["HighVolumeStrategy"])

            empty_strategy_scan = client.post(
                "/api/v1/scans",
                json={
                    "start": "20260101",
                    "end": "20260102",
                    "targets": ["20260102"],
                    "strategy_classes": [],
                },
            )
            self.assertEqual(empty_strategy_scan.status_code, 400)

            unsupported_strategy_scan = client.post(
                "/api/v1/scans",
                json={
                    "start": "20260101",
                    "end": "20260102",
                    "targets": ["20260102"],
                    "strategy_classes": ["DualMATrendStrategyBT"],
                },
            )
            self.assertEqual(unsupported_strategy_scan.status_code, 400)

            backtest_response = client.post(
                "/api/v1/backtests",
                json={
                    "strategy": "DualMATrendStrategyBT",
                    "start": "20260101",
                    "end": "20260102",
                    "stock_codes": ["000001"],
                    "commission": 0.0003,
                    "slippage": 0.001,
                },
            )
            self.assertEqual(backtest_response.status_code, 202)
            backtest_job_id = backtest_response.json()["job_id"]
            job_service.run_job(backtest_job_id)

            backtest_results = client.get(f"/api/v1/backtests/{backtest_job_id}/results")
            self.assertEqual(backtest_results.json()[0]["strategy_name"], "DualMATrendStrategyBT")

            unsupported = client.post(
                "/api/v1/backtests",
                json={
                    "strategy": "UnsupportedStrategy",
                    "start": "20260101",
                    "end": "20260102",
                    "stock_codes": ["000001"],
                    "commission": 0.0003,
                    "slippage": 0.001,
                },
            )
            self.assertEqual(unsupported.status_code, 400)


@contextmanager
def _test_client():
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = str(Path(temp_dir) / "test.duckdb")
        repository = DuckDBStockRepository(db_path)
        job_repository = DuckDBScanJobRepository(db_path)
        app_config = _test_config(db_path)
        job_service = ScanJobService(
            stock_repository=repository,
            job_repository=job_repository,
            app_config=app_config,
            runner=lambda start_date, end_date, target_dates: [],
            auto_start=False,
        )
        app = create_app(
            app_config=app_config,
            repository=repository,
            job_repository=job_repository,
            job_service=job_service,
        )
        with TestClient(app) as client:
            yield client


@contextmanager
def _v2_test_client():
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = str(Path(temp_dir) / "test.duckdb")
        repository = DuckDBStockRepository(db_path)
        scan_job_repository = DuckDBScanJobRepository(db_path)
        job_repository = DuckDBJobRepository(db_path)
        app_config = _test_config(db_path)

        class StubSyncService:
            def __init__(self, repo):
                self.repo = repo

            def run(self, job_id, scope, start_date, end_date, stock_codes=None):
                self.repo.save_sync_results([
                    SyncResult(
                        job_id=job_id,
                        scope=scope,
                        code="000001",
                        status="completed",
                        rows_written=2,
                    )
                ])
                return {"total_items": 1, "success_count": 1, "failed_count": 0}

        class StubBacktestService:
            def __init__(self, repo):
                self.repo = repo

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
                self.repo.save_backtest_results([
                    BacktestResultRecord(
                        job_id=job_id,
                        stock_code="000001",
                        strategy_name=strategy,
                        start_date=start_date,
                        end_date=end_date,
                        final_value=100100,
                        total_return=0.001,
                        annualized_return=0.1,
                        sharpe_ratio=1.0,
                        max_drawdown=0.02,
                        total_trades=1,
                        win_rate=1.0,
                    )
                ])
                return {"total_items": 1, "success_count": 1, "failed_count": 0}

        seen_scan_strategy_classes = []

        def scan_runner(start_date, end_date, target_dates, job_id=None, strategy_classes=None):
            seen_scan_strategy_classes.append(strategy_classes)
            results = [
                {
                    "code": "000001",
                    "name": "平安银行",
                    "strategy": "测试命中",
                    "target_date": target_dates[0],
                    "current_price": 1.2,
                    "current_volume": 100,
                }
            ]
            repository.upsert_strategy_results(results, job_id=job_id)
            return results

        job_service = ResearchJobService(
            stock_repository=repository,
            job_repository=job_repository,
            app_config=app_config,
            sync_service=StubSyncService(job_repository),
            backtest_service=StubBacktestService(job_repository),
            scan_runner=scan_runner,
            auto_start=False,
        )
        job_service.seen_scan_strategy_classes = seen_scan_strategy_classes
        app = create_app(
            app_config=app_config,
            repository=repository,
            job_repository=scan_job_repository,
            unified_job_repository=job_repository,
            job_service=job_service,
        )
        with TestClient(app) as client:
            yield client, job_service


def _test_config(db_path):
    return {
        "logging": {"level": "INFO", "format": "%(asctime)s - %(levelname)s - %(message)s"},
        "data_source": {"provider": "tencent", "timeout": 10.0},
        "storage": {"duckdb_path": str(db_path)},
        "trade_calendar": {"dates": ["20260101", "20260102"]},
        "strategies": {
            "HighVolumeStrategy": {"enabled": True},
            "LongLowerShadowReboundStrategy": {"enabled": False},
            "ContinuationGapStrategy": {"enabled": True},
            "ThreeRisingPatternStrategy": {"enabled": False},
            "TwoDayUpStrategy": {"enabled": True},
            "BreakM100": {"enabled": False},
        },
        "defaults": {"check_days": 60, "max_workers": 1},
    }


if __name__ == "__main__":
    unittest.main()


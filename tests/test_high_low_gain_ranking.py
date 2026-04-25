import tempfile
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.application.job_service import ResearchJobService
from backend.infrastructure.persistence.duckdb_repository import (
    DuckDBJobRepository,
    DuckDBScanJobRepository,
    DuckDBStockRepository,
)


def test_duckdb_high_low_gain_rank_orders_by_gain_desc_and_filters_invalid_data():
    with tempfile.TemporaryDirectory() as temp_dir:
        repository = DuckDBStockRepository(str(Path(temp_dir) / "test.duckdb"))
        _seed_ranking_data(repository)

        ranks = repository.list_high_low_gain_rank("20260101", "20260103", limit=3)

        assert [item.code for item in ranks] == ["000005", "000002", "000001"]
        beta = ranks[1]
        assert beta.name == "Beta"
        assert beta.lowest_price == 5.0
        assert beta.lowest_date == "20260101"
        assert beta.highest_price == 9.0
        assert beta.highest_date == "20260103"
        assert beta.gain_rate == 0.8
        assert beta.gain_percent == 80.0
        assert beta.trade_days == 3


def test_duckdb_high_low_gain_rank_supports_direction_and_min_percent():
    with tempfile.TemporaryDirectory() as temp_dir:
        repository = DuckDBStockRepository(str(Path(temp_dir) / "test.duckdb"))
        _seed_ranking_data(repository)

        up_ranks = repository.list_high_low_gain_rank(
            "20260101",
            "20260103",
            limit=10,
            direction="up",
            min_gain_percent=60,
        )
        assert [item.code for item in up_ranks] == ["000002"]
        assert up_ranks[0].lowest_date < up_ranks[0].highest_date

        down_ranks = repository.list_high_low_gain_rank(
            "20260101",
            "20260103",
            limit=10,
            direction="down",
            min_gain_percent=30,
        )
        assert [item.code for item in down_ranks] == ["000005"]
        assert down_ranks[0].highest_date < down_ranks[0].lowest_date
        assert down_ranks[0].highest_price == 20.0
        assert down_ranks[0].lowest_price == 10.0
        assert down_ranks[0].gain_rate == pytest.approx(0.5)
        assert down_ranks[0].gain_percent == pytest.approx(50.0)


def test_high_low_gain_rank_api_returns_sorted_results_and_validates_inputs():
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = str(Path(temp_dir) / "test.duckdb")
        scan_db_path = str(Path(temp_dir) / "scan.duckdb")
        job_db_path = str(Path(temp_dir) / "jobs.duckdb")
        repository = DuckDBStockRepository(db_path)
        scan_job_repository = DuckDBScanJobRepository(scan_db_path)
        job_repository = DuckDBJobRepository(job_db_path)
        _seed_ranking_data(repository)

        job_service = ResearchJobService(
            stock_repository=repository,
            job_repository=job_repository,
            app_config=_test_config(db_path),
            sync_service=_StubSyncService(),
            backtest_service=_StubBacktestService(),
            auto_start=False,
        )
        app = create_app(
            app_config=_test_config(db_path),
            repository=repository,
            job_repository=scan_job_repository,
            unified_job_repository=job_repository,
            job_service=job_service,
        )

        with TestClient(app) as client:
            response = client.get(
                "/api/v1/rankings/high-low-gain",
                params={"start": "20260101", "end": "20260103", "limit": 1},
            )
            assert response.status_code == 200
            assert response.json()[0]["code"] == "000005"
            assert response.json()[0]["gain_percent"] == 100.0
            assert len(response.json()) == 1

            invalid_date = client.get(
                "/api/v1/rankings/high-low-gain",
                params={"start": "2026-01-01", "end": "20260103"},
            )
            assert invalid_date.status_code == 400

            invalid_range = client.get(
                "/api/v1/rankings/high-low-gain",
                params={"start": "20260103", "end": "20260101"},
            )
            assert invalid_range.status_code == 400

            invalid_limit = client.get(
                "/api/v1/rankings/high-low-gain",
                params={"start": "20260101", "end": "20260103", "limit": 0},
            )
            assert invalid_limit.status_code == 422

            directional = client.get(
                "/api/v1/rankings/high-low-gain",
                params={
                    "start": "20260101",
                    "end": "20260103",
                    "direction": "down",
                    "min_gain_percent": 30,
                },
            )
            assert directional.status_code == 200
            assert directional.json()[0]["code"] == "000005"
            assert directional.json()[0]["highest_date"] < directional.json()[0]["lowest_date"]

            invalid_direction = client.get(
                "/api/v1/rankings/high-low-gain",
                params={"start": "20260101", "end": "20260103", "direction": "sideways"},
            )
            assert invalid_direction.status_code == 400

            invalid_min_gain = client.get(
                "/api/v1/rankings/high-low-gain",
                params={"start": "20260101", "end": "20260103", "min_gain_percent": -1},
            )
            assert invalid_min_gain.status_code == 422


def test_high_low_gain_rank_api_returns_empty_list_when_no_local_data():
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = str(Path(temp_dir) / "test.duckdb")
        scan_db_path = str(Path(temp_dir) / "scan.duckdb")
        job_db_path = str(Path(temp_dir) / "jobs.duckdb")
        repository = DuckDBStockRepository(db_path)
        scan_job_repository = DuckDBScanJobRepository(scan_db_path)
        job_repository = DuckDBJobRepository(job_db_path)
        repository.upsert_stocks([{"code": "000001", "name": "Alpha"}])
        job_service = ResearchJobService(
            stock_repository=repository,
            job_repository=job_repository,
            app_config=_test_config(db_path),
            sync_service=_StubSyncService(),
            backtest_service=_StubBacktestService(),
            auto_start=False,
        )
        app = create_app(
            app_config=_test_config(db_path),
            repository=repository,
            job_repository=scan_job_repository,
            unified_job_repository=job_repository,
            job_service=job_service,
        )

        with TestClient(app) as client:
            response = client.get(
                "/api/v1/rankings/high-low-gain",
                params={"start": "20260101", "end": "20260103"},
            )
            assert response.status_code == 200
            assert response.json() == []


def _seed_ranking_data(repository):
    repository.upsert_stocks([
        {"code": "000001", "name": "Alpha"},
        {"code": "000002", "name": "Beta"},
        {"code": "000003", "name": "InvalidLow"},
        {"code": "000004", "name": "NoData"},
        {"code": "000005", "name": "Reversal"},
    ])
    repository.upsert_daily_data(pd.DataFrame([
        {"stock_code": "000001", "date": "20260101", "open": 10, "close": 11, "high": 12, "low": 10, "volume": 1},
        {"stock_code": "000001", "date": "20260102", "open": 11, "close": 12, "high": 15, "low": 11, "volume": 1},
        {"stock_code": "000001", "date": "20260103", "open": 12, "close": 13, "high": 14, "low": 12, "volume": 1},
        {"stock_code": "000002", "date": "20260101", "open": 5, "close": 6, "high": 6, "low": 5, "volume": 1},
        {"stock_code": "000002", "date": "20260102", "open": 6, "close": 7, "high": 8, "low": 6, "volume": 1},
        {"stock_code": "000002", "date": "20260103", "open": 7, "close": 8, "high": 9, "low": 7, "volume": 1},
        {"stock_code": "000003", "date": "20260101", "open": 1, "close": 1, "high": 10, "low": 0, "volume": 1},
        {"stock_code": "000005", "date": "20260101", "open": 18, "close": 19, "high": 20, "low": 18, "volume": 1},
        {"stock_code": "000005", "date": "20260102", "open": 14, "close": 11, "high": 16, "low": 10, "volume": 1},
        {"stock_code": "000005", "date": "20260103", "open": 12, "close": 13, "high": 14, "low": 12, "volume": 1},
    ]))


class _StubSyncService:
    def run(self, *args, **kwargs):
        return {"total_items": 0, "success_count": 0, "failed_count": 0}


class _StubBacktestService:
    def list_supported_strategies(self):
        return ["DualMATrendStrategyBT"]

    def run(self, *args, **kwargs):
        return {"total_items": 0, "success_count": 0, "failed_count": 0}


def _test_config(db_path):
    return {
        "logging": {"level": "INFO", "format": "%(asctime)s - %(levelname)s - %(message)s"},
        "data_source": {"provider": "tencent", "timeout": 10.0},
        "storage": {"duckdb_path": str(db_path)},
        "trade_calendar": {"dates": ["20260101", "20260102", "20260103"]},
        "strategies": {},
        "defaults": {"check_days": 60, "max_workers": 1},
    }

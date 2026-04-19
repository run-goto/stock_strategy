import pandas as pd

from backend.application.screening import StrategyExecutor, scan_stock_data
from backend.domain.strategy import BaseStrategy


class AlwaysHitStrategy(BaseStrategy):
    def __init__(self, name="always-hit"):
        super().__init__(name)

    def check(self, hist_data: pd.DataFrame) -> bool:
        return True


class ExplodingStrategy(BaseStrategy):
    def __init__(self):
        super().__init__("exploding")

    def check(self, hist_data: pd.DataFrame) -> bool:
        raise RuntimeError("boom")


class CloseAboveStrategy(BaseStrategy):
    def __init__(self, threshold: float):
        super().__init__("close-above")
        self.threshold = threshold
        self.seen_last_dates = []

    def check(self, hist_data: pd.DataFrame) -> bool:
        self.seen_last_dates.append(hist_data.iloc[-1]["date"].strftime("%Y%m%d"))
        return float(hist_data.iloc[-1]["close"]) > self.threshold


class FakeTradeDataService:
    def __init__(self, stocks, histories, failing_codes=None):
        self.stocks = pd.DataFrame(stocks)
        self.histories = histories
        self.failing_codes = set(failing_codes or [])
        self.history_requests = []

    def list_stocks(self) -> pd.DataFrame:
        return self.stocks

    def get_history_for_scan(self, code, name, start_date, end_date, target_dates) -> pd.DataFrame:
        self.history_requests.append((code, name, start_date, end_date, target_dates))
        if code in self.failing_codes:
            raise RuntimeError(f"history unavailable for {code}")
        return self.histories[code]


class FakeStrategyRepository:
    def __init__(self):
        self.saved_results = None
        self.saved_job_id = None

    def upsert_strategy_results(self, results, job_id=None):
        self.saved_results = list(results)
        self.saved_job_id = job_id


def test_scan_stock_data_runs_strategy_on_each_target_date_slice():
    strategy = CloseAboveStrategy(threshold=10.5)
    data = _history(
        [
            ("20260101", 10.0, 100),
            ("20260102", 10.8, 120),
            ("20260103", 10.2, 130),
        ]
    )

    results = scan_stock_data(
        code="000001",
        name="Alpha",
        hist_data=data,
        target_dates=["20260101", "20260102", "20260103"],
        strategies=[strategy],
    )

    assert strategy.seen_last_dates == ["20260101", "20260102", "20260103"]
    assert results == [
        {
            "code": "000001",
            "name": "Alpha",
            "strategy": "close-above",
            "target_date": "20260102",
            "current_price": 10.8,
            "current_volume": 120,
        }
    ]


def test_scan_stock_data_continues_when_one_strategy_raises():
    data = _history([("20260101", 10.0, 100), ("20260102", 11.0, 120)])

    results = scan_stock_data(
        code="000001",
        name="Alpha",
        hist_data=data,
        target_dates=["20260102"],
        strategies=[ExplodingStrategy(), AlwaysHitStrategy()],
    )

    assert results == [
        {
            "code": "000001",
            "name": "Alpha",
            "strategy": "always-hit",
            "target_date": "20260102",
            "current_price": 11.0,
            "current_volume": 120,
        }
    ]


def test_strategy_executor_runs_all_stocks_and_persists_results_with_job_id():
    trade_data_service = FakeTradeDataService(
        stocks=[
            {"code": "000001", "name": "Alpha"},
            {"code": "000002", "name": "Beta"},
        ],
        histories={
            "000001": _history([("20260101", 10.0, 100), ("20260102", 11.0, 120)]),
            "000002": _history([("20260101", 20.0, 200), ("20260102", 21.0, 220)]),
        },
    )
    repository = FakeStrategyRepository()
    executor = StrategyExecutor(
        trade_data_service=trade_data_service,
        repository=repository,
        strategies=[AlwaysHitStrategy()],
        max_workers=1,
    )

    results = executor.run(
        start_date="20260101",
        end_date="20260102",
        target_dates=["20260102"],
        job_id="scan-job-1",
    )

    assert len(results) == 2
    assert {result["code"] for result in results} == {"000001", "000002"}
    assert repository.saved_results == results
    assert repository.saved_job_id == "scan-job-1"
    assert trade_data_service.history_requests == [
        ("000001", "Alpha", "20260101", "20260102", ["20260102"]),
        ("000002", "Beta", "20260101", "20260102", ["20260102"]),
    ]


def test_strategy_executor_skips_one_stock_when_history_fetch_fails():
    trade_data_service = FakeTradeDataService(
        stocks=[
            {"code": "000001", "name": "Alpha"},
            {"code": "000002", "name": "Beta"},
        ],
        histories={
            "000001": _history([("20260101", 10.0, 100), ("20260102", 11.0, 120)]),
            "000002": _history([("20260101", 20.0, 200), ("20260102", 21.0, 220)]),
        },
        failing_codes={"000002"},
    )
    repository = FakeStrategyRepository()
    executor = StrategyExecutor(
        trade_data_service=trade_data_service,
        repository=repository,
        strategies=[AlwaysHitStrategy()],
        max_workers=1,
    )

    results = executor.run(
        start_date="20260101",
        end_date="20260102",
        target_dates=["20260102"],
        job_id="scan-job-2",
    )

    assert results == [
        {
            "code": "000001",
            "name": "Alpha",
            "strategy": "always-hit",
            "target_date": "20260102",
            "current_price": 11.0,
            "current_volume": 120,
        }
    ]
    assert repository.saved_results == results
    assert repository.saved_job_id == "scan-job-2"


def _history(rows):
    return pd.DataFrame(
        [
            {
                "date": pd.Timestamp(date),
                "open": close - 0.1,
                "close": close,
                "high": close + 0.2,
                "low": close - 0.2,
                "volume": volume,
                "amount": close * volume,
            }
            for date, close, volume in rows
        ]
    )

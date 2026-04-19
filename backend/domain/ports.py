"""领域端口 — 仓储与外部数据源的抽象接口。

领域层和应用层仅依赖这些端口，基础设施层提供具体实现。
"""

from abc import ABC, abstractmethod

import pandas as pd

from backend.domain.models import BacktestResultRecord, Job, ScanJob, Stock, StrategyHit, SyncResult, SyncSchedule


class StockRepository(ABC):
    """股票数据仓储端口。"""

    @abstractmethod
    def list_stocks(self) -> list[Stock]:
        ...

    @abstractmethod
    def get_stock_history(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        ...

    @abstractmethod
    def upsert_stocks(self, stocks: list[Stock]) -> None:
        ...

    @abstractmethod
    def upsert_daily_data(self, data: pd.DataFrame, source: str | None = None) -> None:
        ...

    @abstractmethod
    def upsert_strategy_results(self, results: list[StrategyHit], job_id: str | None = None) -> None:
        ...

    @abstractmethod
    def get_available_dates(self, code: str, start_date: str, end_date: str) -> set[str]:
        ...

    @abstractmethod
    def get_strategy_results(self, job_id: str) -> list[StrategyHit]:
        ...


class ScanJobRepository(ABC):
    """扫描任务仓储端口。"""

    @abstractmethod
    def save(self, job: ScanJob) -> None:
        ...

    @abstractmethod
    def get(self, job_id: str) -> ScanJob | None:
        ...

    @abstractmethod
    def list_jobs(self, limit: int = 100) -> list[ScanJob]:
        ...

    @abstractmethod
    def get_results(self, job: ScanJob) -> list[StrategyHit]:
        ...


class JobRepository(ABC):
    """Unified async job repository."""

    @abstractmethod
    def save(self, job: Job) -> None:
        ...

    @abstractmethod
    def get(self, job_id: str) -> Job | None:
        ...

    @abstractmethod
    def list_jobs(self, limit: int = 100) -> list[Job]:
        ...

    @abstractmethod
    def save_sync_results(self, results: list[SyncResult]) -> None:
        ...

    @abstractmethod
    def get_sync_results(self, job_id: str) -> list[SyncResult]:
        ...

    @abstractmethod
    def save_backtest_results(self, results: list[BacktestResultRecord]) -> None:
        ...

    @abstractmethod
    def get_backtest_results(self, job_id: str) -> list[BacktestResultRecord]:
        ...


class SyncScheduleRepository(ABC):
    """Persistent sync schedule repository."""

    @abstractmethod
    def get_sync_schedule(self, schedule_id: str) -> SyncSchedule | None:
        ...

    @abstractmethod
    def save_sync_schedule(self, schedule: SyncSchedule) -> None:
        ...


class MarketDataSource(ABC):
    """行情数据源端口。"""

    @abstractmethod
    def fetch_daily_data(
        self,
        stock_code: str,
        market_code: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """获取日线数据，返回标准化 DataFrame。"""
        ...


"""Application service interfaces.

This module keeps application-level contracts in one place before concrete
workflow implementations.  The three main directions are:

- data synchronization
- strategy execution
- task execution
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

import pandas as pd

from backend.domain.models import Job

DATA_SYNC_SCOPES = frozenset({"stocks", "daily", "all"})


class DataSyncRunner(ABC):
    """Contract for importing market data into local storage."""

    @abstractmethod
    def run(
        self,
        job_id: str,
        scope: str,
        start_date: str | None,
        end_date: str | None,
        stock_codes: list[str] | None = None,
    ) -> dict:
        ...


class TradeDataProvider(ABC):
    """Contract for reading market data used by strategy execution."""

    @abstractmethod
    def list_stocks(self) -> pd.DataFrame:
        ...

    @abstractmethod
    def get_history_for_scan(
        self,
        code: str,
        name: str,
        start_date: str,
        end_date: str,
        target_dates: list[str],
    ) -> pd.DataFrame:
        ...


class StrategyExecutionRunner(ABC):
    """Contract for executing configured stock-picking strategies."""

    @abstractmethod
    def run(
        self,
        start_date: str,
        end_date: str,
        target_dates: list[str],
        job_id: str | None = None,
    ) -> list[dict]:
        ...


class StrategyScanRunner(Protocol):
    """Callable contract used by task execution to launch a scan workflow."""

    def __call__(
        self,
        start_date: str,
        end_date: str,
        target_dates: list[str],
        job_id: str | None = None,
        strategy_classes: list[str] | None = None,
    ) -> list[dict]:
        ...


class BacktestRunner(ABC):
    """Contract for executing a backtest and persisting its result rows."""

    @abstractmethod
    def list_supported_strategies(self) -> list[str]:
        ...

    @abstractmethod
    def run(
        self,
        job_id: str,
        strategy: str,
        start_date: str,
        end_date: str,
        stock_codes: list[str] | None = None,
        scan_job_id: str | None = None,
        initial_cash: float = 100000,
        commission: float = 0.0003,
        slippage: float = 0.0,
    ) -> dict:
        ...


class SyncTaskSubmitter(Protocol):
    """Minimal task contract needed by scheduled sync orchestration."""

    def submit_sync(
        self,
        scope: str,
        start_date: str | None = None,
        end_date: str | None = None,
        stock_codes: list[str] | None = None,
    ) -> dict:
        ...


class JobHandler(ABC):
    """Contract for executing one persisted job type."""

    @abstractmethod
    def run(self, job: Job) -> dict:
        ...


class TradeCalendarProvider(ABC):
    """Contract for resolving trading date ranges and target dates."""

    @abstractmethod
    def recent_range(self, n_days: int = 60) -> tuple[str, str]:
        ...

    @abstractmethod
    def normalize_targets(self, target_dates: list[str]) -> list[str]:
        ...


class TaskExecutionService(ABC):
    """Contract for creating, running, and querying asynchronous jobs."""

    @abstractmethod
    def submit_sync(
        self,
        scope: str,
        start_date: str | None = None,
        end_date: str | None = None,
        stock_codes: list[str] | None = None,
    ) -> dict:
        ...

    @abstractmethod
    def submit_scan(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        target_dates: list[str] | None = None,
        strategy_classes: list[str] | None = None,
    ) -> dict:
        ...

    @abstractmethod
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
        ...

    @abstractmethod
    def run_job(self, job_id: str) -> None:
        ...

    @abstractmethod
    def get_unified_job(self, job_id: str) -> dict | None:
        ...

    @abstractmethod
    def list_unified_jobs(self, job_type: str | None = None, limit: int = 100) -> list[dict]:
        ...

    @abstractmethod
    def get_scan_job(self, job_id: str) -> dict | None:
        ...

    @abstractmethod
    def get_results(self, job_id: str) -> list[dict]:
        ...

    @abstractmethod
    def get_sync_results(self, job_id: str) -> list[dict]:
        ...

    @abstractmethod
    def get_backtest_results(self, job_id: str) -> list[dict]:
        ...

    @abstractmethod
    def shutdown(self) -> None:
        ...

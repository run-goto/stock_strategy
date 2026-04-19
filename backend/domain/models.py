"""领域模型：纯数据结构 + 业务规则，零外部依赖。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


# ---------------------------------------------------------------------------
# Value Objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Stock:
    """股票基本信息。"""

    code: str
    name: str


@dataclass(frozen=True)
class DailyBar:
    """单日行情数据（OHLCV）。"""

    stock_code: str
    date: str  # YYYYMMDD
    open: float | None = None
    close: float | None = None
    high: float | None = None
    low: float | None = None
    volume: int | None = None
    amount: float | None = None


@dataclass(frozen=True)
class StrategyHit:
    """策略命中结果。"""

    code: str
    name: str
    strategy: str
    target_date: str
    current_price: float | None = None
    current_volume: int | None = None
    created_at: str | None = None
    job_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "code": self.code,
            "name": self.name,
            "strategy": self.strategy,
            "target_date": self.target_date,
            "current_price": self.current_price,
            "current_volume": self.current_volume,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Aggregate Root: ScanJob
# ---------------------------------------------------------------------------


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobType(str, Enum):
    SYNC = "sync"
    SCAN = "scan"
    BACKTEST = "backtest"


@dataclass
class Job:
    """Unified async job for sync, scan, and backtest pipelines."""

    job_id: str
    type: JobType
    status: JobStatus
    params: dict = field(default_factory=dict)
    total_items: int = 0
    success_count: int = 0
    failed_count: int = 0
    error: str | None = None
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None

    def mark_running(self) -> None:
        if self.status != JobStatus.QUEUED:
            raise ValueError(f"只有 queued 状态的任务可以启动，当前: {self.status}")
        self.status = JobStatus.RUNNING
        self.started_at = datetime.now().isoformat()

    def mark_completed(
        self,
        total_items: int = 0,
        success_count: int = 0,
        failed_count: int = 0,
    ) -> None:
        if self.status != JobStatus.RUNNING:
            raise ValueError(f"只有 running 状态的任务可以完成，当前: {self.status}")
        self.status = JobStatus.COMPLETED
        self.total_items = total_items
        self.success_count = success_count
        self.failed_count = failed_count
        self.finished_at = datetime.now().isoformat()

    def mark_failed(self, error: str) -> None:
        if self.status != JobStatus.RUNNING:
            raise ValueError(f"只有 running 状态的任务可以失败，当前: {self.status}")
        self.status = JobStatus.FAILED
        self.error = error
        self.finished_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "type": self.type.value,
            "status": self.status.value,
            "params": self.params,
            "total_items": self.total_items,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


@dataclass(frozen=True)
class SyncResult:
    """Per-symbol sync outcome."""

    job_id: str
    scope: str
    code: str | None
    status: str
    rows_written: int = 0
    message: str | None = None
    created_at: str | None = None

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "scope": self.scope,
            "code": self.code,
            "status": self.status,
            "rows_written": self.rows_written,
            "message": self.message,
            "created_at": self.created_at,
        }


@dataclass
class SyncSchedule:
    """Persistent schedule for local stock data synchronization."""

    schedule_id: str
    name: str
    enabled: bool
    scope: str
    run_time: str
    lookback_days: int
    stock_codes: list[str] | None = None
    last_job_id: str | None = None
    last_run_at: str | None = None
    next_run_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict:
        return {
            "schedule_id": self.schedule_id,
            "name": self.name,
            "enabled": self.enabled,
            "scope": self.scope,
            "run_time": self.run_time,
            "lookback_days": self.lookback_days,
            "stock_codes": self.stock_codes,
            "last_job_id": self.last_job_id,
            "last_run_at": self.last_run_at,
            "next_run_at": self.next_run_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class BacktestResultRecord:
    """Persisted summary for one stock in one backtest job."""

    job_id: str
    stock_code: str
    strategy_name: str
    start_date: str
    end_date: str
    final_value: float
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    max_drawdown: float
    total_trades: int
    win_rate: float
    created_at: str | None = None

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "stock_code": self.stock_code,
            "strategy_name": self.strategy_name,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "final_value": self.final_value,
            "total_return": self.total_return,
            "annualized_return": self.annualized_return,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "total_trades": self.total_trades,
            "win_rate": self.win_rate,
            "created_at": self.created_at,
        }


@dataclass
class ScanJob:
    """扫描任务聚合根，包含状态机逻辑。"""

    job_id: str
    status: JobStatus
    start_date: str
    end_date: str
    target_dates: list[str]
    total_results: int = 0
    error: str | None = None
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None

    # -- 状态机方法 --

    def mark_running(self) -> None:
        if self.status != JobStatus.QUEUED:
            raise ValueError(f"只有 queued 状态的任务可以启动，当前: {self.status}")
        self.status = JobStatus.RUNNING
        self.started_at = datetime.now().isoformat()

    def mark_completed(self, total_results: int) -> None:
        if self.status != JobStatus.RUNNING:
            raise ValueError(f"只有 running 状态的任务可以完成，当前: {self.status}")
        self.status = JobStatus.COMPLETED
        self.total_results = total_results
        self.finished_at = datetime.now().isoformat()

    def mark_failed(self, error: str) -> None:
        if self.status != JobStatus.RUNNING:
            raise ValueError(f"只有 running 状态的任务可以失败，当前: {self.status}")
        self.status = JobStatus.FAILED
        self.error = error
        self.finished_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "target_dates": self.target_dates,
            "total_results": self.total_results,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


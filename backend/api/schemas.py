from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    duckdb_path: str
    current_time: str


class StrategyInfo(BaseModel):
    class_name: str
    name: str


class ScanRequest(BaseModel):
    start: str | None = None
    end: str | None = None
    targets: list[str] | None = None
    strategy_classes: list[str] | None = None


class ScanCreatedResponse(BaseModel):
    job_id: str
    status: str
    start_date: str
    end_date: str
    target_dates: list[str]


class ScanJobResponse(BaseModel):
    job_id: str
    type: str | None = None
    status: str
    start_date: str
    end_date: str
    target_dates: list[str]
    total_results: int
    total_items: int | None = None
    success_count: int | None = None
    failed_count: int | None = None
    error: str | None = None
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


class StrategyResultResponse(BaseModel):
    job_id: str | None = None
    code: str
    name: str
    strategy: str
    target_date: str
    current_price: float | None = None
    current_volume: int | None = None
    created_at: str | None = None


class SyncRequest(BaseModel):
    scope: Literal["stocks", "daily", "all"]
    start: str | None = None
    end: str | None = None
    stock_codes: list[str] | None = None


class SyncScheduleUpdateRequest(BaseModel):
    enabled: bool | None = None
    scope: Literal["stocks", "daily", "all"] | None = None
    run_time: str | None = None
    lookback_days: int | None = None
    stock_codes: list[str] | None = None


class BacktestRequest(BaseModel):
    strategy: str
    start: str
    end: str
    stock_codes: list[str] | None = None
    scan_job_id: str | None = None
    initial_cash: float = 100000
    commission: float
    slippage: float


class JobResponse(BaseModel):
    job_id: str
    type: str
    status: str
    params: dict
    total_items: int
    success_count: int
    failed_count: int
    error: str | None = None
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


class SyncCreatedResponse(JobResponse):
    pass


class BacktestCreatedResponse(JobResponse):
    pass


class SyncResultResponse(BaseModel):
    job_id: str
    scope: str
    code: str | None = None
    status: str
    rows_written: int
    message: str | None = None
    created_at: str | None = None


class SyncScheduleResponse(BaseModel):
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


class BacktestResultResponse(BaseModel):
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


class HighLowGainRankResponse(BaseModel):
    code: str
    name: str
    start: str
    end: str
    lowest_price: float
    lowest_date: str
    highest_price: float
    highest_date: str
    gain_rate: float
    gain_percent: float
    trade_days: int


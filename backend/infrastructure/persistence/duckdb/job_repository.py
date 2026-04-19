"""DuckDB unified job, result, and schedule repository."""

import json

from backend.domain.models import BacktestResultRecord, Job, JobStatus, JobType, SyncResult, SyncSchedule
from backend.domain.ports import JobRepository, SyncScheduleRepository
from backend.infrastructure.persistence.duckdb.base import DuckDBBase, format_timestamp


class DuckDBJobRepository(DuckDBBase, JobRepository, SyncScheduleRepository):
    """Unified job and result repository for v2 workflows."""

    def __init__(self, db_path: str = "stock_data.duckdb"):
        super().__init__(db_path)
        self._init_schema()

    def _init_schema(self):
        with self.connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id VARCHAR PRIMARY KEY,
                    type VARCHAR NOT NULL,
                    status VARCHAR NOT NULL,
                    params_json VARCHAR NOT NULL,
                    total_items BIGINT DEFAULT 0,
                    success_count BIGINT DEFAULT 0,
                    failed_count BIGINT DEFAULT 0,
                    error VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    finished_at TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sync_results (
                    job_id VARCHAR NOT NULL,
                    scope VARCHAR NOT NULL,
                    code VARCHAR,
                    status VARCHAR NOT NULL,
                    rows_written BIGINT DEFAULT 0,
                    message VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS backtest_results (
                    job_id VARCHAR NOT NULL,
                    stock_code VARCHAR NOT NULL,
                    strategy_name VARCHAR NOT NULL,
                    start_date VARCHAR NOT NULL,
                    end_date VARCHAR NOT NULL,
                    final_value DOUBLE,
                    total_return DOUBLE,
                    annualized_return DOUBLE,
                    sharpe_ratio DOUBLE,
                    max_drawdown DOUBLE,
                    total_trades BIGINT,
                    win_rate DOUBLE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (job_id, stock_code, strategy_name)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sync_schedules (
                    schedule_id VARCHAR PRIMARY KEY,
                    name VARCHAR NOT NULL,
                    enabled BOOLEAN NOT NULL,
                    scope VARCHAR NOT NULL,
                    run_time VARCHAR NOT NULL,
                    lookback_days BIGINT NOT NULL,
                    stock_codes_json VARCHAR,
                    last_job_id VARCHAR,
                    last_run_at TIMESTAMP,
                    next_run_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def save(self, job: Job) -> None:
        params_json = json.dumps(job.params, ensure_ascii=False)
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    job_id, type, status, params_json, total_items,
                    success_count, failed_count, error, started_at, finished_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    type=excluded.type, status=excluded.status,
                    params_json=excluded.params_json,
                    total_items=excluded.total_items,
                    success_count=excluded.success_count,
                    failed_count=excluded.failed_count,
                    error=excluded.error,
                    started_at=excluded.started_at,
                    finished_at=excluded.finished_at
                """,
                (
                    job.job_id,
                    job.type.value,
                    job.status.value,
                    params_json,
                    job.total_items,
                    job.success_count,
                    job.failed_count,
                    job.error,
                    job.started_at,
                    job.finished_at,
                ),
            )

    def get(self, job_id: str) -> Job | None:
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT job_id, type, status, params_json, total_items,
                       success_count, failed_count, error, created_at,
                       started_at, finished_at
                FROM jobs
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()
        return self._row_to_job(row) if row else None

    def list_jobs(self, limit: int = 100) -> list[Job]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT job_id, type, status, params_json, total_items,
                       success_count, failed_count, error, created_at,
                       started_at, finished_at
                FROM jobs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_job(row) for row in rows]

    def save_sync_results(self, results: list[SyncResult]) -> None:
        if not results:
            return
        records = [
            (item.job_id, item.scope, item.code, item.status, item.rows_written, item.message)
            for item in results
        ]
        with self.connection() as conn:
            conn.executemany(
                """
                INSERT INTO sync_results (job_id, scope, code, status, rows_written, message)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                records,
            )

    def get_sync_results(self, job_id: str) -> list[SyncResult]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT job_id, scope, code, status, rows_written, message, created_at
                FROM sync_results
                WHERE job_id = ?
                ORDER BY created_at, scope, code
                """,
                (job_id,),
            ).fetchall()
        return [
            SyncResult(
                job_id=row[0],
                scope=row[1],
                code=row[2],
                status=row[3],
                rows_written=row[4],
                message=row[5],
                created_at=format_timestamp(row[6]),
            )
            for row in rows
        ]

    def save_backtest_results(self, results: list[BacktestResultRecord]) -> None:
        if not results:
            return
        records = [
            (
                item.job_id,
                item.stock_code,
                item.strategy_name,
                item.start_date,
                item.end_date,
                item.final_value,
                item.total_return,
                item.annualized_return,
                item.sharpe_ratio,
                item.max_drawdown,
                item.total_trades,
                item.win_rate,
            )
            for item in results
        ]
        with self.connection() as conn:
            conn.executemany(
                """
                INSERT INTO backtest_results (
                    job_id, stock_code, strategy_name, start_date, end_date,
                    final_value, total_return, annualized_return, sharpe_ratio,
                    max_drawdown, total_trades, win_rate
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id, stock_code, strategy_name) DO UPDATE SET
                    final_value=excluded.final_value,
                    total_return=excluded.total_return,
                    annualized_return=excluded.annualized_return,
                    sharpe_ratio=excluded.sharpe_ratio,
                    max_drawdown=excluded.max_drawdown,
                    total_trades=excluded.total_trades,
                    win_rate=excluded.win_rate
                """,
                records,
            )

    def get_backtest_results(self, job_id: str) -> list[BacktestResultRecord]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT job_id, stock_code, strategy_name, start_date, end_date,
                       final_value, total_return, annualized_return, sharpe_ratio,
                       max_drawdown, total_trades, win_rate, created_at
                FROM backtest_results
                WHERE job_id = ?
                ORDER BY stock_code, strategy_name
                """,
                (job_id,),
            ).fetchall()
        return [
            BacktestResultRecord(
                job_id=row[0],
                stock_code=row[1],
                strategy_name=row[2],
                start_date=row[3],
                end_date=row[4],
                final_value=row[5],
                total_return=row[6],
                annualized_return=row[7],
                sharpe_ratio=row[8],
                max_drawdown=row[9],
                total_trades=row[10],
                win_rate=row[11],
                created_at=format_timestamp(row[12]),
            )
            for row in rows
        ]

    def get_sync_schedule(self, schedule_id: str) -> SyncSchedule | None:
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT schedule_id, name, enabled, scope, run_time, lookback_days,
                       stock_codes_json, last_job_id, last_run_at, next_run_at,
                       created_at, updated_at
                FROM sync_schedules
                WHERE schedule_id = ?
                """,
                (schedule_id,),
            ).fetchone()
        return self._row_to_sync_schedule(row) if row else None

    def save_sync_schedule(self, schedule: SyncSchedule) -> None:
        stock_codes_json = json.dumps(schedule.stock_codes, ensure_ascii=False) if schedule.stock_codes else None
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO sync_schedules (
                    schedule_id, name, enabled, scope, run_time, lookback_days,
                    stock_codes_json, last_job_id, last_run_at, next_run_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(schedule_id) DO UPDATE SET
                    name=excluded.name,
                    enabled=excluded.enabled,
                    scope=excluded.scope,
                    run_time=excluded.run_time,
                    lookback_days=excluded.lookback_days,
                    stock_codes_json=excluded.stock_codes_json,
                    last_job_id=excluded.last_job_id,
                    last_run_at=excluded.last_run_at,
                    next_run_at=excluded.next_run_at,
                    updated_at=excluded.updated_at
                """,
                (
                    schedule.schedule_id,
                    schedule.name,
                    schedule.enabled,
                    schedule.scope,
                    schedule.run_time,
                    schedule.lookback_days,
                    stock_codes_json,
                    schedule.last_job_id,
                    schedule.last_run_at,
                    schedule.next_run_at,
                ),
            )

    @staticmethod
    def _row_to_job(row) -> Job:
        return Job(
            job_id=row[0],
            type=JobType(row[1]),
            status=JobStatus(row[2]),
            params=json.loads(row[3]),
            total_items=row[4],
            success_count=row[5],
            failed_count=row[6],
            error=row[7],
            created_at=format_timestamp(row[8]),
            started_at=format_timestamp(row[9]),
            finished_at=format_timestamp(row[10]),
        )

    @staticmethod
    def _row_to_sync_schedule(row) -> SyncSchedule:
        stock_codes = json.loads(row[6]) if row[6] else None
        return SyncSchedule(
            schedule_id=row[0],
            name=row[1],
            enabled=bool(row[2]),
            scope=row[3],
            run_time=row[4],
            lookback_days=row[5],
            stock_codes=stock_codes,
            last_job_id=row[7],
            last_run_at=format_timestamp(row[8]),
            next_run_at=format_timestamp(row[9]),
            created_at=format_timestamp(row[10]),
            updated_at=format_timestamp(row[11]),
        )

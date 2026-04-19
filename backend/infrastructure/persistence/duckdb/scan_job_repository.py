"""DuckDB legacy scan job repository."""

import json

from backend.domain.models import JobStatus, ScanJob, StrategyHit
from backend.domain.ports import ScanJobRepository
from backend.infrastructure.persistence.duckdb.base import DuckDBBase, format_timestamp


class DuckDBScanJobRepository(DuckDBBase, ScanJobRepository):
    """DuckDB scan-only job repository kept for compatibility."""

    def __init__(self, db_path: str = "stock_data.duckdb"):
        super().__init__(db_path)
        self._init_schema()

    def _init_schema(self):
        with self.connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scan_jobs (
                    job_id VARCHAR PRIMARY KEY,
                    status VARCHAR NOT NULL,
                    start_date VARCHAR NOT NULL,
                    end_date VARCHAR NOT NULL,
                    targets_json VARCHAR NOT NULL,
                    total_results BIGINT DEFAULT 0,
                    error VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    finished_at TIMESTAMP
                )
            """)

    def save(self, job: ScanJob) -> None:
        targets_json = json.dumps(job.target_dates, ensure_ascii=False)
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO scan_jobs (job_id, status, start_date, end_date, targets_json, total_results, error, started_at, finished_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    status=excluded.status, total_results=excluded.total_results,
                    error=excluded.error, started_at=excluded.started_at,
                    finished_at=excluded.finished_at
                """,
                (
                    job.job_id,
                    job.status.value,
                    job.start_date,
                    job.end_date,
                    targets_json,
                    job.total_results,
                    job.error,
                    job.started_at,
                    job.finished_at,
                ),
            )

    def get(self, job_id: str) -> ScanJob | None:
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT job_id, status, start_date, end_date, targets_json,
                       total_results, error, created_at, started_at, finished_at
                FROM scan_jobs WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()

        if row is None:
            return None
        return self._row_to_job(row)

    def list_jobs(self, limit: int = 100) -> list[ScanJob]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT job_id, status, start_date, end_date, targets_json,
                       total_results, error, created_at, started_at, finished_at
                FROM scan_jobs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_job(row) for row in rows]

    def get_results(self, job: ScanJob) -> list[StrategyHit]:
        if not job.target_dates:
            return []

        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT code, name, strategy, target_date, current_price, current_volume, created_at
                FROM strategy_results
                WHERE job_id = ?
                ORDER BY target_date, code, strategy
                """,
                (job.job_id,),
            ).fetchall()
            if not rows:
                placeholders = ", ".join(["?"] * len(job.target_dates))
                rows = conn.execute(
                    f"""
                    SELECT code, name, strategy, target_date, current_price, current_volume, created_at
                    FROM strategy_results
                    WHERE target_date IN ({placeholders})
                    ORDER BY target_date, code, strategy
                    """,
                    job.target_dates,
                ).fetchall()

        return [
            StrategyHit(
                code=row[0],
                name=row[1],
                strategy=row[2],
                target_date=row[3],
                current_price=row[4],
                current_volume=row[5],
                created_at=format_timestamp(row[6]),
                job_id=job.job_id,
            )
            for row in rows
        ]

    @staticmethod
    def _row_to_job(row) -> ScanJob:
        return ScanJob(
            job_id=row[0],
            status=JobStatus(row[1]),
            start_date=row[2],
            end_date=row[3],
            target_dates=json.loads(row[4]),
            total_results=row[5],
            error=row[6],
            created_at=format_timestamp(row[7]),
            started_at=format_timestamp(row[8]),
            finished_at=format_timestamp(row[9]),
        )

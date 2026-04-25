"""DuckDB stock data repository."""

from typing import Iterable

import pandas as pd

from backend.domain.models import HighLowGainRank, Stock, StrategyHit
from backend.domain.ports import RankingRepository, StockRepository
from backend.infrastructure.persistence.duckdb.base import (
    DuckDBBase,
    add_column_if_missing,
    format_timestamp,
    normalize_stock_data,
    now_iso,
    table_columns,
    table_exists,
    to_optional_float,
    to_optional_int,
)


class DuckDBStockRepository(DuckDBBase, StockRepository, RankingRepository):
    """DuckDB stock data repository implementation."""

    def __init__(self, db_path: str = "stock_data.duckdb"):
        super().__init__(db_path)
        self._init_schema()

    def _init_schema(self):
        with self.connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stocks (
                    code VARCHAR PRIMARY KEY,
                    name VARCHAR NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stock_daily_data (
                    code VARCHAR NOT NULL,
                    trade_date VARCHAR NOT NULL,
                    open DOUBLE,
                    close DOUBLE,
                    high DOUBLE,
                    low DOUBLE,
                    volume BIGINT,
                    amount DOUBLE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    source VARCHAR,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (code, trade_date)
                )
            """)
            add_column_if_missing(conn, "stock_daily_data", "source", "source VARCHAR")
            add_column_if_missing(
                conn,
                "stock_daily_data",
                "updated_at",
                "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            )
            self._init_strategy_results_schema(conn)

    def _init_strategy_results_schema(self, conn):
        if table_exists(conn, "strategy_results") and "job_id" not in table_columns(conn, "strategy_results"):
            conn.execute("ALTER TABLE strategy_results RENAME TO strategy_results_legacy")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS strategy_results (
                job_id VARCHAR NOT NULL,
                code VARCHAR NOT NULL,
                name VARCHAR NOT NULL,
                strategy VARCHAR NOT NULL,
                target_date VARCHAR NOT NULL,
                current_price DOUBLE,
                current_volume BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (job_id, code, strategy, target_date)
            )
        """)

        if table_exists(conn, "strategy_results_legacy"):
            conn.execute("""
                INSERT OR IGNORE INTO strategy_results (
                    job_id, code, name, strategy, target_date,
                    current_price, current_volume, created_at
                )
                SELECT
                    'legacy', code, name, strategy, target_date,
                    current_price, current_volume, created_at
                FROM strategy_results_legacy
            """)
            conn.execute("DROP TABLE strategy_results_legacy")

    def list_stocks(self) -> list[Stock]:
        with self.connection() as conn:
            rows = conn.execute("SELECT code, name FROM stocks ORDER BY code").fetchall()
        return [Stock(code=row[0], name=row[1]) for row in rows]

    def list_stocks_df(self) -> pd.DataFrame:
        with self.connection() as conn:
            return conn.execute("SELECT code, name FROM stocks ORDER BY code").fetchdf()

    def get_stock_history(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        with self.connection() as conn:
            data = conn.execute(
                """
                SELECT
                    code AS stock_code, trade_date AS date,
                    open, close, high, low, volume, amount
                FROM stock_daily_data
                WHERE code = ? AND trade_date BETWEEN ? AND ?
                ORDER BY trade_date
                """,
                (code, start_date, end_date),
            ).fetchdf()
        return normalize_stock_data(data, stock_code=code)

    def upsert_stocks(self, stocks: list[Stock] | pd.DataFrame | Iterable[dict]) -> None:
        if isinstance(stocks, pd.DataFrame):
            stocks_df = stocks
        elif stocks and isinstance(stocks[0], Stock):
            stocks_df = pd.DataFrame([{"code": s.code, "name": s.name} for s in stocks])
        else:
            stocks_df = pd.DataFrame(stocks)

        if stocks_df.empty:
            return

        records = [
            (str(row["code"]), row["name"])
            for _, row in stocks_df[["code", "name"]].dropna().iterrows()
        ]
        with self.connection() as conn:
            conn.executemany(
                """
                INSERT INTO stocks (code, name, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(code) DO UPDATE SET name = excluded.name
                """,
                records,
            )

    def upsert_daily_data(self, data: pd.DataFrame, source: str | None = None) -> None:
        normalized = normalize_stock_data(data)
        if normalized.empty:
            return

        updated_at = now_iso()
        records = [
            (
                str(row["stock_code"]),
                row["date"].strftime("%Y%m%d"),
                to_optional_float(row["open"]),
                to_optional_float(row["close"]),
                to_optional_float(row["high"]),
                to_optional_float(row["low"]),
                to_optional_int(row["volume"]),
                to_optional_float(row["amount"]),
                source,
                updated_at,
            )
            for _, row in normalized.iterrows()
        ]
        with self.connection() as conn:
            conn.executemany(
                """
                INSERT INTO stock_daily_data (code, trade_date, open, close, high, low, volume, amount, source, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(code, trade_date) DO UPDATE SET
                    open=excluded.open, close=excluded.close,
                    high=excluded.high, low=excluded.low,
                    volume=excluded.volume, amount=excluded.amount,
                    source=excluded.source, updated_at=excluded.updated_at
                """,
                records,
            )

    def upsert_strategy_results(self, results: list[StrategyHit] | list[dict], job_id: str | None = None) -> None:
        if not results:
            return

        records = []
        for item in results:
            if isinstance(item, StrategyHit):
                result_job_id = item.job_id or job_id or "legacy"
                records.append((
                    result_job_id,
                    item.code,
                    item.name,
                    item.strategy,
                    item.target_date,
                    item.current_price,
                    item.current_volume,
                ))
            else:
                result_job_id = item.get("job_id") or job_id or "legacy"
                records.append((
                    result_job_id,
                    item["code"],
                    item["name"],
                    item["strategy"],
                    item["target_date"],
                    item.get("current_price"),
                    item.get("current_volume"),
                ))

        with self.connection() as conn:
            conn.executemany(
                """
                INSERT INTO strategy_results (job_id, code, name, strategy, target_date, current_price, current_volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id, code, strategy, target_date) DO UPDATE SET
                    name=excluded.name, current_price=excluded.current_price,
                    current_volume=excluded.current_volume
                """,
                records,
            )

    def get_available_dates(self, code: str, start_date: str, end_date: str) -> set[str]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT trade_date FROM stock_daily_data WHERE code = ? AND trade_date BETWEEN ? AND ?",
                (code, start_date, end_date),
            ).fetchall()
        return {row[0] for row in rows}

    def get_strategy_results(self, job_id: str) -> list[StrategyHit]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT code, name, strategy, target_date, current_price, current_volume, created_at, job_id
                FROM strategy_results
                WHERE job_id = ?
                ORDER BY target_date, code, strategy
                """,
                (job_id,),
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
                job_id=row[7],
            )
            for row in rows
        ]

    def list_high_low_gain_rank(
        self,
        start_date: str,
        end_date: str,
        limit: int = 100,
        direction: str = "range",
        min_gain_percent: float | None = None,
    ) -> list[HighLowGainRank]:
        min_gain_rate = (min_gain_percent or 0) / 100
        if direction == "range":
            return self._list_range_high_low_gain_rank(start_date, end_date, limit, min_gain_rate)
        if direction in {"up", "down"}:
            return self._list_directional_high_low_gain_rank(start_date, end_date, limit, direction, min_gain_rate)
        raise ValueError("direction must be one of range, up, down")

    def _list_range_high_low_gain_rank(
        self,
        start_date: str,
        end_date: str,
        limit: int,
        min_gain_rate: float,
    ) -> list[HighLowGainRank]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                WITH filtered AS (
                    SELECT
                        s.code,
                        s.name,
                        d.trade_date,
                        d.high,
                        d.low
                    FROM stocks s
                    JOIN stock_daily_data d ON d.code = s.code
                    WHERE d.trade_date BETWEEN ? AND ?
                      AND d.high IS NOT NULL
                      AND d.low IS NOT NULL
                      AND d.low > 0
                ),
                stats AS (
                    SELECT
                        code,
                        name,
                        MIN(low) AS lowest_price,
                        MAX(high) AS highest_price,
                        COUNT(*) AS trade_days
                    FROM filtered
                    GROUP BY code, name
                ),
                lowest_dates AS (
                    SELECT code, trade_date AS lowest_date
                    FROM (
                        SELECT
                            code,
                            trade_date,
                            ROW_NUMBER() OVER (PARTITION BY code ORDER BY low ASC, trade_date ASC) AS rn
                        FROM filtered
                    )
                    WHERE rn = 1
                ),
                highest_dates AS (
                    SELECT code, trade_date AS highest_date
                    FROM (
                        SELECT
                            code,
                            trade_date,
                            ROW_NUMBER() OVER (PARTITION BY code ORDER BY high DESC, trade_date ASC) AS rn
                        FROM filtered
                    )
                    WHERE rn = 1
                )
                SELECT
                    stats.code,
                    stats.name,
                    stats.lowest_price,
                    lowest_dates.lowest_date,
                    stats.highest_price,
                    highest_dates.highest_date,
                    (stats.highest_price - stats.lowest_price) / stats.lowest_price AS gain_rate,
                    ((stats.highest_price - stats.lowest_price) / stats.lowest_price) * 100 AS gain_percent,
                    stats.trade_days
                FROM stats
                JOIN lowest_dates ON lowest_dates.code = stats.code
                JOIN highest_dates ON highest_dates.code = stats.code
                WHERE stats.lowest_price > 0
                  AND ((stats.highest_price - stats.lowest_price) / stats.lowest_price) >= ?
                ORDER BY gain_rate DESC, stats.code
                LIMIT ?
                """,
                (start_date, end_date, min_gain_rate, limit),
            ).fetchall()

        return self._rank_rows_to_models(rows, start_date, end_date)

    def _list_directional_high_low_gain_rank(
        self,
        start_date: str,
        end_date: str,
        limit: int,
        direction: str,
        min_gain_rate: float,
    ) -> list[HighLowGainRank]:
        if direction == "up":
            select_prices = """
                first_point.low AS lowest_price,
                first_point.trade_date AS lowest_date,
                second_point.high AS highest_price,
                second_point.trade_date AS highest_date,
                (second_point.high - first_point.low) / first_point.low AS gain_rate,
                ((second_point.high - first_point.low) / first_point.low) * 100 AS gain_percent
            """
        else:
            select_prices = """
                second_point.low AS lowest_price,
                second_point.trade_date AS lowest_date,
                first_point.high AS highest_price,
                first_point.trade_date AS highest_date,
                (first_point.high - second_point.low) / first_point.high AS gain_rate,
                ((first_point.high - second_point.low) / first_point.high) * 100 AS gain_percent
            """

        with self.connection() as conn:
            rows = conn.execute(
                f"""
                WITH filtered AS (
                    SELECT
                        s.code,
                        s.name,
                        d.trade_date,
                        d.high,
                        d.low
                    FROM stocks s
                    JOIN stock_daily_data d ON d.code = s.code
                    WHERE d.trade_date BETWEEN ? AND ?
                      AND d.high IS NOT NULL
                      AND d.low IS NOT NULL
                      AND d.high > 0
                      AND d.low > 0
                ),
                trade_day_stats AS (
                    SELECT code, COUNT(*) AS trade_days
                    FROM filtered
                    GROUP BY code
                ),
                candidates AS (
                    SELECT
                        first_point.code,
                        first_point.name,
                        {select_prices},
                        trade_day_stats.trade_days
                    FROM filtered first_point
                    JOIN filtered second_point
                      ON second_point.code = first_point.code
                     AND first_point.trade_date < second_point.trade_date
                    JOIN trade_day_stats ON trade_day_stats.code = first_point.code
                ),
                ranked AS (
                    SELECT
                        *,
                        ROW_NUMBER() OVER (
                            PARTITION BY code
                            ORDER BY gain_rate DESC, lowest_date ASC, highest_date ASC
                        ) AS rn
                    FROM candidates
                    WHERE gain_rate >= ?
                )
                SELECT
                    code,
                    name,
                    lowest_price,
                    lowest_date,
                    highest_price,
                    highest_date,
                    gain_rate,
                    gain_percent,
                    trade_days
                FROM ranked
                WHERE rn = 1
                ORDER BY gain_rate DESC, code
                LIMIT ?
                """,
                (start_date, end_date, min_gain_rate, limit),
            ).fetchall()

        return self._rank_rows_to_models(rows, start_date, end_date)

    def _rank_rows_to_models(self, rows, start_date: str, end_date: str) -> list[HighLowGainRank]:
        return [
            HighLowGainRank(
                code=row[0],
                name=row[1],
                start=start_date,
                end=end_date,
                lowest_price=float(row[2]),
                lowest_date=row[3],
                highest_price=float(row[4]),
                highest_date=row[5],
                gain_rate=float(row[6]),
                gain_percent=float(row[7]),
                trade_days=int(row[8]),
            )
            for row in rows
        ]

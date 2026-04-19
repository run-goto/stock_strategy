"""Shared DuckDB helpers."""

import logging
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from threading import RLock

import duckdb
import pandas as pd

logger = logging.getLogger(__name__)

STANDARD_COLUMNS = ["stock_code", "date", "open", "close", "high", "low", "volume", "amount"]


def to_optional_float(value) -> float | None:
    if pd.isna(value):
        return None
    return float(value)


def to_optional_int(value) -> int | None:
    if pd.isna(value):
        return None
    return int(value)


def format_timestamp(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def normalize_stock_data(data: pd.DataFrame, stock_code: str | None = None) -> pd.DataFrame:
    """Normalize market data columns and types for DuckDB writes."""
    if data is None or data.empty:
        return pd.DataFrame(columns=STANDARD_COLUMNS)

    normalized = data.copy()
    if "stock_code" not in normalized.columns:
        normalized["stock_code"] = stock_code
    if "amount" not in normalized.columns:
        normalized["amount"] = pd.NA

    normalized = normalized[STANDARD_COLUMNS]
    normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce").dt.date

    for column in ["open", "close", "high", "low", "volume", "amount"]:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    normalized = normalized.dropna(subset=["stock_code", "date"])
    return normalized.sort_values("date").reset_index(drop=True)


def table_exists(conn, table_name: str) -> bool:
    row = conn.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_name = ?
        """,
        (table_name,),
    ).fetchone()
    return bool(row and row[0])


def table_columns(conn, table_name: str) -> set[str]:
    if not table_exists(conn, table_name):
        return set()
    rows = conn.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = ?
        """,
        (table_name,),
    ).fetchall()
    return {row[0] for row in rows}


def add_column_if_missing(conn, table_name: str, column_name: str, ddl: str) -> None:
    if column_name not in table_columns(conn, table_name):
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {ddl}")


class DuckDBBase:
    """DuckDB connection management shared by repository implementations."""

    def __init__(self, db_path: str = "stock_data.duckdb"):
        self.db_path = Path(db_path)
        self._lock = RLock()

    def connect(self):
        return duckdb.connect(str(self.db_path))

    @contextmanager
    def connection(self):
        with self._lock:
            conn = self.connect()
            try:
                yield conn
            finally:
                conn.close()


def now_iso() -> str:
    return datetime.now().isoformat()

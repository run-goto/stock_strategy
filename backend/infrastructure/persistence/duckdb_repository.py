"""Compatibility exports for DuckDB repositories."""

from backend.infrastructure.persistence.duckdb import (
    DuckDBJobRepository,
    DuckDBScanJobRepository,
    DuckDBStockRepository,
)

__all__ = ["DuckDBJobRepository", "DuckDBScanJobRepository", "DuckDBStockRepository"]

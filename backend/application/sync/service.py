"""Data sync workflow for stocks and daily bars."""

import logging
import queue
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

import akshare as ak
import pandas as pd

from backend.application.interfaces import DATA_SYNC_SCOPES, DataSyncRunner
from backend.application.strategy.calendar import validate_date
from backend.application.strategy.execution import TradeDataService
from backend.domain.market import get_market_code
from backend.domain.models import Stock, SyncResult
from backend.domain.ports import JobRepository, MarketDataSource, StockRepository

logger = logging.getLogger(__name__)


class DataSyncService(DataSyncRunner):
    """Synchronize A-share symbols and daily bars into local DuckDB."""

    VALID_SCOPES = DATA_SYNC_SCOPES

    def __init__(
        self,
        stock_repository: StockRepository,
        job_repository: JobRepository,
        data_source: MarketDataSource,
        stock_fetcher: Callable[[], object] | None = None,
        stock_fetch_timeout: float | None = 10.0,
        daily_fetch_workers: int = 8,
    ):
        self.stock_repository = stock_repository
        self.job_repository = job_repository
        self.data_source = data_source
        self.stock_fetcher = stock_fetcher or ak.stock_info_a_code_name
        self.stock_fetch_timeout = stock_fetch_timeout
        self.daily_fetch_workers = max(1, int(daily_fetch_workers or 1))

    def run(
        self,
        job_id: str,
        scope: str,
        start_date: str | None,
        end_date: str | None,
        stock_codes: list[str] | None = None,
    ) -> dict:
        if scope not in self.VALID_SCOPES:
            raise ValueError(f"不支持的数据同步范围: {scope}")

        logger.info(
            "数据同步开始: job_id=%s scope=%s start_date=%s end_date=%s stock_count=%s",
            job_id,
            scope,
            start_date,
            end_date,
            len(stock_codes) if stock_codes else "all",
        )
        results: list[SyncResult] = []
        if scope in {"stocks", "all"}:
            results.append(self._sync_stocks(job_id))

        if scope in {"daily", "all"}:
            if not start_date or not end_date:
                raise ValueError("同步日线数据时 start 和 end 必须同时提供")
            validate_date(start_date)
            validate_date(end_date)
            results.extend(self._sync_daily(job_id, start_date, end_date, stock_codes))

        self.job_repository.save_sync_results(results)
        failed_count = sum(1 for item in results if item.status == "failed")
        logger.info(
            "数据同步完成: job_id=%s scope=%s total_items=%s failed_count=%s",
            job_id,
            scope,
            len(results),
            failed_count,
        )
        return {
            "total_items": len(results),
            "success_count": len(results) - failed_count,
            "failed_count": failed_count,
        }

    def _sync_stocks(self, job_id: str) -> SyncResult:
        stocks_df = self._fetch_stock_list()
        stocks_df = stocks_df[["code", "name"]]
        self.stock_repository.upsert_stocks(stocks_df)
        logger.info("股票列表同步完成: job_id=%s rows_written=%s", job_id, len(stocks_df))
        return SyncResult(
            job_id=job_id,
            scope="stocks",
            code=None,
            status="completed",
            rows_written=len(stocks_df),
            message="股票列表同步完成",
        )

    def _sync_daily(
        self,
        job_id: str,
        start_date: str,
        end_date: str,
        stock_codes: list[str] | None,
    ) -> list[SyncResult]:
        stocks = self._resolve_stocks(stock_codes)
        logger.info(
            "日线同步开始: job_id=%s start_date=%s end_date=%s stock_count=%s workers=%s",
            job_id,
            start_date,
            end_date,
            len(stocks),
            self.daily_fetch_workers,
        )
        results: list[SyncResult] = []
        with ThreadPoolExecutor(max_workers=self.daily_fetch_workers, thread_name_prefix="daily-fetch") as executor:
            futures = {
                executor.submit(self._fetch_daily_stock, stock, start_date, end_date): stock
                for stock in stocks
            }
            for future in as_completed(futures):
                stock = futures[future]
                try:
                    data = future.result()
                    self.stock_repository.upsert_daily_data(
                        data,
                        source=getattr(self.data_source, "name", None),
                    )
                    logger.info(
                        "日线同步完成: job_id=%s code=%s rows_written=%s",
                        job_id,
                        stock.code,
                        len(data),
                    )
                    results.append(
                        SyncResult(
                            job_id=job_id,
                            scope="daily",
                            code=stock.code,
                            status="completed",
                            rows_written=len(data),
                            message=f"{stock.name} 日线同步完成",
                        )
                    )
                except Exception as exc:
                    logger.exception("同步 %s 日线数据失败", stock.code)
                    results.append(
                        SyncResult(
                            job_id=job_id,
                            scope="daily",
                            code=stock.code,
                            status="failed",
                            rows_written=0,
                            message=str(exc),
                        )
                    )
        return results

    def _fetch_daily_stock(self, stock: Stock, start_date: str, end_date: str) -> pd.DataFrame:
        market_code = get_market_code(stock.code)
        return self.data_source.fetch_daily_data(
            stock_code=stock.code,
            market_code=market_code,
            start_date=start_date,
            end_date=end_date,
        )

    def _resolve_stocks(self, stock_codes: list[str] | None) -> list[Stock]:
        stocks = self.stock_repository.list_stocks()
        if not stocks:
            trade_data_service = TradeDataService(
                repository=self.stock_repository,
                data_source=self.data_source,
            )
            trade_data_service.list_stocks()
            stocks = self.stock_repository.list_stocks()

        if not stock_codes:
            return stocks

        stock_by_code = {stock.code: stock for stock in stocks}
        return [
            stock_by_code.get(code, Stock(code=code, name=code))
            for code in stock_codes
        ]

    def _fetch_stock_list(self):
        if not self.stock_fetch_timeout:
            return self.stock_fetcher()

        result_queue: queue.Queue = queue.Queue(maxsize=1)

        def worker():
            try:
                result_queue.put(("ok", self.stock_fetcher()))
            except Exception as exc:
                result_queue.put(("error", exc))

        thread = threading.Thread(target=worker, name="stock-list-fetcher", daemon=True)
        thread.start()
        try:
            status, payload = result_queue.get(timeout=self.stock_fetch_timeout)
        except queue.Empty as exc:
            raise TimeoutError(f"股票列表同步超时: {self.stock_fetch_timeout} 秒") from exc

        if status == "error":
            raise payload
        return payload

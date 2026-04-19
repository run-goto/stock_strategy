"""Strategy execution workflow."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from backend.application.interfaces import StrategyExecutionRunner, TradeDataProvider
from backend.domain.market import get_market_code
from backend.domain.ports import MarketDataSource, StockRepository
from backend.domain.strategy import BaseStrategy

logger = logging.getLogger(__name__)


class TradeDataService(TradeDataProvider):
    """Market data service with local-first history reads."""

    def __init__(
        self,
        repository: StockRepository,
        data_source: MarketDataSource,
        allow_online_fetch: bool = True,
    ):
        self.repository = repository
        self.data_source = data_source
        self.allow_online_fetch = allow_online_fetch

    def list_stocks(self) -> pd.DataFrame:
        stocks = self.repository.list_stocks()
        if stocks:
            return pd.DataFrame([{"code": s.code, "name": s.name} for s in stocks])
        if not self.allow_online_fetch:
            return pd.DataFrame(columns=["code", "name"])

        import akshare as ak

        stocks_df = ak.stock_info_a_code_name()
        stocks_df = stocks_df[["code", "name"]]
        self.repository.upsert_stocks(stocks_df)
        return stocks_df

    def get_history_for_scan(
        self,
        code: str,
        name: str,
        start_date: str,
        end_date: str,
        target_dates: list[str],
    ) -> pd.DataFrame:
        return self.ensure_daily_data(
            code=code,
            name=name,
            start_date=start_date,
            end_date=end_date,
            required_dates=target_dates,
        )

    def ensure_daily_data(
        self,
        code: str,
        name: str,
        start_date: str,
        end_date: str,
        required_dates: list[str],
    ) -> pd.DataFrame:
        local_data = self.repository.get_stock_history(code, start_date, end_date)
        if not self.allow_online_fetch:
            return local_data.sort_values("date").reset_index(drop=True)

        if self._needs_online_fetch(local_data, required_dates):
            logger.info("本地数据不完整，开始补抓 %s(%s): %s ~ %s", name, code, start_date, end_date)
            market_code = get_market_code(code)
            fetched_data = self.data_source.fetch_daily_data(
                stock_code=code,
                market_code=market_code,
                start_date=start_date,
                end_date=end_date,
            )
            if not fetched_data.empty:
                self.repository.upsert_daily_data(fetched_data, source=getattr(self.data_source, "name", None))
                local_data = self.repository.get_stock_history(code, start_date, end_date)

        return local_data.sort_values("date").reset_index(drop=True)

    @staticmethod
    def _needs_online_fetch(local_data: pd.DataFrame, target_dates: list[str]) -> bool:
        if local_data.empty:
            return True
        available_dates = {
            item.strftime("%Y%m%d")
            for item in pd.to_datetime(local_data["date"], errors="coerce").dropna()
        }
        return any(td not in available_dates for td in target_dates)


class StrategyExecutor(StrategyExecutionRunner):
    """Run configured strategies across all listed stocks."""

    def __init__(
        self,
        trade_data_service: TradeDataProvider,
        repository: StockRepository,
        strategies: list[BaseStrategy],
        max_workers: int = 8,
    ):
        self.trade_data_service = trade_data_service
        self.repository = repository
        self.strategies = strategies
        self.max_workers = max_workers

    def run(self, start_date: str, end_date: str, target_dates: list[str], job_id: str | None = None) -> list[dict]:
        stocks = self.trade_data_service.list_stocks()
        logger.info("获取到 %s 只股票", len(stocks))

        result_stocks: list[dict] = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(
                    self._scan_stock, str(row["code"]), row["name"],
                    start_date, end_date, target_dates,
                ): row
                for _, row in stocks[["code", "name"]].iterrows()
            }
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        result_stocks.extend(result)
                except Exception as exc:
                    logger.error("处理任务出错: %s", exc)

        self.repository.upsert_strategy_results(result_stocks, job_id=job_id)
        logger.info("策略执行完成，共找到 %s 条符合条件的记录", len(result_stocks))
        return result_stocks

    def _scan_stock(self, code, name, start_date, end_date, target_dates) -> list[dict]:
        try:
            hist_data = self.trade_data_service.get_history_for_scan(
                code=code,
                name=name,
                start_date=start_date,
                end_date=end_date,
                target_dates=target_dates,
            )
            if hist_data.empty:
                logger.warning("%s(%s) 历史数据为空", name, code)
                return []
            return scan_stock_data(code, name, hist_data, target_dates, self.strategies)
        except Exception as exc:
            logger.exception("处理 %s(%s) 出错: %s", name, code, exc)
            return []


def scan_stock_data(
    code: str,
    name: str,
    hist_data: pd.DataFrame,
    target_dates: list[str],
    strategies: list[BaseStrategy],
) -> list[dict]:
    """Run all strategies for one stock and return hit payloads."""
    hist_data = hist_data.sort_values("date").reset_index(drop=True)
    date_to_index = {
        row["date"].strftime("%Y%m%d"): idx
        for idx, row in hist_data.iterrows()
    }

    results = []
    for target_date in target_dates:
        if target_date not in date_to_index:
            continue
        target_index = date_to_index[target_date]
        hist_data_for_check = hist_data.iloc[:target_index + 1]
        today = hist_data_for_check.iloc[-1]

        for strategy in strategies:
            try:
                if strategy.check(hist_data_for_check):
                    results.append({
                        "code": code,
                        "name": name,
                        "strategy": strategy.name,
                        "target_date": target_date,
                        "current_price": _to_opt_float(today.get("close")),
                        "current_volume": _to_opt_int(today.get("volume")),
                    })
            except Exception as exc:
                logger.error("策略 %s 执行出错: %s", strategy.__class__.__name__, exc)

    return results


def _to_opt_float(v):
    if pd.isna(v):
        return None
    return float(v)


def _to_opt_int(v):
    if pd.isna(v):
        return None
    return int(v)

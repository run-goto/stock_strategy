"""数据源基类 + normalize 工具。"""

import logging
import time
from abc import abstractmethod

import pandas as pd

from backend.domain.market import get_market_code
from backend.domain.ports import MarketDataSource

logger = logging.getLogger(__name__)

STANDARD_COLUMNS = ["stock_code", "date", "open", "close", "high", "low", "volume", "amount"]


def normalize_stock_data(data: pd.DataFrame, stock_code: str | None = None) -> pd.DataFrame:
    """标准化行情 DataFrame 列名和类型。"""
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


class DataSourceBase(MarketDataSource):
    """数据源实现基类，封装计时日志和标准化逻辑。"""

    def __init__(self, timeout: float | None = None):
        self.timeout = timeout
        self.name: str = ""

    def fetch_daily_data(self, stock_code, market_code, start_date, end_date) -> pd.DataFrame:
        start_time = time.time()
        data = self.do_fetch(stock_code, market_code, start_date, end_date)
        elapsed_ms = (time.time() - start_time) * 1000
        logger.info("获取 %s 数据耗时: %.2fms", stock_code, elapsed_ms)
        return normalize_stock_data(data, stock_code=stock_code)

    @abstractmethod
    def do_fetch(self, stock_code, market_code, start_date, end_date) -> pd.DataFrame:
        """子类实现的原始数据获取。"""
        ...


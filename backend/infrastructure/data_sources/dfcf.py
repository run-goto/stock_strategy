import logging

import pandas as pd
import requests

from backend.infrastructure.data_sources.base import DataSourceBase

logger = logging.getLogger(__name__)


class DongFangCaiFu(DataSourceBase):
    def __init__(self, timeout: float | None = None):
        super().__init__(timeout=timeout)
        self.name = "东方财富"

    def do_fetch(self, stock_code, market_code, start_date, end_date):
        try:
            return self._fetch_kline(symbol=stock_code, start_date=start_date, end_date=end_date)
        except Exception as exc:
            logger.error("获取股票 %s 数据失败: %s", stock_code, exc)
            return pd.DataFrame()

    def _fetch_kline(self, symbol, start_date, end_date, period="daily", adjust="") -> pd.DataFrame:
        symbol_code = 1 if symbol.startswith("6") else 0
        adjust_dict = {"qfq": "1", "hfq": "2", "": "0"}
        period_dict = {"daily": "101", "weekly": "102", "monthly": "103"}

        params = {
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116",
            "ut": "7eea3edcaed734bea9cbfc24409ed989",
            "klt": period_dict[period],
            "fqt": adjust_dict[adjust],
            "secid": f"{symbol_code}.{symbol}",
            "beg": start_date,
            "end": end_date,
        }
        response = requests.get(
            "https://push2his.eastmoney.com/api/qt/stock/kline/get",
            params=params,
            timeout=self.timeout,
        )
        data_json = response.json()
        if not (data_json["data"] and data_json["data"]["klines"]):
            return pd.DataFrame()

        temp_df = pd.DataFrame([item.split(",") for item in data_json["data"]["klines"]])
        raw_columns = [
            "date", "open", "close", "high", "low", "volume", "amount",
            "amplitude", "change_percent", "change_amount", "turnover_rate", "market_cap",
        ]
        temp_df = temp_df.iloc[:, :len(raw_columns)]
        temp_df.columns = raw_columns[:len(temp_df.columns)]
        temp_df["stock_code"] = symbol
        return temp_df[["stock_code", "date", "open", "close", "high", "low", "volume", "amount"]]


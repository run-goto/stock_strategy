import logging
from datetime import datetime

import pandas as pd
import requests
from akshare.utils import demjson

from backend.infrastructure.data_sources.base import DataSourceBase

logger = logging.getLogger(__name__)


class Tencent(DataSourceBase):
    def __init__(self, timeout: float | None = None):
        super().__init__(timeout=timeout)
        self.name = "腾讯证券"

    def do_fetch(self, stock_code, market_code, start_date, end_date):
        try:
            symbol = f"{market_code}{stock_code}"
            return self._fetch_kline(symbol=symbol, start_date=start_date, end_date=end_date)
        except Exception as exc:
            logger.error("获取股票 %s 数据失败: %s", stock_code, exc)
            return pd.DataFrame()

    def _fetch_kline(self, symbol, start_date, end_date) -> pd.DataFrame:
        date_format = "%Y%m%d"
        start = datetime.strptime(start_date, date_format)
        end = datetime.strptime(end_date, date_format)
        start_format_str = start.strftime("%Y-%m-%d")
        end_format_str = end.strftime("%Y-%m-%d")
        delta_days = (end - start).days

        params = {
            "_var": "kline_day",
            "param": f"{symbol},day,{start_format_str},{end_format_str},{delta_days},",
            "r": "0.8205512681390605",
        }
        response = requests.get(
            "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get",
            params=params,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data_text = _decode_response_text(response)
        data_json = demjson.decode(data_text[data_text.find("={") + 1:])["data"][symbol]

        if "day" in data_json:
            temp_df = pd.DataFrame(data_json["day"])
        elif "hfqday" in data_json:
            temp_df = pd.DataFrame(data_json["hfqday"])
        else:
            temp_df = pd.DataFrame(data_json["qfqday"])

        if temp_df.empty:
            return pd.DataFrame()

        temp_df = temp_df.iloc[:, :6]
        temp_df.columns = ["date", "open", "close", "high", "low", "amount"]
        temp_df["date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
        for column in ["open", "close", "high", "low", "amount"]:
            temp_df[column] = pd.to_numeric(temp_df[column], errors="coerce")
        temp_df.drop_duplicates(inplace=True, ignore_index=True)
        temp_df.index = pd.to_datetime(temp_df["date"])
        temp_df = temp_df[start_date:end_date]
        temp_df.reset_index(inplace=True, drop=True)

        temp_df["stock_code"] = symbol[2:]
        temp_df["volume"] = temp_df["amount"]
        temp_df["amount"] = pd.NA
        return temp_df[["stock_code", "date", "open", "close", "high", "low", "volume", "amount"]]


def _decode_response_text(response) -> str:
    try:
        return response.content.decode("utf-8")
    except UnicodeDecodeError:
        return response.content.decode("gb18030")


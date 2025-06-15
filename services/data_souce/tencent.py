import logging
from datetime import datetime

import pandas as pd
import requests
from akshare.utils import demjson

from common.market_util import MarketUtil
from services.data_souce.datasource import DataSource

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'  # 修复日志格式
)
logger = logging.getLogger(__name__)


class Tencent(DataSource):
    def __init__(self):
        self.name = "东方财富"

    def do_get_stock_data(self, stock_code, market_code, start_date, end_date):
        return self.stock_zh_a_hist(
            stock_code=stock_code,
            market_code=market_code,
            start_date=start_date,
            end_date=end_date
        )

    def stock_zh_a_hist(self,
                        stock_code: str = "000001",
                        market_code: str = "sh",
                        start_date: str = "19700101",
                        end_date: str = "20500101",
                        ) -> pd.DataFrame:
        """获取股票历史数据"""
        try:
            symbol = f"{market_code}{stock_code}"
            return self.do_stock_zh_a_hist(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as e:
            logger.error(f"获取股票 {stock_code} 数据失败: {str(e)}")
            return pd.DataFrame()

    def do_stock_zh_a_hist(self, symbol: str = "sz000001",
                           start_date: str = "19700101",
                           end_date: str = "20500101",
                           ) -> pd.DataFrame:

        temp_df = self.stock_zh_a_hist_tx(symbol=symbol,
                                          start_date=start_date,
                                          end_date=end_date, timeout=1)

        numeric_fields = {
            "date": "date",
            "open": "open",
            "close": "close",
            "high": "high",
            "low": "low",
            "volume": "amount"
        }
        temp_df["stock_code"] = symbol
        for col_name, display_name in numeric_fields.items():
            try:
                temp_df[col_name] = temp_df[display_name]
            except Exception as e:
                logger.error(f"{display_name} 转换失败: {str(e)}")
                temp_df[col_name] = float('nan')

        temp_df = temp_df[
            [
                "stock_code",
                "date",
                "open",
                "close",
                "high",
                "low",
                "volume"
            ]
        ]
        return temp_df

    @staticmethod
    def stock_zh_a_hist_tx(
            symbol: str = "sz000001",
            start_date: str = "19000101",
            end_date: str = "20500101",
            adjust: str = "",
            timeout: float = None,
    ) -> pd.DataFrame:
        """
        腾讯证券-日频-股票历史数据
        https://gu.qq.com/sh000919/zs
        :param symbol: 带市场标识的股票或者指数代码
        :type symbol: str
        :param start_date: 开始日期
        :type start_date: str
        :param end_date: 结束日期
        :type end_date: str
        :param adjust: choice of {"qfq": "前复权", "hfq": "后复权", "": "不复权"}
        :type adjust: str
        :param timeout: choice of None or a positive float number
        :type timeout: float
        :return: 前复权的股票和指数数据
        :rtype: pandas.DataFrame
        """
        url = "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get"
        date_format = "%Y%m%d"
        start = datetime.strptime(start_date, date_format)
        end = datetime.strptime(end_date, date_format)
        start_format_str = start.strftime("%Y-%m-%d")
        end_format_str = end.strftime("%Y-%m-%d")

        delta_days = (end - start).days

        params = {
            "_var": f"kline_day",
            "param": f"{symbol},day,{start_format_str},{end_format_str},{str(delta_days)},{adjust}",
            "r": "0.8205512681390605",
        }
        r = requests.get(url, params=params, timeout=timeout)
        data_text = r.text
        data_json = demjson.decode(data_text[data_text.find("={") + 1:])["data"][
            symbol
        ]
        if "day" in data_json.keys():
            temp_df = pd.DataFrame(data_json["day"])
        elif "hfqday" in data_json.keys():
            temp_df = pd.DataFrame(data_json["hfqday"])
        else:
            temp_df = pd.DataFrame(data_json["qfqday"])
        big_df = pd.DataFrame()
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
        big_df = big_df.iloc[:, :6]
        big_df.columns = ["date", "open", "close", "high", "low", "amount"]
        big_df["date"] = pd.to_datetime(big_df["date"], errors="coerce").dt.date
        big_df["open"] = pd.to_numeric(big_df["open"], errors="coerce")
        big_df["close"] = pd.to_numeric(big_df["close"], errors="coerce")
        big_df["high"] = pd.to_numeric(big_df["high"], errors="coerce")
        big_df["low"] = pd.to_numeric(big_df["low"], errors="coerce")
        big_df["amount"] = pd.to_numeric(big_df["amount"], errors="coerce")
        big_df.drop_duplicates(inplace=True, ignore_index=True)
        big_df.index = pd.to_datetime(big_df["date"])
        big_df = big_df[start_date:end_date]
        big_df.reset_index(inplace=True, drop=True)
        return big_df


if __name__ == '__main__':
    market_code = MarketUtil.get_market_code("920799")
    df = Tencent().get_stock_data(stock_code="920799", market_code=market_code, start_date="20250601",
                                  end_date="20250607")
    print(df)

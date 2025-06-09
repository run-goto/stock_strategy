import logging

import pandas as pd
import requests

from services.data_souce.datasource import DataSource

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'  # 修复日志格式
)
logger = logging.getLogger(__name__)


class DongFangCaiFu(DataSource):
    def __init__(self):
        self.name = "东方财富"

    def do_get_stock_data(self, stock_code, market_code, start_time, end_time):
        return self.stock_zh_a_hist(
            symbol=stock_code,
            start_date=start_time,
            end_date=end_time
        )

    def stock_zh_a_hist(self,
                        symbol: str = "000001",
                        start_date: str = "19700101",
                        end_date: str = "20500101",
                        ) -> pd.DataFrame:
        """获取股票历史数据"""
        try:
            return self.do_stock_zh_a_hist(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as e:
            logger.error(f"获取股票 {symbol} 数据失败: {str(e)}")
            return pd.DataFrame()

    @staticmethod
    def do_stock_zh_a_hist(symbol: str = "000001",
                           period: str = "daily",
                           start_date: str = "19700101",
                           end_date: str = "20500101",
                           adjust: str = "",
                           timeout: float = None,
                           ) -> pd.DataFrame:
        """
        东方财富网-行情首页-沪深京 A 股-每日行情
        https://quote.eastmoney.com/concept/sh603777.html?from=classic
        :param symbol: 股票代码
        :type symbol: str
        :param period: choice of {'daily', 'weekly', 'monthly'}
        :type period: str
        :param start_date: 开始日期
        :type start_date: str
        :param end_date: 结束日期
        :type end_date: str
        :param adjust: choice of {"qfq": "前复权", "hfq": "后复权", "": "不复权"}
        :type adjust: str
        :param timeout: choice of None or a positive float number
        :type timeout: float
        :return: 每日行情
        :rtype: pandas.DataFrame
        """
        symbol_code = 1 if symbol.startswith("6") else 0
        adjust_dict = {"qfq": "1", "hfq": "2", "": "0"}
        period_dict = {"daily": "101", "weekly": "102", "monthly": "103"}
        url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
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
        r = requests.get(url, params=params, timeout=timeout)
        data_json = r.json()
        if not (data_json["data"] and data_json["data"]["klines"]):
            return pd.DataFrame()
        temp_df = pd.DataFrame([item.split(",") for item in data_json["data"]["klines"]])
        temp_df["股票代码"] = symbol
        temp_df.columns = [
            "日期",
            "开盘",
            "收盘",
            "最高",
            "最低",
            "成交量",
            "成交额",
            "振幅",
            "涨跌幅",
            "涨跌额",
            "换手率",
            "股票代码",
        ]

        numeric_fields = {
            "stock_code": "股票代码",
            "date": "日期",
            "open": "开盘",
            "close": "收盘",
            "high": "最高",
            "low": "最低",
            "volume": "成交量"
        }
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


if __name__ == '__main__':
    df = DongFangCaiFu().stock_zh_a_hist(symbol="603777", start_date="20250601",
                                         end_date="20250607")
    print(df)

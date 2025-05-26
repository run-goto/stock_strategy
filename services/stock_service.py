from time import sleep

import akshare as ak
from datetime import datetime, time
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import logging

import requests

# from models.database import (
#     save_stock_list, save_stock_history, 
#     save_analysis_results, load_analysis_results
# )
from strategies import HighVolumeBreakoutStrategy, LongLowerShadowReboundStrategy, ThreeRisingPatternStrategy
from strategies.high_volume import HighVolumeStrategy

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_trade_days(n_days=30):
    """获取最近N个交易日"""
    today = datetime.now().date()
    trade_cal = ak.tool_trade_date_hist_sina()
    # 将trade_date转换为datetime.date类型
    trade_cal['trade_date'] = pd.to_datetime(trade_cal['trade_date']).dt.date
    trade_cal = trade_cal[trade_cal['trade_date'] <= today]
    trade_days = trade_cal['trade_date'].tail(n_days).tolist()
    # 转换为字符串格式
    start_date = trade_days[0].strftime('%Y%m%d')
    end_date = trade_days[-1].strftime('%Y%m%d')
    return start_date, end_date


def do_stock_zh_a_hist(
        symbol: str = "000001",
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
    market_code = 1 if symbol.startswith("6") else 0
    adjust_dict = {"qfq": "1", "hfq": "2", "": "0"}
    period_dict = {"daily": "101", "weekly": "102", "monthly": "103"}
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116",
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "klt": period_dict[period],
        "fqt": adjust_dict[adjust],
        "secid": f"{market_code}.{symbol}",
        "beg": start_date,
        "end": end_date,
    }
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Google Chrome";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"'
    }
    r = requests.get(url, params=params, timeout=timeout, headers=headers)
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
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    temp_df["开盘"] = pd.to_numeric(temp_df["开盘"], errors="coerce")
    temp_df["收盘"] = pd.to_numeric(temp_df["收盘"], errors="coerce")
    temp_df["最高"] = pd.to_numeric(temp_df["最高"], errors="coerce")
    temp_df["最低"] = pd.to_numeric(temp_df["最低"], errors="coerce")
    temp_df["成交量"] = pd.to_numeric(temp_df["成交量"], errors="coerce")
    temp_df["成交额"] = pd.to_numeric(temp_df["成交额"], errors="coerce")
    temp_df["振幅"] = pd.to_numeric(temp_df["振幅"], errors="coerce")
    temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
    temp_df["涨跌额"] = pd.to_numeric(temp_df["涨跌额"], errors="coerce")
    temp_df["换手率"] = pd.to_numeric(temp_df["换手率"], errors="coerce")
    temp_df = temp_df[
        [
            "日期",
            "股票代码",
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
        ]
    ]
    return temp_df


def stock_zh_a_hist(
        symbol: str = "000001",
        period: str = "daily",
        start_date: str = "19700101",
        end_date: str = "20500101",
        adjust: str = "",
        timeout: float = None
) -> pd.DataFrame:
    """获取股票历史数据"""
    try:
        # 根据股票代码判断交易所
        if symbol.startswith(('600', '601', '603', '605', '688')):
            exchange = 'sh'
        elif symbol.startswith(('000', '001', '002', '003', '300')):
            exchange = 'sz'
        elif symbol.startswith(('430', '830', '831', '832', '833', '834', '835', '836', '837', '838', '839')):
            exchange = 'bj'
        else:
            exchange = 'sh'  # 默认上海交易所

        symbol = f"{exchange}{symbol}"
        df = ak.stock_zh_a_hist_tx(symbol, start_date, end_date, adjust, timeout)
        df.columns = ["日期", "开盘", "收盘", "最高", "最低", "成交量"]
        return df
    except Exception as e:
        logger.error(f"获取股票 {symbol} 数据失败: {str(e)}")
        return pd.DataFrame()


def check_stock(stock_info, days, retry):
    """检查单个股票"""
    code = stock_info[0]
    name = stock_info[1]

    try:
        logger.info(f"正在获取 {name}({code}) 的历史数据...")
        start_date, end_date = get_trade_days(days)
        hist_data = stock_zh_a_hist(
            symbol=code,
            period="daily",
            adjust="qfq",
            start_date=start_date,
            end_date=end_date
        )

        if hist_data.empty:
            logger.warning(f"{name}({code}) 历史数据为空，跳过")
            raise ValueError("历史数据为空")

        # 确保数据按日期排序
        hist_data = hist_data.sort_values('日期')

        # 初始化策略
        strategies = [HighVolumeBreakoutStrategy(), LongLowerShadowReboundStrategy(), ThreeRisingPatternStrategy(),
                      HighVolumeStrategy()]

        for strategy in strategies:
            if strategy.check(hist_data):
                logger.info(f"{name}({code}) 符合{strategy.name}条件")
                return strategy.get_result(hist_data, code, name)

    except Exception as e:
        logger.error(f"获取 {name}({code}) 数据时出错: {str(e)}")
        if retry > 0:
            logger.info(f"重试获取 {name}({code}) 数据...")
            sleep(0.5)
            return check_stock(stock_info, days, retry - 1)
        return None
    return None


def update_stock_data(days=60):
    """更新股票数据"""
    try:
        logger.info("开始更新股票数据...")
        # 获取所有A股列表
        stock_info = ak.stock_info_a_code_name()
        logger.info(f"获取到 {len(stock_info)} 只股票")

        result_stocks = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            # 只使用code和name列
            stock_data = stock_info[['code', 'name']]
            future_to_stock = {
                executor.submit(check_stock, item, days, 3): item
                for item in stock_data.values
            }

            for future in as_completed(future_to_stock):
                try:
                    data = future.result()
                    if data:
                        result_stocks.append(data)
                except Exception as exc:
                    logger.error(f"处理股票时出错: {exc}")

        logger.info(f"数据更新完成，共找到 {len(result_stocks)} 只符合条件的股票")
        return result_stocks


    except Exception as e:
        logger.error(f"更新数据时出错: {str(e)}")
        return None

# file: services/stock_service.py

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import akshare as ak
import pandas as pd

from common.market_util import MarketUtil
from services.batch_insert import create_connection
from services.data_souce.tencent import Tencent
from strategies.base_strategy import BaseStrategy
from services.strategy_loader import load_strategies_from_config
from config.load_app_config import load_app_config

# 加载全局配置
config = load_app_config()

# 初始化日志
logging.basicConfig(
    level=config["logging"]["level"],
    format=config["logging"]["format"]
)
logger = logging.getLogger(__name__)


def get_trade_days(n_days=60):
    """获取最近N个交易日"""
    today = datetime.today().date()
    trade_cal = ak.tool_trade_date_hist_sina()
    trade_cal['trade_date'] = pd.to_datetime(trade_cal['trade_date']).dt.date
    trade_cal = trade_cal[trade_cal['trade_date'] <= today]
    trade_days = trade_cal['trade_date'].tail(n_days).tolist()
    start_date = trade_days[0].strftime('%Y%m%d')
    end_date = trade_days[-1].strftime('%Y%m%d')
    return start_date, end_date


def check_stock(stock_info, start_date, end_date, target_dates):
    code = stock_info[0]
    name = stock_info[1]

    try:
        logger.info(f"正在获取 {name}({code}) 的历史数据...")
        market_code = MarketUtil.get_market_code(code)

        # 根据配置选择数据源
        data_provider = config["data_source"]["provider"]
        if data_provider == "tencent":
            from services.data_souce.tencent import Tencent
            data_source = Tencent()
        elif data_provider == "dongfangcaifu":
            from services.data_souce.dfcf import DongFangCaiFu
            data_source = DongFangCaiFu()
        else:
            raise ValueError(f"不支持的数据源: {data_provider}")

        hist_data = data_source.get_stock_data(
            stock_code=code,
            market_code=market_code,
            start_date=start_date,
            end_date=end_date
        )

        if hist_data.empty:
            logger.warning(f"{name}({code}) 历史数据为空")
            return []

        # 确保按日期排序
        hist_data = hist_data.sort_values('date').reset_index(drop=True)

        # 构建日期索引映射
        date_to_index = {row['date'].strftime('%Y%m%d'): idx for idx, row in hist_data.iterrows()}

        results = []
        strategies = load_strategies_from_config()  #

        for target_date in target_dates:
            if target_date not in date_to_index:
                continue

            target_index = date_to_index[target_date]
            hist_data_for_check = hist_data.iloc[:target_index + 1]

            for strategy in strategies:
                if strategy.check(hist_data_for_check):
                    result = {
                        "code": code,
                        "name": name,
                        "strategy": strategy.name,
                        "target_date": target_date
                    }
                    results.append(result)

        return results

    except Exception as e:
        logger.error(f"处理 {name}({code}) 出错: {str(e)}")
        return []


# file: services/stock_service.py

def update_stock_data(start_date, end_date, target_dates):
    try:
        logger.info(f"开始更新股票数据，时间范围: {start_date} ~ {end_date}")
        stock_info = ak.stock_info_a_code_name()
        logger.info(f"获取到 {len(stock_info)} 只股票")

        max_workers = config["defaults"]["max_workers"]

        result_stocks = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(check_stock, item, start_date, end_date, target_dates): item
                for item in stock_info[['code', 'name']].values
            }

            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        result_stocks.extend(result)
                except Exception as exc:
                    logger.error(f"处理任务出错: {exc}")

        logger.info(f"数据更新完成，共找到 {len(result_stocks)} 条符合条件的记录")
        return result_stocks

    except Exception as e:
        logger.error(f"更新数据时出错: {str(e)}")
        return []


if __name__ == '__main__':
    start_date = '20250807'
    end_date = '20250814'
    logger.info(f"开始更新股票数据，时间范围: {start_date} ~ {end_date}")
    stock_info = ak.stock_info_a_code_name()
    logger.info(f"获取到 {len(stock_info)} 只股票")
    tencent = Tencent()
    conn = create_connection()
    for item in stock_info[['code', 'name']].values:
        code = item[0]
        name = item[1]
        market_code = MarketUtil.get_market_code(code)
        hist_data = tencent.get_stock_data(stock_code=code, market_code=market_code, start_date=start_date,
                                           end_date=end_date)

        if hist_data.empty:
            logger.warning(f"{name}({code}) 历史数据为空")

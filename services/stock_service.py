import logging
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from time import sleep

import akshare as ak
import pandas as pd

from common.market_util import MarketUtil
from services.data_souce.tencent import Tencent
from strategies import LongLowerShadowReboundStrategy, ThreeRisingPatternStrategy
from strategies.high_volume import HighVolumeStrategy

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_trade_days(n_days=30):
    """获取最近N个交易日"""
    today = datetime.today().date()
    trade_cal = ak.tool_trade_date_hist_sina()
    # 将trade_date转换为datetime.date类型
    trade_cal['trade_date'] = pd.to_datetime(trade_cal['trade_date']).dt.date
    trade_cal = trade_cal[trade_cal['trade_date'] <= today]
    trade_days = trade_cal['trade_date'].tail(n_days).tolist()
    # 转换为字符串格式
    start_date = trade_days[0].strftime('%Y%m%d')
    end_date = trade_days[-1].strftime('%Y%m%d')
    return start_date, end_date


def check_stock(stock_info, days, retry):
    """检查单个股票"""
    code = stock_info[0]
    name = stock_info[1]

    try:
        logger.info(f"正在获取 {name}({code}) 的历史数据...")
        start_date, end_date = get_trade_days(days)
        market_code = MarketUtil.get_market_code(code)
        tencent = Tencent()
        hist_data = tencent.get_stock_data(stock_code=code,
                                           market_code=market_code,
                                           start_date=start_date,
                                           end_date=end_date)
        if hist_data.empty:
            logger.warning(f"{name}({code}) 历史数据为空，记录失败信息")
            # 记录失败的股票代码到文件，以便下次启动时重新获取
            with open('failed_stocks.txt', 'a') as f:
                f.write(f"{code},{name},{start_date},{end_date}\n")
            raise ValueError("历史数据为空")
        # 确保数据按日期排序
        hist_data = hist_data.sort_values('date')

        # 初始化策略
        strategies = [LongLowerShadowReboundStrategy(), ThreeRisingPatternStrategy(),
                      HighVolumeStrategy()]

        for strategy in strategies:
            if strategy.check(hist_data):
                logger.info(f"{name}({code}) 符合{strategy.name}条件")
                return strategy.get_result(hist_data, code, name)
    except Exception as e:
        logger.error(f"获取 {name}({code}) 数据时出错: {str(e)}")
        if retry > 0:
            logger.info(f"重试获取 {name}({code}) 数据...")
            sleep(random.uniform(0.1, 1.5))
            return check_stock(stock_info, days, retry - 1)
        return None
    return None


def update_stock_data(days=60, end_date=None):
    """更新股票数据"""
    try:
        logger.info("开始更新股票数据...")
        # 获取所有A股列表
        stock_info = ak.stock_info_a_code_name()
        logger.info(f"获取到 {len(stock_info)} 只股票")

        result_stocks = []
        with ThreadPoolExecutor(max_workers=50) as executor:
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


if __name__ == '__main__':
    update_stock_data()

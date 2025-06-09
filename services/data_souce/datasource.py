import logging
import time
from abc import ABC

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'  # 修复日志格式
)
logger = logging.getLogger(__name__)


class DataSource(ABC):

    def get_stock_data(self, stock_code, market_code, start_date, end_date):
        """
        获取指定股票在特定时间段内的交易数据。

        参数:
            stock_code (str): 股票代码，例如 '600000' 或 '000001'
            market_code (str): 交易所，格式应为 'sh'
            start_time (str): 开始时间，格式应为 'yyyymmdd'
            end_time (str): 结束时间，格式应为 'yyyymmdd'

        返回:
            dict or None: 包含股票交易数据的字典，如果未找到数据则返回 None
        """
        start_time = time.time()
        data = self.do_get_stock_data(stock_code, market_code, start_date, end_date)
        end_time = time.time()
        logger.info(f"获取 {stock_code} 数据耗时: {(end_time - start_time) * 1000}ms")
        return data

    def do_get_stock_data(self, stock_code, market_code, start_time, end_time):
        pass

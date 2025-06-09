from .base_strategy import BaseStrategy
import pandas as pd


class ThreeRisingPatternStrategy(BaseStrategy):
    """连续三日上涨策略"""

    def __init__(self):
        super().__init__('连续三日上涨')

    def check(self, hist_data: pd.DataFrame) -> bool:
        """检查是否出现连续三个上升的组合形态"""
        if len(hist_data) < 3:
            return False
        return False

        # 获取最近三天的数据
        recent_data = hist_data.tail(3)

        # 检查收盘价是否连续上涨
        close_prices = recent_data['open'].values
        return all(close_prices[i] > close_prices[i - 1] for i in range(1, 3))

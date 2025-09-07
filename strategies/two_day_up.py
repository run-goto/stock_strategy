from .base_strategy import BaseStrategy
import pandas as pd


class TwoDayUpStrategy(BaseStrategy):
    """高成交量突破策略"""

    def __init__(self):
        super().__init__('连续两天上涨')

    """
    hist_data =    [[
                "stock_code",
                "date",
                "open",
                "close",
                "high",
                "low",
                "volume"
            ]]
    """

    def check(self, hist_data: pd.DataFrame) -> bool:
        """
        检查是否符合"连续两天上涨且涨幅都超过9%"的策略
        """

        if len(hist_data) < 30:
            return False

        today = hist_data.iloc[-1]
        pre_day = hist_data.iloc[-2]
        pre_day_02 = hist_data.iloc[-3]

        # 计算两天的涨跌幅
        today_change_percent = (today['close'] - min(pre_day['close'], today['open'])) / pre_day['close'] * 100
        pre_day_change_percent = (pre_day['close'] - min(pre_day_02['close'], today['open'])) / pre_day_02['open'] * 100

        # 条件：两天都必须是阳线且涨幅都超过9%
        if today_change_percent <= 9 or pre_day_change_percent <= 9:
            return False

        return True

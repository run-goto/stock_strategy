from .base_strategy import BaseStrategy
import pandas as pd


class BreakM100(BaseStrategy):
    """突破M100日线"""

    def __init__(self):
        super().__init__('突破M100日线')

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
        判断股票是否首次突破 M100 日线（100日均线）
        条件：
        - 当日收盘价 > MA100
        - 前一日收盘价 <= 前一日 MA100
        """
        if len(hist_data) < 101:
            return False

        # 计算100日均线
        hist_data['ma100'] = hist_data['close'].rolling(window=100).mean()

        # 获取当日和前一日数据
        today = hist_data.iloc[-1]
        yesterday = hist_data.iloc[-2]

        # 判断是否为首次突破 M100
        if today['close'] > today['ma100'] and yesterday['close'] <= yesterday['ma100']:
            return True

        return False

from .base_strategy import BaseStrategy
import pandas as pd


class ContinuationGapStrategy(BaseStrategy):
    """持续缺口策略"""

    def __init__(self):
        """
        初始化策略
        """
        super().__init__('持续缺口')

    def check(self, hist_data: pd.DataFrame) -> bool:
        if len(hist_data) < 2:
            return False

        yesterday = hist_data.iloc[-2]
        today = hist_data.iloc[-1]

        # 向上缺口
        gap_up_ratio = (today['open'] - yesterday['close']) / yesterday['close']
        is_gap_up = gap_up_ratio >= 0.2

        # 判断缺口是否未被回补（今日最低价 > 昨日收盘价）
        not_filled = today['low'] > yesterday['close']

        # 成交量判断（可选）
        recent_volume_mean = hist_data['volume'].iloc[:-1].mean()
        sufficient_volume = today['volume'] > recent_volume_mean * 2

        return is_gap_up and not_filled and sufficient_volume

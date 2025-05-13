from .base_strategy import BaseStrategy
import pandas as pd

class LongLowerShadowReboundStrategy(BaseStrategy):
    """长下阴线反弹策略"""
    def __init__(self):
        super().__init__('长下阴线反弹')

    def check(self, hist_data: pd.DataFrame) -> bool:
        return False
        if len(hist_data) < 1:
            return False
        today = hist_data.iloc[-1]
        # 下影线长度 = min(开盘, 收盘) - 最低价
        lower_shadow = min(today['开盘'], today['收盘']) - today['最低']
        # 实体长度 = abs(收盘 - 开盘)
        body = abs(today['收盘'] - today['开盘'])
        # 长下影线：下影线长度大于实体的2倍
        is_long_lower_shadow = lower_shadow > 3 * body
        # 收盘价较最低价上涨超2%
        rebound = (today['收盘'] - today['最低']) / today['最低'] > 0.04
        return is_long_lower_shadow and rebound 
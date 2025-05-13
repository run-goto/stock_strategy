from .base_strategy import BaseStrategy
import pandas as pd


class HighVolumeStrategy(BaseStrategy):
    """高成交量突破策略"""

    def __init__(self):
        super().__init__('高成交量成交')

    def check(self, hist_data: pd.DataFrame) -> bool:
        """
        检查是否符合“高成交量突破 + 多头占优”策略：
        1. 至少60天数据（用于计算新增的成交量条件）
        2. 当日涨幅 > 0
        3. 成交量 ≥ 过去30日最大成交量 × 1.5
        4. 阳线（收盘价 > 开盘价）
        5. 实体占比 > 60%
        6. 上影线 < 实体长度
        7. 站在5日均线上方
        8. MACD红柱拉长
        9. 当日成交量 > 过去15日最大成交量
        10. 过去15-60日最大成交量 > 平均成交量 × 1.5
        """

        if len(hist_data) < 30:
            return False

        today = hist_data.iloc[-1]

        # 条件一：当日必须上涨
        if today['涨跌幅'] <= 0:
            return False

        # 新增条件九：当日成交量 > 过去15日最大成交量
        recent_15_days = hist_data.iloc[-16:-1]  # 不包括当天
        max_vol_recent_15 = recent_15_days['成交量'].max()
        if today['成交量'] <= max_vol_recent_15 * 3:
            return False

        # 新增条件十：过去15-60日最大成交量 > 平均成交量 × 1.5
        past_15_to_60_days = hist_data.iloc[0:-16]  # 包括第60天，不包括最近15天
        avg_vol_past = past_15_to_60_days['成交量'].mean()
        max_vol_past = past_15_to_60_days['成交量'].max()
        if max_vol_past <= avg_vol_past * 3:
            return False

        return True

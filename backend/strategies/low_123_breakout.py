from .base_strategy import BaseStrategy
import pandas as pd
import numpy as np


class Low123BreakoutStrategy(BaseStrategy):
    """ST-02: 低位123结构突破策略
    
    识别日线级别的低位123结构,突破高点2时入场。
    
    形态识别规则:
    1. 找到阶段性低点1(20日最低)
    2. 低点1之后出现反弹高点2(反弹幅度 > 5%)
    3. 随后回落形成低点3,要求:低点3 > 低点1,且低点3出现后10日内未创新低
    
    入场信号: 收盘价突破高点2的价格水平(突破幅度 ≥ 1%)
    止损设置: 初始止损设于低点3下方1%
    """

    def __init__(self):
        super().__init__('低位123结构突破')

    def check(self, hist_data: pd.DataFrame) -> bool:
        """检查是否符合低位123结构突破策略"""
        if len(hist_data) < 60:  # 需要足够的数据来识别形态
            return False

        closes = hist_data['close'].values
        lows = hist_data['low'].values
        highs = hist_data['high'].values
        
        today_idx = len(hist_data) - 1
        today_close = closes[today_idx]

        # 寻找20日内的最低点作为候选低点1
        lookback_20 = min(20, len(hist_data))
        low1_idx = np.argmin(lows[-lookback_20:]) + (len(hist_data) - lookback_20)
        low1_price = lows[low1_idx]

        # 在低点1之后寻找反弹高点2
        after_low1 = hist_data.iloc[low1_idx + 1:]
        if len(after_low1) < 5:
            return False

        high2_idx_in_after = np.argmax(after_low1['high'].values)
        high2_idx = low1_idx + 1 + high2_idx_in_after
        high2_price = highs[high2_idx]

        # 检查反弹幅度是否 > 5%
        rebound_ratio = (high2_price - low1_price) / low1_price
        if rebound_ratio <= 0.05:
            return False

        # 在高点2之后寻找低点3
        after_high2 = hist_data.iloc[high2_idx + 1:]
        if len(after_high2) < 3:
            return False

        low3_idx_in_after = np.argmin(after_high2['low'].values)
        low3_idx = high2_idx + 1 + low3_idx_in_after
        low3_price = lows[low3_idx]

        # 检查低点3 > 低点1
        if low3_price <= low1_price:
            return False

        # 检查低点3出现后10日内未创新低
        after_low3_days = today_idx - low3_idx
        if after_low3_days < 1 or after_low3_days > 10:
            return False

        low3_to_today = lows[low3_idx:today_idx + 1]
        if np.min(low3_to_today) < low3_price:
            return False

        # 检查今日是否突破高点2,突破幅度 >= 1%
        breakout_ratio = (today_close - high2_price) / high2_price
        if breakout_ratio < 0.01:
            return False

        return True


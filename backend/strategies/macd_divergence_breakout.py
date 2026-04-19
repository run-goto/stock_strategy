from .base_strategy import BaseStrategy
import pandas as pd
import numpy as np


class MACDDivergenceBreakoutStrategy(BaseStrategy):
    """ST-03: MACD底背离双突破策略
    
    股价创新低而MACD黄白线(DIFF)未创新低,随后价格突破趋势线与水平阻力线时入场。
    
    底背离识别:
    1. 寻找60日内的两个显著低点(波谷)
    2. 股价低点B < 低点A,且对应的DIFF值低点b ≥ 低点a(允许误差 ±3%)
    
    双突破条件:
    1. 绘制连接低点A之前的反弹高点与低点B之后近期高点的下降趋势线
    2. 以低点B之后的反弹高点做水平阻力线
    3. 当日收盘价同时站上趋势线延伸值和水平阻力线
    
    止损设置: 初始止损设于低点B下方2%
    """

    def __init__(self):
        super().__init__('MACD底背离双突破')

    def _calculate_macd(self, prices, fast=12, slow=26, signal=9):
        """计算MACD指标"""
        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()
        diff = ema_fast - ema_slow
        dea = diff.ewm(span=signal, adjust=False).mean()
        macd = (diff - dea) * 2
        return diff, dea, macd

    def _find_significant_lows(self, hist_data, lookback=60):
        """寻找显著的波谷低点"""
        if len(hist_data) < lookback:
            return []

        data = hist_data.tail(lookback).copy()
        lows = data['low'].values
        closes = data['close'].values
        indices = data.index.values

        # 找到局部低点(前后各3天都比它高)
        significant_lows = []
        for i in range(3, len(lows) - 3):
            if (lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i-3] and
                lows[i] < lows[i+1] and lows[i] < lows[i+2] and lows[i] < lows[i+3]):
                significant_lows.append({
                    'idx': i,
                    'price': lows[i],
                    'date_idx': indices[i]
                })

        return significant_lows

    def check(self, hist_data: pd.DataFrame) -> bool:
        """检查是否符合MACD底背离双突破策略"""
        if len(hist_data) < 80:  # 需要足够数据计算MACD和识别形态
            return False

        closes = hist_data['close']
        
        # 计算MACD
        diff, dea, macd = self._calculate_macd(closes)
        hist_data = hist_data.copy()
        hist_data['diff'] = diff.values

        # 寻找60日内的显著低点
        significant_lows = self._find_significant_lows(hist_data, lookback=60)
        
        if len(significant_lows) < 2:
            return False

        # 检查是否有底背离:找最近的两个低点
        low_a = significant_lows[-2]  # 较早的低点
        low_b = significant_lows[-1]  # 较晚的低点

        # 股价:低点B < 低点A
        if low_b['price'] >= low_a['price']:
            return False

        # 获取对应的DIFF值
        diff_values = hist_data['diff'].values
        diff_a = diff_values[low_a['idx']]
        diff_b = diff_values[low_b['idx']]

        # DIFF:低点b >= 低点a (允许误差±3%)
        if diff_b < diff_a * 0.97:
            return False

        # 检查双突破条件
        today_idx = len(hist_data) - 1
        today_close = hist_data.iloc[-1]['close']

        # 找到低点B之后的最高点作为水平阻力线
        after_low_b = hist_data.iloc[low_b['idx']:]
        if len(after_low_b) < 3:
            return False
        
        resistance_level = after_low_b['high'].max()

        # 简化:检查今日收盘价是否突破阻力位
        breakout_ratio = (today_close - resistance_level) / resistance_level
        if breakout_ratio < 0.01:  # 突破幅度至少1%
            return False

        return True


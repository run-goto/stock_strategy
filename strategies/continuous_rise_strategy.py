from strategies.base_strategy import BaseStrategy
import pandas as pd
import numpy as np

class ContinuousRiseStrategy(BaseStrategy):
    """连续两天上涨策略"""
    
    def __init__(self, threshold=9, volume_multiple=2):
        self.threshold = threshold
        self.volume_multiple = volume_multiple
    
    def check(self, hist_data: pd.DataFrame) -> bool:
        if len(hist_data) < 30:
            return False
            
        # 获取最近两天的数据
        recent_data = hist_data.tail(2)
        
        # 检查是否连续两天上涨
        if not all(recent_data['涨跌幅'] > self.threshold):
            return False
            
        # 计算最近30天的平均成交量
        avg_volume = hist_data['成交量'].mean()
        
        # 检查当日成交量是否超过平均成交量的指定倍数
        if hist_data.iloc[-1]['成交量'] < avg_volume * self.volume_multiple:
            return False
            
        return True 
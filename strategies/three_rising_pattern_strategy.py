from .base_strategy import BaseStrategy
import pandas as pd

class ThreeRisingPatternStrategy(BaseStrategy):
    """连续三个上升形态策略"""
    
    def __init__(self):
        super().__init__('连续三个上升形态')
    
    def check(self, hist_data: pd.DataFrame) -> bool:
        """检查是否出现连续三个上升的组合形态"""
        if len(hist_data) < 3:
            return False
        
        # 获取最近三天的数据
        recent_data = hist_data.tail(3)
        
        # 检查收盘价是否连续上涨
        close_prices = recent_data['收盘'].values
        if not all(close_prices[i] > close_prices[i-1] for i in range(1, 3)):
            return False
        
        # 检查开盘价是否低于前一天的收盘价
        for i in range(1, 3):
            if recent_data.iloc[i]['开盘'] >= recent_data.iloc[i-1]['收盘']:
                return False
        
        # 检查成交量是否递增
        volumes = recent_data['成交量'].values
        if not all(volumes[i] > volumes[i-1] for i in range(1, 3)):
            return False
        
        return True 
from strategies.base_strategy import BaseStrategy
import pandas as pd

class ThreeSmallRiseStrategy(BaseStrategy):
    """三只小阳线策略"""
    
    def check(self, hist_data: pd.DataFrame) -> bool:
        if len(hist_data) < 3:
            return False
            
        # 获取最近三天的数据
        recent_data = hist_data.tail(3)
        
        # 检查是否连续三天上涨
        if not all(recent_data['涨跌幅'] > 0):
            return False
            
        # 检查是否都是小阳线（涨幅小于3%）
        if not all(recent_data['涨跌幅'] < 3):
            return False
            
        return True 
from .base_strategy import BaseStrategy
import pandas as pd

class PriceIncreaseStrategy(BaseStrategy):
    """涨幅策略"""
    
    def __init__(self, threshold: float, days: int):
        super().__init__('涨幅策略')
        self.threshold = threshold
        self.days = days
    
    def check(self, hist_data: pd.DataFrame) -> bool:
        """检查股票是否符合涨幅条件"""
        if len(hist_data) < self.days:
            return False
            
        latest_change = hist_data['涨跌幅'].iloc[-1]
        hist_changes = hist_data['涨跌幅'].iloc[-self.days:]
        
        return latest_change > self.threshold and (hist_changes > self.threshold).any() 
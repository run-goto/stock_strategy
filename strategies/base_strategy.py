from abc import ABC, abstractmethod
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class BaseStrategy(ABC):
    """策略基类"""
    
    def __init__(self, name):
        self.name = name
    
    @abstractmethod
    def check(self, hist_data: pd.DataFrame) -> bool:
        """检查是否符合策略条件"""
        pass
    
    def get_result(self, hist_data: pd.DataFrame, code: str, name: str) -> dict:
        """获取策略结果"""
        try:
            if self.check(hist_data):
                return {
                    'code': code,
                    'name': name,
                    'strategy': self.__class__.__name__,
                    'current_price': hist_data.iloc[-1]['收盘'],
                    'volume': hist_data.iloc[-1]['成交量']
                }
        except Exception as e:
            logger.error(f"策略 {self.__class__.__name__} 执行出错: {str(e)}")
        return None 
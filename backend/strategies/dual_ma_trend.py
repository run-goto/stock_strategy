from .base_strategy import BaseStrategy
import pandas as pd


class DualMATrendStrategy(BaseStrategy):
    """ST-01: 双均线趋势策略
    
    基于日线收盘价与MA100/MA60的关系判断趋势。
    
    入场信号:
    - 当日收盘价 > MA100(首次上穿)
    - 当日成交量 > 20日均量
    
    出场信号:
    - 收盘价 < MA60(首次下穿)
    - 或从最高点回撤超过8%
    
    初始止损: 入场当日最低价下方1%
    """

    def __init__(self):
        super().__init__('双均线趋势策略')

    def check(self, hist_data: pd.DataFrame) -> bool:
        """检查是否符合双均线趋势策略的买入条件"""
        if len(hist_data) < 101:  # 需要至少101天数据计算MA100
            return False

        # 计算均线
        hist_data = hist_data.copy()
        hist_data['ma100'] = hist_data['close'].rolling(window=100).mean()
        hist_data['ma60'] = hist_data['close'].rolling(window=60).mean()
        hist_data['ma20'] = hist_data['close'].rolling(window=20).mean()
        hist_data['vol_ma20'] = hist_data['volume'].rolling(window=20).mean()

        today = hist_data.iloc[-1]
        yesterday = hist_data.iloc[-2]

        # 检查是否为首次突破MA100
        # 今日收盘价 > MA100 且 昨日收盘价 <= 昨日MA100
        if pd.isna(today['ma100']) or pd.isna(yesterday['ma100']):
            return False

        breakout_ma100 = (today['close'] > today['ma100'] and 
                         yesterday['close'] <= yesterday['ma100'])

        if not breakout_ma100:
            return False

        # 检查成交量是否大于20日均量
        if pd.isna(today['vol_ma20']) or today['vol_ma20'] == 0:
            return False

        volume_condition = today['volume'] > today['vol_ma20']

        return breakout_ma100 and volume_condition


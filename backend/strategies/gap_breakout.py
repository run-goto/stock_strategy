from .base_strategy import BaseStrategy
import pandas as pd


class GapBreakoutStrategy(BaseStrategy):
    """ST-04: 向上突破缺口追涨策略
    
    股价以跳空缺口方式突破关键阻力位,视为强势信号,当日追涨。
    
    缺口识别:
    - 当日最低价 > 前一日最高价,形成向上跳空缺口
    
    关键阻力定义:
    - 前60日最高价
    - 前期震荡区间上沿
    - 或MA100均线
    
    入场条件:
    1. 缺口突破任一关键阻力位
    2. 缺口幅度 ≥ 1%
    3. 当日成交量 > 20日均量的1.5倍
    
    止损设置: 缺口上沿价格下方0.5%
    """

    def __init__(self):
        super().__init__('向上突破缺口追涨')

    def check(self, hist_data: pd.DataFrame) -> bool:
        """检查是否符合向上突破缺口追涨策略"""
        if len(hist_data) < 61:  # 需要至少61天数据
            return False

        yesterday = hist_data.iloc[-2]
        today = hist_data.iloc[-1]

        # 条件1: 识别向上跳空缺口
        # 今日最低价 > 昨日最高价
        gap_exists = today['low'] > yesterday['high']
        
        if not gap_exists:
            return False

        # 计算缺口幅度
        gap_ratio = (today['low'] - yesterday['high']) / yesterday['high']
        
        # 条件2: 缺口幅度 >= 1%
        if gap_ratio < 0.01:
            return False

        # 条件3: 成交量 > 20日均量的1.5倍
        vol_ma20 = hist_data['volume'].rolling(window=20).mean().iloc[-2]  # 使用昨日的20日均量
        if pd.isna(vol_ma20) or vol_ma20 == 0:
            return False
        
        volume_condition = today['volume'] > vol_ma20 * 1.5
        
        if not volume_condition:
            return False

        # 条件4: 突破关键阻力位
        # 检查是否突破前60日最高价(不包括今天)
        prev_60_days_high = hist_data['high'].iloc[-61:-1].max()
        
        # 或者突破MA100
        ma100 = hist_data['close'].rolling(window=100).mean().iloc[-1]
        
        # 今日收盘价突破任一阻力位
        breakout_resistance = (today['close'] > prev_60_days_high or 
                              (not pd.isna(ma100) and today['close'] > ma100))

        return breakout_resistance


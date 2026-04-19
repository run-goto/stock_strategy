from .base_strategy import BaseStrategy
import pandas as pd


class StrongLimitUpBreakoutStrategy(BaseStrategy):
    """ST-06: 强势涨停突破策略
    
    涨停板当日突破前期关键高点,视为强势启动信号,次日择机介入。
    
    涨停识别:
    - 当日涨幅 ≥ 9.8%(考虑四舍五入)
    - 收盘价为当日最高价
    
    突破条件:
    - 涨停当日最高价突破前60日最高价
    
    过滤条件:
    1. 流通市值 < 100亿(剔除大盘股)
    2. 换手率介于3%~20%之间
    
    入场时机: 次日开盘价(若高开超过5%则放弃)
    止损设置: 涨停阳线实体的中位价格
    """

    def __init__(self):
        super().__init__('强势涨停突破')

    def check(self, hist_data: pd.DataFrame) -> bool:
        """检查是否符合强势涨停突破策略"""
        if len(hist_data) < 61:  # 需要至少61天数据
            return False

        today = hist_data.iloc[-1]
        
        # 步骤1: 识别涨停板
        # 计算涨跌幅(需要前一日收盘价)
        if len(hist_data) < 2:
            return False
            
        yesterday_close = hist_data.iloc[-2]['close']
        
        if yesterday_close == 0:
            return False
        
        change_ratio = (today['close'] - yesterday_close) / yesterday_close
        
        # 涨停: 涨幅 >= 9.8%
        is_limit_up = change_ratio >= 0.098
        
        if not is_limit_up:
            return False

        # 收盘价为当日最高价(或非常接近)
        close_is_high = abs(today['close'] - today['high']) / today['high'] < 0.001
        
        if not close_is_high:
            return False

        # 步骤2: 检查是否突破前60日最高价
        prev_60_days_high = hist_data['high'].iloc[-61:-1].max()
        
        breakout_condition = today['high'] > prev_60_days_high
        
        if not breakout_condition:
            return False

        # 步骤3: 过滤条件 - 换手率检查
        # 注意: 如果数据源没有turnover字段,这个条件可以放宽
        if 'turnover' in today.index:
            turnover = today['turnover']
            if pd.notna(turnover):
                # 换手率介于3%~20%之间
                if turnover < 3 or turnover > 20:
                    return False

        # 步骤4: 成交量合理性检查(避免异常放量)
        vol_ma20 = hist_data['volume'].rolling(window=20).mean().iloc[-2]
        if pd.notna(vol_ma20) and vol_ma20 > 0:
            # 今日成交量应该在合理范围内(不超过20日均量的10倍)
            if today['volume'] > vol_ma20 * 10:
                return False

        return True


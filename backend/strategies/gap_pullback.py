from .base_strategy import BaseStrategy
import pandas as pd


class GapPullbackStrategy(BaseStrategy):
    """ST-05: 缺口回踩支撑买入策略
    
    出现突破缺口后,等待价格自然回踩缺口上沿,确认支撑有效后入场。
    
    前置条件:
    - 20个交易日内曾出现符合策略ST-04定义的突破缺口
    
    回踩确认条件:
    1. 股价从缺口形成后的高点回落,最低价触及缺口上沿 ±1% 区间
    2. 回落过程中成交量萎缩(< 20日均量)
    3. 随后出现放量阳线(涨幅 > 2% 且成交量 > 20日均量)
    
    入场信号: 确认阳线的收盘价
    止损设置: 缺口上沿下方1%
    """

    def __init__(self):
        super().__init__('缺口回踩支撑买入')

    def _find_recent_gap(self, hist_data, lookback=20):
        """寻找最近20日内的向上突破缺口"""
        if len(hist_data) < lookback + 1:
            return None

        for i in range(len(hist_data) - lookback, len(hist_data)):
            if i == 0:
                continue
                
            yesterday = hist_data.iloc[i - 1]
            today = hist_data.iloc[i]

            # 检查是否有向上缺口
            if today['low'] > yesterday['high']:
                gap_ratio = (today['low'] - yesterday['high']) / yesterday['high']
                
                # 缺口幅度 >= 1%
                if gap_ratio >= 0.01:
                    # 检查是否突破阻力位(前60日高点或MA100)
                    if i >= 60:
                        prev_60_high = hist_data['high'].iloc[i-61:i-1].max()
                        ma100 = hist_data['close'].iloc[:i].rolling(window=100).mean().iloc[-1]
                        
                        breakout = (today['close'] > prev_60_high or 
                                   (not pd.isna(ma100) and today['close'] > ma100))
                        
                        if breakout:
                            return {
                                'gap_date_idx': i,
                                'gap_top': yesterday['high'],  # 缺口上沿是昨日最高价
                                'gap_bottom': today['low']
                            }

        return None

    def check(self, hist_data: pd.DataFrame) -> bool:
        """检查是否符合缺口回踩支撑买入策略"""
        if len(hist_data) < 40:  # 需要足够数据
            return False

        # 步骤1: 寻找最近的突破缺口
        recent_gap = self._find_recent_gap(hist_data, lookback=20)
        
        if recent_gap is None:
            return False

        gap_top = recent_gap['gap_top']
        gap_date_idx = recent_gap['gap_date_idx']
        today_idx = len(hist_data) - 1

        # 缺口必须在今天之前
        if gap_date_idx >= today_idx:
            return False

        # 步骤2: 检查是否有回踩动作
        after_gap = hist_data.iloc[gap_date_idx:]
        
        # 找到缺口后的最高点
        high_after_gap = after_gap['high'].max()
        high_after_gap_idx = after_gap['high'].idxmax()

        # 从最高点开始回落
        from_peak = hist_data.loc[high_after_gap_idx:]
        
        if len(from_peak) < 3:
            return False

        # 步骤3: 检查今日是否回踩到缺口上沿 ±1% 区间
        today = hist_data.iloc[-1]
        tolerance = gap_top * 0.01
        
        touched_support = (abs(today['low'] - gap_top) <= tolerance or
                          abs(today['close'] - gap_top) <= tolerance)

        if not touched_support:
            return False

        # 步骤4: 检查回落过程中成交量是否萎缩
        vol_ma20_before = hist_data['volume'].rolling(window=20).mean().iloc[-2]
        if pd.isna(vol_ma20_before) or vol_ma20_before == 0:
            return False

        # 步骤5: 检查今日是否为放量阳线
        # 阳线: 收盘价 > 开盘价
        is_positive = today['close'] > today['open']
        
        if not is_positive:
            return False

        # 涨幅 > 2%
        change_ratio = (today['close'] - today['open']) / today['open']
        if change_ratio < 0.02:
            return False

        # 成交量 > 20日均量
        volume_condition = today['volume'] > vol_ma20_before

        return volume_condition


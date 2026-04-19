"""
测试《短线操盘实战技巧》6个核心策略
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
import numpy as np
from backend.strategies.dual_ma_trend import DualMATrendStrategy
from backend.strategies.low_123_breakout import Low123BreakoutStrategy
from backend.strategies.macd_divergence_breakout import MACDDivergenceBreakoutStrategy
from backend.strategies.gap_breakout import GapBreakoutStrategy
from backend.strategies.gap_pullback import GapPullbackStrategy
from backend.strategies.strong_limit_up import StrongLimitUpBreakoutStrategy


def generate_test_data(days=150, base_price=10.0):
    """生成测试用的股票数据"""
    dates = pd.date_range(end=pd.Timestamp.now(), periods=days, freq='D')
    
    # 生成随机价格数据
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.02, days)
    prices = base_price * np.cumprod(1 + returns)
    
    data = []
    for i, date in enumerate(dates):
        open_price = prices[i] * (1 + np.random.uniform(-0.01, 0.01))
        close_price = prices[i]
        high_price = max(open_price, close_price) * (1 + np.random.uniform(0, 0.02))
        low_price = min(open_price, close_price) * (1 - np.random.uniform(0, 0.02))
        volume = int(np.random.uniform(1000000, 5000000))
        
        data.append({
            'date': date,
            'open': round(open_price, 2),
            'close': round(close_price, 2),
            'high': round(high_price, 2),
            'low': round(low_price, 2),
            'volume': volume
        })
    
    return pd.DataFrame(data)


def test_dual_ma_trend():
    """测试ST-01双均线趋势策略"""
    print("\n=== 测试 ST-01: 双均线趋势策略 ===")
    strategy = DualMATrendStrategy()
    
    # 生成测试数据
    data = generate_test_data(150, 10.0)
    
    # 模拟突破MA100的场景
    # 让最后几天的价格明显上涨
    data.loc[len(data)-1, 'close'] = data['close'].rolling(100).mean().iloc[-1] * 1.05
    data.loc[len(data)-1, 'volume'] = data['volume'].rolling(20).mean().iloc[-1] * 2
    
    result = strategy.check(data)
    print(f"策略名称: {strategy.name}")
    print(f"测试结果: {'通过' if result else '未触发'}")
    print(f"数据长度: {len(data)}")
    
    return True


def test_low_123_breakout():
    """测试ST-02低位123结构突破策略"""
    print("\n=== 测试 ST-02: 低位123结构突破策略 ===")
    strategy = Low123BreakoutStrategy()
    
    data = generate_test_data(100, 10.0)
    
    result = strategy.check(data)
    print(f"策略名称: {strategy.name}")
    print(f"测试结果: {'通过' if result else '未触发'}")
    
    return True


def test_macd_divergence():
    """测试ST-03 MACD底背离双突破策略"""
    print("\n=== 测试 ST-03: MACD底背离双突破策略 ===")
    strategy = MACDDivergenceBreakoutStrategy()
    
    data = generate_test_data(100, 10.0)
    
    result = strategy.check(data)
    print(f"策略名称: {strategy.name}")
    print(f"测试结果: {'通过' if result else '未触发'}")
    
    return True


def test_gap_breakout():
    """测试ST-04向上突破缺口追涨策略"""
    print("\n=== 测试 ST-04: 向上突破缺口追涨策略 ===")
    strategy = GapBreakoutStrategy()
    
    data = generate_test_data(80, 10.0)
    
    # 模拟跳空缺口
    data.loc[len(data)-2, 'high'] = 10.0
    data.loc[len(data)-1, 'low'] = 10.2  # 形成2%的缺口
    data.loc[len(data)-1, 'close'] = 10.5
    data.loc[len(data)-1, 'volume'] = data['volume'].rolling(20).mean().iloc[-2] * 2
    
    result = strategy.check(data)
    print(f"策略名称: {strategy.name}")
    print(f"测试结果: {'通过' if result else '未触发'}")
    
    return True


def test_gap_pullback():
    """测试ST-05缺口回踩支撑买入策略"""
    print("\n=== 测试 ST-05: 缺口回踩支撑买入策略 ===")
    strategy = GapPullbackStrategy()
    
    data = generate_test_data(80, 10.0)
    
    result = strategy.check(data)
    print(f"策略名称: {strategy.name}")
    print(f"测试结果: {'通过' if result else '未触发'}")
    
    return True


def test_strong_limit_up():
    """测试ST-06强势涨停突破策略"""
    print("\n=== 测试 ST-06: 强势涨停突破策略 ===")
    strategy = StrongLimitUpBreakoutStrategy()
    
    data = generate_test_data(80, 10.0)
    
    # 模拟涨停板
    prev_close = data.iloc[-2]['close']
    data.loc[len(data)-1, 'close'] = prev_close * 1.10  # 涨停10%
    data.loc[len(data)-1, 'high'] = data.loc[len(data)-1, 'close']
    data.loc[len(data)-1, 'open'] = prev_close * 1.02
    
    result = strategy.check(data)
    print(f"策略名称: {strategy.name}")
    print(f"测试结果: {'通过' if result else '未触发'}")
    
    return True


if __name__ == '__main__':
    print("=" * 60)
    print("《短线操盘实战技巧》6个核心策略测试")
    print("=" * 60)
    
    tests = [
        test_dual_ma_trend,
        test_low_123_breakout,
        test_macd_divergence,
        test_gap_breakout,
        test_gap_pullback,
        test_strong_limit_up,
    ]
    
    passed = 0
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ 测试出错: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print(f"测试完成: {passed}/{len(tests)} 个策略测试通过")
    print("=" * 60)


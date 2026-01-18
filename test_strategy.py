# test_strategy.py - 策略调试脚本

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from services.db_service import get_all_stocks, get_daily_data_range
from services.strategy_loader import load_strategies_from_config

def test_strategy():
    print("=" * 50)
    print("策略调试测试")
    print("=" * 50)
    
    # 1. 加载策略
    strategies = load_strategies_from_config()
    print(f"\n可用策略 ({len(strategies)} 个):")
    for s in strategies:
        print(f"  - {s.name} ({s.__class__.__name__})")
    
    # 2. 获取股票列表
    stocks = get_all_stocks(limit=10)
    print(f"\n测试股票 ({len(stocks)} 只):")
    for s in stocks[:5]:
        print(f"  - {s['code']} {s['name']}")
    
    # 3. 测试日期范围
    start_date = "20260101"
    end_date = "20260114"
    print(f"\n日期范围: {start_date} ~ {end_date}")
    
    # 4. 测试数据获取和策略检查
    print("\n" + "=" * 50)
    print("开始测试策略检查...")
    print("=" * 50)
    
    for stock in stocks[:3]:
        code = stock['code']
        name = stock['name']
        print(f"\n测试股票: {code} {name}")
        
        # 获取行情数据
        daily_data = get_daily_data_range(code, start_date, end_date)
        print(f"  获取到 {len(daily_data)} 条行情数据")
        
        if not daily_data or len(daily_data) < 5:
            print("  数据不足，跳过")
            continue
        
        # 转换为 DataFrame
        df = pd.DataFrame(daily_data)
        print(f"  DataFrame 列名: {list(df.columns)}")
        
        df['date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
        df = df.sort_values('date').reset_index(drop=True)
        
        print(f"  最后一条数据:")
        last_row = df.iloc[-1]
        print(f"    日期: {last_row.get('trade_date')}")
        print(f"    开盘: {last_row.get('open')}")
        print(f"    收盘: {last_row.get('close')}")
        print(f"    成交量: {last_row.get('volume')}")
        
        # 测试每个策略
        for strategy in strategies:
            try:
                result = strategy.check(df)
                print(f"  策略 [{strategy.name}]: {'✓ 匹配' if result else '✗ 不匹配'}")
            except Exception as e:
                print(f"  策略 [{strategy.name}]: ❌ 错误 - {str(e)}")

if __name__ == "__main__":
    test_strategy()

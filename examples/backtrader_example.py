"""
Backtrader回测示例

演示如何使用Backtrader框架进行策略回测
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.infrastructure.persistence.duckdb_repository import DuckDBStockRepository
from backend.backtrader_integration import BacktestEngine, DualMATrendStrategyBT


def example_single_stock_backtest():
    """示例1: 单股票回测"""
    print("=" * 70)
    print("示例1: 单股票回测 - 双均线趋势策略")
    print("=" * 70)
    
    # 初始化
    repository = DuckDBStockRepository("stock_data.duckdb")
    engine = BacktestEngine(repository)
    
    # 运行回测
    result = engine.run_single_stock(
        stock_code='000001',  # 平安银行
        strategy_class=DualMATrendStrategyBT,
        start_date='20230101',
        end_date='20231231',
        initial_cash=100000,
        commission=0.0003,  # 万分之三佣金
        strategy_params={
            'ma100_period': 100,
            'ma60_period': 60,
            'drawdown_limit': 0.08,
            'stop_loss_pct': 0.01,
        },
        printlog=True
    )
    
    # 打印结果
    print("\n" + "=" * 70)
    print("回测结果汇总")
    print("=" * 70)
    print(f"股票代码: {result.stock_code}")
    print(f"策略名称: {result.strategy_name}")
    print(f"回测区间: {result.start_date} ~ {result.end_date}")
    print(f"初始资金: ¥100,000.00")
    print(f"最终资金: ¥{result.final_value:,.2f}")
    print(f"总收益率: {result.total_return*100:.2f}%")
    print(f"年化收益: {result.annualized_return*100:.2f}%")
    print(f"夏普比率: {result.sharpe_ratio:.2f}")
    print(f"最大回撤: {result.max_drawdown:.2f}%")
    print(f"交易次数: {result.total_trades}")
    print(f"盈利次数: {result.winning_trades}")
    print(f"亏损次数: {result.losing_trades}")
    print(f"胜率: {result.win_rate*100:.2f}%")
    print("=" * 70)
    
    return result


def example_parameter_optimization():
    """示例2: 参数优化"""
    print("\n" + "=" * 70)
    print("示例2: 策略参数优化")
    print("=" * 70)
    
    # 初始化
    repository = DuckDBStockRepository("stock_data.duckdb")
    engine = BacktestEngine(repository)
    
    # 定义参数范围
    param_ranges = {
        'ma100_period': [80, 100, 120],
        'ma60_period': [40, 60, 80],
        'drawdown_limit': [0.05, 0.08, 0.10],
    }
    
    # 运行参数优化
    opt_results = engine.optimize_strategy(
        stock_code='000001',
        strategy_class=DualMATrendStrategyBT,
        start_date='20230101',
        end_date='20231231',
        param_ranges=param_ranges,
        initial_cash=100000,
    )
    
    # 打印最优参数
    print("\n最优参数组合 (Top 5):")
    print("-" * 70)
    if not opt_results.empty:
        top5 = opt_results.head(5)
        for idx, row in top5.iterrows():
            print(f"\n排名 {idx + 1}:")
            print(f"  MA100周期: {int(row['ma100_period'])}")
            print(f"  MA60周期: {int(row['ma60_period'])}")
            print(f"  最大回撤: {row['drawdown_limit']*100:.1f}%")
            print(f"  总收益率: {row['total_return']*100:.2f}%")
            print(f"  年化收益: {row['annualized_return']*100:.2f}%")
    
    print("=" * 70)
    
    return opt_results


def example_batch_backtest():
    """示例3: 批量回测"""
    print("\n" + "=" * 70)
    print("示例3: 批量回测多只股票")
    print("=" * 70)
    
    # 初始化
    repository = DuckDBStockRepository("stock_data.duckdb")
    engine = BacktestEngine(repository)
    
    # 选择几只股票
    stock_codes = ['000001', '000002', '600000']  # 平安银行、万科A、浦发银行
    
    # 批量回测
    results = engine.run_multiple_stocks(
        stock_codes=stock_codes,
        strategy_class=DualMATrendStrategyBT,
        start_date='20230101',
        end_date='20231231',
        initial_cash=100000,
        strategy_params={
            'ma100_period': 100,
            'ma60_period': 60,
        }
    )
    
    # 打印汇总
    print("\n批量回测结果汇总:")
    print("-" * 70)
    print(f"{'股票代码':<10} {'收益率':<12} {'夏普比率':<10} {'最大回撤':<10} {'交易次数':<10}")
    print("-" * 70)
    
    for result in results:
        print(
            f"{result.stock_code:<10} "
            f"{result.total_return*100:>8.2f}%   "
            f"{result.sharpe_ratio:>8.2f}   "
            f"{result.max_drawdown:>8.2f}%  "
            f"{result.total_trades:>8}"
        )
    
    print("=" * 70)
    
    return results


if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("Backtrader回测示例")
    print("=" * 70)
    
    try:
        # 运行示例1: 单股票回测
        result1 = example_single_stock_backtest()
        
        # 运行示例2: 参数优化 (可选,耗时较长)
        # opt_results = example_parameter_optimization()
        
        # 运行示例3: 批量回测
        # results = example_batch_backtest()
        
        print("\n✅ 回测示例执行完成!")
        
    except Exception as e:
        print(f"\n❌ 回测失败: {e}")
        import traceback
        traceback.print_exc()


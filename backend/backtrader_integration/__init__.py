"""
Backtrader集成模块
提供基于Backtrader的策略回测功能
"""
from .data_feed import DuckDBDataFeed, load_stock_data_from_duckdb, create_backtrader_datafeed
from .strategies_bt import DualMATrendStrategyBT
from .backtest_engine import BacktestEngine, BacktestResult

__all__ = [
    'DuckDBDataFeed',
    'load_stock_data_from_duckdb',
    'create_backtrader_datafeed',
    'DualMATrendStrategyBT',
    'BacktestEngine',
    'BacktestResult',
]


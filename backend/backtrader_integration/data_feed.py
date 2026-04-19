"""
Backtrader数据适配器 - 从DuckDB加载股票数据
"""
import backtrader as bt
import pandas as pd
from datetime import datetime


class DuckDBDataFeed(bt.feeds.PandasData):
    """
    从DuckDB加载的股票数据适配到Backtrader
    
    数据字段映射:
    - datetime: date
    - open: open
    - high: high
    - low: low
    - close: close
    - volume: volume
    - openinterest: None (A股无此字段)
    """
    
    # 定义额外的数据字段
    lines = ('amount',)
    
    params = (
        ('datetime', 'date'),
        ('open', 'open'),
        ('high', 'high'),
        ('low', 'low'),
        ('close', 'close'),
        ('volume', 'volume'),
        ('openinterest', None),
        ('amount', 'amount'),
    )


def load_stock_data_from_duckdb(repository, stock_code: str, 
                                 start_date: str, end_date: str) -> pd.DataFrame:
    """
    从DuckDB加载股票历史数据
    
    Args:
        repository: DuckDBStockRepository实例
        stock_code: 股票代码
        start_date: 开始日期 (YYYYMMDD)
        end_date: 结束日期 (YYYYMMDD)
    
    Returns:
        DataFrame格式的历史数据
    """
    # 从repository获取数据
    df = repository.get_stock_history(stock_code, start_date, end_date)
    
    if df.empty:
        raise ValueError(f"未找到 {stock_code} 在 {start_date} 到 {end_date} 的数据")
    
    if 'trade_date' in df.columns and 'date' not in df.columns:
        df = df.rename(columns={'trade_date': 'date'})

    # 确保日期格式正确。当前仓储返回标准 date 列，旧仓储可能返回 trade_date。
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    
    # 选择需要的列
    df = df[['date', 'open', 'high', 'low', 'close', 'volume', 'amount']]
    
    # 按日期排序
    df = df.sort_values('date').reset_index(drop=True)
    
    return df


def create_backtrader_datafeed(repository, stock_code: str,
                                start_date: str, end_date: str) -> DuckDBDataFeed:
    """
    创建Backtrader数据源
    
    Args:
        repository: DuckDBStockRepository实例
        stock_code: 股票代码
        start_date: 开始日期 (YYYYMMDD)
        end_date: 结束日期 (YYYYMMDD)
    
    Returns:
        Backtrader DataFeed对象
    """
    df = load_stock_data_from_duckdb(repository, stock_code, start_date, end_date)
    
    datafeed = DuckDBDataFeed(dataname=df)
    
    return datafeed


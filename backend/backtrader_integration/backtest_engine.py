"""
Backtrader回测引擎

提供统一的回测执行接口,支持:
- 单股票回测
- 多股票批量回测
- 参数优化
- 结果分析
"""
import backtrader as bt
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
import logging

from .data_feed import create_backtrader_datafeed
from .strategies_bt import DualMATrendStrategyBT

logger = logging.getLogger(__name__)


class BacktestResult:
    """回测结果封装"""
    
    def __init__(self):
        self.stock_code: str = ""
        self.strategy_name: str = ""
        self.start_date: str = ""
        self.end_date: str = ""
        
        # 性能指标
        self.final_value: float = 0.0
        self.total_return: float = 0.0
        self.annualized_return: float = 0.0
        self.sharpe_ratio: float = 0.0
        self.max_drawdown: float = 0.0
        self.total_trades: int = 0
        self.winning_trades: int = 0
        self.losing_trades: int = 0
        self.win_rate: float = 0.0
        
        # 交易详情
        self.trades: List[Dict] = []
        
    def to_dict(self) -> Dict:
        return {
            'stock_code': self.stock_code,
            'strategy_name': self.strategy_name,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'final_value': self.final_value,
            'total_return': self.total_return,
            'annualized_return': self.annualized_return,
            'sharpe_ratio': self.sharpe_ratio,
            'max_drawdown': self.max_drawdown,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': self.win_rate,
        }


class BacktestEngine:
    """
    Backtrader回测引擎
    
    用法:
        engine = BacktestEngine(repository)
        result = engine.run_single_stock(
            stock_code='000001',
            strategy_class=DualMATrendStrategyBT,
            start_date='20230101',
            end_date='20231231',
            initial_cash=100000
        )
    """
    
    def __init__(self, repository):
        """
        初始化回测引擎
        
        Args:
            repository: DuckDBStockRepository实例
        """
        self.repository = repository
        
    def run_single_stock(
        self,
        stock_code: str,
        strategy_class: bt.Strategy,
        start_date: str,
        end_date: str,
        initial_cash: float = 100000,
        commission: float = 0.0003,  # 万分之三
        slippage: float = 0.0,
        strategy_params: Optional[Dict] = None,
        printlog: bool = True,
    ) -> BacktestResult:
        """
        运行单股票回测
        
        Args:
            stock_code: 股票代码
            strategy_class: Backtrader策略类
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
            initial_cash: 初始资金
            commission: 佣金比例
            slippage: 滑点比例
            strategy_params: 策略参数字典
            printlog: 是否打印日志
        
        Returns:
            BacktestResult对象
        """
        logger.info(f"开始回测 {stock_code} | {start_date} ~ {end_date}")
        
        # 创建Cerebro引擎
        cerebro = bt.Cerebro()
        
        # 添加数据
        try:
            data = create_backtrader_datafeed(
                self.repository, stock_code, start_date, end_date
            )
            cerebro.adddata(data)
        except Exception as e:
            logger.error(f"加载数据失败: {e}")
            raise
        
        # 添加策略
        if strategy_params is None:
            strategy_params = {}
        strategy_params['printlog'] = printlog
        cerebro.addstrategy(strategy_class, **strategy_params)
        
        # 设置初始资金
        cerebro.broker.setcash(initial_cash)
        
        # 设置佣金
        cerebro.broker.setcommission(commission=commission)
        if slippage:
            cerebro.broker.set_slippage_perc(perc=slippage)
        
        # 记录初始资金
        starting_cash = cerebro.broker.getvalue()
        logger.info(f'初始资金: {starting_cash:.2f}')
        
        # 添加分析器
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
        cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
        
        # 运行回测
        results = cerebro.run()
        strat = results[0]
        
        # 获取最终资金
        final_value = cerebro.broker.getvalue()
        logger.info(f'最终资金: {final_value:.2f}')
        
        # 构建回测结果
        result = BacktestResult()
        result.stock_code = stock_code
        result.strategy_name = strategy_class.__name__
        result.start_date = start_date
        result.end_date = end_date
        result.final_value = final_value
        result.total_return = (final_value - starting_cash) / starting_cash
        
        # 获取分析器结果
        sharpe = strat.analyzers.sharpe.get_analysis()
        drawdown = strat.analyzers.drawdown.get_analysis()
        returns = strat.analyzers.returns.get_analysis()
        trades = strat.analyzers.trades.get_analysis()
        
        result.sharpe_ratio = sharpe.get('sharperatio', 0) or 0
        result.max_drawdown = drawdown.get('max', {}).get('drawdown', 0) or 0
        result.annualized_return = returns.get('rnorm', 0) or 0
        
        # 交易统计
        if trades and 'total' in trades:
            result.total_trades = trades['total'].get('total', 0) or 0
            result.winning_trades = trades['won'].get('total', 0) or 0
            result.losing_trades = trades['lost'].get('total', 0) or 0
            
            if result.total_trades > 0:
                result.win_rate = result.winning_trades / result.total_trades
        
        logger.info(
            f"回测完成 | 收益率: {result.total_return*100:.2f}% | "
            f"夏普比率: {result.sharpe_ratio:.2f} | "
            f"最大回撤: {result.max_drawdown:.2f}% | "
            f"交易次数: {result.total_trades}"
        )
        
        return result
    
    def run_multiple_stocks(
        self,
        stock_codes: List[str],
        strategy_class: bt.Strategy,
        start_date: str,
        end_date: str,
        initial_cash: float = 100000,
        commission: float = 0.0003,
        slippage: float = 0.0,
        strategy_params: Optional[Dict] = None,
    ) -> List[BacktestResult]:
        """
        批量回测多只股票
        
        Args:
            stock_codes: 股票代码列表
            strategy_class: Backtrader策略类
            start_date: 开始日期
            end_date: 结束日期
            initial_cash: 每只股票的初始资金
            commission: 佣金比例
            slippage: 滑点比例
            strategy_params: 策略参数
        
        Returns:
            回测结果列表
        """
        results = []
        
        for stock_code in stock_codes:
            try:
                result = self.run_single_stock(
                    stock_code=stock_code,
                    strategy_class=strategy_class,
                    start_date=start_date,
                    end_date=end_date,
                    initial_cash=initial_cash,
                    commission=commission,
                    slippage=slippage,
                    strategy_params=strategy_params,
                    printlog=False,  # 批量运行时不打印详细日志
                )
                results.append(result)
            except Exception as e:
                logger.error(f"回测 {stock_code} 失败: {e}")
                continue
        
        return results
    
    def optimize_strategy(
        self,
        stock_code: str,
        strategy_class: bt.Strategy,
        start_date: str,
        end_date: str,
        param_ranges: Dict[str, list],
        initial_cash: float = 100000,
    ) -> pd.DataFrame:
        """
        策略参数优化
        
        Args:
            stock_code: 股票代码
            strategy_class: Backtrader策略类
            start_date: 开始日期
            end_date: 结束日期
            param_ranges: 参数范围字典,如 {'ma100_period': [80, 100, 120]}
            initial_cash: 初始资金
        
        Returns:
            参数优化结果DataFrame
        """
        logger.info(f"开始参数优化: {stock_code}")
        
        # 创建Cerebro引擎
        cerebro = bt.Cerebro(optreturn=True)
        
        # 添加数据
        data = create_backtrader_datafeed(
            self.repository, stock_code, start_date, end_date
        )
        cerebro.adddata(data)
        
        # 添加策略并设置优化参数
        cerebro.optstrategy(
            strategy_class,
            printlog=False,
            **param_ranges
        )
        
        # 设置初始资金和佣金
        cerebro.broker.setcash(initial_cash)
        cerebro.broker.setcommission(commission=0.0003)
        
        # 添加分析器
        cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
        
        # 运行优化
        opt_results = cerebro.run()
        
        # 收集结果
        optimization_results = []
        
        for strat_list in opt_results:
            for strat in strat_list:
                params = dict(strat.params._getitems())
                returns = strat.analyzers.returns.get_analysis()
                
                result = {
                    'params': params,
                    'total_return': returns.get('rtot', 0) or 0,
                    'annualized_return': returns.get('rnorm', 0) or 0,
                }
                optimization_results.append(result)
        
        # 转换为DataFrame
        df_results = pd.DataFrame(optimization_results)
        
        # 展开参数字典
        if not df_results.empty:
            params_df = pd.DataFrame(df_results['params'].tolist())
            df_results = pd.concat([params_df, df_results.drop('params', axis=1)], axis=1)
            
            # 按收益率排序
            df_results = df_results.sort_values('total_return', ascending=False)
        
        logger.info(f"参数优化完成,共测试 {len(df_results)} 组参数")
        
        return df_results


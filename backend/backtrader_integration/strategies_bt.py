"""
ST-01: 双均线趋势策略 (Backtrader版本)

基于日线收盘价与MA100/MA60的关系判断趋势。

入场信号:
- 当日收盘价 > MA100(首次上穿)
- 当日成交量 > 20日均量

出场信号:
- 收盘价 < MA60(首次下穿)
- 或从最高点回撤超过8%

初始止损: 入场当日最低价下方1%
"""
import backtrader as bt


class DualMATrendStrategyBT(bt.Strategy):
    """
    双均线趋势策略 - Backtrader实现
    
    参数:
        ma100_period: MA100周期,默认100
        ma60_period: MA60周期,默认60
        ma20_period: MA20周期,默认20
        vol_ma_period: 成交量均线周期,默认20
        drawdown_limit: 最大回撤比例,默认0.08 (8%)
        stop_loss_pct: 止损比例,默认0.01 (1%)
    """
    
    params = (
        ('ma100_period', 100),
        ('ma60_period', 60),
        ('ma20_period', 20),
        ('vol_ma_period', 20),
        ('drawdown_limit', 0.08),
        ('stop_loss_pct', 0.01),
        ('printlog', True),
    )
    
    def __init__(self):
        # 初始化指标
        self.ma100 = bt.indicators.SimpleMovingAverage(
            self.datas[0].close, period=self.params.ma100_period
        )
        self.ma60 = bt.indicators.SimpleMovingAverage(
            self.datas[0].close, period=self.params.ma60_period
        )
        self.ma20 = bt.indicators.SimpleMovingAverage(
            self.datas[0].close, period=self.params.ma20_period
        )
        self.vol_ma20 = bt.indicators.SimpleMovingAverage(
            self.datas[0].volume, period=self.params.vol_ma_period
        )
        
        # 交叉信号
        self.close_above_ma100 = self.datas[0].close > self.ma100
        self.close_below_ma60 = self.datas[0].close < self.ma60
        
        # 交易状态
        self.order = None
        self.buy_price = None
        self.buy_commission = None
        self.highest_price = None
        self.entry_low = None
        
    def log(self, txt, dt=None):
        """日志记录"""
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()} {txt}')
    
    def notify_order(self, order):
        """订单状态通知"""
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(
                    f'买入执行: 价格={order.executed.price:.2f}, '
                    f'成本={order.executed.value:.2f}, '
                    f'手续费={order.executed.comm:.2f}'
                )
                self.buy_price = order.executed.price
                self.buy_commission = order.executed.comm
                self.highest_price = order.executed.price
                self.entry_low = self.datas[0].low[0]
            else:
                self.log(
                    f'卖出执行: 价格={order.executed.price:.2f}, '
                    f'成本={order.executed.value:.2f}, '
                    f'手续费={order.executed.comm:.2f}'
                )
            
            self.bar_executed = len(self)
        
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('订单取消/保证金不足/拒绝')
        
        self.order = None
    
    def notify_trade(self, trade):
        """交易结果通知"""
        if not trade.isclosed:
            return
        
        self.log(f'交易利润, 毛利润={trade.pnl:.2f}, 净利润={trade.pnlcomm:.2f}')
    
    def next(self):
        """策略核心逻辑 - 每个bar执行"""
        # 如果有未完成订单,等待
        if self.order:
            return
        
        # 检查是否已持仓
        if not self.position:
            # === 入场条件 ===
            # 1. 收盘价突破MA100 (今日>MA100 且 昨日<=MA100)
            breakout_ma100 = (
                self.datas[0].close[0] > self.ma100[0] and
                self.datas[0].close[-1] <= self.ma100[-1]
            )
            
            # 2. 成交量大于20日均量
            volume_condition = self.datas[0].volume[0] > self.vol_ma20[0]
            
            if breakout_ma100 and volume_condition:
                # 计算仓位大小 (使用固定比例)
                size = int(self.broker.getcash() / self.datas[0].close[0] * 0.2)  # 20%仓位
                
                if size > 0:
                    self.log(f'买入信号: 收盘价={self.datas[0].close[0]:.2f}, '
                            f'MA100={self.ma100[0]:.2f}, '
                            f'成交量={self.datas[0].volume[0]}')
                    
                    # 买入并设置止损
                    self.order = self.buy(size=size)
                    
                    # 设置止损单 (入场价下方1%)
                    stop_price = self.datas[0].low[0] * (1 - self.params.stop_loss_pct)
                    self.sell(exectype=bt.Order.Stop, price=stop_price)
        
        else:
            # === 出场条件 ===
            current_price = self.datas[0].close[0]
            
            # 更新最高价
            if self.highest_price is None or current_price > self.highest_price:
                self.highest_price = current_price
            
            # 1. 收盘价跌破MA60
            if self.close_below_ma60[0]:
                self.log(f'卖出信号: 跌破MA60, 价格={current_price:.2f}')
                self.order = self.sell()
                return
            
            # 2. 从最高点回撤超过8%
            if self.highest_price:
                drawdown = (self.highest_price - current_price) / self.highest_price
                if drawdown > self.params.drawdown_limit:
                    self.log(f'卖出信号: 回撤{drawdown*100:.2f}%, 价格={current_price:.2f}')
                    self.order = self.sell()
                    return
    
    def stop(self):
        """回测结束时的统计"""
        self.log(
            f'回测完成 | '
            f'最终资金: {self.broker.getvalue():.2f} | '
            f'收益率: {(self.broker.getvalue() / self.broker.startingcash - 1) * 100:.2f}%'
        )


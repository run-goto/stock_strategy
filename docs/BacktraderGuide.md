# Backtrader回测框架使用指南

## 概述

本项目已集成Backtrader专业量化回测框架,提供强大的策略回测、参数优化和性能分析功能。

## 架构说明

```
backtrader_integration/
├── __init__.py              # 模块导出
├── data_feed.py             # DuckDB数据适配器
├── strategies_bt.py         # Backtrader策略实现
└── backtest_engine.py       # 回测引擎封装
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 运行示例

```bash
python examples/backtrader_example.py
```

### 3. 编写自己的回测脚本

```python
from backend.infrastructure.persistence.duckdb_repository import DuckDBStockRepository
from backend.backtrader_integration import BacktestEngine, DualMATrendStrategyBT

# 初始化
repository = DuckDBStockRepository("stock_data.duckdb")
engine = BacktestEngine(repository)

# 运行回测
result = engine.run_single_stock(
    stock_code='000001',
    strategy_class=DualMATrendStrategyBT,
    start_date='20230101',
    end_date='20231231',
    initial_cash=100000,
    commission=0.0003,
    slippage=0.001,
)

# 查看结果
print(f"收益率: {result.total_return*100:.2f}%")
print(f"夏普比率: {result.sharpe_ratio:.2f}")
```

## 核心组件

### 1. 数据适配器 (data_feed.py)

从DuckDB加载股票数据并转换为Backtrader格式:

```python
from backend.backtrader_integration import create_backtrader_datafeed

data = create_backtrader_datafeed(
    repository, 
    stock_code='000001',
    start_date='20230101',
    end_date='20231231'
)
```

### 2. 策略实现 (strategies_bt.py)

基于Backtrader的策略类,继承自`bt.Strategy`:

```python
import backtrader as bt

class MyStrategy(bt.Strategy):
    params = (
        ('param1', 10),
        ('param2', 20),
    )
    
    def __init__(self):
        # 初始化指标
        self.ma = bt.indicators.SimpleMovingAverage(
            self.datas[0].close, period=self.params.param1
        )
    
    def next(self):
        # 策略逻辑
        if not self.position:
            if self.datas[0].close > self.ma:
                self.buy()
        else:
            if self.datas[0].close < self.ma:
                self.sell()
```

### 3. 回测引擎 (backtest_engine.py)

提供高级API简化回测流程:

#### 单股票回测

```python
result = engine.run_single_stock(
    stock_code='000001',
    strategy_class=DualMATrendStrategyBT,
    start_date='20230101',
    end_date='20231231',
    initial_cash=100000,
    commission=0.0003,
    strategy_params={'ma100_period': 100}
)
```

#### 批量回测

```python
results = engine.run_multiple_stocks(
    stock_codes=['000001', '000002', '600000'],
    strategy_class=DualMATrendStrategyBT,
    start_date='20230101',
    end_date='20231231',
    initial_cash=100000
)
```

#### 参数优化

```python
opt_results = engine.optimize_strategy(
    stock_code='000001',
    strategy_class=DualMATrendStrategyBT,
    start_date='20230101',
    end_date='20231231',
    param_ranges={
        'ma100_period': [80, 100, 120],
        'ma60_period': [40, 60, 80],
    }
)
```

## 回测结果

`BacktestResult`对象包含以下指标:

| 指标 | 说明 |
|------|------|
| final_value | 最终资金 |
| total_return | 总收益率 |
| annualized_return | 年化收益率 |
| sharpe_ratio | 夏普比率 |
| max_drawdown | 最大回撤 |
| total_trades | 总交易次数 |
| winning_trades | 盈利交易数 |
| losing_trades | 亏损交易数 |
| win_rate | 胜率 |

## 已实现的策略

### ST-01: 双均线趋势策略 (DualMATrendStrategyBT)

**特点**:
- 基于MA100/MA60判断趋势
- 成交量过滤
- 自动止损和止盈
- 回撤控制

**参数**:
- `ma100_period`: MA100周期 (默认100)
- `ma60_period`: MA60周期 (默认60)
- `drawdown_limit`: 最大回撤 (默认8%)
- `stop_loss_pct`: 止损比例 (默认1%)

**用法**:
```python
from backend.backtrader_integration import DualMATrendStrategyBT

result = engine.run_single_stock(
    stock_code='000001',
    strategy_class=DualMATrendStrategyBT,
    start_date='20230101',
    end_date='20231231',
    strategy_params={
        'ma100_period': 100,
        'ma60_period': 60,
        'drawdown_limit': 0.08,
    }
)
```

## 高级功能

### 1. 自定义佣金和滑点

```python
# 设置佣金
cerebro.broker.setcommission(commission=0.0003)

# 设置滑点
cerebro.broker.set_slippage_perc(0.001)  # 0.1%滑点
```

### 2. 添加多个分析器

```python
cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
```

### 3. 可视化

```python
import matplotlib
matplotlib.use('TkAgg')  # Windows需要

# 运行回测时添加绘图
cerebro.plot(style='candlestick')
```

### 4. Walk-Forward分析

```python
# 分段回测
periods = [
    ('20220101', '20220630'),
    ('20220701', '20221231'),
    ('20230101', '20230630'),
]

for start, end in periods:
    result = engine.run_single_stock(...)
    print(f"{start}~{end}: {result.total_return*100:.2f}%")
```

## 最佳实践

### 1. 避免未来函数

✅ 正确:
```python
def next(self):
    # 使用当前bar的收盘价
    if self.data.close[0] > self.ma[0]:
        self.buy()
```

❌ 错误:
```python
def next(self):
    # 使用了未来数据!
    if self.data.close[1] > self.ma[1]:
        self.buy()
```

### 2. 合理的仓位管理

```python
# 固定比例仓位
size = int(self.broker.getcash() / self.data.close[0] * 0.2)

# 固定金额
size = int(10000 / self.data.close[0])
```

### 3. 设置止损

```python
# 买入时同时设置止损单
self.buy()
stop_price = self.data.low[0] * 0.99
self.sell(exectype=bt.Order.Stop, price=stop_price)
```

### 4. 充分的样本外测试

```python
# 训练集: 2022年
opt_results = engine.optimize_strategy(
    start_date='20220101',
    end_date='20221231',
    ...
)

# 测试集: 2023年
result = engine.run_single_stock(
    start_date='20230101',
    end_date='20231231',
    ...
)
```

## 常见问题

### Q1: 如何提高回测速度?

A: 
- 减少打印日志 (`printlog=False`)
- 使用`optreturn=True`进行参数优化
- 批量回测时使用多线程

### Q2: 如何处理停牌股票?

A: Backtrader会自动跳过缺失数据的日期,确保数据连续性即可。

### Q3: 如何保存回测结果?

```python
import json

result_dict = result.to_dict()
with open('backtest_result.json', 'w') as f:
    json.dump(result_dict, f, indent=2)
```

### Q4: 如何对比多个策略?

```python
strategies = [
    DualMATrendStrategyBT,
    AnotherStrategy,
    YetAnotherStrategy,
]

for strat_class in strategies:
    result = engine.run_single_stock(..., strategy_class=strat_class)
    print(f"{strat_class.__name__}: {result.total_return*100:.2f}%")
```

## 与原有系统的对比

| 特性 | 原系统 | Backtrader |
|------|--------|------------|
| 信号扫描 | ✅ | ✅ |
| 历史回测 | ❌ | ✅ |
| 参数优化 | ❌ | ✅ |
| 性能分析 | 基础 | 全面 |
| 可视化 | ❌ | ✅ |
| 实盘交易 | 待开发 | 支持 |

## 下一步计划

- [ ] 将其他5个策略迁移到Backtrader
- [ ] 添加回测结果可视化
- [ ] 集成到API服务
- [ ] 支持多因子策略
- [ ] 添加风险管理模块

## 参考资料

- [Backtrader官方文档](https://www.backtrader.com/docu/)
- [Backtrader GitHub](https://github.com/mementum/backtrader)
- [量化交易策略开发最佳实践](https://www.backtrader.com/blog/posts/2019-08-29-fractional-sizes/fractional-sizes/)

---

**注意**: 回测结果不代表未来表现,请谨慎使用策略进行实盘交易。


# A股策略回测系统 - 软件说明文档

## 📖 项目概述

A股策略回测系统是一个基于Python的专业量化交易策略开发与回测平台。系统整合了Backtrader回测框架、DuckDB数据存储和FastAPI服务，提供从策略开发、历史回测到信号扫描的完整解决方案。

### 核心价值

- 🎯 **专业回测**: 基于Backtrader框架，提供机构级回测能力
- ⚡ **高性能**: DuckDB列式存储，快速数据查询
- 🔌 **插件化**: 策略模块化设计，易于扩展
- 🌐 **API服务**: RESTful API，支持第三方集成
- 📊 **可视化**: Web前端界面，直观展示回测结果

---

## 🏗️ 系统架构

本系统采用**四层架构设计**,各层职责清晰,松耦合,易于扩展和维护。

```
┌─────────────────────────────────────────────────┐
│              第四层: 展示层 (Presentation)        │
│  ┌──────────────┐  ┌──────────┐  ┌───────────┐  │
│  │  Web前端界面  │  │ API文档  │  │ 数据导出  │  │
│  │  (HTML/JS)   │  │ Swagger  │  │ Excel/PDF │  │
│  └──────────────┘  └──────────┘  └───────────┘  │
└──────────────────────┬──────────────────────────┘
                       │ RESTful API / WebSocket
┌──────────────────────▼──────────────────────────┐
│              第三层: 回测层 (Backtesting)         │
│  ┌──────────────┐  ┌──────────┐  ┌───────────┐  │
│  │Backtrader引擎│  │ 参数优化  │  │ 性能分析  │  │
│  │  策略执行    │  │ 网格搜索  │  │ 指标计算  │  │
│  └──────────────┘  └──────────┘  └───────────┘  │
└──────────────────────┬──────────────────────────┘
                       │ 策略信号 / 回测请求
┌──────────────────────▼──────────────────────────┐
│              第二层: 选股层 (Selection)           │
│  ┌──────────────┐  ┌──────────┐  ┌───────────┐  │
│  │ 策略扫描引擎  │  │ 信号过滤  │  │ 任务调度  │  │
│  │ 多策略并行   │  │ 条件组合  │  │ 异步执行  │  │
│  └──────────────┘  └──────────┘  └───────────┘  │
└──────────────────────┬──────────────────────────┘
                       │ 股票池 / 行情数据
┌──────────────────────▼──────────────────────────┐
│              第一层: 数据层 (Data)                │
│  ┌──────────────┐  ┌──────────┐  ┌───────────┐  │
│  │ DuckDB仓储   │  │ 数据源   │  │ 数据清洗  │  │
│  │ 时序数据存储  │  │ AKShare  │  │ 标准化    │  │
│  └──────────────┘  └──────────┘  └───────────┘  │
└─────────────────────────────────────────────────┘
```

### 分层说明

#### 第一层: 数据层 (Data Layer)

**职责**: 负责数据的获取、存储、清洗和管理

**核心组件**:
- `DuckDBStockRepository`: DuckDB数据仓储,提供高效的数据读写
- `DataSource`适配器: 统一不同数据源接口 (腾讯证券、东方财富)
- `TradeDataService`: 交易数据服务,协调数据获取和缓存

**主要功能**:
- ✅ 股票基本信息管理 (代码、名称、市场)
- ✅ 日线行情数据存储 (开高低收量额)
- ✅ 策略扫描结果持久化
- ✅ 回测任务记录管理
- ✅ 数据自动补抓和更新

**技术特点**:
- 使用DuckDB列式数据库,查询速度快,文件体积小
- 支持断点续传,网络中断后可继续
- 本地优先策略,减少网络依赖

---

#### 第二层: 选股层 (Selection Layer)

**职责**: 基于策略规则对全市场股票进行扫描,筛选出符合条件的候选股票

**核心组件**:
- `StrategyExecutor`: 策略执行器,支持多策略并行扫描
- `StrategyLoader`: 策略加载器,从配置文件动态加载策略
- `BaseStrategy`: 策略基类,定义统一的策略接口

**主要功能**:
- ✅ 全A股策略信号扫描 (~5000只股票)
- ✅ 多策略并行执行 (可配置并发数)
- ✅ 策略插件化,易于扩展新策略
- ✅ 异步任务队列,支持后台执行
- ✅ 扫描结果持久化和查询

**工作流程**:
```
1. 获取股票列表 → 2. 并行加载历史数据 → 3. 执行策略检查 
→ 4. 收集命中信号 → 5. 保存结果到数据库
```

**性能指标**:
- 全市场扫描时间: < 5分钟
- 并发工作线程: 默认50,可配置
- 内存占用: ~500MB

---

#### 第三层: 回测层 (Backtesting Layer)

**职责**: 提供专业的策略历史回测、参数优化和性能分析能力

**核心组件**:
- `BacktestEngine`: Backtrader回测引擎封装
- `DuckDBDataFeed`: DuckDB数据适配器,将数据转换为Backtrader格式
- `StrategiesBT`: Backtrader版本的策略实现

**主要功能**:
- ✅ 单股票历史回测
- ✅ 批量股票回测
- ✅ 策略参数网格搜索优化
- ✅ Walk-Forward推进分析
- ✅ 全面的性能指标计算
  - 总收益率、年化收益
  - 夏普比率、索提诺比率
  - 最大回撤、卡尔玛比率
  - 胜率、盈亏比
- ✅ 资金曲线生成
- ✅ 交易明细记录

**技术特点**:
- 基于Backtrader专业框架,机构级回测能力
- 支持佣金、滑点模拟
- 自动处理停牌、除权除息
- 防止未来函数,确保回测真实性

**回测流程**:
```
1. 加载历史数据 → 2. 初始化Cerebro引擎 → 3. 添加策略和指标 
→ 4. 设置初始资金和佣金 → 5. 运行回测 → 6. 分析结果
```

---

#### 第四层: 展示层 (Presentation Layer)

**职责**: 提供用户交互界面和数据可视化,展示回测结果和分析报告

**核心组件**:
- `Frontend`: 静态Web页面 (HTML/CSS/JavaScript)
- `FastAPI Routes`: RESTful API接口
- `Chart.js`: 数据可视化图表库

**主要功能**:
- ✅ Web前端界面
  - 策略回测配置页面
  - 回测结果展示页面
  - 参数优化页面
  - 历史记录管理
- ✅ RESTful API服务
  - 健康检查接口
  - 策略管理接口
  - 扫描任务接口
  - 回测执行接口
  - 数据查询接口
- ✅ 数据可视化
  - 资金曲线图 (Chart.js)
  - 性能指标卡片
  - 数据表格展示
- ✅ Swagger API文档
  - 交互式API测试
  - 自动生成接口文档

**技术栈**:
- 前端: HTML5 + CSS3 + JavaScript ES6+
- 后端: FastAPI + Uvicorn
- 图表: Chart.js 4.x
- 文档: Swagger/OpenAPI

---

## 🛠️ 技术栈

### 后端技术

| 组件 | 技术选型 | 版本 | 用途 |
|------|---------|------|------|
| Web框架 | FastAPI | ≥0.115.0 | RESTful API服务 |
| 回测引擎 | Backtrader | ≥1.9.78 | 策略回测与优化 |
| 数据库 | DuckDB | ≥1.2.0 | 时序数据存储 |
| 数据处理 | Pandas | ≥1.3.0 | 数据清洗与分析 |
| 数据源 | AKShare | ≥1.10.0 | A股行情数据 |
| 配置管理 | PyYAML | ≥6.0.2 | YAML配置文件 |
| ASGI服务器 | Uvicorn | ≥0.30.0 | 异步服务器 |

### 前端技术

| 组件 | 技术选型 | 版本 | 用途 |
|------|---------|------|------|
| 基础 | HTML5/CSS3 | - | 页面结构与样式 |
| 脚本 | JavaScript ES6+ | - | 交互逻辑 |
| 图表 | Chart.js | 4.4.0 | 数据可视化 |
| 通信 | Fetch API | - | HTTP请求 |
| 存储 | LocalStorage | - | 本地数据持久化 |

### 开发工具

- Python 3.10+
- pytest (单元测试)
- Git (版本控制)

---

## 📂 项目结构 (按四层架构组织)

```
stock_strategy/
│
├── 📊 第一层: 数据层 (Data Layer)
│   ├── services/
│   │   ├── data_sources/          # 数据源适配
│   │   │   ├── datasource.py      # 数据源基类
│   │   │   ├── tencent.py         # 腾讯证券API
│   │   │   └── dfcf.py            # 东方财富API
│   │   ├── duckdb_repository.py   # DuckDB数据仓储
│   │   └── trade_data_service.py  # 交易数据服务
│   ├── common/
│   │   └── market_util.py         # 市场代码工具
│   └── stock_data.duckdb          # DuckDB数据库文件
│
├── 🔍 第二层: 选股层 (Selection Layer)
│   ├── strategies/                # 策略模块
│   │   ├── base_strategy.py       # 策略基类
│   │   ├── dual_ma_trend.py       # ST-01: 双均线趋势
│   │   ├── low_123_breakout.py    # ST-02: 低位123突破
│   │   ├── macd_divergence_breakout.py  # ST-03: MACD背离
│   │   ├── gap_breakout.py        # ST-04: 缺口突破
│   │   ├── gap_pullback.py        # ST-05: 缺口回踩
│   │   ├── strong_limit_up.py     # ST-06: 涨停突破
│   │   ├── high_volume.py         # 高成交量突破
│   │   ├── continuation_gap_strategy.py  # 持续缺口
│   │   └── two_day_up.py          # 连续两天上涨
│   ├── services/
│   │   ├── strategy_executor.py   # 策略执行器
│   │   ├── strategy_loader.py     # 策略加载器
│   │   └── stock_service.py       # 股票服务
│   └── config/
│       ├── app_config.yaml        # 策略配置
│       └── load_app_config.py     # 配置加载器
│
├── 📈 第三层: 回测层 (Backtesting Layer)
│   ├── backtrader_integration/    # Backtrader集成
│   │   ├── data_feed.py           # DuckDB数据适配器
│   │   ├── strategies_bt.py       # Backtrader策略实现
│   │   └── backtest_engine.py     # 回测引擎封装
│   └── examples/
│       └── backtrader_example.py  # 回测示例代码
│
├── 🖥️ 第四层: 展示层 (Presentation Layer)
│   ├── api/                       # API服务
│   │   ├── app.py                 # FastAPI应用工厂
│   │   ├── routes.py              # API路由定义
│   │   ├── schemas.py             # Pydantic数据模型
│   │   └── job_service.py         # 任务管理服务
│   ├── frontend/                  # Web前端
│   │   ├── index.html             # 主页面
│   │   ├── static/
│   │   │   ├── css/style.css      # 样式文件
│   │   │   └── js/app.js          # JavaScript逻辑
│   │   └── README.md              # 前端说明
│   └── docs/                      # 文档
│       ├── APIReference.md        # API接口文档
│       └── SoftwareManual.md      # 软件说明文档
│
├── 🧪 测试目录
│   └── tests/
│       ├── test_api.py            # API测试
│       ├── test_core_refactor.py  # 核心功能测试
│       └── test_short_term_strategies.py  # 策略测试
│
├── 📝 文档目录
│   └── docs/
│       ├── PRD.md                 # 产品需求文档
│       ├── Strategies.md          # 策略规格说明
│       ├── ShortTermStrategies.md # 短线策略说明
│       └── BacktraderGuide.md     # Backtrader使用指南
│
├── main.py                        # 应用入口 (启动API服务)
├── start_frontend.py              # 前端启动脚本
└── requirements.txt               # Python依赖
```

---

## 🚀 快速开始

### 1. 环境要求

- Python 3.10 或更高版本
- Windows/Linux/macOS
- 4GB+ RAM
- 网络连接 (获取股票数据)

### 2. 安装步骤

```bash
# 克隆项目
git clone <repository-url>
cd stock_strategy

# 创建虚拟环境 (推荐)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate     # Windows

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置系统

编辑 `backend/config/app_config.yaml`:

```yaml
# 数据源配置
data_source:
  provider: tencent  # tencent 或 dfcf
  timeout: 10.0

# 存储配置
storage:
  duckdb_path: stock_data.duckdb

# 策略配置
strategies:
  DualMATrendStrategy:
    enabled: true
  GapBreakoutStrategy:
    enabled: true
  # ... 其他策略

# 默认参数
defaults:
  check_days: 60
  max_workers: 50
```

### 4. 启动服务

#### 方式1: 启动API服务

```bash
python main.py --host 127.0.0.1 --port 8000
```

访问API文档: http://127.0.0.1:8000/docs

#### 方式2: 启动前端页面

```bash
python start_frontend.py
```

访问前端: http://localhost:8080

#### 方式3: 同时启动 (两个终端)

```bash
# 终端1: API服务
python main.py

# 终端2: 前端页面
python start_frontend.py
```

### 5. 运行示例

```bash
# 运行Backtrader回测示例
python examples/backtrader_example.py

# 运行单元测试
python -m unittest discover -s tests -v
```

---

## 💡 核心功能 (按四层架构)

### 📊 第一层: 数据层功能

#### 1.1 数据获取与管理

**功能描述**: 从多个数据源获取A股行情数据,并存储到DuckDB数据库。

**支持的数据源**:
- AKShare (免费A股数据)
- 腾讯证券API
- 东方财富API

**数据类型**:
- 股票基本信息 (代码、名称、市场)
- 日线行情 (开高低收量额)
- 复权因子 (前复权、后复权)

**示例代码**:

```python
from backend.infrastructure.persistence.duckdb_repository import DuckDBStockRepository
from backend.application.screening import TradeDataService
from backend.infrastructure.data_sources import create_data_source

# 初始化
repository = DuckDBStockRepository("stock_data.duckdb")
data_source = create_data_source("tencent", timeout=10.0)
trade_service = TradeDataService(repository, data_source)

# 获取股票列表
stocks = trade_service.list_stocks()
print(f"共 {len(stocks)} 只股票")

# 获取历史行情
history = trade_service.get_history_for_scan(
    code='000001',
    name='平安银行',
    start_date='20230101',
    end_date='20231231',
    target_dates=['20231231']
)
print(f"获取到 {len(history)} 条行情数据")
```

**数据流程**:
```
网络API → DataSource适配器 → 数据清洗 → DuckDB存储
```

---

### 🔍 第二层: 选股层功能

#### 2.1 策略信号扫描

**功能描述**: 对全A股进行策略信号扫描，找出符合条件的股票。

**使用场景**:
- 每日盘后扫描次日候选股票
- 盘中实时监控信号
- 历史数据回测验证

**示例代码**:

```python
from backend.application.strategy_loader import load_strategies_from_config
from backend.application.screening import StrategyExecutor, TradeDataService
from backend.infrastructure.data_sources import create_data_source
from backend.infrastructure.persistence.duckdb_repository import DuckDBStockRepository

# 构建执行器
repository = DuckDBStockRepository("stock_data.duckdb")
data_source = create_data_source("tencent", timeout=10.0)
trade_service = TradeDataService(repository, data_source)
executor = StrategyExecutor(
    trade_data_service=trade_service,
    repository=repository,
    strategies=load_strategies_from_config(),
    max_workers=50,
)

# 运行扫描
results = executor.run(
    start_date='20240101',
    end_date='20241231',
    target_dates=['20241231']
)

print(f"找到 {len(results)} 条信号")
for result in results[:5]:
    print(f"{result['code']} {result['name']} - {result['strategy']}")
```

**性能指标**:
- 全A股 (~5000只) 扫描时间: < 5分钟
- 并发工作线程: 可配置 (默认50)
- 内存占用: ~500MB

#### 2.2 策略插件化

**添加新策略步骤**:

1. 创建策略文件 `strategies/my_strategy.py`:

```python
from .base_strategy import BaseStrategy
import pandas as pd

class MyStrategy(BaseStrategy):
    def __init__(self):
        super().__init__('我的策略')
    
    def check(self, hist_data: pd.DataFrame) -> bool:
        # 实现策略逻辑
        if len(hist_data) < 60:
            return False
        
        # ... 你的判断逻辑
        
        return True
```

2. 在配置中启用 `backend/config/app_config.yaml`:

```yaml
strategies:
  MyStrategy:
    enabled: true
```

3. 重启服务即可生效。

---

### 📈 第三层: 回测层功能

#### 3.1 Backtrader回测引擎

**功能描述**: 专业的策略历史回测，支持参数优化和性能分析。

**支持的回测类型**:
- ✅ 单股票回测
- ✅ 批量回测
- ✅ 参数网格搜索
- ✅ Walk-Forward分析

**示例代码**:

```python
from backend.backtrader_integration import BacktestEngine, DualMATrendStrategyBT
from backend.infrastructure.persistence.duckdb_repository import DuckDBStockRepository

# 初始化
repository = DuckDBStockRepository("stock_data.duckdb")
engine = BacktestEngine(repository)

# 运行回测
result = engine.run_single_stock(
    stock_code='000001',
    strategy_class=DualMATrendStrategyBT,
    start_date='20230101',
    end_date='20231231',
    initial_cash=100000
)

# 查看结果
print(f"收益率: {result.total_return*100:.2f}%")
print(f"夏普比率: {result.sharpe_ratio:.2f}")
print(f"最大回撤: {result.max_drawdown:.2f}%")
print(f"交易次数: {result.total_trades}")
print(f"胜率: {result.win_rate*100:.2f}%")
```

#### 3.2 参数优化

**功能描述**: 自动搜索策略最优参数组合。

**示例代码**:

```python
# 定义参数范围
param_ranges = {
    'ma100_period': [80, 100, 120],
    'ma60_period': [40, 60, 80],
    'drawdown_limit': [0.05, 0.08, 0.10],
}

# 运行优化
opt_results = engine.optimize_strategy(
    stock_code='000001',
    strategy_class=DualMATrendStrategyBT,
    start_date='20230101',
    end_date='20231231',
    param_ranges=param_ranges
)

# 查看最优参数
print("Top 5 参数组合:")
print(opt_results.head(5))
```

**性能指标**:
- 单股票1年日线回测: < 1秒
- 参数优化 (27组参数): < 30秒
- 批量回测 (100只股票): < 2分钟

---

### 🖥️ 第四层: 展示层功能

#### 4.1 Web前端界面

**功能描述**: 提供直观的用户界面,用于配置回测参数、查看结果和数据可视化。

**主要页面**:
- **策略回测页**: 配置参数、运行回测、查看实时结果
- **回测结果页**: 历史记录列表、快速查看
- **参数优化页**: 网格搜索最优参数

**启动方式**:

```bash
python start_frontend.py
```

访问: http://localhost:8080

**界面特性**:
- 🎨 现代化UI设计 (渐变色、卡片布局)
- 📱 响应式布局 (支持桌面/平板/手机)
- 📊 Chart.js资金曲线图
- 💾 LocalStorage本地存储
- ⚡ 流畅的交互动画

#### 4.2 RESTful API服务

**功能描述**: 提供标准化的API接口,支持第三方系统集成。

**启动方式**:

```bash
python main.py --host 127.0.0.1 --port 8000
```

访问API文档: http://127.0.0.1:8000/docs

**主要接口**:
- `GET /api/v1/health` - 健康检查
- `GET /api/v1/strategies` - 获取策略列表
- `POST /api/v1/scans` - 创建扫描任务
- `POST /api/v1/backtests` - 创建回测任务
- `GET /api/v1/backtests/{job_id}/results` - 查询回测结果
- `GET /api/v1/stocks` - 获取股票列表

**调用示例**:

```python
import requests

# 运行回测
response = requests.post(
    'http://127.0.0.1:8000/api/v1/backtests',
    json={
        'stock_code': '000001',
        'strategy': 'DualMATrendStrategyBT',
        'start_date': '20230101',
        'end_date': '20231231',
        'initial_cash': 100000
    }
)

result = response.json()
print(f"收益率: {result['total_return']*100:.2f}%")
```

---

## 📊 已实现策略

### 《短线操盘实战技巧》6大策略

| 编号 | 策略名称 | 类名 | 适用场景 | 风险等级 |
|------|---------|------|---------|---------|
| ST-01 | 双均线趋势策略 | DualMATrendStrategy | 趋势跟踪 | 低 |
| ST-02 | 低位123结构突破 | Low123BreakoutStrategy | 底部反转 | 中 |
| ST-03 | MACD底背离双突破 | MACDDivergenceBreakoutStrategy | 超跌反弹 | 中高 |
| ST-04 | 向上突破缺口追涨 | GapBreakoutStrategy | 强势突破 | 高 |
| ST-05 | 缺口回踩支撑买入 | GapPullbackStrategy | 二次买点 | 中 |
| ST-06 | 强势涨停突破 | StrongLimitUpBreakoutStrategy | 短线追涨 | 很高 |

### 其他策略

- HighVolumeStrategy: 高成交量突破
- ContinuationGapStrategy: 持续缺口
- TwoDayUpStrategy: 连续两天上涨
- BreakM100: 突破100日均线

**详细策略说明**: 参见 `docs/ShortTermStrategies.md`

---

## 🔧 自定义开发

### 添加新策略

1. **创建策略文件** `strategies/my_strategy.py`:

```python
from .base_strategy import BaseStrategy
import pandas as pd

class MyStrategy(BaseStrategy):
    def __init__(self):
        super().__init__('我的策略')
    
    def check(self, hist_data: pd.DataFrame) -> bool:
        # 实现策略逻辑
        if len(hist_data) < 60:
            return False
        
        # ... 你的判断逻辑
        
        return True
```

2. **在配置中启用** `backend/config/app_config.yaml`:

```yaml
strategies:
  MyStrategy:
    enabled: true
```

3. **重启服务**即可生效。

### 添加Backtrader策略

1. **创建策略文件** `backtrader_integration/strategies_bt.py`:

```python
import backtrader as bt

class MyStrategyBT(bt.Strategy):
    params = (('param1', 10),)
    
    def __init__(self):
        self.ma = bt.indicators.SMA(period=self.params.param1)
    
    def next(self):
        if not self.position:
            if self.data.close > self.ma:
                self.buy()
        else:
            if self.data.close < self.ma:
                self.sell()
```

2. **在回测中使用**:

```python
from backend.backtrader_integration.strategies_bt import MyStrategyBT

result = engine.run_single_stock(
    stock_code='000001',
    strategy_class=MyStrategyBT,
    start_date='20230101',
    end_date='20231231'
)
```

---

## 🧪 测试

### 运行测试

```bash
# 运行所有测试
python -m unittest discover -s tests -v

# 运行特定测试
python -m unittest tests.test_api.ApiTest.test_health_and_strategies
```

### 测试覆盖

- ✅ API接口测试
- ✅ 数据仓储测试
- ✅ 策略加载测试
- ✅ 回测引擎测试
- ✅ 数据源适配测试

---

## 📈 性能指标

### 扫描性能

- 全A股 (~5000只) 扫描时间: < 5分钟
- 并发工作线程: 可配置 (默认50)
- 内存占用: ~500MB

### 回测性能

- 单股票1年日线回测: < 1秒
- 参数优化 (27组参数): < 30秒
- 批量回测 (100只股票): < 2分钟

### 数据存储

- DuckDB文件大小: ~300KB (压缩后)
- 查询速度: 毫秒级
- 支持数据量: 千万级记录

---

## 🔐 安全注意事项

1. **数据隐私**: 所有数据存储在本地，不上传云端
2. **API限流**: 数据源API有调用频率限制
3. **投资建议**: 本系统仅供研究学习，不构成投资建议
4. **风险提示**: 实盘交易前务必充分回测和模拟

---

## ❓ 常见问题

### Q1: 如何获取更多历史数据?

A: 系统会自动从网络API补抓缺失的数据。首次运行时建议设置较大的日期范围。

### Q2: 回测结果为什么和预期不符?

A: 检查以下几点:
- 数据是否完整 (有无停牌日)
- 佣金和滑点设置是否合理
- 是否存在未来函数
- 样本外测试验证

### Q3: 如何提高扫描速度?

A: 
- 增加 `max_workers` 配置
- 使用SSD硬盘存储DuckDB
- 减少不必要的策略
- 缓存常用数据

### Q4: 支持哪些操作系统?

A: Windows、Linux、macOS均可，推荐使用Linux获得最佳性能。

### Q5: 如何备份数据?

A: 直接复制 `stock_data.duckdb` 文件即可。

---

## 📞 技术支持

- 📧 Issue提交: GitHub Issues
- 📖 文档: `docs/` 目录
- 💬 社区讨论: GitHub Discussions

---

## 📄 许可证

MIT License

---

## 🙏 致谢

感谢以下开源项目:
- [Backtrader](https://www.backtrader.com/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [DuckDB](https://duckdb.org/)
- [AKShare](https://akshare.akfamily.xyz/)
- [Chart.js](https://www.chartjs.org/)

---

**最后更新**: 2026-04-12  
**版本**: v1.0.0


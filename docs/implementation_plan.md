# DDD 架构重构计划

## 设计思路

用 DDD（领域驱动设计）的分层思想重新组织代码：

```
stock_strategy/
├── backend/domain/                        # 领域层 — 纯业务逻辑，零外部依赖
│   ├── __init__.py
│   ├── models.py                  # 领域模型：Stock, DailyBar, StrategyResult, ScanJob
│   ├── strategy.py                # BaseStrategy ABC（从 strategies/ 迁入）
│   └── ports.py                   # 仓储端口、数据源端口（ABC 接口定义）
│
├── backend/application/                   # 应用层 — 用例编排，依赖领域层接口
│   ├── __init__.py
│   ├── scan_service.py            # ScanJobService：扫描任务生命周期管理
│   ├── screening.py               # StrategyExecutor + scan_stock_data：选股编排
│   └── strategy_loader.py         # 策略发现与加载
│
├── backend/infrastructure/                # 基础设施层 — 技术实现，实现领域端口
│   ├── __init__.py
│   ├── persistence/
│   │   ├── __init__.py
│   │   └── duckdb_repository.py   # 实现 StockRepository + ScanJobRepository
│   ├── data_sources/
│   │   ├── __init__.py            # create_data_source 工厂
│   │   ├── base.py                # normalize_stock_data + DataSource 实现基类
│   │   ├── tencent.py
│   │   └── dfcf.py
│   └── config.py                  # load_app_config + get_trade_days
│
├── backend/api/                           # 接口层 — HTTP API（基本不变）
│   ├── __init__.py
│   ├── app.py                     # create_app — 组装所有依赖
│   ├── routes.py
│   └── schemas.py
│
├── backend/strategies/                    # 策略插件目录 — 具体策略实现
│   ├── __init__.py                # 简化为空或仅 re-export BaseStrategy
│   ├── high_volume.py
│   ├── gap_breakout.py
│   └── ...（所有现有策略文件不变）
│
├── backend/backtrader_integration/        # 回测层（本次不动）
├── config/                        # 配置文件（YAML 保留原位）
├── tests/
└── main.py
```

## 领域层 `backend/domain/`

### [NEW] `backend/domain/models.py`

领域模型，使用 `dataclass` 定义。替代现有代码中散落的 [dict](file:///c:/workspace/code/python/stock_strategy/stock_strategy/backtrader_integration/backtest_engine.py#45-61) 传递：

| 模型 | 类型 | 说明 |
|---|---|---|
| [Stock](file:///c:/workspace/code/python/stock_strategy/stock_strategy/services/duckdb_repository.py#13-359) | Entity | 股票基本信息 (code, name) |
| `DailyBar` | Value Object | 日线数据 (OHLCV) |
| `StrategyHit` | Value Object | 策略命中结果 — 替代裸 dict |
| [ScanJob](file:///c:/workspace/code/python/stock_strategy/stock_strategy/api/job_service.py#13-91) | Aggregate Root | 扫描任务 — 包含状态机逻辑 (queued→running→completed/failed) |

### [NEW] `backend/domain/strategy.py`

[BaseStrategy](file:///c:/workspace/code/python/stock_strategy/stock_strategy/strategies/base_strategy.py#8-31) ABC 迁入。移除死代码 [get_result()](file:///c:/workspace/code/python/stock_strategy/stock_strategy/strategies/base_strategy.py#19-31)。

### [NEW] `backend/domain/ports.py`

仓储端口（接口），领域层依赖的抽象：

```python
class StockRepository(ABC):
    """股票数据仓储端口"""
    def list_stocks() -> list[Stock]
    def get_stock_history(code, start, end) -> list[DailyBar]
    def upsert_stocks(stocks)
    def upsert_daily_data(bars)
    def upsert_strategy_results(results)

class ScanJobRepository(ABC):
    """扫描任务仓储端口"""
    def create_scan_job(job) -> ScanJob
    def update_scan_job(job)
    def get_scan_job(job_id) -> ScanJob | None
    def get_scan_job_results(job_id) -> list[StrategyHit]

class MarketDataSource(ABC):
    """行情数据源端口"""
    def fetch_daily_bars(code, market, start, end) -> list[DailyBar]
```

---

## 应用层 `backend/application/`

### [NEW] `backend/application/scan_service.py`

从 [api/job_service.py](file:///c:/workspace/code/python/stock_strategy/stock_strategy/api/job_service.py) 迁入 [ScanJobService](file:///c:/workspace/code/python/stock_strategy/stock_strategy/api/job_service.py#13-91) + [resolve_scan_dates](file:///c:/workspace/code/python/stock_strategy/stock_strategy/api/job_service.py#93-118)。业务编排不属于 API 层。使用领域端口接口。

### [NEW] `backend/application/screening.py`

从 [services/strategy_executor.py](file:///c:/workspace/code/python/stock_strategy/stock_strategy/services/strategy_executor.py) 迁入 [StrategyExecutor](file:///c:/workspace/code/python/stock_strategy/stock_strategy/services/strategy_executor.py#13-80) + [scan_stock_data](file:///c:/workspace/code/python/stock_strategy/stock_strategy/services/strategy_executor.py#82-121)。输出 `StrategyHit` 而非裸 dict。

### [NEW] `backend/application/strategy_loader.py`

从 [services/strategy_loader.py](file:///c:/workspace/code/python/stock_strategy/stock_strategy/services/strategy_loader.py) 迁入。

---

## 基础设施层 `backend/infrastructure/`

### [NEW] `backend/infrastructure/persistence/duckdb_repository.py`

从 [services/duckdb_repository.py](file:///c:/workspace/code/python/stock_strategy/stock_strategy/services/duckdb_repository.py) 迁入。实现 [StockRepository](file:///c:/workspace/code/python/stock_strategy/stock_strategy/services/duckdb_repository.py#13-359) + `ScanJobRepository` 端口。内部的 [_to_optional_float](file:///c:/workspace/code/python/stock_strategy/stock_strategy/services/duckdb_repository.py#361-365) 等辅助函数留在此处（仅 DuckDB 实现需要）。

### [NEW] `backend/infrastructure/data_sources/`

从 `services/data_sources/` 迁入。`base.py` 实现 `MarketDataSource` 端口。

### [NEW] `backend/infrastructure/config.py`

合并 `config/load_app_config.py` + `services/stock_service.py` 中的 `get_trade_days()` + `build_strategy_executor()` 组装函数。

---

## 接口层 `backend/api/`

### [MODIFY] `backend/api/app.py`

更新 imports，使用 `infrastructure.config` 中的组装函数。

### [MODIFY] `backend/api/routes.py`

更新 imports。

---

## 清理

| 操作 | 路径 |
|---|---|
| DELETE | `services/` 整个目录 |
| DELETE | `common/market_util.py`（`get_market_code` 迁入 `backend/infrastructure/data_sources/base.py`）|
| MODIFY | `backend/strategies/__init__.py` — 简化，从 `domain.strategy` 重导出 `BaseStrategy` |
| MODIFY | `backend/strategies/*.py` — import 路径 `from .base_strategy import` → `from domain.strategy import`（或保留 `__init__` 重导出） |

> [!IMPORTANT]
> 为最小化策略文件改动，`backend/strategies/__init__.py` 将 re-export `BaseStrategy from domain.strategy`，保持策略文件中 `from .base_strategy import BaseStrategy` 不变（`base_strategy.py` 改为薄代理）。

---

## Verification Plan

```bash
python -m compileall -q main.py api domain application infrastructure strategies tests
python -m unittest discover -s tests -v
```



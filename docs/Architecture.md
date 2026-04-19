# A 股本地研究平台 v2 架构

## Overview

v2 采用后端优先的本地研究平台架构：

```text
FastAPI
  |
  v
ResearchJobService (single worker queue)
  |
  +--> DataSyncService  --> DuckDB: stocks, stock_daily_data, sync_results
  |
  +--> StrategyExecutor --> DuckDB: strategy_results
  |
  +--> BacktestService  --> BacktestEngine --> DuckDB: backtest_results
  |
  v
DuckDBJobRepository --> DuckDB: jobs
```

设计目标是让“同步数据、运行选股、验证回测”成为三条清晰、可追踪、可测试的工作流，而不是把所有行为藏在一个扫描请求里。

## Layers

代码结构：

```text
backend/   Python 后端：API、应用层、领域层、基础设施、策略、回测
frontend/  静态前端：HTML/CSS/JS
docs/      产品与技术文档
tests/     后端自动化测试
```

### Domain

- `backend.domain.models` 定义 `Job`、`JobType`、`JobStatus`、`Stock`、`StrategyHit`、`SyncResult`、`BacktestResultRecord`。
- `backend.domain.ports` 定义仓储和外部数据源端口。
- `backend.domain.strategy.BaseStrategy` 保持选股策略插件接口。

### Application

- `ResearchJobService` 统一创建、运行和查询 `sync/scan/backtest` 任务。
- `DataSyncService` 负责股票列表和日线行情同步。
- `StrategyExecutor` 继续负责全市场选股扫描。
- `BacktestService` 负责把 API 请求转成 Backtrader 回测，并持久化汇总结果。

任务状态流：

```text
queued -> running -> completed
                  -> failed
```

### Infrastructure

- `DuckDBStockRepository` 管理股票、行情和选股结果。
- `DuckDBJobRepository` 管理统一任务、同步明细和回测结果。
- `DuckDBScanJobRepository` 保留旧扫描任务兼容路径。
- `backend.infrastructure.data_sources` 继续提供 Tencent、东方财富等行情数据源适配。

### API

- `POST /api/v1/syncs`
- `POST /api/v1/scans`
- `POST /api/v1/backtests`
- `GET /api/v1/jobs/{job_id}`
- `GET /api/v1/scans/{job_id}/results`
- `GET /api/v1/syncs/{job_id}/results`
- `GET /api/v1/backtests/{job_id}/results`

## Data Flow

### 数据同步

```text
POST /syncs
  -> ResearchJobService
  -> DataSyncService
  -> DataSource.fetch_daily_data()
  -> DuckDBStockRepository.upsert_daily_data()
  -> DuckDBJobRepository.save_sync_results()
```

### 选股扫描

```text
POST /scans
  -> ResearchJobService
  -> StrategyExecutor
  -> TradeDataService.ensure_daily_data()
  -> BaseStrategy.check()
  -> DuckDBStockRepository.upsert_strategy_results(job_id=...)
```

### 回测验证

```text
POST /backtests
  -> ResearchJobService
  -> BacktestService
  -> BacktestEngine.run_single_stock()
  -> DuckDBDataFeed
  -> DuckDBJobRepository.save_backtest_results()
```

## Design Rules

- DuckDB 写入继续使用单进程串行队列，先保证本地可靠性。
- 选股结果必须带 `job_id`，不同扫描任务不能互相覆盖。
- 回测必须显式传入 `commission` 和 `slippage`。
- v2 只暴露 `DualMATrendStrategyBT`，其他策略迁移到 Backtrader 前不能在 API 中承诺支持。
- 文档和代码示例必须使用当前 `backend.application`、`backend.infrastructure` 路径，不再引用旧 `services.*`。

## Not In Scope

- 实盘交易、券商接口、资金管理、风控拦截。
- 多用户权限和登录系统。
- 分布式任务队列。
- 前端真实回测改造。
- 参数优化、Walk-forward、样本外验证平台。


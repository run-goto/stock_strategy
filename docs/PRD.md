# PRD: A 股本地研究平台 v2

## Summary

本项目从“策略扫描 API MVP”升级为单机本地研究平台，面向个人量化研究者，提供三条后端优先能力：

- 股票数据同步：同步 A 股股票列表和日线行情到本地 DuckDB。
- 选股扫描：按日期范围和目标日期运行启用策略，输出策略命中股票。
- 回测验证：基于本地 DuckDB 行情和 Backtrader，对候选股票运行第一版可验证回测。

系统继续使用 FastAPI、DuckDB、策略插件和 Backtrader。v2 不做实盘下单、券商接口、多用户权限、分布式任务队列或前端真实回测改造。

## Product Goals

- 用户可以通过 HTTP API 发起数据同步、选股扫描和回测任务，并通过统一任务接口查询状态。
- 数据同步是显式任务，避免把所有数据缺口都隐藏在选股或回测执行过程中。
- 选股结果按 `job_id` 隔离，避免同一日期不同任务的命中结果互相覆盖。
- 回测第一版只支持已实现的 `DualMATrendStrategyBT`，并要求请求显式携带交易成本参数。
- 所有结果持久化到 DuckDB，便于后续脚本、Notebook 或前端读取。

## Users & Use Cases

核心用户：个人量化研究者。

核心场景：

- 每天收盘后先同步股票列表和目标日期行情，再运行策略扫描。
- 对扫描命中的候选股票运行统一回测，快速排除明显不可靠的候选。
- 在本地 DuckDB 中保留任务、同步、选股、回测结果，便于复盘。
- 通过 API 把结果接入后续脚本或 Notebook。

## Functional Requirements

### Unified Jobs

- `GET /api/v1/jobs/{job_id}` 返回统一任务状态。
- 任务类型包括 `sync`、`scan`、`backtest`。
- 任务状态包括 `queued`、`running`、`completed`、`failed`。
- 任务字段包括 `job_id/type/status/params/total_items/success_count/failed_count/error/created_at/started_at/finished_at`。
- v2 使用单进程串行任务队列，避免 DuckDB 并发写冲突。

### Data Sync

- `POST /api/v1/syncs` 创建数据同步任务。
- 请求字段：`scope`、`start`、`end`、`stock_codes`。
- `scope` 支持 `stocks`、`daily`、`all`。
- `daily` 和 `all` 必须提供 `start` 和 `end`，日期格式为 `YYYYMMDD`。
- 股票列表写入 `stocks`，日线行情写入 `stock_daily_data`。
- 同步明细写入 `sync_results`，保留每只股票成功、失败、写入行数和错误消息。

### Screening

- `GET /api/v1/strategies` 返回当前配置启用的选股策略类名和展示名。
- `POST /api/v1/scans` 创建选股扫描任务，支持 `start`、`end`、`targets`。
- `GET /api/v1/scans/{job_id}/results` 返回扫描命中结果，按 `job_id` 隔离。
- 选股逻辑继续使用 `BaseStrategy.check(hist_data) -> bool`。
- 本地数据缺失时仍可按需补抓，但应复用数据同步层的日线数据写入路径。

### Backtesting

- `POST /api/v1/backtests` 创建回测任务。
- 请求字段：`strategy`、`start`、`end`、`stock_codes` 或 `scan_job_id`、`initial_cash`、`commission`、`slippage`。
- v2 第一版只支持 `DualMATrendStrategyBT`。
- `GET /api/v1/backtests/{job_id}/results` 返回每只股票的回测汇总指标。
- 回测结果包括 `final_value/total_return/annualized_return/sharpe_ratio/max_drawdown/total_trades/win_rate`。
- 不提供参数优化、Walk-forward、样本外验证平台；这些留给研究级 v3。

## Data Layer

- DuckDB 默认路径仍为 `stock_data.duckdb`。
- 核心表包括 `stocks`、`stock_daily_data`、`strategy_results`、`jobs`、`sync_results`、`backtest_results`。
- `stock_daily_data` 标准字段为 `code/trade_date/open/close/high/low/volume/amount/source/updated_at`。
- `strategy_results` 使用 `(job_id, code, strategy, target_date)` 作为主键。

## Non-Goals

- 不做交易下单、资金管理、风控拦截或券商接口。
- 不做多用户、登录认证、权限系统。
- 不做多进程或分布式任务队列。
- 不做前端真实回测改造，前端仍是后续工作。
- 不把回测结果解释为投资建议，只输出研究结果。

## Acceptance Criteria

- `POST /api/v1/syncs` 合法请求返回 `202` 和 `job_id`；非法日期返回 `400`。
- `POST /api/v1/scans` 保持兼容，合法日期返回 `202` 和 `job_id`。
- `POST /api/v1/backtests` 使用 `DualMATrendStrategyBT` 返回 `202`；不支持策略返回 `400`。
- `GET /api/v1/jobs/{job_id}` 能查询三类任务状态。
- 选股结果按 `job_id` 隔离。
- Backtrader 数据适配器可以读取仓储返回的标准 `date` 列。
- `python -m unittest discover -s tests` 和 `python -m compileall -q main.py api domain application infrastructure backtrader_integration strategies tests` 通过。


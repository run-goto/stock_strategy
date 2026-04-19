# A 股本地研究平台 v2 API Reference

Base URL: `http://127.0.0.1:8000/api/v1`

## Health

### GET `/health`

返回服务状态和 DuckDB 路径。

## Jobs

### GET `/jobs/{job_id}`

查询统一任务状态。

响应字段：

- `job_id`
- `type`: `sync`、`scan`、`backtest`
- `status`: `queued`、`running`、`completed`、`failed`
- `params`
- `total_items`
- `success_count`
- `failed_count`
- `error`
- `created_at`
- `started_at`
- `finished_at`

## Data Sync

### POST `/syncs`

创建数据同步任务。

```json
{
  "scope": "daily",
  "start": "20260101",
  "end": "20260102",
  "stock_codes": ["000001"]
}
```

`scope` 支持：

- `stocks`: 同步股票列表
- `daily`: 同步日线行情，必须提供 `start` 和 `end`
- `all`: 同步股票列表和日线行情，必须提供 `start` 和 `end`

### GET `/syncs/{job_id}/results`

返回同步明细，每条包含 `scope/code/status/rows_written/message`。

## Strategies

### GET `/strategies`

返回当前配置启用的选股策略。

## Screening

### POST `/scans`

创建选股扫描任务。

```json
{
  "start": "20260101",
  "end": "20260102",
  "targets": ["20260102"]
}
```

### GET `/scans/{job_id}`

查询扫描任务状态。该接口为兼容旧调用保留；新调用也可以用 `GET /jobs/{job_id}`。

### GET `/scans/{job_id}/results`

返回该扫描任务的策略命中结果。结果按 `job_id` 隔离。

## Backtests

### POST `/backtests`

创建回测任务。v2 第一版只支持 `DualMATrendStrategyBT`。

```json
{
  "strategy": "DualMATrendStrategyBT",
  "start": "20260101",
  "end": "20261231",
  "stock_codes": ["000001"],
  "initial_cash": 100000,
  "commission": 0.0003,
  "slippage": 0.001
}
```

也可以通过扫描任务结果指定股票池：

```json
{
  "strategy": "DualMATrendStrategyBT",
  "start": "20260101",
  "end": "20261231",
  "scan_job_id": "abc123",
  "initial_cash": 100000,
  "commission": 0.0003,
  "slippage": 0.001
}
```

不支持的策略返回 `400`。

### GET `/backtests/{job_id}/results`

返回每只股票的回测汇总：

- `stock_code`
- `strategy_name`
- `start_date`
- `end_date`
- `final_value`
- `total_return`
- `annualized_return`
- `sharpe_ratio`
- `max_drawdown`
- `total_trades`
- `win_rate`

## Notes

- v2 不提供 `/backtest/optimize`。
- v2 不提供回测 WebSocket。
- 当前前端仍可能包含模拟回测代码；后端 API 是本版本的事实来源。
- 回测结果仅用于研究，不构成投资建议。


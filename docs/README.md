# A 股本地研究平台 v2 文档中心

本项目是面向个人量化研究者的本地研究平台，后端优先支持三大能力：

- 股票数据同步
- 选股扫描
- 回测验证

技术栈：FastAPI、DuckDB、策略插件、Backtrader。

## 快速导航

| 文档 | 用途 |
|------|------|
| [PRD.md](PRD.md) | 产品边界、功能需求、验收标准 |
| [Architecture.md](Architecture.md) | v2 整体架构、数据流、模块职责 |
| [APIReference.md](APIReference.md) | 后端 API 调用说明 |
| [ShortTermStrategies.md](ShortTermStrategies.md) | 选股策略说明 |
| [BacktraderGuide.md](BacktraderGuide.md) | Backtrader 策略和回测模块背景 |

## 当前能力

### 已实现

- `POST /api/v1/syncs`: 创建股票列表或日线行情同步任务。
- `POST /api/v1/scans`: 创建选股扫描任务。
- `POST /api/v1/backtests`: 创建回测任务，第一版只支持 `DualMATrendStrategyBT`。
- `GET /api/v1/jobs/{job_id}`: 查询统一任务状态。
- DuckDB 持久化任务、同步明细、选股结果和回测结果。

### 暂不承诺

- 实盘下单、券商接口、资金管理、风控拦截。
- 多用户、登录认证、权限系统。
- 分布式任务队列。
- 前端真实回测页面。
- 参数优化、Walk-forward、样本外验证平台。

## 推荐工作流

```text
1. POST /api/v1/syncs
   同步股票列表和目标日期日线行情

2. GET /api/v1/jobs/{sync_job_id}
   等待同步完成

3. POST /api/v1/scans
   运行选股扫描

4. GET /api/v1/scans/{scan_job_id}/results
   查看命中股票

5. POST /api/v1/backtests
   用 stock_codes 或 scan_job_id 创建回测任务

6. GET /api/v1/backtests/{backtest_job_id}/results
   查看回测汇总指标
```

## 验证命令

```bash
python -m compileall -q main.py api domain application infrastructure backtrader_integration strategies tests
python -m unittest discover -s tests -v
```

## 重要说明

回测结果只用于研究，不构成投资建议。v2 第一版的回测能力是“可验证单/批回测”，不是完整研究级验证平台。


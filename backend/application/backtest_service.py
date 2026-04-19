"""Backtest workflow built around the existing Backtrader integration."""

import logging

from backend.application.interfaces import BacktestRunner
from backend.application.strategy.calendar import validate_date
from backend.backtrader_integration import BacktestEngine, DualMATrendStrategyBT
from backend.domain.models import BacktestResultRecord
from backend.domain.ports import JobRepository, StockRepository

logger = logging.getLogger(__name__)


class BacktestService(BacktestRunner):
    """Run supported Backtrader strategies and persist summary results."""

    SUPPORTED_STRATEGIES = {
        "DualMATrendStrategyBT": DualMATrendStrategyBT,
    }

    def __init__(
        self,
        stock_repository: StockRepository,
        job_repository: JobRepository,
    ):
        self.stock_repository = stock_repository
        self.job_repository = job_repository

    def list_supported_strategies(self) -> list[str]:
        return list(self.SUPPORTED_STRATEGIES)

    def run(
        self,
        job_id: str,
        strategy: str,
        start_date: str,
        end_date: str,
        stock_codes: list[str] | None = None,
        scan_job_id: str | None = None,
        initial_cash: float = 100000,
        commission: float = 0.0003,
        slippage: float = 0.0,
    ) -> dict:
        validate_date(start_date)
        validate_date(end_date)
        strategy_class = self.SUPPORTED_STRATEGIES.get(strategy)
        if strategy_class is None:
            raise ValueError(f"当前仅支持回测策略: {', '.join(self.SUPPORTED_STRATEGIES)}")

        resolved_codes = self._resolve_stock_codes(stock_codes, scan_job_id)
        if not resolved_codes:
            raise ValueError("回测必须提供 stock_codes 或包含命中结果的 scan_job_id")

        engine = BacktestEngine(self.stock_repository)
        records: list[BacktestResultRecord] = []
        failed_count = 0
        for stock_code in resolved_codes:
            try:
                result = engine.run_single_stock(
                    stock_code=stock_code,
                    strategy_class=strategy_class,
                    start_date=start_date,
                    end_date=end_date,
                    initial_cash=initial_cash,
                    commission=commission,
                    slippage=slippage,
                    printlog=False,
                )
                records.append(
                    BacktestResultRecord(
                        job_id=job_id,
                        stock_code=result.stock_code,
                        strategy_name=result.strategy_name,
                        start_date=result.start_date,
                        end_date=result.end_date,
                        final_value=result.final_value,
                        total_return=result.total_return,
                        annualized_return=result.annualized_return,
                        sharpe_ratio=result.sharpe_ratio,
                        max_drawdown=result.max_drawdown,
                        total_trades=result.total_trades,
                        win_rate=result.win_rate,
                    )
                )
            except Exception:
                failed_count += 1
                logger.exception("回测 %s 失败", stock_code)

        self.job_repository.save_backtest_results(records)
        return {
            "total_items": len(resolved_codes),
            "success_count": len(records),
            "failed_count": failed_count,
        }

    def _resolve_stock_codes(
        self,
        stock_codes: list[str] | None,
        scan_job_id: str | None,
    ) -> list[str]:
        if stock_codes:
            return list(dict.fromkeys(stock_codes))
        if not scan_job_id:
            return []
        getter = getattr(self.stock_repository, "get_strategy_results", None)
        if getter is None:
            return []
        hits = getter(scan_job_id)
        return list(dict.fromkeys(hit.code for hit in hits))


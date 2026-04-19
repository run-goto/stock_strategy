"""Trading calendar and scan date resolution."""

from __future__ import annotations

from datetime import datetime

from backend.application.interfaces import TradeCalendarProvider


class AkshareTradeCalendarProvider(TradeCalendarProvider):
    """Trading calendar backed by akshare."""

    def recent_range(self, n_days: int = 60) -> tuple[str, str]:
        import akshare as ak
        import pandas as pd

        today = datetime.today().date()
        trade_cal = ak.tool_trade_date_hist_sina()
        trade_cal["trade_date"] = pd.to_datetime(trade_cal["trade_date"]).dt.date
        trade_cal = trade_cal[trade_cal["trade_date"] <= today]
        trade_days = trade_cal["trade_date"].tail(n_days).tolist()
        start_date = trade_days[0].strftime("%Y%m%d")
        end_date = trade_days[-1].strftime("%Y%m%d")
        return start_date, end_date

    def normalize_targets(self, target_dates: list[str]) -> list[str]:
        parsed_targets = [datetime.strptime(item, "%Y%m%d").date() for item in target_dates]
        max_target = max(parsed_targets)

        import akshare as ak
        import pandas as pd

        trade_cal = ak.tool_trade_date_hist_sina()
        trade_cal["trade_date"] = pd.to_datetime(trade_cal["trade_date"]).dt.date
        trade_days = sorted(trade_cal.loc[trade_cal["trade_date"] <= max_target, "trade_date"].tolist())
        return _map_targets_to_recent_trade_dates(parsed_targets, trade_days)


class ConfigTradeCalendarProvider(TradeCalendarProvider):
    """Trading calendar that prefers configured dates and falls back to akshare."""

    def __init__(self, app_config: dict | None = None, fallback: TradeCalendarProvider | None = None):
        self.app_config = app_config or {}
        self.fallback = fallback or AkshareTradeCalendarProvider()

    def recent_range(self, n_days: int = 60) -> tuple[str, str]:
        configured_dates = self._configured_dates()
        if not configured_dates:
            return self.fallback.recent_range(n_days)
        trade_days = configured_dates[-n_days:]
        return trade_days[0].strftime("%Y%m%d"), trade_days[-1].strftime("%Y%m%d")

    def normalize_targets(self, target_dates: list[str]) -> list[str]:
        configured_dates = self._configured_dates()
        if not configured_dates:
            return self.fallback.normalize_targets(target_dates)

        parsed_targets = [datetime.strptime(item, "%Y%m%d").date() for item in target_dates]
        max_target = max(parsed_targets)
        trade_days = [item for item in configured_dates if item <= max_target]
        return _map_targets_to_recent_trade_dates(parsed_targets, trade_days)

    def _configured_dates(self) -> list:
        configured_dates = self.app_config.get("trade_calendar", {}).get("dates")
        if not configured_dates:
            return []
        return sorted(datetime.strptime(str(item), "%Y%m%d").date() for item in configured_dates)


def resolve_scan_dates(
    app_config: dict,
    start_date: str | None,
    end_date: str | None,
    target_dates: list[str] | None,
    calendar_provider: TradeCalendarProvider | None = None,
) -> tuple[str, str, list[str]]:
    calendar_provider = calendar_provider or ConfigTradeCalendarProvider(app_config)
    if start_date:
        validate_date(start_date)
    if end_date:
        validate_date(end_date)

    if bool(start_date) != bool(end_date):
        raise ValueError("start 和 end 必须同时提供")

    if not start_date or not end_date:
        start_date, end_date = calendar_provider.recent_range(app_config["defaults"]["check_days"])

    if target_dates:
        for td in target_dates:
            validate_date(td)
        target_dates = calendar_provider.normalize_targets(target_dates)
    else:
        _, default_target = calendar_provider.recent_range(15)
        target_dates = [default_target]

    return start_date, end_date, target_dates


def validate_date(date_str: str) -> str:
    try:
        datetime.strptime(date_str, "%Y%m%d")
    except ValueError as exc:
        raise ValueError("日期格式应为 YYYYMMDD") from exc
    return date_str


def _map_targets_to_recent_trade_dates(parsed_targets: list, trade_days: list) -> list[str]:
    normalized: list[str] = []
    for target in parsed_targets:
        candidates = [item for item in trade_days if item <= target]
        if not candidates:
            raise ValueError(f"目标日期早于交易日历范围: {target.strftime('%Y%m%d')}")
        trade_date = candidates[-1].strftime("%Y%m%d")
        if trade_date not in normalized:
            normalized.append(trade_date)
    return normalized

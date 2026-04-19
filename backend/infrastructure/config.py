"""基础设施配置：配置加载、交易日历、依赖组装。"""

import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_PROJECT_ROOT = _BACKEND_ROOT.parent
DEFAULT_CONFIG_PATH = _BACKEND_ROOT / "config" / "app_config.yaml"
LOG_HANDLER_NAME = "stock-strategy-file"


def load_app_config(config_path: str | Path = DEFAULT_CONFIG_PATH) -> dict:
    """加载 YAML 配置文件。"""
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"找不到配置文件: {config_path}")
    with open(config_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_trade_days(n_days: int = 60) -> tuple[str, str]:
    """获取最近 N 个交易日的起止日期 (start_date, end_date)。"""
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


def get_recent_trade_dates(target_dates: list[str], app_config: dict | None = None) -> list[str]:
    """Map calendar target dates to the nearest previous trading dates."""
    parsed_targets = [datetime.strptime(item, "%Y%m%d").date() for item in target_dates]
    max_target = max(parsed_targets)
    trade_days = _load_trade_calendar(max_target, app_config)

    normalized: list[str] = []
    for target in parsed_targets:
        candidates = [item for item in trade_days if item <= target]
        if not candidates:
            raise ValueError(f"目标日期早于交易日历范围: {target.strftime('%Y%m%d')}")
        trade_date = candidates[-1].strftime("%Y%m%d")
        if trade_date not in normalized:
            normalized.append(trade_date)
    return normalized


def _load_trade_calendar(max_target, app_config: dict | None = None) -> list:
    configured_dates = (app_config or {}).get("trade_calendar", {}).get("dates")
    if configured_dates:
        return sorted(
            datetime.strptime(str(item), "%Y%m%d").date()
            for item in configured_dates
            if datetime.strptime(str(item), "%Y%m%d").date() <= max_target
        )

    import akshare as ak
    import pandas as pd

    trade_cal = ak.tool_trade_date_hist_sina()
    trade_cal["trade_date"] = pd.to_datetime(trade_cal["trade_date"]).dt.date
    return sorted(trade_cal.loc[trade_cal["trade_date"] <= max_target, "trade_date"].tolist())


def get_duckdb_path(app_config: dict) -> str:
    return app_config.get("storage", {}).get("duckdb_path", "stock_data.duckdb")


def configure_logging(app_config: dict) -> Path:
    """Configure console and rotating file logging for the local service."""
    logging_config = app_config.get("logging", {})
    log_level = getattr(logging, logging_config.get("level", "INFO").upper(), logging.INFO)
    log_format = logging_config.get("format", "%(asctime)s - %(levelname)s - %(message)s")
    log_dir = Path(logging_config.get("dir", "logs"))
    if not log_dir.is_absolute():
        log_dir = _PROJECT_ROOT / log_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / logging_config.get("file", "app.log")
    max_bytes = int(logging_config.get("max_bytes", 10 * 1024 * 1024))
    backup_count = int(logging_config.get("backup_count", 5))

    formatter = logging.Formatter(log_format)
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    for handler in list(root_logger.handlers):
        if getattr(handler, "name", None) == LOG_HANDLER_NAME:
            root_logger.removeHandler(handler)
            handler.close()

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.name = LOG_HANDLER_NAME
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    has_stream_handler = any(
        isinstance(handler, logging.StreamHandler)
        and not isinstance(handler, RotatingFileHandler)
        for handler in root_logger.handlers
    )
    if not has_stream_handler:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(log_level)
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)

    logger.info("日志已初始化: %s", log_file)
    return log_file


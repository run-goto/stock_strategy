"""Strategy discovery and config-driven loading."""

import importlib
from pathlib import Path

import yaml

from backend.domain.strategy import BaseStrategy

_STRATEGIES_DIR = Path(__file__).resolve().parents[2] / "strategies"
_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "app_config.yaml"


def load_strategies_from_config(
    config: dict | None = None,
    config_path: str | Path = _DEFAULT_CONFIG_PATH,
    strategy_classes: list[str] | None = None,
) -> list[BaseStrategy]:
    """Load enabled strategy instances, optionally filtered by class name."""
    if config is None:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

    strategies_config: dict = config.get("strategies", {})
    requested_classes = _normalize_strategy_classes(strategy_classes)

    strategy_files = [
        f.stem
        for f in _STRATEGIES_DIR.iterdir()
        if f.is_file() and f.name != "__init__.py" and f.name.endswith(".py")
    ]

    enabled: list[BaseStrategy] = []
    for file_name in strategy_files:
        module = importlib.import_module(f"backend.strategies.{file_name}")
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, BaseStrategy)
                and attr is not BaseStrategy
            ):
                if strategies_config.get(attr.__name__, {}).get("enabled", False):
                    enabled.append(attr())

    if requested_classes is None:
        return enabled

    enabled_by_class = {strategy.__class__.__name__: strategy for strategy in enabled}
    unavailable = [class_name for class_name in requested_classes if class_name not in enabled_by_class]
    if unavailable:
        raise ValueError(f"不支持或未启用的选股策略: {', '.join(unavailable)}")

    return [enabled_by_class[class_name] for class_name in requested_classes]


def _normalize_strategy_classes(strategy_classes: list[str] | None) -> list[str] | None:
    if strategy_classes is None:
        return None

    normalized: list[str] = []
    for class_name in strategy_classes:
        if class_name and class_name not in normalized:
            normalized.append(class_name)
    if not normalized:
        raise ValueError("至少选择一个选股策略")

    return normalized

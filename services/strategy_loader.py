# file: services/strategy_loader.py

import importlib
import os
from pathlib import Path
import yaml

from strategies.base_strategy import BaseStrategy


def load_strategies_from_config(config_path="config/app_config.yaml"):
    """
    从配置文件中加载启用的策略类
    """
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    strategies_dir = Path("strategies")
    strategy_files = [
        f.stem for f in strategies_dir.iterdir()
        if f.is_file() and f.name != "__init__.py" and f.name.endswith(".py")
    ]

    enabled_strategies = []

    for file_name in strategy_files:
        module_name = f"strategies.{file_name}"
        module = importlib.import_module(module_name)

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, BaseStrategy) and attr != BaseStrategy:
                strategy_class_name = attr.__name__
                if config["strategies"].get(strategy_class_name, {}).get("enabled", False):
                    enabled_strategies.append(attr())

    return enabled_strategies

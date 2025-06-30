# file: config/config_loader.py

import yaml
from pathlib import Path


def load_app_config(config_path="config/app_config.yaml"):
    """
    加载 YAML 配置文件并返回配置字典
    """
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"找不到配置文件: {config_path}")

    with open(config_file, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return config

"""策略基类代理 — 保持 strategies/*.py 中 `from .base_strategy import BaseStrategy` 不变。"""

from backend.domain.strategy import BaseStrategy  # noqa: F401

__all__ = ["BaseStrategy"]


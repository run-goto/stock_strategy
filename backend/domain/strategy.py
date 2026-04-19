"""策略基类 — 领域层核心抽象。"""

from abc import ABC, abstractmethod

import pandas as pd


class BaseStrategy(ABC):
    """选股策略基类。

    所有策略必须继承此类并实现 check() 方法。
    """

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def check(self, hist_data: pd.DataFrame) -> bool:
        """检查历史数据是否命中策略条件。

        Args:
            hist_data: 按日期升序排列的历史行情 DataFrame，
                       至少包含 date, open, close, high, low, volume 列。

        Returns:
            True 表示命中。
        """


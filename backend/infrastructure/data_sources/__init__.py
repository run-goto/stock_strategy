from backend.infrastructure.data_sources.base import DataSourceBase, normalize_stock_data, get_market_code
from backend.infrastructure.data_sources.dfcf import DongFangCaiFu
from backend.infrastructure.data_sources.tencent import Tencent


def create_data_source(provider: str, timeout: float | None = None) -> DataSourceBase:
    provider_name = (provider or "").lower()
    if provider_name == "tencent":
        return Tencent(timeout=timeout)
    if provider_name in {"dongfangcaifu", "dfcf", "eastmoney"}:
        return DongFangCaiFu(timeout=timeout)
    raise ValueError(f"不支持的数据源: {provider}")


__all__ = [
    "DataSourceBase",
    "DongFangCaiFu",
    "Tencent",
    "create_data_source",
    "get_market_code",
    "normalize_stock_data",
]


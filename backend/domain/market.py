"""Market-related domain helpers."""


def get_market_code(stock_code: str) -> str:
    """Return the market prefix used by upstream data sources."""
    if stock_code.startswith("6"):
        return "sh"
    if stock_code.startswith(("0", "3")):
        return "sz"
    if stock_code.startswith(("8", "9", "4")):
        return "bj"
    return "sh"

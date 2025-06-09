class MarketUtil:

    @staticmethod
    def get_market_code(stock_code):
        if stock_code.startswith("6"):
            return "sh"
        elif stock_code.startswith("0") or stock_code.startswith("3"):
            return "sz"
        elif stock_code.startswith("8") or stock_code.startswith("9") or stock_code.startswith("4"):
            return "bj"
        else:
            return "sh"

from abc import ABC


class DataSource(ABC):
    def __init__(self):
        pass

    def get_stack_data(self, stock_code, market_code, start_data, end_data):
        pass

import logging
from services.stock_service import update_stock_data

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """主程序入口，命令行输出策略分析结果"""
    logger.info("启动A股策略分析系统（命令行模式）")
    # 可根据需要调整参数
    days = 30
    result_stocks = update_stock_data(days)
    if not result_stocks:
        print("未找到符合条件的股票")
        return
    result_stocks = sorted(result_stocks, key=lambda x: x['strategy'], reverse=True)
    for stock in result_stocks:
        print(f"{stock['name']}, {stock['code']},{stock['strategy']}")


if __name__ == '__main__':
    main()

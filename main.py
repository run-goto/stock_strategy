import logging
from views import create_stock_view

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """主程序入口"""
    logger.info("启动A股策略分析系统")
    app = create_stock_view()
    app.run(debug=True, host='0.0.0.0', port=8050)

if __name__ == '__main__':
    main() 
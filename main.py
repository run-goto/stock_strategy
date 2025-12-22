# file: main.py

import argparse
from datetime import datetime, timedelta

from services.stock_service import update_stock_data
from config.load_app_config import load_app_config

config = load_app_config()
default_check_days = config["defaults"]["check_days"]


def validate_date(date_str):
    try:
        datetime.strptime(date_str, "%Y%m%d")
        return date_str
    except ValueError:
        raise argparse.ArgumentTypeError("日期格式应为 YYYYMMDD")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="执行股票策略分析")
    parser.add_argument("--start", type=validate_date, help="开始日期 (YYYYMMDD)")
    parser.add_argument("--end", type=validate_date, help="结束日期 (YYYYMMDD)")
    parser.add_argument("--targets", nargs='+', type=validate_date, help="目标日期列表 (YYYYMMDD)")

    args = parser.parse_args()

    # 如果未指定 start/end，则自动计算最近 check_days 天
    if not args.start or not args.end:
        from services.stock_service import get_trade_days

        args.start, args.end = get_trade_days(default_check_days)

    if not args.targets:
        # 生成最近30个自然日的日期列表（格式为 YYYYMMDD）
        trade_days = []
        for i in range(5):
            date_str = (datetime.today() - timedelta(days=i)).strftime("%Y%m%d")
            print(date_str)
            trade_days.append(date_str)

        # 去重并倒序排列（可选）
        args.targets = sorted(set(trade_days), reverse=True)
    results = update_stock_data(args.start, args.end, args.targets)

    if results:
        for res in results:
            print(res)
    else:
        print("未找到符合条件的股票。")

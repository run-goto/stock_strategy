# file: main.py

import argparse
from datetime import datetime

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
        args.targets = [args.end]  # 默认只检查最后一天

    results = update_stock_data(args.start, args.end, ['20250630'])

    if results:
        for res in results:
            print(res)
    else:
        print("未找到符合条件的股票。")

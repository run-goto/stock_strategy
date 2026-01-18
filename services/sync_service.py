# file: services/sync_service.py
"""
数据同步服务模块
负责从外部数据源同步股票基础信息和每日行情数据
"""

import logging
from typing import List, Dict, Tuple
from datetime import datetime
import akshare as ak
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.db_service import (
    upsert_stocks, get_all_stocks, get_stock_count,
    insert_daily_data, get_stock_loaded_dates
)
from common.market_util import MarketUtil
from config.load_app_config import load_app_config

logger = logging.getLogger(__name__)
config = load_app_config()


def sync_stock_list() -> Dict:
    """
    同步股票基础信息列表
    从akshare获取最新A股列表并更新数据库
    """
    try:
        logger.info("开始同步股票列表...")
        
        # 获取A股股票列表
        stock_info = ak.stock_info_a_code_name()
        stocks = [(row['code'], row['name']) for _, row in stock_info.iterrows()]
        
        # 更新数据库
        count_before = get_stock_count()
        upsert_stocks(stocks)
        count_after = get_stock_count()
        
        new_count = count_after - count_before
        
        logger.info(f"股票列表同步完成: 总数={count_after}, 新增={new_count}")
        
        return {
            'success': True,
            'total': count_after,
            'new_count': new_count,
            'message': f'同步完成，共{count_after}只股票，新增{new_count}只'
        }
        
    except Exception as e:
        logger.error(f"同步股票列表失败: {str(e)}")
        return {
            'success': False,
            'message': f'同步失败: {str(e)}'
        }


def sync_stock_daily_data(code: str, start_date: str, end_date: str) -> Dict:
    """
    同步单只股票的每日行情数据
    """
    try:
        # 获取数据源配置
        data_provider = config["data_source"]["provider"]
        
        if data_provider == "tencent":
            from services.data_souce.tencent import Tencent
            data_source = Tencent()
        elif data_provider == "dongfangcaifu":
            from services.data_souce.dfcf import DongFangCaiFu
            data_source = DongFangCaiFu()
        else:
            raise ValueError(f"不支持的数据源: {data_provider}")
        
        market_code = MarketUtil.get_market_code(code)
        hist_data = data_source.get_stock_data(
            stock_code=code,
            market_code=market_code,
            start_date=start_date,
            end_date=end_date
        )
        
        if hist_data.empty:
            return {'success': True, 'count': 0, 'code': code}
        
        # 转换为数据库格式
        data_list = []
        for _, row in hist_data.iterrows():
            data_list.append({
                'code': code,
                'trade_date': row['date'].strftime('%Y%m%d') if hasattr(row['date'], 'strftime') else str(row['date']).replace('-', ''),
                'open': row.get('open'),
                'close': row.get('close'),
                'high': row.get('high'),
                'low': row.get('low'),
                'volume': row.get('volume'),
                'amount': row.get('amount')
            })
        
        insert_daily_data(data_list)
        
        return {'success': True, 'count': len(data_list), 'code': code}
        
    except Exception as e:
        logger.error(f"同步 {code} 行情数据失败: {str(e)}")
        return {'success': False, 'code': code, 'error': str(e)}


def sync_all_stocks_daily_data(start_date: str, end_date: str, 
                                progress_callback=None) -> Dict:
    """
    批量同步所有股票的每日行情数据
    """
    try:
        logger.info(f"开始批量同步行情数据: {start_date} ~ {end_date}")
        
        # 获取所有股票
        stocks = get_all_stocks(limit=10000)
        total = len(stocks)
        
        if total == 0:
            return {
                'success': False,
                'message': '没有股票数据，请先同步股票列表'
            }
        
        max_workers = config["defaults"].get("max_workers", 10)
        success_count = 0
        fail_count = 0
        processed = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(sync_stock_daily_data, stock['code'], start_date, end_date): stock
                for stock in stocks
            }
            
            for future in as_completed(futures):
                processed += 1
                result = future.result()
                
                if result.get('success'):
                    success_count += 1
                else:
                    fail_count += 1
                
                if progress_callback:
                    progress_callback(processed, total)
                
                if processed % 100 == 0:
                    logger.info(f"同步进度: {processed}/{total}")
        
        logger.info(f"批量同步完成: 成功={success_count}, 失败={fail_count}")
        
        return {
            'success': True,
            'total': total,
            'success_count': success_count,
            'fail_count': fail_count,
            'message': f'同步完成，成功{success_count}只，失败{fail_count}只'
        }
        
    except Exception as e:
        logger.error(f"批量同步失败: {str(e)}")
        return {
            'success': False,
            'message': f'同步失败: {str(e)}'
        }


def get_trade_days(n_days: int = 60) -> Tuple[str, str]:
    """获取最近N个交易日的日期范围"""
    today = datetime.today().date()
    trade_cal = ak.tool_trade_date_hist_sina()
    trade_cal['trade_date'] = pd.to_datetime(trade_cal['trade_date']).dt.date
    trade_cal = trade_cal[trade_cal['trade_date'] <= today]
    trade_days = trade_cal['trade_date'].tail(n_days).tolist()
    start_date = trade_days[0].strftime('%Y%m%d')
    end_date = trade_days[-1].strftime('%Y%m%d')
    return start_date, end_date


def sync_today_daily_data(progress_callback=None) -> Dict:
    """
    同步当天所有股票的交易数据
    """
    try:
        today = datetime.today().strftime('%Y%m%d')
        logger.info(f"开始同步当天({today})行情数据...")
        
        # 获取所有股票
        stocks = get_all_stocks(limit=10000)
        total = len(stocks)
        
        if total == 0:
            return {
                'success': False,
                'message': '没有股票数据，请先同步股票列表'
            }
        
        max_workers = config["defaults"].get("max_workers", 10)
        success_count = 0
        fail_count = 0
        processed = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(sync_stock_daily_data, stock['code'], today, today): stock
                for stock in stocks
            }
            
            for future in as_completed(futures):
                processed += 1
                result = future.result()
                
                if result.get('success'):
                    success_count += 1
                else:
                    fail_count += 1
                
                if progress_callback:
                    progress_callback(processed, total)
                
                if processed % 100 == 0:
                    logger.info(f"同步进度: {processed}/{total}")
        
        logger.info(f"当天数据同步完成: 成功={success_count}, 失败={fail_count}")
        
        return {
            'success': True,
            'total': total,
            'success_count': success_count,
            'fail_count': fail_count,
            'date': today,
            'message': f'同步{today}数据完成，成功{success_count}只，失败{fail_count}只'
        }
        
    except Exception as e:
        logger.error(f"同步当天数据失败: {str(e)}")
        return {
            'success': False,
            'message': f'同步失败: {str(e)}'
        }

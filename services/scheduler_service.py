# file: services/scheduler_service.py
"""
定时任务服务
- 每天下午4点自动执行股票数据更新
- 每天晚上11点检测数据是否完整，不完整则二次加载
"""

import schedule
import time
import threading
import logging
from datetime import datetime

from services.sync_service import sync_today_daily_data, sync_stock_list
from services.db_service import (
    get_stock_count, get_today_loaded_stock_count, 
    save_sync_log, get_sync_log
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 完成率阈值（超过这个比例认为同步完成）
COMPLETION_THRESHOLD = 0.95  # 95%


def job_sync_today_data():
    """定时任务：同步当天行情数据（下午4点）"""
    logger.info("=" * 50)
    logger.info(f"[定时任务] 开始执行每日数据同步 - {datetime.now()}")
    logger.info("=" * 50)
    
    today = datetime.today().strftime('%Y%m%d')
    
    try:
        result = sync_today_daily_data()
        
        # 获取统计数据
        total_stocks = get_stock_count()
        success_count = result.get('success_count', 0) if result.get('success') else 0
        fail_count = result.get('fail_count', 0) if result.get('success') else 0
        
        # 检查是否完成（成功率超过阈值）
        is_complete = (success_count / total_stocks) >= COMPLETION_THRESHOLD if total_stocks > 0 else False
        
        # 保存同步日志
        save_sync_log(
            sync_date=today,
            sync_type='daily',
            total_stocks=total_stocks,
            success_count=success_count,
            fail_count=fail_count,
            is_complete=is_complete
        )
        
        if result['success']:
            logger.info(f"[定时任务] 数据同步完成: {result['message']}")
            logger.info(f"[定时任务] 完成情况: {success_count}/{total_stocks} ({success_count/total_stocks*100:.1f}%)")
        else:
            logger.error(f"[定时任务] 数据同步失败: {result['message']}")
            
    except Exception as e:
        logger.error(f"[定时任务] 执行出错: {str(e)}")


def job_check_and_retry():
    """定时任务：检测数据完整性，不完整则二次加载（晚上11点）"""
    logger.info("=" * 50)
    logger.info(f"[定时任务] 开始数据完整性检测 - {datetime.now()}")
    logger.info("=" * 50)
    
    today = datetime.today().strftime('%Y%m%d')
    
    try:
        # 获取总股票数和已加载数
        total_stocks = get_stock_count()
        loaded_count = get_today_loaded_stock_count(today)
        
        # 获取今日同步日志
        sync_log = get_sync_log(today, 'daily')
        retry_count = sync_log['retry_count'] if sync_log else 0
        
        completion_rate = loaded_count / total_stocks if total_stocks > 0 else 0
        is_complete = completion_rate >= COMPLETION_THRESHOLD
        
        logger.info(f"[定时任务] 数据检测结果:")
        logger.info(f"  - 总股票数: {total_stocks}")
        logger.info(f"  - 已加载数: {loaded_count}")
        logger.info(f"  - 完成率: {completion_rate*100:.1f}%")
        logger.info(f"  - 已重试次数: {retry_count}")
        
        if is_complete:
            logger.info(f"[定时任务] ✓ 数据已完整，无需二次加载")
            # 更新日志状态
            save_sync_log(
                sync_date=today,
                sync_type='daily',
                total_stocks=total_stocks,
                success_count=loaded_count,
                fail_count=total_stocks - loaded_count,
                is_complete=True
            )
        else:
            if retry_count >= 3:
                logger.warning(f"[定时任务] ✗ 已重试3次，停止重试。请检查网络或数据源状态。")
            else:
                logger.info(f"[定时任务] ✗ 数据不完整，开始二次加载（第{retry_count + 1}次重试）...")
                
                # 执行二次同步
                result = sync_today_daily_data()
                
                # 重新统计
                new_loaded_count = get_today_loaded_stock_count(today)
                new_completion_rate = new_loaded_count / total_stocks if total_stocks > 0 else 0
                new_is_complete = new_completion_rate >= COMPLETION_THRESHOLD
                
                # 更新同步日志
                save_sync_log(
                    sync_date=today,
                    sync_type='daily',
                    total_stocks=total_stocks,
                    success_count=new_loaded_count,
                    fail_count=total_stocks - new_loaded_count,
                    is_complete=new_is_complete
                )
                
                if result['success']:
                    logger.info(f"[定时任务] 二次加载完成: {result['message']}")
                    logger.info(f"[定时任务] 新完成率: {new_completion_rate*100:.1f}%")
                else:
                    logger.error(f"[定时任务] 二次加载失败: {result['message']}")
                    
    except Exception as e:
        logger.error(f"[定时任务] 检测执行出错: {str(e)}")


def job_sync_stock_list():
    """定时任务：每周一同步股票列表"""
    # 只在周一执行
    if datetime.now().weekday() == 0:  # 0 = 周一
        logger.info("[定时任务] 开始同步股票列表...")
        try:
            result = sync_stock_list()
            if result['success']:
                logger.info(f"[定时任务] 股票列表同步完成: {result['message']}")
            else:
                logger.error(f"[定时任务] 股票列表同步失败: {result['message']}")
        except Exception as e:
            logger.error(f"[定时任务] 执行出错: {str(e)}")


def run_scheduler():
    """运行定时任务调度器"""
    logger.info("=" * 50)
    logger.info("定时任务调度器启动")
    logger.info("=" * 50)
    logger.info("已配置的任务:")
    logger.info("  - 每天 16:00 同步当天行情数据")
    logger.info("  - 每天 23:00 检测数据完整性，不完整则二次加载")
    logger.info("  - 每周一 16:00 同步股票列表")
    logger.info(f"  - 完成率阈值: {COMPLETION_THRESHOLD*100:.0f}%")
    logger.info("=" * 50)
    
    # 每天下午4点执行数据同步
    schedule.every().day.at("16:00").do(job_sync_today_data)
    
    # 每天晚上11点检测并二次加载
    schedule.every().day.at("23:00").do(job_check_and_retry)
    
    # 每周一下午4点同步股票列表
    schedule.every().monday.at("16:00").do(job_sync_stock_list)
    
    while True:
        schedule.run_pending()
        time.sleep(60)  # 每分钟检查一次


def start_scheduler_thread():
    """在后台线程中启动调度器"""
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    logger.info("定时任务调度器已在后台启动")
    return scheduler_thread


if __name__ == "__main__":
    # 直接运行时启动调度器
    run_scheduler()

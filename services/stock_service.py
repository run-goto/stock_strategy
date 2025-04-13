import akshare as ak
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import logging
from models.database import (
    save_stock_list, save_stock_history, 
    save_analysis_results, load_analysis_results
)
from strategies import ContinuousRiseStrategy, ThreeSmallRiseStrategy

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_trade_days(n_days=30):
    """获取最近N个交易日"""
    today = datetime.now().date()
    trade_cal = ak.tool_trade_date_hist_sina()
    # 将trade_date转换为datetime.date类型
    trade_cal['trade_date'] = pd.to_datetime(trade_cal['trade_date']).dt.date
    trade_cal = trade_cal[trade_cal['trade_date'] <= today]
    trade_days = trade_cal['trade_date'].tail(n_days).tolist()
    # 转换为字符串格式
    start_date = trade_days[0].strftime('%Y%m%d')
    end_date = trade_days[-1].strftime('%Y%m%d')
    return start_date, end_date

def stock_zh_a_hist(
        symbol: str = "000001",
        period: str = "daily",
        start_date: str = "19700101",
        end_date: str = "20500101",
        adjust: str = "",
        timeout: float = None
) -> pd.DataFrame:
    """获取股票历史数据"""
    try:
        # 根据股票代码判断交易所
        if symbol.startswith(('600', '601', '603', '605', '688')):
            exchange = 'sh'
        elif symbol.startswith(('000', '001', '002', '003', '300')):
            exchange = 'sz'
        elif symbol.startswith(('430', '830', '831', '832', '833', '834', '835', '836', '837', '838', '839')):
            exchange = 'bj'
        else:
            exchange = 'sh'  # 默认上海交易所
            
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period=period,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust
        )
        return df
    except Exception as e:
        logger.error(f"获取股票 {symbol} 数据失败: {str(e)}")
        return pd.DataFrame()

def check_stock(stock_info, threshold, days):
    """检查单个股票"""
    code = stock_info[0]
    name = stock_info[1]
    
    try:
        logger.info(f"正在获取 {name}({code}) 的历史数据...")
        start_date, end_date = get_trade_days(days)
        hist_data = stock_zh_a_hist(
            symbol=code, 
            period="daily", 
            adjust="qfq",
            start_date=start_date,
            end_date=end_date
        )
        
        if hist_data.empty:
            logger.warning(f"{name}({code}) 历史数据为空，跳过")
            return None
            
        # 确保数据按日期排序
        hist_data = hist_data.sort_values('日期')
        
        # 初始化策略
        continuous_rise_strategy = ContinuousRiseStrategy(threshold=threshold)
        three_small_rise_strategy = ThreeSmallRiseStrategy()
        
        # 检查连续上涨策略
        result = continuous_rise_strategy.get_result(hist_data, code, name)
        if result:
            logger.info(f"{name}({code}) 符合连续上涨条件")
            return result
        
        # 检查三只小阳线策略
        result = three_small_rise_strategy.get_result(hist_data, code, name)
        if result:
            logger.info(f"{name}({code}) 符合三只小阳线条件")
            return result
                
    except Exception as e:
        logger.error(f"获取 {name}({code}) 数据时出错: {str(e)}")
        return None
        
    return None

def update_stock_data(threshold=9, days=30):
    """更新股票数据"""
    try:
        logger.info("开始更新股票数据...")
        # 获取所有A股列表
        stock_info = ak.stock_info_a_code_name()
        logger.info(f"获取到 {len(stock_info)} 只股票")
        
        result_stocks = []
        with ThreadPoolExecutor(max_workers=50) as executor:
            # 只使用code和name列
            stock_data = stock_info[['code', 'name']]
            future_to_stock = {
                executor.submit(check_stock, item, threshold, days): item 
                for item in stock_data.values
            }
            
            for future in as_completed(future_to_stock):
                try:
                    data = future.result()
                    if data:
                        result_stocks.append(data)
                except Exception as exc:
                    logger.error(f"处理股票时出错: {exc}")
        
        logger.info(f"数据更新完成，共找到 {len(result_stocks)} 只符合条件的股票")
        return result_stocks
        
    except Exception as e:
        logger.error(f"更新数据时出错: {str(e)}")
        return None 
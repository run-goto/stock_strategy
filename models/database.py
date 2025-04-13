import sqlite3
from contextlib import contextmanager
import pandas as pd

# 数据库配置
DB_FILE = 'stock_data.db'

@contextmanager
def get_db_connection():
    """创建数据库连接的上下文管理器"""
    conn = sqlite3.connect(DB_FILE)
    try:
        yield conn
    finally:
        conn.close()

def init_database():
    """初始化数据库表"""
    with get_db_connection() as conn:
        # 检查表是否存在，如果不存在则创建
        conn.execute('''
        CREATE TABLE IF NOT EXISTS stock_list (
            code TEXT PRIMARY KEY,
            name TEXT,
            exchange TEXT
        )
        ''')
        
        conn.execute('''
        CREATE TABLE IF NOT EXISTS stock_history (
            code TEXT,
            date DATE,
            open REAL,
            close REAL,
            high REAL,
            low REAL,
            volume REAL,
            amount REAL,
            amplitude REAL,
            pct_change REAL,
            change_amount REAL,
            turnover REAL,
            PRIMARY KEY (code, date)
        )
        ''')
        
        conn.execute('''
        CREATE TABLE IF NOT EXISTS analysis_results (
            date DATE,
            code TEXT,
            name TEXT,
            current_price REAL,
            current_volume REAL,
            PRIMARY KEY (date, code)
        )
        ''')
        conn.commit()

def save_stock_list(stock_info_df):
    """保存股票列表到数据库"""
    with get_db_connection() as conn:
        stock_info_df.to_sql('stock_list', conn, if_exists='replace', index=False)

def save_stock_history(code, hist_data_df):
    """保存股票历史数据到数据库"""
    with get_db_connection() as conn:
        # 删除该股票的旧数据
        conn.execute('DELETE FROM stock_history WHERE code = ?', (code,))
        conn.commit()
        
        # 保存新数据
        hist_data_df['code'] = code
        hist_data_df.to_sql('stock_history', conn, if_exists='append', index=False)

def save_analysis_results(date, results):
    """保存分析结果到数据库"""
    with get_db_connection() as conn:
        # 删除当天的旧数据
        conn.execute('DELETE FROM analysis_results WHERE date = ?', (date,))
        
        # 插入新数据
        for result in results:
            conn.execute('''
            INSERT INTO analysis_results (date, code, name, current_price, current_volume)
            VALUES (?, ?, ?, ?, ?)
            ''', (date, result['code'], result['name'], result['current_price'], result['current_volume']))
        conn.commit()

def load_analysis_results(date):
    """从数据库加载分析结果"""
    with get_db_connection() as conn:
        # 获取分析结果
        results_df = pd.read_sql('''
        SELECT r.*, h.* 
        FROM analysis_results r
        LEFT JOIN stock_history h ON r.code = h.code
        WHERE r.date = ? AND h.date <= ?
        ORDER BY h.date
        ''', conn, params=(date, date))
        
        if results_df.empty:
            return None
            
        # 转换为之前的格式
        results = []
        for code in results_df['code'].unique():
            code_data = results_df[results_df['code'] == code]
            results.append({
                'code': code,
                'name': code_data['name'].iloc[0],
                'current_price': code_data['current_price'].iloc[0],
                'current_volume': code_data['current_volume'].iloc[0],
                'hist_data': code_data.to_dict('records')
            })
        return results 
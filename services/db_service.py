# file: services/db_service.py
"""
SQLite数据库服务模块
管理股票基础信息和每日行情数据
"""

import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'stock_data.db')


def get_connection():
    """获取数据库连接"""
    # 增加timeout以处理并发写入时的锁等待
    # check_same_thread=False允许连接在不同线程中使用
    conn = sqlite3.connect(DB_PATH, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # 启用WAL模式，允许并发读取和更好的写入性能
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=30000')  # 30秒超时
    return conn


def init_database():
    """初始化数据库表结构"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 股票基础信息表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stocks (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 每日行情数据表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_daily_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            open REAL,
            close REAL,
            high REAL,
            low REAL,
            volume INTEGER,
            amount REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(code, trade_date)
        )
    ''')
    
    # 策略结果缓存表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS strategy_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            strategy TEXT NOT NULL,
            target_date TEXT NOT NULL,
            current_price REAL,
            current_volume INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(code, strategy, target_date)
        )
    ''')
    
    # 同步日志表 - 记录每日加载情况
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sync_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sync_date TEXT NOT NULL,
            sync_type TEXT NOT NULL,
            total_stocks INTEGER,
            success_count INTEGER,
            fail_count INTEGER,
            is_complete BOOLEAN,
            retry_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 创建索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_daily_code ON stock_daily_data(code)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_daily_date ON stock_daily_data(trade_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_results_date ON strategy_results(target_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sync_logs_date ON sync_logs(sync_date)')
    
    conn.commit()
    conn.close()
    logger.info("数据库初始化完成")


# ==================== 股票基础信息 ====================

def get_all_stocks(search: str = None, limit: int = 100, offset: int = 0) -> List[Dict]:
    """获取所有股票列表"""
    conn = get_connection()
    cursor = conn.cursor()
    
    if search:
        cursor.execute('''
            SELECT code, name, updated_at FROM stocks 
            WHERE code LIKE ? OR name LIKE ?
            ORDER BY code
            LIMIT ? OFFSET ?
        ''', (f'%{search}%', f'%{search}%', limit, offset))
    else:
        cursor.execute('''
            SELECT code, name, updated_at FROM stocks 
            ORDER BY code
            LIMIT ? OFFSET ?
        ''', (limit, offset))
    
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_stock_count() -> int:
    """获取股票总数"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM stocks')
    count = cursor.fetchone()[0]
    conn.close()
    return count


def upsert_stocks(stocks: List[Tuple[str, str]]):
    """批量插入或更新股票信息"""
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    cursor.executemany('''
        INSERT INTO stocks (code, name, updated_at) VALUES (?, ?, ?)
        ON CONFLICT(code) DO UPDATE SET name=excluded.name, updated_at=excluded.updated_at
    ''', [(code, name, now) for code, name in stocks])
    
    conn.commit()
    inserted = cursor.rowcount
    conn.close()
    return inserted


# ==================== 每日行情数据 ====================

def get_stock_loaded_dates(code: str) -> List[str]:
    """获取某只股票已加载的交易日期列表"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT trade_date FROM stock_daily_data 
        WHERE code = ? 
        ORDER BY trade_date DESC
    ''', (code,))
    rows = cursor.fetchall()
    conn.close()
    return [row['trade_date'] for row in rows]


def get_daily_data(code: str, trade_date: str) -> Optional[Dict]:
    """获取某只股票某天的行情数据"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM stock_daily_data 
        WHERE code = ? AND trade_date = ?
    ''', (code, trade_date))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_daily_data_range(code: str, start_date: str, end_date: str) -> List[Dict]:
    """获取某只股票日期范围内的行情数据"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM stock_daily_data 
        WHERE code = ? AND trade_date >= ? AND trade_date <= ?
        ORDER BY trade_date
    ''', (code, start_date, end_date))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def insert_daily_data(data_list: List[Dict]):
    """批量插入每日行情数据"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.executemany('''
        INSERT OR IGNORE INTO stock_daily_data 
        (code, trade_date, open, close, high, low, volume, amount)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', [(
        d['code'], d['trade_date'], d.get('open'), d.get('close'),
        d.get('high'), d.get('low'), d.get('volume'), d.get('amount')
    ) for d in data_list])
    
    conn.commit()
    inserted = cursor.rowcount
    conn.close()
    return inserted


def get_all_loaded_dates() -> List[str]:
    """获取所有已加载的交易日期"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT trade_date FROM stock_daily_data 
        ORDER BY trade_date DESC
    ''')
    rows = cursor.fetchall()
    conn.close()
    return [row['trade_date'] for row in rows]


def get_date_stock_count(trade_date: str) -> int:
    """获取某个交易日已加载的股票数量"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT COUNT(DISTINCT code) FROM stock_daily_data 
        WHERE trade_date = ?
    ''', (trade_date,))
    count = cursor.fetchone()[0]
    conn.close()
    return count


# ==================== 策略结果 ====================

def save_strategy_results(results: List[Dict]):
    """保存策略分析结果"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.executemany('''
        INSERT OR REPLACE INTO strategy_results 
        (code, name, strategy, target_date, current_price, current_volume)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', [(
        r['code'], r['name'], r['strategy'], r['target_date'],
        r.get('current_price'), r.get('current_volume')
    ) for r in results])
    
    conn.commit()
    conn.close()


def get_strategy_results(target_date: str = None, strategy: str = None) -> List[Dict]:
    """查询策略分析结果"""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = 'SELECT * FROM strategy_results WHERE 1=1'
    params = []
    
    if target_date:
        query += ' AND target_date = ?'
        params.append(target_date)
    if strategy:
        query += ' AND strategy = ?'
        params.append(strategy)
    
    query += ' ORDER BY created_at DESC'
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ==================== 同步日志 ====================

def save_sync_log(sync_date: str, sync_type: str, total_stocks: int, 
                  success_count: int, fail_count: int, is_complete: bool, retry_count: int = 0):
    """保存同步日志"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 检查是否已有当天记录
    cursor.execute('''
        SELECT id, retry_count FROM sync_logs 
        WHERE sync_date = ? AND sync_type = ?
    ''', (sync_date, sync_type))
    existing = cursor.fetchone()
    
    now = datetime.now().isoformat()
    
    if existing:
        # 更新现有记录
        cursor.execute('''
            UPDATE sync_logs SET 
                total_stocks = ?, success_count = ?, fail_count = ?, 
                is_complete = ?, retry_count = ?, updated_at = ?
            WHERE id = ?
        ''', (total_stocks, success_count, fail_count, is_complete, 
              existing['retry_count'] + 1, now, existing['id']))
    else:
        # 插入新记录
        cursor.execute('''
            INSERT INTO sync_logs 
            (sync_date, sync_type, total_stocks, success_count, fail_count, is_complete, retry_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (sync_date, sync_type, total_stocks, success_count, fail_count, is_complete, retry_count))
    
    conn.commit()
    conn.close()


def get_sync_log(sync_date: str, sync_type: str = 'daily'):
    """获取指定日期的同步日志"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM sync_logs 
        WHERE sync_date = ? AND sync_type = ?
    ''', (sync_date, sync_type))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_recent_sync_logs(limit: int = 30):
    """获取最近的同步日志"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM sync_logs 
        ORDER BY sync_date DESC, created_at DESC
        LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_today_loaded_stock_count(trade_date: str) -> int:
    """获取指定交易日已加载的股票数量"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT COUNT(DISTINCT code) FROM stock_daily_data 
        WHERE trade_date = ?
    ''', (trade_date,))
    count = cursor.fetchone()[0]
    conn.close()
    return count


# 初始化数据库
init_database()


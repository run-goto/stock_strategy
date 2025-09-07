import mysql.connector
from mysql.connector import Error
import pandas as pd
from datetime import datetime


def create_connection():
    """
    创建MySQL数据库连接
    """
    try:
        connection = mysql.connector.connect(
            host='139.224.197.204',  # 根据实际情况修改
            database='stock_db',
            user='stock',  # 替换为你的用户名
            password='Stock_1234_+'  # 替换为你的密码
        )
        if connection.is_connected():
            print("成功连接到MySQL数据库")
            return connection
    except Error as e:
        print(f"连接MySQL时出错: {e}")
        return None


def insert_stock_data(connection, stock_data):
    """
    将股票数据插入到stock_data表中

    Parameters:
    connection: MySQL数据库连接对象
    stock_data: 包含股票数据的字典或DataFrame
    """
    try:
        cursor = connection.cursor()

        # 单条数据插入SQL语句
        insert_query = """
        INSERT INTO stock_data (CODE, NAME, DATE, OPEN, high, low, CLOSE, volume, amount)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        if isinstance(stock_data, dict):
            # 插入单条记录
            record = (
                stock_data['CODE'],
                stock_data['NAME'],
                stock_data['DATE'],
                stock_data['OPEN'],
                stock_data['high'],
                stock_data['low'],
                stock_data['CLOSE'],
                stock_data['volume'],
                stock_data['amount']
            )
            cursor.execute(insert_query, record)

        elif isinstance(stock_data, list):
            # 插入多条记录
            records = []
            for data in stock_data:
                record = (
                    data['CODE'],
                    data['NAME'],
                    data['DATE'],
                    data['OPEN'],
                    data['high'],
                    data['low'],
                    data['CLOSE'],
                    data['volume'],
                    data['amount']
                )
                records.append(record)
            cursor.executemany(insert_query, records)

        elif isinstance(stock_data, pd.DataFrame):
            # 从DataFrame插入数据
            for _, row in stock_data.iterrows():
                record = (
                    row['CODE'],
                    row['NAME'],
                    row['DATE'],
                    row['OPEN'],
                    row['high'],
                    row['low'],
                    row['CLOSE'],
                    row['volume'],
                    row['amount']
                )
                cursor.execute(insert_query, record)

        connection.commit()
        print(f"成功插入 {cursor.rowcount} 条记录")

    except Error as e:
        print(f"插入数据时出错: {e}")
        connection.rollback()
    finally:
        cursor.close()


def batch_insert_stock_data(connection, data_list):
    """
    批量插入股票数据

    Parameters:
    connection: MySQL数据库连接对象
    data_list: 股票数据列表
    """
    try:
        cursor = connection.cursor()

        insert_query = """
        INSERT INTO stock_data (CODE, NAME, DATE, OPEN, high, low, CLOSE, volume, amount)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        cursor.executemany(insert_query, data_list)
        connection.commit()
        print(f"成功批量插入 {cursor.rowcount} 条记录")

    except Error as e:
        print(f"批量插入数据时出错: {e}")
        connection.rollback()
    finally:
        cursor.close()


# 使用示例
if __name__ == "__main__":
    # 创建数据库连接
    conn = create_connection()

    if conn:
        # 示例1: 插入单条数据
        single_data = {
            'CODE': '000001',
            'NAME': '平安银行',
            'DATE': '2023-01-01',
            'OPEN': 12.5,
            'high': 13.2,
            'low': 12.3,
            'CLOSE': 13.0,
            'volume': 1000000,
            'amount': 12500000.0
        }

        insert_stock_data(conn, single_data)

        # 示例2: 插入多条数据
        multiple_data = [
            {
                'CODE': '000002',
                'NAME': '万科A',
                'DATE': '2023-01-01',
                'OPEN': 20.5,
                'high': 21.2,
                'low': 20.1,
                'CLOSE': 20.8,
                'volume': 2000000,
                'amount': 41000000.0
            },
            {
                'CODE': '600000',
                'NAME': '浦发银行',
                'DATE': '2023-01-01',
                'OPEN': 8.5,
                'high': 8.8,
                'low': 8.3,
                'CLOSE': 8.6,
                'volume': 3000000,
                'amount': 25500000.0
            }
        ]

        insert_stock_data(conn, multiple_data)

        # 示例3: 使用批量插入
        batch_data = [
            ('000001', '平安银行', '2023-01-02', 13.0, 13.5, 12.8, 13.3, 1500000, 19500000.0),
            ('000002', '万科A', '2023-01-02', 20.8, 21.5, 20.6, 21.2, 2500000, 52000000.0),
            ('600000', '浦发银行', '2023-01-02', 8.6, 8.9, 8.5, 8.7, 3500000, 30000000.0)
        ]

        batch_insert_stock_data(conn, batch_data)

        # 关闭连接
        conn.close()
        print("数据库连接已关闭")

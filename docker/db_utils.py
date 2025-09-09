# db_utils.py - 预置在容器内的数据库连接工具
"""
数据库连接工具模块
提供安全的数据库连接函数，配置通过环境变量注入
"""

import os
import pymysql
from typing import Optional


def get_announcement_connection():
    """
    获取announcement数据库连接
    
    Returns:
        pymysql.Connection: 数据库连接对象
    """
    required_vars = ['DB_ANNOUNCEMENT_HOST', 'DB_ANNOUNCEMENT_USER', 'DB_ANNOUNCEMENT_PASSWORD', 'DB_ANNOUNCEMENT_DATABASE']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        raise Exception(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    return pymysql.connect(
        host=os.getenv('DB_ANNOUNCEMENT_HOST'),
        port=int(os.getenv('DB_ANNOUNCEMENT_PORT', 3306)),
        user=os.getenv('DB_ANNOUNCEMENT_USER'),
        password=os.getenv('DB_ANNOUNCEMENT_PASSWORD'),
        database=os.getenv('DB_ANNOUNCEMENT_DATABASE'),
        charset=os.getenv('DB_ANNOUNCEMENT_CHARSET', 'utf8mb4'),
        init_command=os.getenv('DB_ANNOUNCEMENT_INIT_COMMAND', "SET SESSION collation_connection = 'utf8mb4_unicode_ci'")
    )

def test_connections():
    """
    测试数据库连接是否正常
    
    Returns:
        dict: 连接测试结果
    """
    results = {}
    
    # 测试announcement连接
    try:
        conn = get_announcement_connection()
        conn.ping()
        conn.close()
        results['announcement'] = 'OK'
    except Exception as e:
        results['announcement'] = f'Error: {str(e)}'
    
    return results

if __name__ == '__main__':
    # 测试连接
    print("Testing database connections...")
    results = test_connections()
    for db, status in results.items():
        print(f"{db}: {status}")
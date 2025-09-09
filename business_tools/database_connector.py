# business_tools/database_connector.py
"""
数据库连接器 - 提供MySQL数据库连接功能
"""

import pymysql
from typing import List, Dict, Any, Optional
import sys
import os

# 添加配置路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from config.db_config import get_db_config, get_db_announcement_config

class DatabaseConnector:
    """
    数据库连接器类
    """
    
    def __init__(self):
        self.reits_config = get_db_config()
        self.announcement_config = get_db_announcement_config()
        print("[DatabaseConnector] 数据库连接器初始化完成")
    
    def execute_query(self, sql: str, database: str = "reits") -> List[Dict[str, Any]]:
        """
        执行SQL查询
        
        Args:
            sql: SQL查询语句
            database: 数据库名称
            
        Returns:
            List[Dict[str, Any]]: 查询结果列表
        """
        if database == "announcement":
            config = self.announcement_config
        else:
            raise ValueError(f"不支持的数据库: {database}")
        
        connection = None
        try:
            print(f"[DatabaseConnector] 连接到数据库: {database}")
            print(f"[DatabaseConnector] 执行SQL: {sql}")
            
            # 建立数据库连接
            connection = pymysql.connect(**config)
            
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(sql)
                results = cursor.fetchall()
                
            print(f"[DatabaseConnector] 查询完成，返回 {len(results)} 条记录")
            return results
            
        except Exception as e:
            print(f"[DatabaseConnector] 数据库查询错误: {e}")
            raise Exception(f"数据库查询失败: {str(e)}")
            
        finally:
            if connection:
                connection.close()
                print(f"[DatabaseConnector] 数据库连接已关闭")
    
    def test_connection(self, database: str = "reits") -> bool:
        """
        测试数据库连接
        
        Args:
            database: 数据库名称
            
        Returns:
            bool: 连接是否成功
        """
        try:
            result = self.execute_query("SELECT 1 as test", database)
            return len(result) > 0 and result[0].get('test') == 1
        except Exception as e:
            print(f"[DatabaseConnector] 连接测试失败: {e}")
            return False

# 创建全局连接器实例
db_connector = DatabaseConnector()

def get_database_connector() -> DatabaseConnector:
    """获取数据库连接器实例"""
    return db_connector
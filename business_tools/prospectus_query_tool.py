# business_tools/prospectus_query_tool.py
"""
招募说明书查询工具 - 提供招募说明书文件名称查询功能
基于OpenAI Agents框架，供Agent调用
"""

import sys
import os
from typing import Dict, Any, Optional

# 添加路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

try:
    from agents import function_tool
except ImportError:
    # For testing purposes, create mock decorator
    def function_tool(func):
        return func

try:
    from .database_connector import get_database_connector
except ImportError:
    # 当直接运行此文件时，使用绝对导入
    from database_connector import get_database_connector

class ProspectusQueryTool:
    """
    招募说明书查询工具类
    提供特定基金的招募说明书文件查询功能
    """
    
    def __init__(self):
        self.db_connector = get_database_connector()
        print("[ProspectusQueryTool] 招募说明书查询工具初始化完成")
    
    @function_tool
    def query_prospectus_files(self, fund_code: str) -> Dict[str, Any]:
        """
        查询特定基金的招募说明书文件
        
        专门用于招募说明书查询的Agent工具接口
        
        Args:
            fund_code: 基金代码，如 "508056.SH"
            
        Returns:
            Dict[str, Any]: 包含招募说明书文件信息的字典
            
            成功时：
            {
                "success": True,
                "fund_code": "508056.SH",
                "initial_file": "中金普洛斯REIT招募说明书.pdf",      # 首发招募说明书
                "expansion_file": "中金普洛斯REIT扩募说明书.pdf",    # 扩募招募说明书(可能为None)
                "has_initial": True,
                "has_expansion": False,
                "message": "查询成功"
            }
            
            失败时：
            {
                "success": False,
                "fund_code": fund_code,
                "initial_file": None,
                "expansion_file": None,
                "has_initial": False,
                "has_expansion": False,
                "error": "错误信息"
            }
        """
        return self._get_prospectus_files_internal(fund_code)
    
    def _get_prospectus_files_internal(self, fund_code: str) -> Dict[str, Any]:
        """
        内部实现：获取特定基金的招募说明书文件
        """
        print(f"[ProspectusQueryTool] 开始查询基金 {fund_code} 的招募说明书文件")
        
        # 参数验证
        if not fund_code or fund_code.strip() == "" or fund_code == "unknown":
            error_msg = "基金代码无效"
            print(f"[ProspectusQueryTool] {error_msg}")
            return self._create_error_result(fund_code, error_msg)
        
        try:
            # 查询首发招募说明书
            initial_file = self._query_initial_prospectus(fund_code)
            
            # 查询扩募招募说明书
            expansion_file = self._query_expansion_prospectus(fund_code)
            
            # 构造结果
            has_initial = initial_file is not None
            has_expansion = expansion_file is not None
            
            print(f"[ProspectusQueryTool] 查询结果 - 首发: {initial_file}, 扩募: {expansion_file}")
            
            return {
                "success": True,
                "fund_code": fund_code,
                "initial_file": initial_file,
                "expansion_file": expansion_file,
                "has_initial": has_initial,
                "has_expansion": has_expansion,
                "message": f"查询成功，找到{'首发' if has_initial else ''}{'和扩募' if has_expansion else ''}招募说明书"
            }
            
        except Exception as e:
            error_msg = f"查询招募说明书失败: {str(e)}"
            print(f"[ProspectusQueryTool] {error_msg}")
            return self._create_error_result(fund_code, error_msg)
    
    def _query_initial_prospectus(self, fund_code: str) -> Optional[str]:
        """
        查询首发招募说明书
        
        Args:
            fund_code: 基金代码
            
        Returns:
            Optional[str]: 首发招募说明书文件名，如果不存在则返回None
        """
        print(f"[ProspectusQueryTool] 查询首发招募说明书...")
        
        # SQL查询 - 查询首发招募说明书
        sql = f"""
        SELECT file_name, date 
        FROM processed_files 
        WHERE fund_code = '{fund_code}' 
          AND elasticsearch_database_done = 'true'
          AND doc_type_2 = '招募说明书'
          AND file_name NOT LIKE '%扩募%'
          AND file_name NOT LIKE '%提示性%'
        ORDER BY date ASC
        LIMIT 1
        """
        
        try:
            results = self.db_connector.execute_query(sql, database="announcement")
            
            if results and len(results) > 0:
                file_name = results[0]['file_name']
                print(f"[ProspectusQueryTool] 找到首发招募说明书: {file_name}")
                return file_name
            else:
                print(f"[ProspectusQueryTool] 未找到首发招募说明书")
                return None
                
        except Exception as e:
            print(f"[ProspectusQueryTool] 查询首发招募说明书异常: {e}")
            return None
    
    def _query_expansion_prospectus(self, fund_code: str) -> Optional[str]:
        """
        查询扩募招募说明书
        
        Args:
            fund_code: 基金代码
            
        Returns:
            Optional[str]: 扩募招募说明书文件名，如果不存在则返回None
        """
        print(f"[ProspectusQueryTool] 查询扩募招募说明书...")
        
        # SQL查询 - 查询扩募招募说明书
        sql = f"""
        SELECT file_name, date 
        FROM processed_files 
        WHERE fund_code = '{fund_code}' 
          AND elasticsearch_database_done = 'true'
          AND doc_type_2 = '招募说明书'
          AND file_name LIKE '%扩募%'
          AND file_name NOT LIKE '%提示性%'
        ORDER BY date ASC
        LIMIT 1
        """
        
        try:
            results = self.db_connector.execute_query(sql, database="announcement")
            
            if results and len(results) > 0:
                file_name = results[0]['file_name']
                print(f"[ProspectusQueryTool] 找到扩募招募说明书: {file_name}")
                return file_name
            else:
                print(f"[ProspectusQueryTool] 未找到扩募招募说明书")
                return None
                
        except Exception as e:
            print(f"[ProspectusQueryTool] 查询扩募招募说明书异常: {e}")
            return None
    
    def _create_error_result(self, fund_code: str, error_msg: str) -> Dict[str, Any]:
        """
        创建错误结果
        
        Args:
            fund_code: 基金代码
            error_msg: 错误信息
            
        Returns:
            Dict[str, Any]: 错误结果字典
        """
        return {
            "success": False,
            "fund_code": fund_code,
            "initial_file": None,
            "expansion_file": None,
            "has_initial": False,
            "has_expansion": False,
            "error": error_msg
        }

# 创建全局工具实例
prospectus_query_tool = ProspectusQueryTool()

# 导出函数接口（兼容现有调用方式）
def get_prospectus_files(fund_code: str) -> Dict[str, Any]:
    """
    获取招募说明书文件的函数接口（兼容性接口）
    
    Args:
        fund_code: 基金代码
        
    Returns:
        Dict[str, Any]: 招募说明书文件信息
    """
    return prospectus_query_tool._get_prospectus_files_internal(fund_code)

# 新的推荐接口
def query_prospectus_files(fund_code: str) -> Dict[str, Any]:
    """
    查询招募说明书文件的推荐接口
    
    Args:
        fund_code: 基金代码
        
    Returns:
        Dict[str, Any]: 招募说明书文件信息
    """
    return prospectus_query_tool._get_prospectus_files_internal(fund_code)

# 测试函数
def test_prospectus_query_tool():
    """测试招募说明书查询工具"""
    print("=== 测试招募说明书查询工具 ===")
    
    # 测试数据库连接
    print("\n1. 测试数据库连接...")
    if prospectus_query_tool.db_connector.test_connection("announcement"):
        print("✅ announcement数据库连接正常")
    else:
        print("❌ announcement数据库连接失败")
        return
    
    # 测试招募说明书查询
    print("\n2. 测试招募说明书查询...")
    test_fund_codes = ["508056.SH", "180102.SZ", "508099.SH"]  # 测试几个基金代码
    
    for fund_code in test_fund_codes:
        print(f"\n🔍 测试基金: {fund_code}")
        result = get_prospectus_files(fund_code)
        
        if result["success"]:
            print(f"✅ 查询成功")
            print(f"   首发文件: {result['initial_file'] or '无'}")
            print(f"   扩募文件: {result['expansion_file'] or '无'}")
        else:
            print(f"❌ 查询失败: {result.get('error', '未知错误')}")

if __name__ == "__main__":
    test_prospectus_query_tool()
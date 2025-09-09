# business_tools/__init__.py
"""
业务工具模块 - 支持数据分析专用模式

提供REITs公告信息查询相关的业务工具：
- 基金查询工具：获取基金代码、基金简称、资产类型等信息
- 招募说明书查询工具（仅在完整模式下加载）
- 问题拆分工具（待实现）

条件导入模式：
- 数据分析专用模式：仅加载必要的基金查询工具，不加载招募说明书查询等检索功能
- 完整模式：加载所有业务工具
"""

import os

# 检查是否为数据分析专用模式
DATA_ANALYSIS_ONLY = os.environ.get('KR_DATA_ANALYSIS_ONLY', 'false').lower() == 'true'

# 导入基金查询工具和数据库连接器（数据分析必需）
try:
    from .fund_query_tool_reitstrading import (
        FundQueryAgent,
        get_all_fund_codes,
        intelligent_fund_query
    )
    
    # 为了保持兼容性，提供别名
    FundQueryTool = FundQueryAgent
    fund_query_tool = intelligent_fund_query
    
    # 添加缺失的函数，提供占位符
    def find_fund_by_name_or_code(query: str):
        """基于fund_query_tool_reitstrading的简化接口"""
        return {
            "success": False,
            "error": f"请使用 intelligent_fund_query 进行智能基金查询: {query}",
            "data": [],
            "count": 0
        }
    
    # 导入数据库连接器
    from .database_connector import (
        DatabaseConnector,
        get_database_connector
    )
    
    # 标记基础工具可用性
    _fund_query_available = True
    
    if DATA_ANALYSIS_ONLY:
        # 数据分析专用模式：不加载招募说明书查询工具
        print("🔸 [business_tools] 数据分析专用模式：跳过招募说明书查询工具")
        _prospectus_query_available = False
        
        # 提供占位符函数，避免导入错误
        def get_prospectus_files(fund_code: str):
            return {
                "success": False,
                "error": "招募说明书查询工具在数据分析专用模式下不可用",
                "fund_code": fund_code,
                "initial_file": None,
                "expansion_file": None,
                "has_initial": False,
                "has_expansion": False
            }
            
        def query_prospectus_files(fund_code: str):
            return {
                "success": False,
                "error": "招募说明书查询工具在数据分析专用模式下不可用",
                "fund_code": fund_code,
                "initial_file": None,
                "expansion_file": None,
                "has_initial": False,
                "has_expansion": False
            }
        
        ProspectusQueryTool = None
        prospectus_query_tool = None
        
    else:
        # 完整模式：导入所有工具
        print("🔸 [business_tools] 完整模式：加载所有业务工具")
        from .prospectus_query_tool import (
            ProspectusQueryTool,
            get_prospectus_files,
            query_prospectus_files,
            prospectus_query_tool
        )
        _prospectus_query_available = True
    
except ImportError as e:
    print(f"[business_tools] 导入错误: {e}")
    # 创建占位符函数
    def get_all_fund_codes():
        return {
            "success": False,
            "error": "基金查询工具未正确配置",
            "data": [],
            "count": 0
        }
    
    def find_fund_by_name_or_code(query: str):
        return {
            "success": False,
            "error": f"基金查询工具未正确配置，查询: {query}",
            "data": [],
            "count": 0
        }
        
    def get_prospectus_files(fund_code: str):
        return {
            "success": False,
            "error": "招募说明书查询工具未正确配置",
            "fund_code": fund_code,
            "initial_file": None,
            "expansion_file": None,
            "has_initial": False,
            "has_expansion": False
        }
        
    def query_prospectus_files(fund_code: str):
        return {
            "success": False,
            "error": "招募说明书查询工具未正确配置",
            "fund_code": fund_code,
            "initial_file": None,
            "expansion_file": None,
            "has_initial": False,
            "has_expansion": False
        }
    
    FundQueryTool = None
    fund_query_tool = None
    ProspectusQueryTool = None
    prospectus_query_tool = None
    DatabaseConnector = None
    get_database_connector = None
    _fund_query_available = False
    _prospectus_query_available = False

# 定义对外公开的接口
__all__ = [
    # 基金查询工具
    'FundQueryTool',
    'get_all_fund_codes',
    'find_fund_by_name_or_code',
    'fund_query_tool',
    
    # 招募说明书查询工具
    'ProspectusQueryTool',
    'get_prospectus_files',
    'query_prospectus_files',
    'prospectus_query_tool',
    
    # 数据库连接器
    'DatabaseConnector',
    'get_database_connector',
    
    # 状态检查
    'is_fund_query_available',
    'is_prospectus_query_available',
    'get_available_tools',
]

def is_fund_query_available() -> bool:
    """检查基金查询工具是否可用"""
    return _fund_query_available

def is_prospectus_query_available() -> bool:
    """检查招募说明书查询工具是否可用"""
    return _prospectus_query_available

def get_available_tools() -> dict:
    """获取可用工具列表"""
    return {
        "fund_query": _fund_query_available,
        "prospectus_query": _prospectus_query_available,
        "question_split": False,    # 待实现
    }

# 模块初始化信息
print("✅ business_tools 模块加载完成")
print(f"   - 基金查询工具: {'✅ 可用' if _fund_query_available else '❌ 不可用'}")
print(f"   - 招募说明书查询工具: {'✅ 可用' if _prospectus_query_available else '❌ 不可用'}")
print("   - 问题拆分工具: ⏳ 待实现")

if not (_fund_query_available and _prospectus_query_available):
    print("⚠️ 部分功能不可用，请检查数据库配置和依赖项")

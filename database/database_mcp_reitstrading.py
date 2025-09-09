"""
announcement数据库中价格数据 MCP 连接器

专门为announcement数据库中价格数据提供独立的 MCP 服务，与现有数据库系统完全分离。

核心功能：
1. 创建专门的announcement数据库中价格数据MCP服务器
2. 提供announcement数据库中价格数据的架构信息
3. 独立的配置和连接管理
"""

import os
import logging
from typing import Dict, Any, Optional
from .schema_provider_reitstrading import get_reitstrading_database_schema_info

try:
    from agents.mcp import MCPServerStdio, MCPServerStdioParams
    _agents_available = True
except ImportError:
    _agents_available = False
    MCPServerStdio = None
    MCPServerStdioParams = None

logger = logging.getLogger(__name__)


def create_reitstrading_database_mcp_server() -> MCPServerStdio:
    """
    创建专门的announcement数据库中价格数据 MCP 服务器
    
    Returns:
        MCPServerStdio: 配置好的announcement数据库中价格数据MCP服务器实例
        
    Raises:
        ImportError: 如果 OpenAI Agents 未安装
        Exception: 如果配置或连接失败
    """
    if not _agents_available:
        raise ImportError("OpenAI Agents 未安装。请运行: pip install openai-agents")
    
    # 获取announcement数据库数据库配置
    try:
        from config.db_config import get_db_announcement_config
        config = get_db_announcement_config()
        
        env_config = {
            "MYSQL_HOST": str(config["host"]),
            "MYSQL_PORT": str(config["port"]),
            "MYSQL_USER": config["user"],
            "MYSQL_PASSWORD": config["password"],
            "MYSQL_DATABASE": config["database"]  
        }
    except Exception as e:
        raise Exception(f"reitstrading数据库配置错误: {e}")
    
    # 使用修改后的本地Python MCP服务器
    current_dir = os.path.dirname(os.path.abspath(__file__))
    mysql_server_path = os.path.join(current_dir, "../mcp_servers/mysql_mcp_server-main/mysql_mcp_server-main/src/mysql_mcp_server/server.py")
    mysql_server_path = os.path.abspath(mysql_server_path)
    
    if not os.path.isfile(mysql_server_path):
        raise Exception(f"修改后的mysql-mcp-server不可用: {mysql_server_path}")
    
    # 创建announcement数据库中价格数据专用的 MCP 服务器，使用Python运行修改后的服务器
    params: MCPServerStdioParams = {
        "command": "python",
        "args": [mysql_server_path],
        "env": env_config
    }
    
    mcp_server = MCPServerStdio(
        params=params,
        cache_tools_list=True,
        name="reitstrading Database MCP Server"  # 专门的名称
    )
    
    logger.info(f"创建announcement数据库中价格数据 MCP 服务器: {mcp_server.name}")
    return mcp_server

def get_reitstrading_agent_instructions_with_schema(base_instructions: str = "") -> str:
    """
    为announcement数据库中价格数据 Agent 指令添加数据库架构信息
    
    Args:
        base_instructions: Agent 的基础指令
        
    Returns:
        str: 包含announcement数据库中价格数据架构信息的完整指令
    """
    schema_info = get_reitstrading_database_schema_info()
    
    instructions = f"""
{base_instructions}

{schema_info}

## announcement数据库中价格数据查询助手职责
你现在具备了专业的announcement数据库中价格数据查询能力。请遵循以下原则：

1. **查询规范**：
   - 严格使用 announcement.表名 格式
   - 英文表名和字段名直接使用，无需反引号
   - JSON字段查询使用相应的JSON函数

2. **查询策略**：
   - 优先提供用户最关心的核心数据
   - 大数量查询时使用 LIMIT 限制结果
   - 注意用户隐私数据的查询权限
   - JSON字段查询时注意格式和性能

3. **结果呈现**：
   - 简洁明了地提供全部查询结果

请根据用户的问题，智能选择合适的表进行查询。
    """.strip()
    
    return instructions

def check_reitstrading_database_dependencies() -> Dict[str, bool]:
    """
    检查announcement数据库中价格数据 MCP 相关依赖
    
    Returns:
        Dict[str, bool]: 依赖检查结果
    """
    result = {
        "openai_agents": _agents_available,
        "mysql_mcp_server": False,
        "announcement_database_config": False
    }
    
    # 检查修改后的Python MCP服务器
    current_dir = os.path.dirname(os.path.abspath(__file__))
    mysql_server_path = os.path.join(current_dir, "../mcp_servers/mysql_mcp_server-main/mysql_mcp_server-main/src/mysql_mcp_server/server.py")
    mysql_server_path = os.path.abspath(mysql_server_path)
    try:
        result["mysql_mcp_server"] = os.path.isfile(mysql_server_path)
    except Exception:
        result["mysql_mcp_server"] = False
    
    # 检查数据库配置
    try:
        from config.db_config import get_db_announcement_config
        get_db_announcement_config()
        result["announcement_database_config"] = True
    except Exception:
        result["announcement_database_config"] = False
    
    return result

# 向后兼容的函数名
create_reitstrading_cross_database_mcp = create_reitstrading_database_mcp_server
get_reitstrading_database_schema_prompt = get_reitstrading_database_schema_info
check_reitstrading_mcp_dependencies = check_reitstrading_database_dependencies 
"""
announcement数据库 MCP 连接器

专门为announcement数据库提供独立的 MCP 服务，与现有数据库系统完全分离。

核心功能：
1. 创建专门的announcement数据库MCP服务器
2. 提供announcement数据库的架构信息
3. 独立的配置和连接管理
"""

import os
import logging
from typing import Dict
from .schema_provider_announcement import get_announcement_database_schema_info

try:
    # 尝试导入，如果有依赖问题就标记为不可用
    from agents.mcp.server import MCPServerStdio
    _agents_available = True
except (ImportError, ModuleNotFoundError) as e:
    _agents_available = False
    MCPServerStdio = None
    _import_error = str(e)

logger = logging.getLogger(__name__)


def create_announcement_database_mcp_server():
    """
    创建专门的announcement数据库 MCP 服务器
    
    Returns:
        MCPServerStdio: 配置好的announcement数据库MCP服务器实例
        
    Raises:
        ImportError: 如果 OpenAI Agents 未安装
        Exception: 如果配置或连接失败
    """
    if not _agents_available:
        raise ImportError("OpenAI Agents 未安装。请运行: pip install openai-agents")
    
    # 获取announcement数据库配置
    try:
        from config.db_config import get_db_announcement_config
        config = get_db_announcement_config()
        
        env_config = {
            "MYSQL_HOST": str(config["host"]),
            "MYSQL_PORT": str(config["port"]),
            "MYSQL_USER": config["user"],
            "MYSQL_PASSWORD": config["password"],
            "MYSQL_DATABASE": config["database"]  # announcement 数据库
        }
    except Exception as e:
        raise Exception(f"announcement数据库配置错误: {e}")
    
    # 使用修改后的本地Python MCP服务器
    current_dir = os.path.dirname(os.path.abspath(__file__))
    mysql_server_path = os.path.join(current_dir, "../mcp_servers/mysql_mcp_server-main/mysql_mcp_server-main/src/mysql_mcp_server/server.py")
    mysql_server_path = os.path.abspath(mysql_server_path)
    
    if not os.path.isfile(mysql_server_path):
        raise Exception(f"修改后的mysql-mcp-server不可用: {mysql_server_path}")
    
    # 创建announcement数据库专用的 MCP 服务器，使用Python运行修改后的服务器
    mcp_server = MCPServerStdio(
        name="Announcement Database MCP Server",  # 专门的名称
        params={
            "command": "python",
            "args": [mysql_server_path],
            "env": env_config
        }
    )
    
    logger.info(f"创建announcement数据库 MCP 服务器: {mcp_server.name}")
    return mcp_server

def get_announcement_agent_instructions_with_schema(base_instructions: str = "") -> str:
    """
    为announcement数据库 Agent 指令添加数据库架构信息
    
    Args:
        base_instructions: Agent 的基础指令
        
    Returns:
        str: 包含announcement数据库架构信息的完整指令
    """
    schema_info = get_announcement_database_schema_info()
    
    instructions = f"""
{base_instructions}

{schema_info}

## announcement数据库查询助手职责
你现在具备了专业的announcement数据库查询能力。请遵循以下原则：

1. **查询规范**：
   - 严格使用 announcement.表名 格式
   - 英文表名和字段名直接使用，无需反引号
   - 注意MySQL 5.7版本限制，不支持窗口函数

2. **查询策略**：
   - 优先提供用户最关心的核心数据
   - 大数量查询时使用 LIMIT 限制结果
   - 注意用户隐私数据的查询权限
   - 只执行只读查询（SELECT、SHOW、DESCRIBE、EXPLAIN）

3. **结果呈现**：
   - 简洁明了地提供全部查询结果
   - 重点关注公告类型分类和时间范围

4. **数据特点**：
   - 数据范围：2021年6月21日至今
   - 覆盖约100个REITs基金的全部公告信息
   - 主要表：v_processed_files（公告信息）、product_info（基金产品信息）

请根据用户的问题，智能选择合适的表进行查询。
    """.strip()
    
    return instructions

def check_announcement_database_dependencies() -> Dict[str, bool]:
    """
    检查announcement数据库 MCP 相关依赖
    
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
    
    # 检查announcement数据库配置
    try:
        from config.db_config import get_db_announcement_config
        get_db_announcement_config()
        result["announcement_database_config"] = True
    except Exception:
        result["announcement_database_config"] = False
    
    return result

# 向后兼容的函数名
create_announcement_cross_database_mcp = create_announcement_database_mcp_server
get_announcement_database_schema_prompt = get_announcement_database_schema_info
check_announcement_mcp_dependencies = check_announcement_database_dependencies
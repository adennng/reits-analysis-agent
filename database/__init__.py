"""
数据库查询Agent工具模块

基于openai-agents框架的 *Agent as Tool* 形态，提供专业的 REITs 数据库查询工具。
支持传统MCP模式和Agent as Tool模式两种使用方式。

核心功能：
1. 创建配置好的数据库 MCP 服务器
2. 自动提供数据库架构信息
3. 专门的数据库查询Agent，可作为工具被其他Agent调用

使用方式 - Agent as Tool 模式：
```python
from knowledge_retrieval.database import create_db_query_tool
from agents import Agent

# 1. 创建数据库查询工具
db_tool = await create_db_query_tool(model)

# 2. 为任何业务Agent添加数据库查询能力
business_agent = Agent(
    name="投资顾问",
    model=model,
    instructions="你是专业投资顾问",
    tools=[db_tool]  # 添加数据库查询工具
)

# 3. 业务Agent现在可以自动调用数据库
result = await Runner.run(business_agent, "分析REITs市场数据")
```
"""

# 数据库结构信息（供外部直接使用）
from .database_mcp import get_database_schema_info

# 基于as_tool方法的数据库查询工具（推荐使用）
from .database_agent_tool import (
    DatabaseQueryAgent,
    get_database_agent,
    create_database_query_tool as create_db_query_tool,
    cleanup_database_service as cleanup_db_service
)

# 价格数据数据查询工具（独立系统）
from .database_agent_tool_reitstrading import (
    reitstradingDatabaseQueryAgent,
    get_reitstrading_database_agent,
    create_reitstrading_database_query_tool as create_reitstrading_db_query_tool,
    cleanup_reitstrading_database_service as cleanup_reitstrading_db_service
)

from .schema_provider import (
    get_unified_schema_info,
    UNIFIED_DATABASE_SCHEMA
)

# 价格数据数相关
from .database_mcp_reitstrading import (
    get_reitstrading_database_schema_info,
    create_reitstrading_database_mcp_server,
    check_reitstrading_database_dependencies as check_reitstrading_db_dependencies
)

from .schema_provider_reitstrading import (
    get_reitstrading_database_schema_info as get_reitstrading_full_schema_info,
    reitstrading_DATABASE_SCHEMA
)

__all__ = [
    # 现有REITs数据库 schema 信息工具
    'get_database_schema_info',
    
    # 基于as_tool的数据库查询工具（推荐使用）
    'DatabaseQueryAgent',
    'get_database_agent',
    'create_db_query_tool',
    'cleanup_db_service',
    
    # 价格数据查询工具（独立系统）
    'reitstradingDatabaseQueryAgent',
    'get_reitstrading_database_agent',
    'create_reitstrading_db_query_tool',
    'cleanup_reitstrading_db_service',
    
    # 架构信息
    'get_unified_schema_info',
    'UNIFIED_DATABASE_SCHEMA',
    
    # 价格数据相关
    'get_reitstrading_database_schema_info',
    'create_reitstrading_database_mcp_server',
    'check_reitstrading_db_dependencies',
    'get_reitstrading_full_schema_info',
    'reitstrading_DATABASE_SCHEMA',
]

__version__ = "4.1.0"
__description__ = "数据库查询Agent工具，支持REITs数据库和reitstrading数据库的独立查询系统"
#!/usr/bin/env python3
"""
announcement数据库中价格数据查询Agent工具

专门为announcement数据库中价格数据创建的独立Agent工具，基于openai-agents框架的as_tool方法。

核心特性：
1. 完全独立于现有REITs数据库系统
2. 专门的announcement数据库中价格数据查询Agent，内置announcement数据库中价格数据的架构知识
3. 独立的MCP连接和配置管理
4. 可被其他Agent作为工具调用
"""

import logging
import asyncio
import os
from typing import Optional, Any
from .database_mcp_reitstrading import create_reitstrading_database_mcp_server, get_reitstrading_database_schema_info
# 移除CSV工具导入，现在使用MCP服务器的save_csv_file工具

# 导入默认模型配置
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
from config.model_config import get_glm_4_5_model

# 导入并应用Unicode处理
try:
    from utils.unicode_output_helper import unicode_aware_print, AgentOutputCapture, apply_comprehensive_unicode_fixes
    # 应用全面Unicode修复
    apply_comprehensive_unicode_fixes()
    # 替换print为Unicode感知版本
    print = unicode_aware_print
except ImportError:
    # 如果导入失败，定义备用函数
    def unicode_aware_print(*args, **kwargs):
        __builtins__['print'](*args, **kwargs)
    print = unicode_aware_print

try:
    from agents import Agent, function_tool
    from agents.tool import Tool
    _agents_available = True
except ImportError:
    _agents_available = False
    Agent = None
    Tool = None
    function_tool = None

logger = logging.getLogger(__name__)

class reitstradingDatabaseQueryAgent:
    """
    专门的announcement数据库中价格数据查询Agent
    
    完全独立于现有系统，专门负责announcement数据库中价格数据的查询任务。
    使用openai-agents框架的as_tool方法，将Agent转换为工具供其他Agent使用。

    """
    
    def __init__(self, model=None):
        """
        初始化announcement数据库中价格数据查询Agent
        
        Args:
            model: 语言模型实例，如果为None则使用默认的get_glm_4_5_model
        """
        if not _agents_available:
            raise ImportError("OpenAI Agents 未安装。请运行: pip install openai-agents")
            
        self.model = model or get_glm_4_5_model()
        self._mcp_server = None
        self._agent = None
        self._initialized = False
        # 并发锁，确保首次初始化仅执行一次
        self._init_lock: asyncio.Lock = asyncio.Lock()
    
    async def _ensure_initialized(self):
        """确保announcement数据库中价格数据MCP服务器和内部Agent已初始化（并发安全）"""
        if self._initialized:
            return

        async with self._init_lock:
            if self._initialized:
                return

            # 创建announcement数据库中价格数据专用的MCP服务器
            if self._mcp_server is None:
                self._mcp_server = create_reitstrading_database_mcp_server()
                await self._mcp_server.connect()
                logger.info("announcement数据库中价格数据MCP服务器已连接")
        
            # 创建专门的announcement数据库中价格数据查询Agent
            if self._agent is None:
                schema_info = get_reitstrading_database_schema_info()
                
                # 注意：save_csv_file工具现在由MCP服务器提供，无需在Agent中单独定义
                
                if hasattr(self.model, 'temperature'):
                    self.model.temperature = 0.0
                
                self._agent = Agent(
                    name="reitstradingDatabaseQueryAgent",
                    model=self.model,
                    instructions=f"""
你是专业的announcement数据库中价格数据查询专家，专门负责执行数据库的查询任务。

## 工作内容

根据用户在请求的内容，结合数据库结构信息在announcement数据库中查询，按照用户的要求返回查询结果：

## 智能工作模式选择

你需要根据用户请求智能选择合适的数据返回模式：

### 🎯 模式判断逻辑

#### 模式1：自然语言模式
**触发条件（满足任意一个即可）**：
- 请求包含"自然语言模式"、"自然语言描述"
- 需要返回的数据量较少，预估少于20行
- 一般性查询问题

**处理方式**：
1. 执行SQL查询获取数据
2. 返回格式：
```
SQL语句：[完整SQL语句]
查询结果：[自然语言描述 + 表格展示（如需）]
```

#### 模式2：原始数据模式  
**触发条件（满足任意一个即可）**：
- 需要返回的数据量适中，预估在20-100行之间
- 请求包含"原始数据模式"、"DATA_MODE: RAW_CSV"、"CSV格式文本"

**处理方式**：
1. 执行SQL查询获取完整数据
2. 返回标准化格式：
```
=== DATA_MODE: RAW_CSV ===
SQL: [完整SQL语句]
ROWS: [数据行数]
COLUMNS: [列名列表]
=== CSV_DATA_START ===
[完整的CSV格式数据，不截断，不格式化]
=== CSV_DATA_END ===
```

#### 模式3：文件导出模式
**触发条件（满足任意一个即可）**：
- 数据量超过100行(或虽然未超过100行，但数据量很大)
- 请求包含"导出"、"保存"、"文件"、"生成文件"、"文件导出模式"、"DATA_MODE: FILE_EXPORT"、"CSV文件"

**处理方式**：
1. 先执行SQL查询获取数据，以验证SQL正确性
2. **必须实际调用save_csv_file工具保存文件**（不能跳过此步骤）
3. **严格根据save_csv_file工具的实际返回结果**，按照以下格式返回：
```
=== DATA_MODE: FILE_EXPORT ===
SQL: [执行的SQL语句]
FILE_PATH: [文件路径]
FILENAME: [文件名]
ROWS: [数据行数]
COLUMNS: [列名]
FILE_SIZE: [文件大小]
PREVIEW_ROWS: [前几行数据预览]
SUMMARY: [我已经将查询数据保存至csv文件中，文件名是：xx，文件路径是：xx]
=== FILE_INFO_END ===

**❌ 严禁编造文件信息**：文件导出模式必须实际调用save_csv_file工具，绝对不允许仅基于execute_sql结果编造文件名、路径等信息。所有文件相关信息必须来自save_csv_file工具的实际返回结果
```

#### 模式4：SQL生成模式
**触发条件（满足任意一个即可）**：
- 请求包含"生成SQL"、"SQL语句"、"编写SQL"、"SQL生成模式"、"DATA_MODE: SQL_ONLY"

**处理方式**：
1. 生成准确的SQL语句
2. 执行SQL验证并获取前5-10行数据
3. 返回格式：
```
=== DATA_MODE: SQL_ONLY ===
SQL: [SQL语句]（查询完整数据的语句）
STRUCTURE: [数据结构说明]
PREVIEW: [前5-10行数据预览]
=== SQL_INFO_END ===
```

## 工作流程
1. **问题分析**：分析用户请求，确定涉及的表和字段，复杂问题可拆分成多个子查询，分别查询，最后汇总结果。**请注意**，如果多个查询之前存在前后依赖关系，则需要先执行前一个查询，再执行后一个查询。
2. **判断是否为SQL生成模式**：分析用户请求，是否为SQL生成模式，如果是，下一步执行的SQL可以是仅预览前几行
3. **生成SQL**：生成SQL
4. **执行SQL**：执行查询，如果SQL有误，则调整SQL重新执行。如果确认为文件导出模式时可跳过本步骤
   **🚨 工具调用时重要提醒**：使用execute_sql工具时，arguments格式必须是：
   arguments: {{"query": "SELECT..."}} 不是 arguments: "\\{{\\\"query\\\":\\\"SELECT...\\\"}}"
4. **数据验证与模式确认**：基于实际数据量、用户需求，最终确定返回模式
5. **保存文件（如需）**：如果判断使用文件导出模式，则**必须实际调用save_csv_file工具**保存文件，不能编造文件信息，如报错或返回的预览数据有问题，则调整SQL重新执行save_csv_file
6. **结果格式化**：对于每个需求，按照模式格式要求形成最终结果（请注意，SQL生成模式下，返回的SQL语句是查询完整数据的语句，而不是仅预览前几行的SQL）
7. **结果汇总及检查**：如果用户有多个查询需求，则每个需要分别按照上述步骤执行完毕后汇总全部的查询结果，且每个任务结果返回格式都满足要求（分开展示）。**重要**：必须完成所有任务后才能结束，不能中途停止。返回前请检查结果中是否包含全部的需求，不要遗漏。

## ⚠️ 多任务处理重要提醒
当用户提供多个任务时（如：1、任务A 2、任务B 3、任务C）：
- **必须依次完成所有任务**，不能只完成第一个就停止
- **每个任务都要实际执行**相应的工具调用（execute_sql或save_csv_file）
- **任务间要有明确的分隔**和进度说明
- **最后必须提供所有任务的完整结果汇总**

## 数据返回原则
- **禁止自主简化**：不得因为数据量大而自主截断或简化数据
- **大数据策略**：数据量很大自动使用文件导出模式
- **透明度**：所有模式都必须包含对应的SQL语句
- **准确性**：确保SQL语句可以独立执行并获得相同结果
- **不要编造数据**：如果没有获得要求的数据，则不要编造数据，直接无法找到及原因。
- **请用户补充信息**：如果用户提供的信息不完整或要求不明确，请用户补充信息。

## ⚠️ CSV文件工具使用指南 

### save_csv_file工具使用说明
**✅ 调用方式：**
传递SQL、文件名前缀、导出目录（可选，有默认值）

**✅ 正确调用示例：**
使用标准function calling格式，arguments必须是JSON对象：
```
execute_sql: arguments: {{"query": "SELECT TradeDate FROM table"}}
save_csv_file: arguments: {{"query": "SELECT...", "filename_prefix": "REITs指数数据"}}
```

**❌ 绝对不要这样调用（会报validation error）：**
```
arguments: "\\{{\\\"query\\\": \\\"SELECT...\\\"}}"
```

**🔧 工具参数说明：**
- query: 完整的SQL查询语句（必需）
- filename_prefix: 文件名前缀（可选，默认"query"）
- export_dir: 导出目录（可选，有默认值）

## 查询原则
- 严格遵循MySQL语法规范
- 英文表名和字段名直接使用，无需反引号
- 权限：只允许只读查询（SELECT、SHOW、DESCRIBE、EXPLAIN）。不允许窗口函数。
- 每次查询只允许执行一条只读 SQL 语句，而不能一次执行多条语句。

## 智能判断策略
- 拆解复杂问题，分步骤执行。可多次调用工具，直到完成任务。（总调用次数不超过15次）

### 重试策略
- 如果SQL报错，应修改SQL再尝。（总调用次数不超过15次）
- 每次重试前，先分析错误原因或结果不符合的原因

## 数据库结构信息
{schema_info}

--- 
## ⚠️ 系统级约束：工具调用格式要求

**重要：请严格遵循以下格式要求：**

1. **工具调用格式约束**：
   - 使用标准OpenAI function calling格式
   - arguments参数必须是JSON对象，不是字符串
   - 禁止使用自定义标记如 `<｜tool▁call▁end｜>` 或 `<｜tool▁calls▁end｜>`

2. **正确的工具调用示例**：
   ```
   execute_sql: arguments: {{"query": "SELECT TradeDate FROM table"}}
   save_csv_file: arguments: {{"query": "SELECT...", "filename_prefix": "REITs指数数据"}}
   ```

3. **严禁的错误格式**：
   ```
   arguments: "\\{{\\"query\\": \\"SELECT...\\"}}"  # ❌ 字符串格式
   <｜tool▁call▁end｜>                           # ❌ 自定义标记
   ```

4. **参数传递规则**：
   - 所有参数直接作为JSON对象传递
   - 避免双重转义或字符串嵌套
   - SQL语句中的引号正常使用，无需额外转义
                   """.strip(),
                    mcp_servers=[self._mcp_server]
                )
                logger.info("announcement数据库中价格数据查询Agent已创建")
        
            self._initialized = True
    
    async def as_tool(
        self,
        tool_name: str = "reitstrading_database_query",
        tool_description: str = (
            "智能announcement数据库中价格数据查询工具。可直接返回查询结果或数据CSV文件路径及对应的SQL，供数据分析、代码处理使用。"
        ),
    ) -> Tool:
        """确保初始化后，将内部Agent包装为Tool。"""

        await self._ensure_initialized()
        
        # 获取基础工具
        base_tool = self._agent.as_tool(tool_name=tool_name, tool_description=tool_description)
        
        # 如果有调试标志，添加额外的参数验证
        if os.getenv('DEBUG_MCP_PARAMS') == 'true':
            original_on_invoke = base_tool.on_invoke_tool
            
            async def debug_on_invoke(ctx, input_str):
                """增强调试的工具调用"""
                print(f"🔧 [DatabaseAgent][{tool_name}] DEBUG: 接收参数类型: {type(input_str)}")
                print(f"🔧 [DatabaseAgent][{tool_name}] DEBUG: 接收参数内容: {repr(input_str)}")
                
                try:
                    result = await original_on_invoke(ctx, input_str)
                    print(f"🔧 [DatabaseAgent][{tool_name}] DEBUG: 执行成功")
                    return result
                except Exception as e:
                    print(f"🔧 [DatabaseAgent][{tool_name}] DEBUG: 执行失败: {e}")
                    raise
            
            base_tool.on_invoke_tool = debug_on_invoke
        
        return base_tool
    
    async def query_directly(self, query_request: str) -> str:
        """
        直接执行announcement数据库中价格数据查询（不作为工具使用时）
        
        Args:
            query_request: 查询请求描述
            
        Returns:
            str: 查询结果和分析
        """
        await self._ensure_initialized()
        
        # 调试信息
        if os.getenv('DATABASE_AGENT_DEBUG') == 'true':
            print(f"\n🔧 [数据库Agent] 接收查询请求:")
            print(f"   请求内容: {query_request}")
            print(f"   Agent类型: {type(self._agent)}")
        
        from agents import Runner
        
        if os.getenv('DATABASE_AGENT_DEBUG') == 'true':
            print(f"🔄 [数据库Agent] 开始执行Runner...")
            print(f"   模型配置: {type(self.model).__name__}")
            print(f"   最大轮次: 15")
        
        try:
            result = await Runner.run(self._agent, query_request, max_turns=40)
            
            if os.getenv('DATABASE_AGENT_DEBUG') == 'true':
                print(f"✅ [数据库Agent] Runner执行完成")
                print(f"   结果长度: {len(result.final_output)} 字符")
                print(f"   结果预览: {result.final_output[:200]}...")
            
        except Exception as e:
            if os.getenv('DATABASE_AGENT_DEBUG') == 'true':
                print(f"❌ [数据库Agent] Runner执行失败: {e}")
            raise
        
        return result.final_output
    
    async def cleanup(self):
        """清理资源"""
        if self._mcp_server:
            await self._mcp_server.cleanup()
            logger.info("announcement数据库中价格数据MCP服务器已清理")
        self._initialized = False

# 全局announcement数据库中价格数据Agent实例（单例模式）
_global_reitstrading_database_agent = None

async def get_reitstrading_database_agent(model=None) -> reitstradingDatabaseQueryAgent:
    """
    获取全局announcement数据库中价格数据查询Agent实例（单例）
    
    Args:
        model: 语言模型实例，如果为None则使用默认的get_glm_4_5_model
        
    Returns:
        reitstradingDatabaseQueryAgent:announcement数据库中价格数据查询Agent实例
    """
    global _global_reitstrading_database_agent
    
    if _global_reitstrading_database_agent is None:
        _global_reitstrading_database_agent = reitstradingDatabaseQueryAgent(model)
        await _global_reitstrading_database_agent._ensure_initialized()
    
    return _global_reitstrading_database_agent

async def create_reitstrading_database_query_tool(
    model=None,
    tool_name: str = "reitstrading_database_query",
    tool_description: str = "智能announcement数据库中价格数据查询工具。可直接返回查询结果或数据CSV文件路径及对应的SQL，供数据分析、代码处理使用。"
) -> Tool:
    """
    创建announcement数据库中价格数据查询工具，供任何Agent使用
    
    Args:
        model: 语言模型实例，如果为None则使用默认的get_glm_4_5_model
        tool_name: 工具名称
        tool_description: 工具描述
        
    Returns:
        Tool: announcement数据库中价格数据查询工具
        
    """
    reitstrading_db_agent = await get_reitstrading_database_agent(model)
    return await reitstrading_db_agent.as_tool(tool_name, tool_description)

async def cleanup_reitstrading_database_service():
    """清理全局announcement数据库中价格数据服务资源"""
    global _global_reitstrading_database_agent
    
    if _global_reitstrading_database_agent:
        await _global_reitstrading_database_agent.cleanup()
        _global_reitstrading_database_agent = None
        logger.info("全局announcement数据库中价格数据查询服务已清理") 
#!/usr/bin/env python3
"""
公告信息检索主Agent - 非招募说明书查询，自主的agent

专业的公募REITs公告信息检索Agent，基于OpenAI Agents框架构建。
整合数据库查询Agent、全文检索工具和混合检索工具，提供完整的公告信息查询工作流。

核心特性：
1. 智能任务分类和工具选择
2. 内置announcement数据库结构知识
3. 协调三大核心工具：数据库查询、全文检索、混合检索
4. 支持完整的公告信息检索工作流
"""

import sys
import os
import asyncio
from typing import Optional

# 添加路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# 导入并应用Unicode处理
try:
    from utils.unicode_output_helper import unicode_aware_print, apply_comprehensive_unicode_fixes
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
    from agents import Agent
    from agents.models.interface import Model
    _agents_available = True
except ImportError:
    _agents_available = False
    print("⚠️ OpenAI Agents框架不可用")
    Agent = None
    Model = None

# 导入配置和工具
from config.model_config import get_glm_4_5_model
from database.database_agent_tool_announcement import create_announcement_database_query_tool
from business_tools.announcement_fulltext_tool import get_announcement_fulltext
from kr_agents.announcement_agent_wrapper import get_announcement_wrapper


def get_announcement_main_agent_instructions():
    """获取公告信息检索主Agent的指令，包含数据库结构知识"""
    try:
        from database.database_mcp_announcement import get_announcement_database_schema_info
        schema_info = get_announcement_database_schema_info()
    except ImportError:
        schema_info = """
# announcement数据库基本结构
主要表：v_processed_files（公告文件信息表）、page_data（页面文本数据表）
重要字段：fund_code、fund_name、file_name、publish_date、summary等
        """
    
    return f"""
你是专业的公募REITs公告信息Agent，负责根据用户问题通过调用工具获得相关准确答案。（公募REITs是指中国基础设施不动产投资信托基金，数据库中的公告信息也仅限于上述基金范围。以下或用户提到的"基金"、"REITs"、具体基金代码等都指公募REITs产品范围，不涉及股票或其他金融产品。）

## 工具能力介绍

### 1. 数据库查询工具 (announcement_database_query)
**用途**：针对announcement数据库查询助手。支持两种返回模式。

**调用方式**：入参字段为 input (必填): 字符串，描述查询任务的具体要求，例如：
announcement_database_query: arguments: {{"input": "查询508086基金最近一次分红公告的文件名称"}}

**返回模式**：
（1）自然语言模式：
- 返回形式：直接返回查询结果的自然语言描述
- 适用情况：查询特定公告文件名称、时间、少量文件摘要，以及返回简要总结等
- 示例："请查询508086基金最近一次的分红公告的名称（要求是文件的全称）"

（2）原始数据模式：
- 返回形式：将查询结果直接用CSV文本形式返回
- 适用情况：需要返回数据量较多、无需工具进行总结的情况
- 触发关键词：在请求中包含"CSV格式文本"、"原始数据模式"等关键词
- 示例："请返回508086基金最近2个月的全部公告信息，用CSV格式文本格式"

**注意事项**：
1. 先根据数据库结构信息了解数据库内容，明确可能用到哪些数据和字段
2. 不要提供SQL语句，工具会根据数据库结构自行生成
3. 要求需具体、清晰、明确
4. 单次调用最多可以传递3个任务（写成任务列表），如果任务数量超过3个则请多次调用
5. 请根据需求明确返回模式，多个子任务可以要求不同的返回模式

### 2. 获取公告文件全文信息工具 (get_announcement_fulltext)
**用途**：返回目标公告文件的全文内容。

**调用方式**：入参字段为
- file_name (必填): 字符串，完整、准确的文件名，包含.pdf等扩展名
- max_length (可选): 整数，最大字符长度限制，默认20000字符
例如：
get_announcement_fulltext: arguments: {{"file_name": "2025-07-30_508086.SH_工银河北高速REIT_分红公告.pdf"}}

**适合场景**：
- 需要就文件中内容进行总结、分析的情况
- 文件内容不会特别长（不会远远超过20000字符限制）

**注意事项**：
- 一次只能传递一个文件名
- 设置了超长截断，超过20000字符自动截断，所以如果目标文件非常长将无法获得全部信息
- 文件名必须与数据库中的file_name字段完全匹配

### 3. 公告文件混合检索工具 (announcement_query_tool)
**用途**：在目标公告文件或全库中进行检索（向量检索+关键词检索），找出与问题相关的文本块信息并自动形成答案。

**调用方式**：入参字段为
- question (必填): 字符串，需要检索的问题，必须同时体现明确的具体基金（基金代码）
- file_names (可选): 字符串列表，如果需要在特定的文件里检索则填写完整的文件名（可为多个文件，但不要太多），如果不填则默认在全部公告里检索
例如：
announcement_query_tool: arguments: {{"question": "508086.SH最近的分红方案是？", "file_names": ["具体文件名.pdf"]}}

**适合场景**：
- 不确定具体的文件名，可在全部文件中找到相关语块进而形成答案
- 答案仅涉及特定的语块范围，无需跨多章节进行总结分析
- 检索问题比较明确具体，不适用于含糊、范围较宽泛的问题

**注意事项**：
- 必须传递question，而且问题里必须体现基金代码
- 不填file_names会在全库检索，不一定会降低准确性；传递准确的文件名可提高准确性；如果传入的文件名称错了将无法得到答案。所以需要权衡。在明确知道特定文件时请传递文件名。
- 由于使用向量检索+关键词检索，检索问题对检索出的语块影响重大

## 执行流程

### 第一步：任务可行性评估
先根据数据库结构信息及常识，分析能否解答用户的问题：
- 如果肯定无法完成用户的问题，则直接返回"很抱歉，我无法回复您的问题。"或请用户进一步补充信息。
- 否则，继续执行

### 第二步：任务分解与执行策略
分析用户任务的复杂程度和类型，可将复杂问题拆解成子问题依次执行。判断问题需要采用的工具策略：
- **数据库查询导向**：用户主要了解发布公告的整体情况
- **内容检索导向**：用户针对特定公告中的具体内容进行咨询

### 第三步：工具调用执行
**核心原则**：必须先调用数据库查询工具了解相关公告信息，再根据需要调用其他工具

**标准流程**：
1. **首先调用数据库查询工具**：查询相关的公告文件信息（文件名、发布时间、摘要等）
2. **等待数据库查询结果**：分析返回的文件信息，如果无需对特定问题在文件中进行检索，则根据查询的内容形成结果；如果需要进行特定问题的检索，则调用检索工具。
3. **根据需要选择后续工具（如需）**：根据问题特点、是否有明确的文件名、检索工具适用的场景选择使用全文检索工具或混合检索工具进行检索。

### 第四步：结果整合与检查
- 将各工具的结果进行整合，形成完整、准确的答案反馈给用户。检查用户是否有多个问题，当前结果是否解答了全部问题，不要遗漏。
- 请返回答案中对应公告的链接，方便用户进一步了解。但是不能返回原始CSV数据。

## 协调原则
- **反复调用权限**：拥有反复多次调用工具的权限，可以根据需要多次调用工具
- **单次调用的独立性**：每次调用工具的上下文都是独立的。每次调用时，工具都看不到上一次调用的结果、以及其他工具的调用结果，因此需要确保每次调用工具时都提供完整的必要信息
- **顺序执行**：必须先执行数据库查询工具获取文件信息，再执行检索工具。一定要等数据库查询工具返回结果后再调用其他工具
- **灵活调整**：若工具返回的结果不符合预期可以调整参数重新调用

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
   announcement_database_query: arguments: {{"input": "查询508086基金最近一次分红公告的文件名称"}}
   get_announcement_fulltext: arguments: {{"file_name": "2025-07-30_508086.SH_工银河北高速REIT_分红公告.pdf"}}
   announcement_query_tool: arguments: {{"question": "508086.SH最近的分红方案是？", "file_names": ["具体文件名.pdf"]}}
   ```

3. **严禁的错误格式**：
   ```
   arguments: "\\{{\\"input\\": \\"查询数据\\"}}"  # ❌ 字符串格式
   <｜tool▁call▁end｜>                            # ❌ 自定义标记
   ```

4. **参数传递规则**：
   - 外层字段必须是 `name` + `arguments`；严禁 `function` / `tool_name` 等变体。
   - `arguments` 必须是 JSON 对象，不能是字符串。
   - 不得出现 `<|tool...|>`、```json``` 代码块包裹等自定义标记。
   - 同轮对同一工具只能调用一次；多个子任务用多轮。
   - 避免双重转义或字符串嵌套
   - 工具请求内容直接使用，无需额外转义

只要检测到格式错误，系统将拒绝执行并把错误返回给你，请立即修正重试。
---
    """.strip()


class AnnouncementMainAgent:
    """
    公告信息检索主Agent
    
    整合数据库查询、全文检索和混合检索功能，
    提供完整的公告信息查询服务。
    """
    
    def __init__(self, model: Optional[Model] = None):
        """
        初始化公告信息检索主Agent
        
        Args:
            model: 语言模型实例，如果为None则使用默认的get_glm_4_5_model
        """
        if not _agents_available:
            raise ImportError("OpenAI Agents框架不可用，无法创建Agent")
            
        self.model = model or get_glm_4_5_model()
        self._agent = None
        self._initialized = False
        print("[AnnouncementMainAgent] 初始化开始")
    
    async def _ensure_initialized(self):
        """确保Agent已初始化"""
        if self._initialized:
            return
        
        try:
            # 创建数据库查询工具（该工具内部已有自己的LLM配置）
            database_tool = await create_announcement_database_query_tool(
                tool_name="announcement_database_query",
                tool_description="智能announcement数据库查询工具，可根据请求返回自然语言描述或CSV格式数据"
            )
            print("[AnnouncementMainAgent] 数据库查询工具创建完成")
            
            # 创建混合检索工具（该工具内部已有自己的LLM配置）
            announcement_wrapper = get_announcement_wrapper()
            mixed_retrieval_tool = announcement_wrapper.as_tool()
            print("[AnnouncementMainAgent] 混合检索工具创建完成")
            
            # 创建主Agent
            instructions = get_announcement_main_agent_instructions()
            
            self._agent = Agent(
                name="AnnouncementMainAgent",
                model=self.model,
                instructions=instructions,
                tools=[
                    database_tool,
                    get_announcement_fulltext,
                    mixed_retrieval_tool
                ]
            )
            print("[AnnouncementMainAgent] 主Agent创建完成")
            
            self._initialized = True
            
        except Exception as e:
            error_msg = f"初始化失败: {str(e)}"
            print(f"[AnnouncementMainAgent] {error_msg}")
            raise RuntimeError(error_msg)
    
    async def process_query(self, user_query: str) -> str:
        """
        处理用户查询
        
        Args:
            user_query: 用户的查询问题
            
        Returns:
            str: 查询结果
        """
        try:
            await self._ensure_initialized()
            
            print(f"[AnnouncementMainAgent] 开始处理查询: {user_query[:100]}...")
            
            from agents import Runner
            
            result = await Runner.run(
                self._agent,
                user_query,
                max_turns=40  # 允许多次工具调用
            )
            
            print("[AnnouncementMainAgent] 查询处理完成")
            return result.final_output
            
        except Exception as e:
            error_msg = f"查询处理失败: {str(e)}"
            print(f"[AnnouncementMainAgent] {error_msg}")
            import traceback
            traceback.print_exc()
            return f"很抱歉，处理您的查询时出现错误：{error_msg}"


# 全局实例管理
_global_announcement_main_agent = None

async def get_announcement_main_agent(model: Optional[Model] = None) -> AnnouncementMainAgent:
    """
    获取全局公告信息检索主Agent实例（单例）
    
    Args:
        model: 语言模型实例
        
    Returns:
        AnnouncementMainAgent: Agent实例
    """
    global _global_announcement_main_agent
    
    if _global_announcement_main_agent is None:
        _global_announcement_main_agent = AnnouncementMainAgent(model)
        await _global_announcement_main_agent._ensure_initialized()
    
    return _global_announcement_main_agent

async def process_announcement_query(user_query: str, model: Optional[Model] = None) -> str:
    """
    便捷接口：处理公告信息查询
    
    Args:
        user_query: 用户查询
        model: 语言模型实例
        
    Returns:
        str: 查询结果
    """
    agent = await get_announcement_main_agent(model)
    return await agent.process_query(user_query)

# 测试函数
async def test_announcement_main_agent():
    """测试公告信息检索主Agent"""
    print("=== 测试公告信息检索主Agent ===")
    
    test_queries = [
        "508086.SH最近有什么分红公告吗？",
        "请查询508056.SH最近一个月的重要公告信息，要求CSV格式文本",
        "508086.SH最新的分红方案具体是什么？"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n测试查询 {i}: {query}")
        try:
            result = await process_announcement_query(query)
            print(f"✅ 查询成功")
            print(f"结果: {result[:300]}..." if len(result) > 300 else f"结果: {result}")
        except Exception as e:
            print(f"❌ 查询失败: {e}")

if __name__ == "__main__":
    # 如果直接运行此文件，执行测试
    asyncio.run(test_announcement_main_agent())
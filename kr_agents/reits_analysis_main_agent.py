#!/usr/bin/env python3
"""
REITs数据分析主Agent

专业的REITs数据处理分析Agent，基于OpenAI Agents框架构建。
整合数据库查询Agent和Python执行Agent，提供完整的数据分析工作流。

核心特性：
1. 智能任务分类（简单查询 vs 复杂数据处理）
2. 内置announcement数据库中价格数据结构知识
3. 协调数据库查询Agent和Python执行Agent
4. 支持完整的数据分析工作流
"""

import sys
import os
import asyncio
from typing import Optional

# 添加路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)  # knowledge_retrieval 目录
agent_dir = os.path.dirname(parent_dir)    # agent 目录
sys.path.insert(0, agent_dir)

# 🎯 启用数据分析专用模式，避免加载检索组件
# 这样可以让REITs数据分析Agent独立运行，不会触发VectorSearcher、KeywordSearcher等检索组件的初始化
os.environ['KR_DATA_ANALYSIS_ONLY'] = 'true'
print("🔸 [ReitsAnalysisMainAgent] 已启用数据分析专用模式")

# 导入并应用Unicode处理
try:
    from knowledge_retrieval.utils.unicode_output_helper import unicode_aware_print, AgentOutputCapture, apply_comprehensive_unicode_fixes
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
    from agents.model_settings import ModelSettings
    _agents_available = True
except ImportError:
    _agents_available = False
    print("⚠️ OpenAI Agents框架不可用")
    Agent = None
    Model = None

# 导入配置和工具
from knowledge_retrieval.config.model_config import get_glm_4_5_model
from knowledge_retrieval.database.schema_provider_reitstrading import get_reitstrading_database_schema_info
from knowledge_retrieval.database.database_agent_tool_reitstrading import create_reitstrading_database_query_tool
from knowledge_retrieval.kr_agents.python_execution_agent import get_python_execution_agent
# 基金查询工具将在需要时导入


def get_reits_analysis_main_agent_instructions():
    """获取REITs数据分析主Agent的指令，包含数据库结构知识"""
    try:
        schema_info = get_reitstrading_database_schema_info()
    except ImportError:
        schema_info = """
# REITs数据库基本结构
主要表：price_data（交易数据）、index_price_data（指数行情）、product_info（基金产品信息）
        """
    
    return f"""
你是专业的公募REITs数据分析Agent，负责根据用户问题通过调用工具获得相关准确答案。（公募REITs是指中国基础设施不动产投资信托基金，数据库中的基金也仅限于上述基金范围。以下或用户提到的"基金"、"REITs"、具体基金代码等都指公募REITs产品范围，不涉及股票或其他金融产品。）

## 工具能力介绍

### 1. 智能基金分析工具(intelligent_fund_analysis)
**用途**：根据用户问题自动从announcement数据库中价格数据查询并智能匹配最相关的**基金代码**
- **注意事项**：当用户的问题明确提到了具体基金时，首先调用此工具
- 后续数据库操作需要准确的**基金代码**，而用户一般仅会提供模糊的信息,例如，不带后缀的基金代码（如508086，数据库中使用的是带后缀的基金代码）、或不完整的基金简称。
- 数据库中的基金代码均带后缀（如508086.SH），用户很可能提供不带后缀的基金代码。只要问题涉及具体基金，无论用户是否提供基金代码，均先调用本工具验证下
- 调用本工具将返回最匹配的基金信息，包含**基金代码**、基金简称以及匹配原因。
- **调用方式**：**入参字段固定为 `user_query`**，值为问题文本。例如：
intelligent_fund_analysis: arguments: {{"user_query": "查询508086基金信息"}}

### 2. 数据库查询工具(reitstrading_database_query)
**用途**：专门针对announcement数据库中价格数据的查询助手，对于每个任务可返回查询结果及SQL。可返回模式如下：
- 自然语言模式：直接返回查询结果，适用于只需要查询几个数据、或简单计算后的结果，不需要全部原始数据的情况。
- 文件导出模式（DATA_MODE: FILE_EXPORT）：将查询的结果生成CSV文件，返回CSV文件名及路径及对应的SQL语句。
- SQL生成模式（DATA_MODE: SQL_ONLY）：只返回查询的SQL及前几行数据预览，默认适用于只要求提供SQL情况。

**返回模式的选择**：
- 可要求以特定的模式返回查询结果：
- 如果只需要直接返回少量的查询结果，不需要过程数据，则选择自然语言模式，例如，“请查询哪个基金最近一个月价格（不复权）涨幅最大，返回对应的基金代码，自然语言模式。”。
- 如果需要生成CSV文件（为了直接提供给用户，或后续调用Python工具进行处理）则选择文件导出模式，例如，“请查询中证REITs全收益指数最近一年价格，生成CSV文件（DATA_MODE: FILE_EXPORT）”。 **CSV文件的查看方式**：你本身不具备查看成CSV文件文件的能力，因此如果数据库查询工具返回的是CSV文件，则需要调用Python工具进行查看或进行进一步计算。
- 如果仅需要提供准确的SQL（为了后续调用Python工具进行处理），则选择SQL生成模式，例如，“请生成查询中证REITs全收益指数最近一年价格的SQL”（DATA_MODE: SQL_ONLY）。”。
- **数据库查询工具可以进行简单计算及分析**，为了提高效率可以让数据库查询工具对查询出的数据做简单计算。但是复杂计算请选择使用文件导出模式或SQL生成获取原始数据，然后传递给Python工具进行计算。
- 首要满足返回给用户完整的数据，如果结果数据较多/基金数量较多，为了避免上下文过长以及窗口展示的显示，尽量选择文件导出模式或SQL生成模式，然后调用Python工具进行处理（如需），以便最后向用户返回完整数据的文件（csv或excel）。

**注意事项**：
1. 先根据"数据库结构信息"了解数据库内容，清楚可能用到哪些数据。需求中可以明确具体的表、字段等。
2. 不要提供SQL语句，工具会根据数据库结构自行生成
3. 要求需具体、清晰、明确
4. 降低问题复杂程度，如需多组数据请拆分成不同的子任务，单次调用最多可以传递3个任务（写成任务列表），工具将执行完所有子任务后统一返回结果。如果任务数量超过3个则请多次调用。
5. 请根据需求明确返回模式，多个子任务可以要求不同的返回模式。

- **调用方式**：**入参字段固定为 `input`**，值为需要该工具执行的任务。例如：
reitstrading_database_query: arguments: {{"input": "查询最近一年xx基金的价格数据，文件导出模式"}}

### 3. Python工具(execute_python_code)
**用途**：具备Python代码编写、执行能力，可完成复杂任务：
- 读取CSV文件内容：需传递文件路径、文件名，为了便于Python工具理解，请同时传递列名和前几行数据
- 执行SQL语句：需传递SQL语句及对应的数据结构
- 实现数据可视化（绘图、生成图表）
- 实现复杂计算和数据处理
- 生成文件（Excel、图片等）

**获取数据方式（以下均可）**：
- 直接传递具体数据：直接在要求里说明具体数据，只适用于少量数据
- 传递CSV文件名及路径：为了便于Python工具理解，请同时传递列名和前几行数据！！！
- 传递查询数据SQL语句及对应的数据结构

**注意事项**：
1. Python工具无法自行获得数据及数据库表结构，所以一定先执行数据库查询工具（获得【具体数据】或【CSV文件名及路径】或【查询数据SQL语句】），然后由你向Python工具其传递
   - 例如："请绘制基金代码为XX的最近3个月价格走势图，查询价格数据的SQL语句及数据结构是xxx"、"请将这些分红信息整理成一个excel文件，具体信息是xxx"、"请绘制中证REITs全收益指数折线图，数据的CSV文件路径是：xxx，文件名是：xxx，列名分别是：xx，前xx行数据是..."
2. 传递的要求需具体、清晰、明确
3. **效率优先**：（1）任务不要过于繁琐/难度大，以降低编码难度和执行的时间。（2）说明CSV文件的列名和前几行数据、SQL语句的数据结构等，便于Python工具理解，以避免Python工具自行探索。

- **调用方式**：**入参字段固定为 `input`**，值为需要该工具执行的任务。例如：
execute_python_code: arguments: {{"input": "绘制价格走势图，使用CSV文件：/path/to/data.csv"}}

## 执行流程

### 第一步：获取基金准确的基金代码（如需）
先用获取智能基金分析工具获取当前全部基金信息（当用户询问涉及具体基金时）

### 第二步：任务可行性评估
阅读"数据库结构信息"，大致了解数据库中信息能否完成用户的任务、哪些信息可能有用
- 如果肯定无法完成用户的问题，则直接返回"很抱歉，我无法回复您的问题。"
- 否则，继续执行

### 第三步：任务分解与执行
- 分析用户任务的复杂程度，将复杂问题拆解成各工具可单次调用执行的任务，然后按照需求**依次**调用相关工具。单次调用工具时，为了提高准确性也可将任务再进行拆分（如需）。
- **请注意**：Python工具的执行需要传递数据，所以执行Python工具之前需要先执行数据库查询工具，获取数据（具体数据、或CSV文件名及路径、或SQL语句）。
- **请注意**：你需要按照逻辑顺序依次执行各工具的调用，如果多个步骤之间存在前后依赖关系，则需要先执行前一个步骤，再执行后一个步骤。不要跳过、也不要一起执行本来需要顺序执行的步骤。
- 虽然单次调用工具可以执行多个小任务，但是不宜一次性过多，否则容易出错。可以多次调用。

**示例**：用户问题"请绘制最近一年基金涨幅最高的3只基金的价格走势图"
第一步：拆分任务，可以拆分成数据查询和画图成两个大任务，依次由数据库查询工具和Python工具执行。其中数据查询又可以拆分成两个小任务，需要先找出基金代码，然后获取基金价格数据。
第二步： 调用数据库查询工具：传递任务“1、请先找出最近一年基金涨幅最高的3只基金的基金代码。2、然后返回查询这三个基金最近一年的价格（不复权）数据的SQL语句(（DATA_MODE: SQL_ONLY）。（第2个任务也可以写成：然后将这三个基金最近一年的价格（不复权）数据，形成CSV文件（DATA_MODE: FILE_EXPORT）)”。在数据库查询工具返回准确结果后执行下一步。
第三步： 调用Python工具：请绘制XX、XX、XX这三只基金最近一年的价格走势图，获取价格数据的的SQL语句是：xx，数据结构是：xx。（或者，请绘制XX、XX、XX这三只基金最近一年的价格走势图，数据CSV文件的路径是:xx，文件名是：xx，共有xx列，列名分别是：xx，前xx行数据预览是:xx。

### 第四步：结果整合及检查
1. 最终形成答案/总结/分析回答用户。检查结果中是否包含全部的需求，不要遗漏。
2. 如果没有完成任务，则不要编造数据，返回无法执行及其原因。
3. 如果结果数据较多，不便直接文本返回全部数据。请自行形成包含完整数据的文件（csv或excel），然后返回文件路径。

## 协调原则
- **反复调用权限**：拥有反复多次调用工具的权限，可以根据需要多次调用工具。
- **任务分解**：可以将复杂问题拆分成各个工具可单次调用执行的任务，然后**依次**调用相关工具。单次调用工具时，也可将任务再进行拆分（如需）。
- **单次调用的独立性**：每次调用工具的上下文都是独立的。每次调用，工具看不到上一次调用的结果，更看不见其他工具的上下文。因此你需要合理安排调用顺序，是否要等上一次调用工具返回结果再下一次调用工具。确保每次调用工具时，工具都能获得所需的最完整的信息。
- **灵活调整**：若工具返回的结果不符合预期可以调整提问方式重新调用

## 输出原则
- 禁止在执行过程中请向用户提出问题，除非无法执行任务。
- 如果需要向用户返回文件，请直接返回文件路径（纯文本描述） ，不要返回Markdown语法，而且一个文件只返回一遍即可。(后续系统会根据文件路径处理成可下载的形式，无需你处理)

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
   intelligent_fund_analysis: arguments: {{"user_query": "查询508086基金信息"}}
   reitstrading_database_query: arguments: {{"input": "查询最近一年xx基金的价格数据，文件导出模式"}}
   execute_python_code: arguments: {{"input": "绘制价格走势图，使用CSV文件：/path/to/data.csv"}}
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

记住：你是专业的REITs数据分析Agent，要充分利用数据库结构知识，智能协调三个工具，为用户提供专业、准确、有价值的REITs数据分析服务。
    """.strip()


class ReitsAnalysisMainAgent:
    """
    REITs数据分析主Agent
    
    整合数据库查询Agent和Python执行Agent，提供完整的REITs数据分析服务。
    
    模型配置：
    - 主Agent：使用 get_glm_4_5_model 模型
    - 数据库查询Agent：使用 deepseek_v3 模型（各自默认）
    - Python执行Agent：使用 deepseek-v3 模型（各自默认）
    """
    
    def __init__(self, model: Optional[Model] = None):
        """
        初始化REITs数据分析主Agent
        
        Args:
            model: 语言模型实例，如果为None则使用默认的get_glm_4_5_model
        """
        if not _agents_available:
            raise ImportError("OpenAI Agents 未安装。请运行: pip install openai-agents")
        
        self.model = model or get_glm_4_5_model()
        self.agent = None
        self._initialized = False
        
        print("[ReitsAnalysisMainAgent] REITs数据分析主Agent初始化开始")
    
    async def _ensure_initialized(self):
        """确保Agent和工具已初始化"""
        if self._initialized:
            return
        
        print("[DEBUG] 🔄 开始初始化REITs分析主Agent...")
        
        try:
            # 创建数据库查询工具（使用database agent自己的默认模型：deepseek_v3）
            print("[DEBUG] 🔧 创建数据库查询工具...")
            db_tool = await create_reitstrading_database_query_tool()
            
            # 创建Python执行工具（使用python agent自己的默认模型：deepseek_v3）
            print("[DEBUG] 🔧 创建Python执行工具...")
            python_agent = await get_python_execution_agent()
            python_tool = python_agent.as_tool(
                tool_name="execute_python_code",
                tool_description="执行Python代码进行数据处理、分析、可视化、生产文件。支持数据库查询，需直接提供数据或CSV文件路径或数据查询SQL语句）。"
            )
            
            # 获取智能基金分析工具
            print("[DEBUG] 🔧 获取智能基金分析工具...")
            from knowledge_retrieval.business_tools.fund_query_tool_reitstrading import create_intelligent_fund_analysis_tool
            intelligent_fund_tool = await create_intelligent_fund_analysis_tool()
            
            # 创建主Agent
            print("[DEBUG] 🤖 创建REITs分析主Agent...")
            instructions = get_reits_analysis_main_agent_instructions()
            
            # 设置模型温度值
            if hasattr(self.model, 'temperature'):
                self.model.temperature = 0.0
            
            self.agent = Agent(
                name="ReitsAnalysisMainAgent",
                model=self.model,
                instructions=instructions,
                tools=[intelligent_fund_tool, db_tool, python_tool],
                model_settings=ModelSettings(
                    extra_body={"enable_thinking": False}
                ),
            )
            
            self._initialized = True
            print("[ReitsAnalysisMainAgent] Agent初始化完成")
            
        except Exception as e:
            print(f"❌ 初始化失败: {e}")
            import traceback
            traceback.print_exc()
    
    async def analyze(self, user_request: str) -> str:
        """
        分析用户请求并返回结果
        
        Args:
            user_request: 用户的分析请求
            
        Returns:
            str: 分析结果
        """
        await self._ensure_initialized()
        
        if not self._initialized:
            return "❌ Agent未正确初始化，无法提供分析服务"
        
        print(f"[ReitsAnalysisMainAgent] 开始分析用户请求: {user_request}")
        
        # 调试信息
        if os.getenv('DEBUG_MAIN_AGENT') == 'true':
            print(f"\n🎯 [主Agent] 详细调试信息:")
            print(f"   用户请求: {user_request}")
            print(f"   Agent名称: {self.agent.name}")
            print(f"   可用工具数量: {len(self.agent.tools) if hasattr(self.agent, 'tools') else 0}")
            print(f"   最大轮次: 20")
        
        try:
            from agents import Runner
            
            if os.getenv('DEBUG_MAIN_AGENT') == 'true':
                print(f"🚀 [主Agent] 启动Runner执行...")
            
            result = await Runner.run(
                self.agent, 
                user_request,
                max_turns=40  # 设置最大执行轮次为15，允许多次调用工具进行迭代优化
            )
            
            if os.getenv('DEBUG_MAIN_AGENT') == 'true':
                print(f"✅ [主Agent] Runner执行完成")
                print(f"   最终输出长度: {len(result.final_output)} 字符")
                if hasattr(result, 'raw_responses'):
                    print(f"   实际执行轮次: {len(result.raw_responses)}")
                print(f"   最终输出预览: {result.final_output[:300]}...")
            
            return result.final_output
            
        except Exception as e:
            error_msg = f"分析失败: {str(e)}"
            print(f"[ReitsAnalysisMainAgent] {error_msg}")
            return error_msg
    
    async def cleanup(self):
        """清理资源"""
        # 这里可以添加任何需要清理的资源
        print("[ReitsAnalysisMainAgent] 资源清理完成")


# 全局实例管理
_global_reits_agent = None

async def get_reits_analysis_main_agent(model: Optional[Model] = None) -> ReitsAnalysisMainAgent:
    """
    获取全局REITs分析主Agent实例（单例）
    
    Args:
        model: 语言模型实例
        
    Returns:
        ReitsAnalysisMainAgent: Agent实例
    """
    global _global_reits_agent
    
    if _global_reits_agent is None:
        _global_reits_agent = ReitsAnalysisMainAgent(model)
        await _global_reits_agent._ensure_initialized()
    
    return _global_reits_agent


async def analyze_reits_data(user_request: str, model: Optional[Model] = None) -> str:
    """
    REITs数据分析的便捷接口
    
    Args:
        user_request: 用户的分析请求
        model: 语言模型实例
        
    Returns:
        str: 分析结果
        
    Example:
        ```python
        # 简单查询分析
        result = await analyze_reits_data("最近涨幅最大的5只基金有哪些？")
        
        # 复杂数据处理
        result = await analyze_reits_data("帮我绘制501018基金最近3个月的价格走势图")
        
        print(result)
        ```
    """
    agent = await get_reits_analysis_main_agent(model)
    return await agent.analyze(user_request)


async def cleanup_reits_analysis_service():
    """清理全局REITs分析服务资源"""
    global _global_reits_agent
    
    if _global_reits_agent:
        await _global_reits_agent.cleanup()
        _global_reits_agent = None
        print("全局REITs分析服务已清理")


# ==================== Agent工厂函数 ====================

class ReitsAgentFactory:
    """
    REITs Agent工厂类
    
    提供统一的Agent创建、配置和管理接口，整合所有工具Agent
    """
    
    def __init__(self, model: Optional[Model] = None, max_turns: int = 40):
        """
        初始化REITs Agent工厂
        
        Args:
            model: 语言模型实例
            max_turns: 最大执行轮次
        """
        self.model = model or get_glm_4_5_model()
        self.max_turns = max_turns
        self._created_agents = {}
        self._tools_cache = {}
        
        print(f"[ReitsAgentFactory] REITs Agent工厂初始化完成 (max_turns={max_turns})")
    
    async def create_database_tool(self):
        """创建数据库查询工具（使用database agent默认模型）"""
        if "database_tool" not in self._tools_cache:
            print("[ReitsAgentFactory] 创建数据库查询工具...")
            self._tools_cache["database_tool"] = await create_reitstrading_database_query_tool()
        return self._tools_cache["database_tool"]
    
    async def create_python_tool(self):
        """创建Python执行工具（使用python agent默认模型）"""
        if "python_tool" not in self._tools_cache:
            print("[ReitsAgentFactory] 创建Python执行工具...")
            python_agent = await get_python_execution_agent()
            self._tools_cache["python_tool"] = python_agent.as_tool(
                tool_name="execute_python_code",
                tool_description="执行Python代码进行数据处理、分析、可视化、生产文件。支持数据库查询，需直接提供数据或CSV文件路径或数据查询SQL语句）。"
            )
        return self._tools_cache["python_tool"]
    
    async def create_fund_query_tool(self):
        """创建智能基金分析工具"""
        if "fund_query_tool" not in self._tools_cache:
            print("[ReitsAgentFactory] 创建智能基金分析工具...")
            from knowledge_retrieval.business_tools.fund_query_tool_reitstrading import create_intelligent_fund_analysis_tool
            self._tools_cache["fund_query_tool"] = await create_intelligent_fund_analysis_tool()
        return self._tools_cache["fund_query_tool"]
    
    async def create_main_agent(self, custom_instructions: Optional[str] = None) -> ReitsAnalysisMainAgent:
        """
        创建REITs分析主Agent
        
        Args:
            custom_instructions: 自定义指令（可选）
            
        Returns:
            REITs分析主Agent实例
        """
        agent_key = "main_agent"
        
        if agent_key not in self._created_agents:
            print("[ReitsAgentFactory] 创建REITs分析主Agent...")
            
            # 创建所有工具
            db_tool = await self.create_database_tool()
            python_tool = await self.create_python_tool()
            fund_tool = await self.create_fund_query_tool()
            
            # 使用自定义指令或默认指令
            instructions = custom_instructions or get_reits_analysis_main_agent_instructions()
            
            # 直接创建Agent实例
            if not _agents_available:
                raise ImportError("OpenAI Agents 未安装。请运行: pip install openai-agents")
            
            # 设置模型温度值
            if hasattr(self.model, 'temperature'):
                self.model.temperature = 0.0
            
            agent = Agent(
                name="ReitsAnalysisMainAgent",
                model=self.model,
                instructions=instructions,
                tools=[fund_tool, db_tool, python_tool],
                model_settings=ModelSettings(
                    extra_body={"enable_thinking": False}
                ),
            )
            
            # 包装为ReitsAnalysisMainAgent类
            main_agent = ReitsAnalysisMainAgent(self.model)
            main_agent.agent = agent
            main_agent._initialized = True
            
            self._created_agents[agent_key] = main_agent
            print("[ReitsAgentFactory] REITs分析主Agent创建完成")
        
        return self._created_agents[agent_key]
    
    async def create_custom_agent(
        self, 
        name: str,
        instructions: str,
        include_database: bool = True,
        include_python: bool = True,
        include_fund_query: bool = True,
        custom_tools: Optional[list] = None
    ) -> Agent:
        """
        创建自定义Agent
        
        Args:
            name: Agent名称
            instructions: Agent指令
            include_database: 是否包含数据库工具
            include_python: 是否包含Python工具
            include_fund_query: 是否包含基金查询工具
            custom_tools: 自定义工具列表
            
        Returns:
            自定义Agent实例
        """
        if not _agents_available:
            raise ImportError("OpenAI Agents 未安装。请运行: pip install openai-agents")
        
        print(f"[ReitsAgentFactory] 创建自定义Agent: {name}")
        
        tools = []
        
        # 添加标准工具（每个工具使用各自的默认模型）
        if include_fund_query:
            tools.append(await self.create_fund_query_tool())
        
        if include_database:
            tools.append(await self.create_database_tool())
        
        if include_python:
            tools.append(await self.create_python_tool())
        
        # 添加自定义工具
        if custom_tools:
            tools.extend(custom_tools)
        
        # 设置模型温度值为0.1
        if hasattr(self.model, 'temperature'):
            self.model.temperature = 0.0
        
        agent = Agent(
            name=name,
            model=self.model,
            instructions=instructions,
            tools=tools,
            model_settings=ModelSettings(
                extra_body={"enable_thinking": False}
            ),
        )
        
        agent_key = f"custom_{name}"
        self._created_agents[agent_key] = agent
        
        print(f"[ReitsAgentFactory] 自定义Agent '{name}' 创建完成，包含 {len(tools)} 个工具")
        return agent
    
    async def run_analysis(
        self, 
        user_request: str, 
        agent: Optional[ReitsAnalysisMainAgent] = None
    ) -> str:
        """
        运行REITs数据分析
        
        Args:
            user_request: 用户分析请求
            agent: Agent实例（可选，如果为None则使用主Agent）
            
        Returns:
            分析结果
        """
        if agent is None:
            agent = await self.create_main_agent()
        
        print(f"[ReitsAgentFactory] 开始分析任务 (max_turns={self.max_turns})")
        print(f"[ReitsAgentFactory] 用户请求: {user_request}")
        
        try:
            # 如果是ReitsAnalysisMainAgent，使用其analyze方法
            if hasattr(agent, 'analyze'):
                result = await agent.analyze(user_request)
            else:
                # 直接使用Runner运行
                from agents import Runner
                result = await Runner.run(
                    agent, 
                    user_request,
                    max_turns=self.max_turns
                )
                result = result.final_output if hasattr(result, 'final_output') else str(result)
            
            print("[ReitsAgentFactory] 分析任务完成")
            return result
            
        except Exception as e:
            error_msg = f"分析任务执行失败: {str(e)}"
            print(f"[ReitsAgentFactory] {error_msg}")
            return error_msg
    
    async def cleanup(self):
        """清理所有创建的Agent和工具资源"""
        print("[ReitsAgentFactory] 开始清理资源...")
        
        # 清理创建的Agent
        for agent_key, agent in self._created_agents.items():
            try:
                if hasattr(agent, 'cleanup'):
                    await agent.cleanup()
                print(f"[ReitsAgentFactory] Agent '{agent_key}' 清理完成")
            except Exception as e:
                print(f"[ReitsAgentFactory] Agent '{agent_key}' 清理失败: {e}")
        
        self._created_agents.clear()
        self._tools_cache.clear()
        
        print("[ReitsAgentFactory] 所有资源清理完成")


# ==================== 便捷工厂函数 ====================

async def create_reits_agent_factory(
    model: Optional[Model] = None, 
    max_turns: int = 40
) -> ReitsAgentFactory:
    """
    创建REITs Agent工厂的便捷接口
    
    Args:
        model: 语言模型实例
        max_turns: 最大执行轮次
        
    Returns:
        REITs Agent工厂实例
    """
    return ReitsAgentFactory(model, max_turns)


async def quick_reits_analysis(
    user_request: str, 
    model: Optional[Model] = None,
    max_turns: int = 40
) -> str:
    """
    快速REITs数据分析接口，自动创建和管理Agent
    
    Args:
        user_request: 用户分析请求
        model: 语言模型实例
        max_turns: 最大执行轮次
        
    Returns:
        分析结果
        
    Example:
        ```python
        # 快速分析
        result = await quick_reits_analysis("分析最近表现最好的5只REITs基金")
        print(result)
        
        # 使用自定义模型和轮次
        result = await quick_reits_analysis(
            "帮我绘制501018基金的走势图", 
            model=my_model,
            max_turns=30
        )
        print(result)
        ```
    """
    factory = await create_reits_agent_factory(model, max_turns)
    
    try:
        result = await factory.run_analysis(user_request)
        return result
    finally:
        await factory.cleanup()


async def create_multi_agent_system(
    model: Optional[Model] = None,
    max_turns: int = 40
) -> tuple[ReitsAgentFactory, ReitsAnalysisMainAgent]:
    """
    创建完整的多Agent系统
    
    Args:
        model: 语言模型实例
        max_turns: 最大执行轮次
        
    Returns:
        tuple: (Agent工厂实例, 主Agent实例)
        
    Example:
        ```python
        # 创建多Agent系统
        factory, main_agent = await create_multi_agent_system()
        
        # 使用主Agent进行分析
        result1 = await factory.run_analysis("查询基金信息", main_agent)
        
        # 创建自定义Agent
        custom_agent = await factory.create_custom_agent(
            name="SpecialAnalyst",
            instructions="你是专门的REITs风险分析专家..."
        )
        
        # 使用自定义Agent
        result2 = await factory.run_analysis("分析风险", custom_agent)
        
        # 清理资源
        await factory.cleanup()
        ```
    """
    factory = await create_reits_agent_factory(model, max_turns)
    main_agent = await factory.create_main_agent()
    
    return factory, main_agent


# 测试函数
async def test_reits_analysis_main_agent():
    """测试REITs分析主Agent的功能"""
    print("🧪 测试REITs分析主Agent")
    print("=" * 80)
    
    test_cases = [
        {
            "description": "📋 测试1: 基金识别功能测试",
            "request": "计算180101最近20个交易日的价格涨幅和波动率"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{test_case['description']}")
        print("-" * 60)
        print(f"📝 请求: {test_case['request']}")
        print("-" * 60)
        
        try:
            result = await analyze_reits_data(test_case['request'])
            print(f"✅ 测试{i}完成")
            print(f"📊 分析结果:")
            print(result)
            
        except Exception as e:
            print(f"❌ 测试{i}失败: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n" + "=" * 80)
    
    print("\n🎉 REITs分析主Agent测试完成！")


async def test_reits_agent_factory():
    """测试REITs Agent工厂的功能"""
    print("🧪 测试REITs Agent工厂")
    print("=" * 80)
    
    try:
        # 测试1: 快速分析接口
        print("\n📋 测试1: 快速分析接口")
        print("-" * 60)
        result = await quick_reits_analysis("请告诉我目前有哪些REITs基金？", max_turns=40)
        print("✅ 快速分析测试完成")
        print(f"📊 分析结果预览: {result[:200]}...")
        
        # 测试2: 工厂创建和管理
        print("\n📋 测试2: 工厂创建和管理")
        print("-" * 60)
        factory = await create_reits_agent_factory(max_turns=40)
        
        # 创建主Agent
        main_agent = await factory.create_main_agent()
        print("✅ 主Agent创建成功")
        
        # 使用工厂运行分析
        result = await factory.run_analysis("最近涨幅最大的基金有哪些？", main_agent)
        print("✅ 工厂分析测试完成")
        print(f"📊 分析结果预览: {result[:200]}...")
        
        # 测试3: 自定义Agent创建
        print("\n📋 测试3: 自定义Agent创建")
        print("-" * 60)
        custom_agent = await factory.create_custom_agent(
            name="SimpleQueryAgent",
            instructions="你是专门的基金查询助手，只负责查询基金信息。",
            include_python=False  # 不包含Python工具
        )
        print("✅ 自定义Agent创建成功")
        
        # 测试4: 多Agent系统
        print("\n📋 测试4: 多Agent系统")
        print("-" * 60)
        system_factory, system_main_agent = await create_multi_agent_system(max_turns=40)
        result = await system_factory.run_analysis("查询基金代码", system_main_agent)
        print("✅ 多Agent系统测试完成")
        print(f"📊 分析结果预览: {result[:200]}...")
        
        # 清理资源
        await factory.cleanup()
        await system_factory.cleanup()
        
        print("\n🎉 REITs Agent工厂测试完成！")
        
    except Exception as e:
        print(f"❌ 工厂测试失败: {e}")
        import traceback
        traceback.print_exc()


# 导出接口
__all__ = [
    # 原有接口
    'ReitsAnalysisMainAgent',
    'get_reits_analysis_main_agent',
    'analyze_reits_data',
    'cleanup_reits_analysis_service',
    'test_reits_analysis_main_agent',
    
    # 工厂接口
    'ReitsAgentFactory',
    'create_reits_agent_factory',
    'quick_reits_analysis',
    'create_multi_agent_system',
    'test_reits_agent_factory'
]

if __name__ == "__main__":
    asyncio.run(test_reits_analysis_main_agent())
# business_tools/fund_query_tool_announcement.py
"""
announcement基金查询智能Agent工具 - 基于OpenAI Agents框架（函数工具封装版）

这是一个Agent as Tool，具备智能分析用户问题并匹配最相关基金的能力。
连接announcement数据库，内置deepseek_chat_model

核心功能：
1. 执行数据库查询获取所有基金信息
2. 使用LLM智能分析用户问题
3. 匹配最相关的基金信息
4. 返回自然语言结果
"""

import sys
import os
import json
import asyncio
from typing import List, Dict, Any, Optional

# 添加路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(current_dir)
sys.path.insert(0, parent_dir)

# 导入并应用Unicode处理
try:
    from utils.unicode_output_helper import unicode_aware_print, AgentOutputCapture, apply_comprehensive_unicode_fixes
    # 应用全面Unicode修复（仅执行一次）
    if not hasattr(apply_comprehensive_unicode_fixes, '_fund_query_applied'):
        apply_comprehensive_unicode_fixes()
        apply_comprehensive_unicode_fixes._fund_query_applied = True
    # 替换print为Unicode感知版本
    print = unicode_aware_print
except ImportError:
    # 如果导入失败，定义备用函数
    def unicode_aware_print(*args, **kwargs):
        __builtins__['print'](*args, **kwargs)
    print = unicode_aware_print

# 导入OpenAI Agents框架
try:
    from agents import Agent, function_tool
    from agents.models.interface import Model
    _agents_available = True
except ImportError:
    _agents_available = False
    print("⚠️ OpenAI Agents框架不可用")
    
    # 创建模拟装饰器用于开发测试
    def function_tool(func):
        return func
    
    class Agent:
        def __init__(self, *args, **kwargs):
            pass
        def as_tool(self, **kwargs):
            return None

# 导入数据库连接器和模型配置
try:
    from .database_connector import get_database_connector
except ImportError:
    # 当直接运行此文件时，使用绝对导入
    from database_connector import get_database_connector

from config.model_config import get_deepseek_chat_model


class FundQueryAgent:
    """
    基金查询智能Agent
    
    集成数据库查询和LLM分析能力，智能匹配用户问题中的基金信息
    """
    
    def __init__(self, model: Optional[Model] = None):
        """
        初始化基金查询Agent
        
        Args:
            model: LLM模型实例，默认使用deepseek_chat_model
        """
        self.db_connector = get_database_connector()
        self.model = model or get_deepseek_chat_model()
        self.agent = None
        self._fund_cache = None
        self._cache_timestamp = None
        
        print("[FundQueryAgent] 基金查询智能Agent初始化开始")
        
        # 统一温度，提升确定性
        try:
            if hasattr(self.model, "temperature"):
                self.model.temperature = 0.0
        except Exception:
            pass
        
        # 初始化Agent
        if _agents_available and self.model:
            self._initialize_agent()
        
        print("[FundQueryAgent] 基金查询智能Agent初始化完成")
    
    def _initialize_agent(self):
        """初始化内部Agent"""
        instructions = """
你是专业的基金信息分析专家。你的任务是根据用户问题，从提供的基金信息中找出用户问题涉及的基金所对应的最匹配的基金信息。

## 工作流程：
1. **分析用户问题**：理解用户想要查询的具体基金
2. **关键词提取**：提取基金代码、简称等关键词
3. **智能匹配**：在基金数据中找出最相关的基金代码
4. **结果整理**：用自然语言返回基金的详细信息

## 匹配策略：
- **精确匹配**：优先匹配完全相同的基金代码或简称，以及不含后缀的基金代码匹配，如"508089"可匹配"508089.SH"
- **模糊匹配**：支持基金简称关键词匹配，如"中关村"可匹配"建信中关村REIT"；如“华夏特变电工”可匹配“华夏特变电工新能源REIT”
- **智能推理**：根据用户描述的特征推断可能的基金
- **多候选返回**：如果答案就一个但是有多个可能匹配结果，则返回最相关的一个

## 返回格式：
请用自然语言返回匹配的基金信息，如涉及多个基金请用列表返回，每个基金的内容包含：
- fund_code
- short_name 
- 选择的原因

## 注意事项：
- 如果用户问题模糊，尽量匹配最相关的基金
- 如果确实找不到匹配的基金，请明确说明
- 保持回答简洁清晰，重点突出基金的关键信息
"""
        
        self.agent = Agent(
            name="FundQueryAgent",
            model=self.model,
            instructions=instructions
        )
        
        print("[FundQueryAgent] 内部分析Agent创建完成")
    
    def _get_all_funds_from_database(self) -> Dict[str, Any]:
        """从数据库获取所有基金信息（带缓存）"""
        import time
        current_time = time.time()
        
        # 如果缓存存在且未过期（1小时），直接返回缓存
        if (self._fund_cache is not None and 
            self._cache_timestamp is not None and 
            current_time - self._cache_timestamp < 3600):
            print("[FundQueryAgent] 使用缓存的基金数据")
            return self._fund_cache
        
        print("[FundQueryAgent] 开始查询数据库获取基金信息")
        
        try:
            # 执行SQL查询
            sql = "SELECT fund_code, short_name FROM product_info"
            results = self.db_connector.execute_query(sql, database="announcement")
            
            # 过滤掉包含None值的记录，确保数据完整性
            if results:
                filtered_results = []
                for fund in results:
                    if (fund.get('fund_code') is not None and 
                        fund.get('short_name') is not None):
                        filtered_results.append(fund)
                
                print(f"[FundQueryAgent] 原始查询结果: {len(results)} 只基金")
                print(f"[FundQueryAgent] 过滤后有效基金: {len(filtered_results)} 只基金")
                results = filtered_results
            
            result_data = {
                "success": True,
                "data": results,
                "count": len(results),
                "message": f"查询成功，共找到 {len(results)} 只基金"
            }
            
            # 更新缓存
            self._fund_cache = result_data
            self._cache_timestamp = current_time
            
            print(f"[FundQueryAgent] 基金信息已缓存，共 {len(results)} 只基金")
            
            return result_data
            
        except Exception as e:
            error_msg = f"查询基金信息失败: {str(e)}"
            print(f"[FundQueryAgent] {error_msg}")
            
            return {
                "success": False,
                "data": [],
                "count": 0,
                "error": error_msg
            }
    
    async def analyze_fund_query(self, user_task: str) -> str:
        """
        分析用户问题并返回匹配的基金信息
        
        Args:
            user_task: 用户的查询任务（包含问题和要求）
            
        Returns:
            str: 自然语言形式的基金信息分析结果
        """
        # 入参校验与关键日志
        if not isinstance(user_task, str) or not user_task.strip():
            raise ValueError("[FundQueryAgent] 无效的参数：user_task 必须为非空字符串")
        print(f"[FundQueryAgent] analyze_fund_query() 接收到的 user_task: {user_task[:200]}{'...' if len(user_task) > 200 else ''}")

        print(f"[FundQueryAgent] 开始分析用户任务: {user_task}")
        
        # 获取所有基金数据
        funds_result = self._get_all_funds_from_database()
        
        if not funds_result["success"]:
            return f"抱歉，无法获取基金数据：{funds_result.get('error', '未知错误')}"
        
        funds_data = funds_result["data"]
        print(f"[FundQueryAgent] 获取到 {len(funds_data)} 只基金数据，开始智能分析")
        
        # 如果没有可用的LLM，直接返回所有基金信息
        if not _agents_available or not self.model or not self.agent:
            print("[FundQueryAgent] _agents_available/model/agent 不可用，进入降级返回")
            return self._return_all_funds_with_fallback_message(funds_data)
        
        try:
            # 构建分析提示
            analysis_prompt = f"""
用户任务：{user_task}

基金数据总数：{len(funds_data)} 只基金

完整基金数据：
{json.dumps(funds_data, ensure_ascii=False, indent=2)}

请根据用户任务，分析用户想要查询的具体基金，并从以上 {len(funds_data)} 只基金中找出最匹配的基金信息。
"""
            
            # 调用内部Agent进行分析
            from agents import Runner
            
            result = await Runner.run(
                self.agent,
                analysis_prompt,
                max_turns=3
            )
            
            analysis_result = result.final_output
            print(f"[FundQueryAgent] LLM分析完成，结果长度: {len(analysis_result)} 字符")
            
            return analysis_result
            
        except Exception as e:
            error_msg = f"智能分析失败: {str(e)}"
            print(f"[FundQueryAgent] {error_msg}")
            
            # 降级到返回所有基金信息
            return self._return_all_funds_with_fallback_message(funds_data)
    
    def _return_all_funds_with_fallback_message(self, funds_data: List[Dict]) -> str:
        """
        返回所有基金信息的降级方法（当LLM不可用时使用）
        
        Args:
            funds_data: 基金数据列表
            
        Returns:
            str: 带有降级提示的所有基金信息
        """
        print("[FundQueryAgent] 使用降级模式，返回所有基金信息")
        
        fallback_message = "智能匹配工具出现异常，以下是全部基金的信息，供你参考找出目标基金"
        
        if not funds_data:
            return f"{fallback_message}\n\n抱歉，未能获取到任何基金数据。"
        
        return f"{fallback_message}\n\n当前系统中共有 {len(funds_data)} 只基金：\n\n{json.dumps(funds_data, ensure_ascii=False, indent=2)}"


# 全局Agent实例管理
_global_fund_agent = None

async def get_fund_query_agent(model: Optional[Model] = None) -> FundQueryAgent:
    """
    获取全局基金查询Agent实例（单例）
    
    Args:
        model: LLM模型实例
        
    Returns:
        FundQueryAgent: Agent实例
    """
    global _global_fund_agent
    
    if _global_fund_agent is None:
        _global_fund_agent = FundQueryAgent(model)
    
    return _global_fund_agent


# 兼容旧接口的函数工具（保持向后兼容）
def get_all_fund_codes() -> Dict[str, Any]:
    """
    获取所有基金的代码和基本信息（兼容旧接口）
    
    这是原来的接口，现在返回结构化数据。
    为了完全利用新的Agent功能，建议主Agent使用新的智能工具。
    
    Returns:
        Dict[str, Any]: 包含基金信息列表和状态的字典
    """
    print("[get_all_fund_codes] 使用兼容接口获取基金信息")
    
    # 创建临时的基金查询实例
    temp_agent = FundQueryAgent()
    result = temp_agent._get_all_funds_from_database()
    
    return result


# 为主Agent提供的智能基金分析工具
async def create_intelligent_fund_analysis_tool(model: Optional[Model] = None):
    """
    创建智能基金分析**函数工具**，供主Agent调用。
    正确做法：对外暴露函数工具（function_tool），内部完整执行
    “查库 → 构造提示 → LLM 分析”的流程。
    
    Args:
        model: LLM模型实例（可选）
    Returns:
        function tool: 可被主Agent调用的函数工具
    """
    # 获取基金查询Agent（内部含温度设定）
    fund_agent = await get_fund_query_agent(model)

    # 若 Agents 框架缺失或内部 Agent 不可用：降级为直接返回全集的函数工具
    if (not _agents_available) or (not fund_agent.agent):
        print("⚠️ OpenAI Agents 框架/内部Agent不可用，返回降级函数工具（full list）")

        @function_tool
        async def intelligent_fund_analysis(user_query: str) -> str:
            """
            智能基金分析工具（降级）：忽略智能匹配，直接返回全部基金信息。
            入参:
              - user_query: 用户自然语言问题
            """
            if not isinstance(user_query, str) or not user_query.strip():
                raise ValueError("[intelligent_fund_analysis] 无效的参数：user_query 必须为非空字符串")
            print(f"[intelligent_fund_analysis:degraded] 收到 user_query: {user_query[:120]}{'...' if len(user_query)>120 else ''}")
            return await fallback_fund_query(user_query)

        intelligent_fund_analysis.__name__ = "intelligent_fund_analysis"
        intelligent_fund_analysis.__doc__ = "根据用户问题从 announcement 匹配基金（降级模式：返回全部基金信息）。参数字段为 user_query。"
        print("[create_intelligent_fund_analysis_tool] 已创建降级函数工具 intelligent_fund_analysis")
        return intelligent_fund_analysis

    # ✅ 标准路径：暴露函数工具，内部调用 analyze_fund_query()
    @function_tool
    async def intelligent_fund_analysis(user_query: str) -> str:
        """
        智能基金分析工具：根据用户问题从 announcement 数据库查询并智能匹配最相关的基金信息，
        返回基金代码、简称、全称、资产类型和匹配原因。支持模糊匹配与智能推理。
        入参:
          - user_query: 用户自然语言问题（必须）
        """
        if not isinstance(user_query, str) or not user_query.strip():
            raise ValueError("[intelligent_fund_analysis] 无效的参数：user_query 必须为非空字符串")
        print(f"[intelligent_fund_analysis] 收到 user_query: {user_query[:200]}{'...' if len(user_query)>200 else ''}")
        return await fund_agent.analyze_fund_query(user_query)

    # 显式命名与说明（部分框架会读取）
    intelligent_fund_analysis.__name__ = "intelligent_fund_analysis"
    intelligent_fund_analysis.__doc__ = (
        "根据用户问题从 announcement 匹配基金。参数字段固定为 user_query；"
        "内部会自动查询基金全集并让 LLM 做匹配与说明。"
    )
    print("[create_intelligent_fund_analysis_tool] 智能基金分析函数工具创建完成")
    return intelligent_fund_analysis


# 异步版本的智能基金查询接口
async def intelligent_fund_query(user_task: str, model: Optional[Model] = None) -> str:
    """
    智能基金查询接口
    
    Args:
        user_task: 用户的查询任务
        model: LLM模型实例（可选）
        
    Returns:
        str: 自然语言形式的查询结果
    """
    fund_agent = await get_fund_query_agent(model)
    return await fund_agent.analyze_fund_query(user_task)


# 降级版本的基金查询接口（当Agent工具创建失败时使用）
async def fallback_fund_query(user_task: str) -> str:
    """
    降级版本的基金查询接口，直接返回所有基金信息
    
    Args:
        user_task: 用户的查询任务（忽略，直接返回所有基金）
        
    Returns:
        str: 带有降级提示的所有基金信息
    """
    print("[fallback_fund_query] 使用降级查询模式")
    
    # 创建临时的基金查询实例
    temp_agent = FundQueryAgent()
    funds_result = temp_agent._get_all_funds_from_database()
    
    if not funds_result["success"]:
        return f"智能匹配工具出现异常，同时无法获取基金数据：{funds_result.get('error', '未知错误')}"
    
    funds_data = funds_result["data"]
    return temp_agent._return_all_funds_with_fallback_message(funds_data)


# 测试函数
async def test_fund_query_agent():
    """测试基金查询Agent的功能"""
    print("=== 测试基金查询智能Agent ===")
    
    # 测试1: 智能查询
    print("\n1. 测试智能查询...")
    test_queries = [
        "180301.SZ最新的收盘价是？"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n测试查询 {i}: {query}")
        try:
            result = await intelligent_fund_query(query)
            print(f"✅ 查询成功")
            print(f"结果: {result[:200]}..." if len(result) > 200 else f"结果: {result}")
        except Exception as e:
            print(f"❌ 查询失败: {e}")
    
    # 测试2: 兼容性接口
    print("\n2. 测试兼容性接口...")
    try:
        # 直接创建Agent实例来测试数据库查询功能
        temp_agent = FundQueryAgent()
        result = temp_agent._get_all_funds_from_database()
        print(f"✅ 兼容性接口测试成功，获取 {result['count']} 只基金")
    except Exception as e:
        print(f"❌ 兼容性接口测试失败: {e}")


if __name__ == "__main__":
    # 如果直接运行此文件，执行测试
    asyncio.run(test_fund_query_agent())
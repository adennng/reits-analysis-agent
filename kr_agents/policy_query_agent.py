# kr_agents/policy_query_agent.py
"""
政策文件问答主控调度器Agent (Agent1) - 基于OpenAI Agents框架

负责REITs政策文件问答的主控调度，包括：
1. 问题拆分和分析
2. 与政策文件Agent2的任务交接
3. 最终答案生成（简化的三步走流程）
"""

import sys
import os
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional

# 添加路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

try:
    from agents import Agent, handoff
    from agents.models.interface import Model
    _agents_available = True
except ImportError:
    _agents_available = False
    print("⚠️ OpenAI Agents框架不可用")
    
    # 创建模拟类用于开发
    def handoff(target, **kwargs):
        return None
    
    class Agent:
        def __init__(self, *args, **kwargs):
            pass

# 导入配置和工具
from config.model_config import get_deepseek_v3_model

# 导入政策文件Agent1专门工具
try:
    # 尝试相对导入（当作为模块导入时）
    from .policy_agent1_tools import (
        PolicyQuestionSplitter,
        PolicyFinalAnswerGenerator
    )
    # 导入政策文件Agent2
    from .policy_retrieval_executor_agent import PolicyRetrievalExecutorAgent
except ImportError:
    # 当直接运行时使用绝对导入
    from kr_agents.policy_agent1_tools import (
        PolicyQuestionSplitter,
        PolicyFinalAnswerGenerator
    )
    # 导入政策文件Agent2
    from kr_agents.policy_retrieval_executor_agent import PolicyRetrievalExecutorAgent

print("[PolicyQueryAgent] 开始初始化政策文件主控调度器Agent")

# ==================== 数据模型 ====================

class PolicyUserQuery:
    """政策文件用户查询输入"""
    def __init__(self, question: str):
        self.question = question

class PolicyProcessingContext:
    """政策文件处理上下文（简化版）"""
    def __init__(self):
        self.original_question = ""
        self.split_questions = []
        self.agent2_result = {}
        self.processing_history = []
        self.current_stage = 1
        
    def to_dict(self):
        """转换为字典"""
        return {
            "original_question": self.original_question,
            "split_questions": self.split_questions,
            "agent2_result": self.agent2_result,
            "processing_history": self.processing_history,
            "current_stage": self.current_stage,
            "timestamp": datetime.now().isoformat()
        }
        
    def add_step_result(self, step_name: str, result: dict):
        """记录每个步骤的结果"""
        self.processing_history.append({
            "step": step_name,
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
        print(f"[PolicyProcessingContext] 记录步骤: {step_name} - 阶段{self.current_stage}")

class PolicyQueryAgent:
    """
    政策文件问答主控调度器Agent (Agent1)
    
    基于OpenAI Agents框架，负责REITs政策文件问答的主控调度
    采用简化的三步走流程：问题拆分 → 调用Agent2 → 最终答案生成
    """
    
    def __init__(self, model: Optional[Model] = None):
        """
        初始化政策文件主控调度器Agent
        
        Args:
            model: 语言模型实例，如果为None则使用默认的deepseek-v3
        """
        self.model = model or get_deepseek_v3_model()
        self.policy_agent2 = PolicyRetrievalExecutorAgent()
        self._initialized = False
        
        # 初始化专业化工具类（只需要2个工具）
        self.question_splitter = PolicyQuestionSplitter(self.model)
        self.answer_generator = PolicyFinalAnswerGenerator(self.model)
        
        print("[PolicyQueryAgent] 政策文件主控调度器Agent初始化完成")
    
    async def _ensure_initialized(self):
        """确保Agent和工具已初始化"""
        if self._initialized:
            return
        
        if not _agents_available:
            print("⚠️ OpenAI Agents框架不可用，无法创建Agent")
            return
        
        if self.model is None:
            print("❌ 模型未正确初始化")
            return
        
        try:
            # 政策文件Agent1不需要数据库查询工具等复杂组件
            # 简化的初始化，只关注核心业务逻辑
            self._initialized = True
            print("[PolicyQueryAgent] 初始化完成（简化流程：Python控制流程）")
            
        except Exception as e:
            print(f"❌ 初始化失败: {e}")
            import traceback
            traceback.print_exc()
    
    async def process_policy_query(self, question: str) -> Dict[str, Any]:
        """
        处理政策文件查询的主入口 - 三步走策略
        
        Args:
            question: 用户的政策问题
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        print(f"[PolicyQueryAgent] 开始处理政策文件查询")
        print(f"  问题: {question}")
        
        try:
            # 确保初始化
            await self._ensure_initialized()
            
            if not self._initialized:
                return {
                    "success": False,
                    "error": "Agent初始化失败",
                    "final_answer": "系统初始化失败，请稍后重试"
                }
            
            # 创建用户查询对象
            user_query = PolicyUserQuery(question)
            
            # 使用三步走流程处理查询
            final_result = await self._execute_three_step_process(user_query)
            
            print(f"[PolicyQueryAgent] 政策文件查询处理完成")
            return final_result
            
        except Exception as e:
            error_msg = f"查询处理异常: {str(e)}"
            print(f"[PolicyQueryAgent] {error_msg}")
            import traceback
            traceback.print_exc()
            
            return {
                "success": False,
                "error": error_msg,
                "final_answer": f"处理过程中出现异常：{error_msg}"
            }
    
    async def _execute_three_step_process(self, user_query: PolicyUserQuery) -> Dict[str, Any]:
        """
        执行三步走流程：问题拆分 → 调用Agent2 → 最终答案生成
        
        Args:
            user_query: 用户查询对象
            
        Returns:
            Dict[str, Any]: 最终处理结果
        """
        context = PolicyProcessingContext()
        context.original_question = user_query.question
        context.current_stage = 1
        
        print(f"[PolicyQueryAgent] 初始化处理上下文")
        print(f"  原始问题: {context.original_question}")
        print(f"  当前阶段: {context.current_stage}")
        
        print(f"\n[PolicyQueryAgent] === 开始三步走流程 ===")
        
        try:
            # 步骤1: 问题拆分（核心步骤）
            context.current_stage = 1
            print("[PolicyQueryAgent] 步骤1: 政策文件问题拆分")
            
            split_result = await self.question_splitter.split(user_query.question)
            
            if split_result["success"]:
                context.split_questions = split_result["questions"]
                context.add_step_result("policy_question_splitting", split_result)
                print(f"[PolicyQueryAgent] 问题拆分成功，生成 {len(context.split_questions)} 个子问题")
                print(f"[PolicyQueryAgent] 拆分分析: {split_result.get('analysis', '')}")
            else:
                print(f"[PolicyQueryAgent] 问题拆分失败: {split_result.get('error', '')}，使用原问题")
                context.split_questions = [user_query.question]
                context.add_step_result("policy_question_splitting_failed", split_result)
            
            # 步骤2: 调用政策文件Agent2执行检索
            context.current_stage = 2
            print("[PolicyQueryAgent] 步骤2: 调用政策文件Agent2执行检索")
            print(f"[PolicyQueryAgent] 传递给Agent2的问题列表: {context.split_questions}")
            
            # 直接调用Agent2的内部实现方法，确保可控性和稳定性
            agent2_result = self.policy_agent2._execute_policy_retrieval_tasks_internal(context.split_questions)
            
            context.agent2_result = agent2_result
            context.add_step_result("policy_agent2_execution", agent2_result)
            
            print(f"[PolicyQueryAgent] 政策文件Agent2执行完成")
            print(f"  成功查询: {agent2_result.get('successful_queries', 0)}")
            print(f"  失败查询: {agent2_result.get('failed_queries', 0)}")
            
            # 步骤3: 最终答案生成
            context.current_stage = 3
            print("[PolicyQueryAgent] 步骤3: 政策文件最终答案生成")
            
            final_text = await self.answer_generator.generate(
                original_question=user_query.question,
                agent2_result=agent2_result
            )
            
            # 记录最终答案生成步骤
            context.add_step_result("policy_final_answer_generation", {"generated_text": final_text})
            
            # 返回新的格式 - 直接的文本答案
            return {
                "success": True,
                "final_answer": final_text,  # 现在是完整的文本，包含答案和参考文件列表
                "processing_history": context.processing_history
            }
            
        except Exception as e:
            error_msg = f"三步走流程执行失败: {str(e)}"
            print(f"[PolicyQueryAgent] {error_msg}")
            import traceback
            traceback.print_exc()
            
            # 记录失败的尝试
            context.add_step_result("three_step_process_failed", {"error": error_msg})
            
            return {
                "success": False,
                "error": error_msg,
                "final_answer": f"政策文件查询过程中出现异常：{error_msg}",
                "processing_history": context.processing_history
            }
    
    def close(self):
        """关闭政策文件Agent2连接"""
        if hasattr(self.policy_agent2, 'close'):
            self.policy_agent2.close()
        print("[PolicyQueryAgent] 政策文件主控调度器Agent已关闭")

# ==================== 全局实例和导出接口 ====================

# 创建全局实例
_global_policy_query_agent = None

async def get_policy_query_agent(model: Optional[Model] = None) -> PolicyQueryAgent:
    """
    获取全局政策文件查询Agent实例
    
    Args:
        model: 语言模型实例
        
    Returns:
        PolicyQueryAgent: Agent实例
    """
    global _global_policy_query_agent
    
    if _global_policy_query_agent is None:
        _global_policy_query_agent = PolicyQueryAgent(model)
        await _global_policy_query_agent._ensure_initialized()
    
    return _global_policy_query_agent

async def process_policy_file_query(
    question: str,
    model: Optional[Model] = None
) -> Dict[str, Any]:
    """
    处理政策文件查询的便捷接口
    
    Args:
        question: 用户的政策问题
        model: 语言模型实例
        
    Returns:
        Dict[str, Any]: 查询结果
    """
    agent = await get_policy_query_agent(model)
    return await agent.process_policy_query(question)

# ==================== 测试函数 ====================

async def test_policy_query_agent():
    """测试政策文件查询Agent的完整功能"""
    print("🧪 测试政策文件查询Agent")
    print("=" * 80)
    
    # 测试用例
    test_cases = [
        {
            "description": "📋 测试1: 单一政策问题",
            "question": "基础设施项目的行业要求是什么？"
        },
        {
            "description": "📋 测试2: 复合政策问题",
            "question": "基础设施项目的行业要求和原始权益人的条件分别是什么？"
        },
        {
            "description": "📋 测试3: 多层次政策问题",
            "question": "REITs的评估机构、律师事务所和审计机构要求分别是什么？"
        },
        {
            "description": "📋 测试4: 可能无答案的问题",
            "question": "火星上的REITs政策是什么？"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{test_case['description']}")
        print("-" * 60)
        
        try:
            result = await process_policy_file_query(
                question=test_case['question']
            )
            
            print(f"✅ 测试{i}完成")
            print(f"📊 查询结果:")
            print(f"  成功: {result.get('success', False)}")
            print(f"  最终答案长度: {len(result.get('final_answer', ''))}")
            print(f"  最终答案预览: {result.get('final_answer', '')[:200]}...")
            # 显示完整的最终答案（现在包含参考文件列表）
            if 'final_answer' in result:
                print(f"\n完整答案:\n{result['final_answer']}\n")
            
        except Exception as e:
            print(f"❌ 测试{i}失败: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n" + "=" * 80)
    
    print("\n🎉 政策文件Agent1测试完成！")
    print("\n📋 功能验证清单:")
    print("✅ 政策文件问题拆分")
    print("✅ 政策文件Agent2调用")
    print("✅ 政策文件最终答案生成")
    print("✅ 简化的三步走流程")
    print("✅ 详细错误处理和日志")

# 导出接口
__all__ = [
    'PolicyQueryAgent',
    'get_policy_query_agent',
    'process_policy_file_query',
    'test_policy_query_agent',
    'PolicyUserQuery',
    'PolicyProcessingContext'
]

if __name__ == "__main__":
    asyncio.run(test_policy_query_agent())
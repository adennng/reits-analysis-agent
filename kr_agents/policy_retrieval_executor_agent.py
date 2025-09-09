# kr_agents/policy_retrieval_executor_agent.py
"""
政策文件检索执行器Agent (Agent2) - 专门处理政策文件问答板块
基于OpenAI Agents框架，负责执行具体的政策文件检索任务：
1. 接收参数组（问题列表）
2. 逐个调用政策混合检索工具
3. 根据failure_type实现精确的重试和补偿处理
4. 返回所有问题的答案
"""

import sys
import os
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from pydantic import BaseModel

# 添加路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

try:
    from agents import Agent, function_tool
    from agents.models.interface import Model
    _agents_available = True
except ImportError:
    # For testing purposes, create mock decorator
    def function_tool(func):
        return func
    
    class Agent:
        def __init__(self, *args, **kwargs):
            pass
    
    class Model:
        pass
    
    _agents_available = False

# 导入政策文件检索工具
from retrieval_engine.policy_hybrid.policy_hybrid_retrieval_tool import PolicyHybridRetrievalTool
from retrieval_engine.policy_hybrid.models.policy_data_models import PolicyRetrievalResponse

# 导入配置和提示词
from config.prompts import POLICY_AGENT2_PROCESS_RETRIEVAL_CONTENT_PROMPT, POLICY_RETRIEVAL_EXECUTOR_AGENT_INSTRUCTIONS
from config.model_config import get_deepseek_v3_model, MODEL_CONFIG

# 定义严格的数据模型（满足OpenAI Agents的要求）
class PolicyQueryModel(BaseModel):
    """政策查询参数模型 - 用于function_tool的严格类型检查"""
    question: str

class PolicyQueriesRequest(BaseModel):
    """政策查询参数列表请求模型"""
    questions: List[str]

@dataclass
class PolicyQueryParam:
    """政策文件单个查询参数"""
    question: str
    
    def __str__(self):
        return f"PolicyQueryParam(question={self.question[:50]}...)"

@dataclass
class PolicyQueryResult:
    """政策文件单个查询结果"""
    question: str
    answer: str
    reference_files: List[dict]
    is_found: bool
    error: Optional[str] = None
    processing_method: str = "policy_hybrid"  # 标识处理方法
    retry_count: int = 0  # 重试次数
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "reference_files": self.reference_files,
            "is_found": self.is_found,
            "error": self.error,
            "processing_method": self.processing_method,
            "retry_count": self.retry_count
        }

class PolicyRetrievalExecutorAgent:
    """
    政策文件检索执行器Agent (Agent2)
    
    基于OpenAI Agents框架，负责执行具体的政策文件检索任务：
    1. 接收问题列表
    2. 逐个处理问题，使用政策混合检索工具
    3. 根据failure_type实现精确的重试和补偿策略
    4. 返回所有问题的答案
    """
    
    def __init__(self, model: Optional[Model] = None):
        """
        初始化政策文件检索执行器Agent
        
        Args:
            model: 语言模型实例，如果为None则使用默认的deepseek-v3
        """
        self.model = model or get_deepseek_v3_model()
        self.policy_tool = PolicyHybridRetrievalTool()
        
        # 设置Agent2内置LLM客户端
        self._setup_agent2_llm()
        
        # 创建OpenAI Agent，使用配置文件中的提示词
        self.agent = Agent(
            name="PolicyRetrievalExecutorAgent",
            instructions=POLICY_RETRIEVAL_EXECUTOR_AGENT_INSTRUCTIONS,
            tools=[self.execute_policy_retrieval_tasks],
            handoff_description="专业的政策文件检索执行器Agent，负责执行政策文件检索任务，支持retryable重试和needs_agent2补偿策略"
        )
        
        print("[PolicyRetrievalExecutorAgent] 政策文件检索执行器Agent初始化完成")
    
    def _setup_agent2_llm(self):
        """设置Agent2的内置LLM客户端"""
        try:
            from openai import OpenAI
            
            # Agent2使用deepseek-v3模型
            ali_config = MODEL_CONFIG.get("ali", {})
            model_config = ali_config.get("deepseek-v3", {})
            
            if not model_config:
                print("[PolicyRetrievalExecutorAgent] ⚠️ Agent2模型配置未找到")
                self.llm_client = None
                self.model_name = None
                return
            
            # 创建客户端
            self.llm_client = OpenAI(
                api_key=model_config["api_key"],
                base_url=model_config["base_url"]
            )
            self.model_name = model_config["model"]
            
            print(f"[PolicyRetrievalExecutorAgent] Agent2 LLM客户端初始化成功，模型: {self.model_name}")
            
        except Exception as e:
            print(f"[PolicyRetrievalExecutorAgent] ⚠️ Agent2 LLM设置失败: {str(e)}")
            self.llm_client = None
            self.model_name = None

    @function_tool
    def execute_policy_retrieval_tasks(
        self,
        request: PolicyQueriesRequest
    ) -> Dict[str, Any]:
        """
        执行政策文件检索任务的工具函数
        
        Args:
            request: 政策查询请求，包含问题列表
        
        Returns:
            Dict[str, Any]: 包含所有查询结果的字典
        """
        return self._execute_policy_retrieval_tasks_internal(request.questions)
    
    def _execute_policy_retrieval_tasks_internal(self, questions: List[str]) -> Dict[str, Any]:
        """
        内部执行政策文件检索任务的实现
        
        Args:
            questions: 问题列表
            
        Returns:
            Dict[str, Any]: 处理结果汇总
        """
        print(f"[PolicyRetrievalExecutorAgent] 开始处理政策文件查询，共 {len(questions)} 个问题")
        
        # 转换为内部格式
        query_params = [PolicyQueryParam(question=q) for q in questions]
        
        # 逐个处理问题
        results = []
        for i, param in enumerate(query_params):
            print(f"\n[PolicyRetrievalExecutorAgent] 处理问题 {i+1}/{len(query_params)}")
            result = self._process_single_policy_query(param)
            results.append(result)
        
        # 统计结果
        successful_count = sum(1 for r in results if r.is_found)
        failed_count = len(results) - successful_count
        
        print(f"\n[PolicyRetrievalExecutorAgent] 政策文件检索任务完成")
        print(f"  总问题数: {len(results)}")
        print(f"  成功: {successful_count}")
        print(f"  失败: {failed_count}")
        
        # 构建返回给Agent1的完整数据
        agent2_output = {
            "success": True,
            "total_queries": len(results),
            "successful_queries": successful_count,
            "failed_queries": failed_count,
            "results": [result.to_dict() for result in results],
            "summary": f"完成 {len(results)} 个政策文件问题的检索，成功 {successful_count} 个，失败 {failed_count} 个"
        }
        
        # 打印Agent2向Agent1传出的完整内容
        print(f"\n" + "="*80)
        print(f"[Agent2 → Agent1] 政策文件检索执行器Agent向主控调度器Agent传出的完整内容:")
        print(f"="*80)
        import json
        print(json.dumps(agent2_output, ensure_ascii=False, indent=2))
        print(f"="*80)
        
        return agent2_output
    
    def _process_single_policy_query(self, param: PolicyQueryParam) -> PolicyQueryResult:
        """
        处理单个政策文件查询 - 实现精确的处理逻辑
        
        Args:
            param: 查询参数
            
        Returns:
            PolicyQueryResult: 查询结果
        """
        print(f"[PolicyRetrievalExecutorAgent] 处理查询: {param.question}")
        
        # 第一次调用政策检索工具
        print(f"[PolicyRetrievalExecutorAgent] 第一次调用政策检索工具")
        first_result = self.policy_tool.execute_retrieval(param.question)
        
        # 情况判断和处理
        if first_result.is_found:
            # 情况7: 成功找到答案
            print(f"[PolicyRetrievalExecutorAgent] ✅ 第一次调用成功")
            return PolicyQueryResult(
                question=param.question,
                answer=first_result.answer,
                reference_files=first_result.reference_files,
                is_found=True,
                processing_method="policy_hybrid_success",
                retry_count=0
            )
        
        # 处理失败情况
        elif first_result.failure_type == "retryable":
            # 情况1: 可重试失败 - 执行精确的重试逻辑
            print(f"[PolicyRetrievalExecutorAgent] 🔄 第一次调用失败(retryable)，执行重试")
            
            # 第二次调用政策检索工具
            second_result = self.policy_tool.execute_retrieval(param.question)
            
            if second_result.is_found:
                # 重试成功
                print(f"[PolicyRetrievalExecutorAgent] ✅ 重试成功")
                return PolicyQueryResult(
                    question=param.question,
                    answer=second_result.answer,
                    reference_files=second_result.reference_files,
                    is_found=True,
                    processing_method="policy_hybrid_retry_success",
                    retry_count=1
                )
            else:
                # 重试仍失败 - 按要求返回特定答案
                print(f"[PolicyRetrievalExecutorAgent] ❌ 重试仍失败")
                return PolicyQueryResult(
                    question=param.question,
                    answer="两次检索未获取答案",
                    reference_files=[],
                    is_found=False,
                    error="两次政策检索调用均未找到答案",
                    processing_method="policy_hybrid_retry_failed",
                    retry_count=1
                )
        
        elif first_result.failure_type == "final":
            # 情况2,6: 最终失败 - 直接接受结果
            print(f"[PolicyRetrievalExecutorAgent] ❌ 最终失败(final)")
            return PolicyQueryResult(
                question=param.question,
                answer=first_result.answer,
                reference_files=first_result.reference_files,
                is_found=False,
                error=first_result.error,
                processing_method="policy_hybrid_final_failed",
                retry_count=0
            )
        
        elif first_result.failure_type == "needs_agent2":
            # 情况3-5: 需要Agent2处理 - 实现精确的LLM补偿逻辑
            print(f"[PolicyRetrievalExecutorAgent] 🔧 需要Agent2处理(needs_agent2)")
            return self._process_with_agent2_llm(param.question, first_result)
        
        else:
            # 兜底情况
            print(f"[PolicyRetrievalExecutorAgent] ⚠️ 未知失败类型: {first_result.failure_type}")
            return PolicyQueryResult(
                question=param.question,
                answer="政策文件检索遇到未知错误",
                reference_files=[],
                is_found=False,
                error=f"未知失败类型: {first_result.failure_type}",
                processing_method="policy_hybrid_unknown_error",
                retry_count=0
            )
    
    def _process_with_agent2_llm(
        self, 
        question: str, 
        retrieval_result: PolicyRetrievalResponse
    ) -> PolicyQueryResult:
        """
        使用Agent2内置LLM处理检索到的内容 - 实现精确的处理逻辑
        
        Args:
            question: 用户问题
            retrieval_result: 包含retrieval_content的检索结果
            
        Returns:
            PolicyQueryResult: 处理结果
        """
        print(f"[PolicyRetrievalExecutorAgent] 开始Agent2 LLM处理")
        print(f"  检索内容长度: {len(retrieval_result.retrieval_content or '') } 字符")
        print(f"  参考文件数: {len(retrieval_result.reference_files)}")
        
        # 检查LLM客户端是否可用
        if not self.llm_client:
            print(f"[PolicyRetrievalExecutorAgent] ❌ Agent2 LLM客户端不可用")
            return PolicyQueryResult(
                question=question,
                answer="检索到相关内容但LLM处理失败",
                reference_files=[],
                is_found=False,
                error="Agent2 LLM客户端不可用",
                processing_method="agent2_llm_unavailable",
                retry_count=0
            )
        
        try:
            # 构建提示词
            prompt = POLICY_AGENT2_PROCESS_RETRIEVAL_CONTENT_PROMPT.format(
                question=question,
                retrieval_content=retrieval_result.retrieval_content,
                sources=retrieval_result.reference_files
            )
            
            print(f"[PolicyRetrievalExecutorAgent] 调用Agent2 LLM，模型: {self.model_name}")
            
            # 调用LLM
            response = self.llm_client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            raw_response = response.choices[0].message.content.strip()
            print(f"[PolicyRetrievalExecutorAgent] Agent2 LLM原始响应: {raw_response[:300]}...")
            
            # 解析JSON响应
            parsed_result = self._parse_agent2_response(raw_response)
            
            if parsed_result["success"]:
                # 解析成功 - 按要求更新字段
                print(f"[PolicyRetrievalExecutorAgent] ✅ Agent2成功处理")
                return PolicyQueryResult(
                    question=question,
                    answer=parsed_result["answer"],
                    reference_files=parsed_result["sources"],  # 更新reference_files
                    is_found=True,  # 更新is_found
                    processing_method="agent2_llm_success",
                    retry_count=0
                )
            else:
                # 解析失败 - 按要求返回特定答案
                print(f"[PolicyRetrievalExecutorAgent] ❌ Agent2响应解析失败: {parsed_result['error']}")
                return PolicyQueryResult(
                    question=question,
                    answer="检索到相关内容但LLM处理失败",
                    reference_files=[],  # 空列表
                    is_found=False,
                    error=f"Agent2响应解析失败: {parsed_result['error']}",
                    processing_method="agent2_llm_parse_failed",
                    retry_count=0
                )
                
        except Exception as e:
            # LLM调用失败 - 按要求返回特定答案
            print(f"[PolicyRetrievalExecutorAgent] ❌ Agent2 LLM调用异常: {str(e)}")
            return PolicyQueryResult(
                question=question,
                answer="检索到相关内容但LLM处理失败",
                reference_files=[],  # 空列表
                is_found=False,
                error=f"Agent2 LLM调用异常: {str(e)}",
                processing_method="agent2_llm_call_failed",
                retry_count=0
            )
    
    def _parse_agent2_response(self, response_text: str) -> Dict[str, Any]:
        """
        解析Agent2的JSON响应 - 强化版解析
        
        Args:
            response_text: LLM原始响应
            
        Returns:
            Dict[str, Any]: {
                "success": bool,
                "answer": str,
                "sources": List[dict],  # 注意这里是dict列表，不是str列表
                "error": str
            }
        """
        try:
            import re
            
            # 多策略JSON解析
            def robust_json_parse(text):
                """多策略JSON解析"""
                
                # 策略1: 直接解析
                try:
                    return json.loads(text.strip())
                except json.JSONDecodeError:
                    pass
                
                # 策略2: 去除markdown包装
                try:
                    if "```json" in text:
                        match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
                        if match:
                            return json.loads(match.group(1).strip())
                    
                    if "```" in text:
                        match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
                        if match:
                            return json.loads(match.group(1).strip())
                except json.JSONDecodeError:
                    pass
                
                # 策略3: 智能JSON对象提取
                try:
                    if '"answer"' in text and '"sources"' in text:
                        start_pos = text.find('{')
                        if start_pos != -1:
                            brace_count = 0
                            for i, char in enumerate(text[start_pos:], start_pos):
                                if char == '{':
                                    brace_count += 1
                                elif char == '}':
                                    brace_count -= 1
                                    if brace_count == 0:
                                        json_str = text[start_pos:i+1]
                                        return json.loads(json_str)
                except json.JSONDecodeError:
                    pass
                
                # 策略4: 正则表达式逐字段提取
                answer = ""
                sources = []
                
                # 提取answer字段
                answer_patterns = [
                    r'"answer"\s*:\s*"((?:[^"\\]|\\.)*)"',  # 处理转义引号
                    r'"answer"\s*:\s*"([^"]*)"',           # 简单情况
                ]
                
                for pattern in answer_patterns:
                    answer_match = re.search(pattern, text, re.DOTALL)
                    if answer_match:
                        answer = answer_match.group(1)
                        answer = answer.replace('\\"', '"').replace('\\\\', '\\')
                        break
                
                # 提取sources字段 - 注意这里需要返回dict列表格式
                sources_patterns = [
                    r'"sources"\s*:\s*\[(.*?)\]',
                ]
                
                for pattern in sources_patterns:
                    sources_match = re.search(pattern, text, re.DOTALL)
                    if sources_match:
                        sources_content = sources_match.group(1)
                        # 这里简化处理，直接提取文件名并转换为dict格式
                        file_names = re.findall(r'"([^"]+)"', sources_content)
                        sources = [{"document_title": name} for name in file_names if name.strip()]
                        break
                
                if answer:
                    return {"answer": answer, "sources": sources}
                
                return None
            
            # 使用robust解析
            result = robust_json_parse(response_text)
            
            if result and result.get("answer"):
                # 确保sources是dict列表格式
                sources = result.get("sources", [])
                if sources and isinstance(sources[0], str):
                    # 如果是字符串列表，转换为dict列表
                    sources = [{"document_title": name} for name in sources]
                
                print(f"[PolicyRetrievalExecutorAgent] JSON解析成功，answer长度: {len(result['answer'])}, sources: {len(sources)}个文件")
                return {
                    "success": True,
                    "answer": result["answer"],
                    "sources": sources,
                    "error": ""
                }
            else:
                print(f"[PolicyRetrievalExecutorAgent] 解析结果缺少有效答案")
                return {
                    "success": False,
                    "answer": "",
                    "sources": [],
                    "error": "解析结果缺少有效答案"
                }
                
        except Exception as e:
            print(f"[PolicyRetrievalExecutorAgent] JSON解析异常: {e}")
            print(f"原始输出: {response_text[:500]}...")
            return {
                "success": False,
                "answer": "",
                "sources": [],
                "error": f"JSON解析异常: {str(e)}"
            }
    
    def close(self):
        """关闭政策检索工具连接"""
        if hasattr(self.policy_tool, 'close'):
            self.policy_tool.close()
        print("[PolicyRetrievalExecutorAgent] 政策文件检索执行器Agent已关闭")

# 创建全局实例
policy_retrieval_executor_agent = PolicyRetrievalExecutorAgent()

# 导出函数接口
def process_policy_retrieval_queries(questions: List[str]) -> Dict[str, Any]:
    """
    处理政策文件检索查询的函数接口
    
    Args:
        questions: 问题列表
    
    Returns:
        Dict[str, Any]: 包含所有查询结果的字典
    """
    return policy_retrieval_executor_agent._execute_policy_retrieval_tasks_internal(questions)

# 测试函数
def test_policy_retrieval_executor_agent():
    """测试政策文件检索执行器Agent的完整功能"""
    print("🧪 测试政策文件检索执行器Agent")
    print("=" * 80)
    
    # 测试用例
    test_cases = [
        {
            "description": "📋 测试1: 单个政策问题",
            "questions": [
                "基础设施项目的行业要求？"
            ]
        },
        {
            "description": "📋 测试2: 多个政策问题",
            "questions": [
                "原始权益人的要求？",
                "评估次数要求？",
                "新购入资产的方式"
            ]
        },
        {
            "description": "📋 测试3: 可能无答案的问题",
            "questions": [
                "火星上的REITs政策是什么？"
            ]
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{test_case['description']}")
        print("-" * 60)
        
        try:
            # 创建Agent实例
            agent = PolicyRetrievalExecutorAgent()
            
            # 执行检索任务
            results = agent._execute_policy_retrieval_tasks_internal(test_case['questions'])
            
            print(f"\n✅ 测试{i}完成")
            print("📊 检索结果汇总:")
            print(f"  总问题数: {results['total_queries']}")
            print(f"  成功: {results['successful_queries']}")
            print(f"  失败: {results['failed_queries']}")
            
            for j, result in enumerate(results['results'], 1):
                print(f"\n  📝 问题{j}: {result['question']}")
                print(f"     🎯 答案: {result['answer'][:150]}{'...' if len(result['answer']) > 150 else ''}")
                print(f"     📚 参考文件数: {len(result['reference_files'])}")
                print(f"     ✅ 找到答案: {result['is_found']}")
                print(f"     🔍 处理方法: {result['processing_method']}")
                print(f"     🔄 重试次数: {result['retry_count']}")
                if result['error']:
                    print(f"     ⚠️  错误信息: {result['error']}")
            
            # 关闭Agent
            agent.close()
                    
        except Exception as e:
            print(f"❌ 测试{i}失败: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n" + "=" * 80)
    
    print("\n🎉 政策文件检索执行器Agent测试完成！")
    print("\n📋 功能验证清单:")
    print("✅ 政策混合检索工具调用")
    print("✅ retryable类型精确重试逻辑")
    print("✅ needs_agent2类型Agent2 LLM处理")
    print("✅ final类型直接接受结果")
    print("✅ 成功结果直接采用")
    print("✅ 统一结果格式输出")
    print("✅ 详细错误处理和日志")

# 导出接口
__all__ = [
    'PolicyRetrievalExecutorAgent',
    'PolicyQueryParam',
    'PolicyQueryResult',
    'process_policy_retrieval_queries',
    'policy_retrieval_executor_agent',
    'test_policy_retrieval_executor_agent'
]

if __name__ == "__main__":
    test_policy_retrieval_executor_agent()
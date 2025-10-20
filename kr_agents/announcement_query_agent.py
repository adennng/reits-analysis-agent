# kr_agents/announcement_query_agent.py
"""
公告信息问答主控调度器Agent (Agent1) - 自动执行全部流程，适用招募说明书查询和非招募说明书查询
招募说明书查询时，用announcement_agent_wrapper.py里的直接Python调用的方式；
非招募说明书查询时，用announcement_agent_wrapper.py里的Agent as Tool被其他Agent的LLM作为工具调用。

负责REITs公告信息问答的主控调度，包括：
1. 问题分析和基金代码识别
2. 文件范围确定和检索策略制定
3. 问题拆分和参数组织
4. 与Agent2的任务交接
5. 最终答案生成（直接处理，无重试机制）
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
# 注意：新架构不再需要ANNOUNCEMENT_QUERY_AGENT_INSTRUCTIONS
from config.model_config import get_deepseek_v3_model
from finetune.prospectus_finetune_runner import run_prospectus_finetune_session

# 导入Agent1专门工具
try:
    # 尝试相对导入（当作为模块导入时）
    from .agent1_tools import (
        FundCodeIdentifier,
        QuestionSplitter,
        FinalAnswerGenerator  # 最终答案生成专业化工具
    )
    # 导入Agent2
    from .retrieval_executor_agent import RetrievalExecutorAgent
except ImportError:
    # 当直接运行时使用绝对导入
    from kr_agents.agent1_tools import (
        FundCodeIdentifier,
        QuestionSplitter,
        FinalAnswerGenerator  # 最终答案生成专业化工具
    )
    # 导入Agent2
    from kr_agents.retrieval_executor_agent import RetrievalExecutorAgent

print("[AnnouncementQueryAgent] 开始初始化主控调度器Agent")

# ==================== 数据模型 ====================

class UserQuery:
    """用户查询输入"""
    def __init__(self, question: str, is_prospectus_query: bool = False, file_names: Optional[List[str]] = None):
        self.question = question
        self.is_prospectus_query = is_prospectus_query
        self.file_names = file_names

class ProcessingContext:
    """完整的处理上下文"""
    def __init__(self):
        self.original_question = ""
        self.is_prospectus_query = False
        self.fund_codes = []
        self.fund_mapping = {}  # 🆕 新增：基金代码和名称的映射关系
        self.file_names = []    # 🆕 新增：文件名列表（简化版）
        self.query_params = []
        self.retrieval_results = []
        self.processing_history = []
        self.current_stage = 1
        self.precomposed_answer: Optional[str] = None  # 🆕 新增：预生成答案
        
        # 兼容性字段（保持与原有代码的兼容）
        self.attempt_number = 1
        self.all_attempt_results = []
        
    def to_dict(self):
        """转换为字典，传递给LLM工具"""
        return {
            "original_question": self.original_question,
            "is_prospectus_query": self.is_prospectus_query,
            "current_fund_codes": self.fund_codes,
            "fund_mapping": self.fund_mapping,  # 🆕 包含基金映射关系
            "file_names": self.file_names,      # 🆕 包含文件名列表
            "processing_history": self.processing_history,
            "current_stage": self.current_stage,
            "precomposed_answer": self.precomposed_answer,
            "timestamp": datetime.now().isoformat()
        }
        
    def add_step_result(self, step_name: str, result: dict):
        """记录每个步骤的结果"""
        self.processing_history.append({
            "step": step_name,
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
        print(f"[ProcessingContext] 记录步骤: {step_name} - 阶段{self.current_stage}")

# 向后兼容：保持ProcessingState别名
ProcessingState = ProcessingContext

class AnnouncementQueryAgent:
    """
    公告信息问答主控调度器Agent (Agent1)
    
    基于OpenAI Agents框架，负责REITs公告信息问答的主控调度
    """
    
    def __init__(self, model: Optional[Model] = None):
        """
        初始化主控调度器Agent
        
        Args:
            model: 语言模型实例，如果为None则使用默认的deepseek-v3
        """
        self.model = model or get_deepseek_v3_model()
        self.agent2 = RetrievalExecutorAgent()
# 新架构不需要agent实例
        self._initialized = False
        
        # 初始化专业化工具类
        self.fund_identifier = FundCodeIdentifier(self.model)
        self.question_splitter = QuestionSplitter(self.model)
        self.answer_generator = FinalAnswerGenerator(self.model)  # 新增：最终答案生成工具
        
        print("[AnnouncementQueryAgent] 主控调度器Agent初始化完成")
    
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
            # 新方案：完全基于Python控制流程，不再创建Agent实例
            # 所有阶段由Python严格控制，专业化工具类负责LLM调用
            self._initialized = True
            print("[AnnouncementQueryAgent] 初始化完成（新方案：Python控制流程）")
            
        except Exception as e:
            print(f"❌ 初始化失败: {e}")
            import traceback
            traceback.print_exc()
    
    async def process_query(
        self, 
        question: str, 
        is_prospectus_query: bool = False,
        file_names: Optional[List[str]] = None
    ) -> str:
        """
        处理用户查询的主入口
        
        Args:
            question: 用户问题
            is_prospectus_query: 是否为招募说明书查询
            file_names: 上层传递的文件列表，可选
            
        Returns:
            str: 最终答案文本
        """
        print(f"[AnnouncementQueryAgent] 开始处理用户查询")
        print(f"  问题: {question}")
        print(f"  招募说明书查询: {is_prospectus_query}")
        
        try:
            # 确保初始化
            await self._ensure_initialized()
            
            if not self._initialized:
                return "系统初始化失败，请稍后重试"
            
            # 创建用户查询对象
            user_query = UserQuery(question, is_prospectus_query, file_names)
            
            # 使用单次处理机制处理查询
            final_result = await self._process_query_single_attempt(user_query)
            
            print(f"[AnnouncementQueryAgent] 查询处理完成")
            return final_result
            
        except Exception as e:
            error_msg = f"查询处理异常: {str(e)}"
            print(f"[AnnouncementQueryAgent] {error_msg}")
            import traceback
            traceback.print_exc()
            
            return f"处理过程中出现异常：{error_msg}"
    
    async def _process_query_single_attempt(self, user_query: UserQuery) -> str:
        """
        使用单次处理机制处理查询（Agent2返回结果后直接进行阶段九：最终答案生成）
        
        Args:
            user_query: 用户查询对象
            
        Returns:
            str: 最终答案文本
        """
        context = ProcessingContext()
        context.original_question = user_query.question
        context.is_prospectus_query = user_query.is_prospectus_query
        context.current_stage = 1
        context.attempt_number = 1
        
        # 设置上层传递的文件列表
        if user_query.file_names is not None:
            context.file_names = user_query.file_names.copy()  # 复制一份避免引用问题
            print(f"[AnnouncementQueryAgent] 上层传递了文件列表: {len(context.file_names)} 个文件")
        else:
            context.file_names = [None]  # 默认全库检索
            print(f"[AnnouncementQueryAgent] 未传递文件列表，设置为全库检索")
        
        print(f"[AnnouncementQueryAgent] 初始化处理上下文")
        print(f"  原始问题: {context.original_question}")
        print(f"  招募说明书查询: {context.is_prospectus_query}")
        print(f"  当前阶段: {context.current_stage}")
        
        print(f"\n[AnnouncementQueryAgent] === 开始单次处理流程 ===")
        
        try:
            # 单次尝试处理
            attempt_result = await self._single_attempt_process(user_query, context)
            context.all_attempt_results.append(attempt_result)
            context.retrieval_results.append(attempt_result)
            
            print(f"[AnnouncementQueryAgent] Agent2执行完成，直接生成最终答案")
            
        except Exception as e:
            error_msg = f"处理失败: {str(e)}"
            print(f"[AnnouncementQueryAgent] {error_msg}")
            
            # 记录失败的尝试
            failed_result = {
                "success": False,
                "error": error_msg,
                "total_queries": 0,
                "successful_queries": 0,
                "failed_queries": 0,
                "results": []
            }
            context.all_attempt_results.append(failed_result)
            context.retrieval_results.append(failed_result)
        
        # 阶段7: 最终答案生成（使用专业化FinalAnswerGenerator工具）
        context.current_stage = 7
        print("[AnnouncementQueryAgent] 阶段7: 最终答案生成")
        
        final_answer_text = await self.answer_generator.generate(
            question=user_query.question,
            all_results=context.retrieval_results,
            context=context.to_dict(),
            precomposed_answer=context.precomposed_answer
        )
        
        # 记录最终答案生成步骤
        context.add_step_result("final_answer_generation", {"final_answer": final_answer_text})
        
        return final_answer_text
    
    async def _single_attempt_process(
        self, 
        user_query: UserQuery, 
        context: ProcessingContext
    ) -> Dict[str, Any]:
        """
        单次尝试的完整处理流程
        
        Args:
            user_query: 用户查询对象
            context: 处理上下文对象
            
        Returns:
            Dict[str, Any]: 单次尝试的结果
        """
        print(f"[AnnouncementQueryAgent] 开始单次处理流程")
        
        # 阶段2: 基金代码识别
        if not context.fund_codes or context.attempt_number > 1:
            context.current_stage = 2
            print("[AnnouncementQueryAgent] 阶段2: 基金代码识别")

            # 使用新的专业化工具类
            fund_result = await self.fund_identifier.identify(
                question=user_query.question,
                context=context.to_dict()
            )
            
            if not fund_result["success"]:
                raise Exception(f"基金代码识别失败: {fund_result.get('error', '未知错误')}")
            
            context.fund_codes = fund_result["fund_codes"]
            
            # 🆕 保存基金映射关系
            context.fund_mapping = {}
            for matched_fund in fund_result.get("matched_funds", []):
                fund_code = matched_fund.get("fund_code")
                if fund_code:
                    context.fund_mapping[fund_code] = {
                        "fund_name": matched_fund.get("fund_name", ""),
                        "match_confidence": matched_fund.get("match_confidence", ""),
                        "match_reason": matched_fund.get("match_reason", "")
                    }
            
            context.add_step_result("fund_identification", fund_result)
            print(f"[AnnouncementQueryAgent] 识别到基金代码: {context.fund_codes}")
            print(f"[AnnouncementQueryAgent] 基金映射关系: {context.fund_mapping}")
            
            if not context.fund_codes:
                raise Exception("未能识别到任何基金代码")

        # 招募说明书查询改走 Finetune 流程
        if user_query.is_prospectus_query:
            print("[AnnouncementQueryAgent] 检测到招募说明书查询，启动Finetune流程")
            context.current_stage = 3
            return await self._execute_prospectus_finetune(user_query, context)

        # 阶段3: 文件范围确定
        context.current_stage = 3
        print("[AnnouncementQueryAgent] 阶段3: 文件范围确定")
        await self._determine_file_scope(user_query, context)
        
        # 阶段4: 问题拆分和参数组织  
        context.current_stage = 4
        print("[AnnouncementQueryAgent] 阶段4: 问题拆分和参数组织")
        await self._organize_query_parameters(user_query, context)
        
        # 阶段5: 调用Agent2执行检索（新方案：Python直接调用）
        context.current_stage = 5
        print("[AnnouncementQueryAgent] 阶段5: 调用Agent2执行检索（新方案直接调用）")
        
        try:
            # 新方案要求：Python直接调用Agent2现有方法，更可控，状态管理更清晰
            # 避免Handoff的复杂性和不确定性，便于错误处理和重试逻辑
            agent2_result = self.agent2._execute_retrieval_tasks_internal(context.query_params)
            
            # 阶段6: Agent2结果接收（新方案：自动接收，Python状态管理）
            context.retrieval_results.append(agent2_result)
            context.add_step_result("agent2_execution", agent2_result)
            
            print(f"[AnnouncementQueryAgent] Agent2执行完成")
            print(f"  成功查询: {agent2_result.get('successful_queries', 0)}")
            print(f"  失败查询: {agent2_result.get('failed_queries', 0)}")
            
            return agent2_result
            
        except Exception as e:
            # 新方案要求：便于错误处理和重试逻辑
            error_msg = f"Agent2调用失败: {str(e)}"
            print(f"[AnnouncementQueryAgent] {error_msg}")
            import traceback
            traceback.print_exc()
            
            error_result = {
                "success": False,
                "error": error_msg,
                "total_queries": len(context.query_params),
                "successful_queries": 0,
                "failed_queries": len(context.query_params),
                "results": []
            }
            context.retrieval_results.append(error_result)
            context.add_step_result("agent2_execution_failed", error_result)
            
            return error_result

    async def _execute_prospectus_finetune(
        self,
        user_query: UserQuery,
        context: ProcessingContext
    ) -> Dict[str, Any]:
        """使用Finetune系统执行招募说明书检索"""

        print("[AnnouncementQueryAgent] 进入Finetune招募说明书检索流程")
        formatted_codes = "、".join(context.fund_codes)
        formatted_question = (
            f"系统识别出用户问题中涉及的准确的基金代码是{formatted_codes}，"
            f"用户提问的问题是：{user_query.question}"
        )

        context.add_step_result(
            "prospectus_finetune_request",
            {
                "formatted_question": formatted_question,
                "fund_codes": context.fund_codes,
                "original_question": user_query.question,
            }
        )

        print(f"[AnnouncementQueryAgent] Finetune输入问题: {formatted_question}")

        finetune_result = run_prospectus_finetune_session(
            formatted_question,
            is_expansion=False,
        )

        success = finetune_result.get("success", False)
        error_message = finetune_result.get("error")
        raw_answer = (finetune_result.get("final_answer") or "").strip()
        source_files = [
            file_name.strip()
            for file_name in finetune_result.get("source_files", [])
            if isinstance(file_name, str) and file_name.strip()
        ]

        print(f"[AnnouncementQueryAgent] Finetune检索完成，success={success}")
        print(f"[AnnouncementQueryAgent] Finetune返回的源文件: {source_files}")

        # 处理答案
        if not raw_answer:
            raw_answer = "很抱歉，未找到相关答案。"
            success = False

        reference_lines = [f"{idx + 1}. {file_name}" for idx, file_name in enumerate(source_files)]
        if reference_lines:
            final_answer_text = raw_answer + "\n\n参考文件：\n" + "\n".join(reference_lines)
        else:
            final_answer_text = raw_answer

        context.precomposed_answer = final_answer_text
        context.file_names = source_files
        context.add_step_result(
            "prospectus_finetune_result",
            {
                "success": success,
                "error": error_message,
                "source_files": source_files,
                "final_answer": final_answer_text,
            }
        )

        result_items = []
        file_for_entry = source_files[0] if source_files else None
        for fund_code in context.fund_codes or [""]:
            result_items.append({
                "fund_code": fund_code,
                "question": user_query.question,
                "file_name": file_for_entry,
                "answer": final_answer_text,
                "sources": source_files,
                "is_found": success,
                "retrieval_method": "prospectus_finetune",
                "error": None if success else (error_message or "未找到相关答案"),
            })

        total_queries = len(result_items) if result_items else 1
        successful_queries = total_queries if success else 0
        failed_queries = 0 if success else total_queries

        attempt_result = {
            "success": success,
            "error": None if success else (error_message or "未找到相关答案"),
            "total_queries": total_queries,
            "successful_queries": successful_queries,
            "failed_queries": failed_queries,
            "results": result_items,
            "summary": (
                f"完成 {total_queries} 个招募说明书检索，成功 {successful_queries} 个，失败 {failed_queries} 个"
            )
        }

        return attempt_result

    async def _determine_file_scope(self, user_query: UserQuery, context: ProcessingContext):
        """
        确定文件检索范围 - 简化的二分支逻辑
        
        Args:
            user_query: 用户查询对象
            context: 处理上下文对象
        """
        if user_query.is_prospectus_query:
            print("[AnnouncementQueryAgent] 招募说明书查询已由Finetune流程接管，跳过文件范围确定")
            context.add_step_result(
                "file_scope_skipped_for_prospectus",
                {"reason": "handled_by_finetune", "file_names": context.file_names}
            )
            return
        else:
            # 分支B：使用上层传递的文件列表或全库检索
            print("[AnnouncementQueryAgent] 分支B: 使用上层传递的文件列表")
            if context.file_names == [None]:
                print("[AnnouncementQueryAgent] 设置为全库检索")
            else:
                print(f"[AnnouncementQueryAgent] 使用传递的文件列表: {len(context.file_names)} 个文件")
            
            # 记录步骤结果
            context.add_step_result("file_scope_provided", {"file_names": context.file_names})
    
    async def _organize_query_parameters(self, user_query: UserQuery, context: ProcessingContext):
        """
        使用专业化QuestionSplitter工具进行智能分析和组织查询参数
        
        Args:
            user_query: 用户查询对象
            context: 处理上下文对象
        """
        print("[AnnouncementQueryAgent] 开始调用专业化QuestionSplitter工具")
        print(f"  原始问题: {user_query.question}")
        print(f"  基金代码: {context.fund_codes}")
        print(f"  基金映射关系: {context.fund_mapping}")
        print(f"  文件名列表: {context.file_names}")
        print(f"  招募说明书查询: {user_query.is_prospectus_query}")
        
        try:
            # 设置当前阶段为4（问题拆分阶段）
            context.current_stage = 4
            
            # 使用专业化QuestionSplitter工具
            split_result = await self.question_splitter.split(
                question=user_query.question,
                fund_codes=context.fund_codes,
                file_names=context.file_names,
    
                context=context.to_dict()
            )
            
            if split_result["success"]:
                context.query_params = split_result["query_params"]
                context.add_step_result("question_splitting", split_result)
                print(f"[AnnouncementQueryAgent] 专业化QuestionSplitter工具成功，生成 {len(context.query_params)} 个查询参数")
                print(f"[AnnouncementQueryAgent] 拆分分析: {split_result.get('analysis', '')}") 
            else:
                print(f"[AnnouncementQueryAgent] 专业化QuestionSplitter工具失败: {split_result.get('error', '')}，使用后备逻辑")
                context.query_params = self._fallback_organize_parameters(user_query, context)
                context.add_step_result("question_splitting_fallback", {"query_params": context.query_params})
                
        except Exception as e:
            print(f"[AnnouncementQueryAgent] 专业化QuestionSplitter工具异常: {str(e)}，使用后备逻辑")
            import traceback
            traceback.print_exc()
            context.query_params = self._fallback_organize_parameters(user_query, context)
            context.add_step_result("question_splitting_error", {"error": str(e), "query_params": context.query_params})
        
        print(f"[AnnouncementQueryAgent] 最终生成查询参数组: {len(context.query_params)} 个")
        for i, param in enumerate(context.query_params, 1):
            print(f"  {i}. {param['fund_code']} - {param['question'][:50]}... - {param['file_name']}")
    
    def _fallback_organize_parameters(self, user_query: UserQuery, context: ProcessingContext) -> List[Dict[str, Any]]:
        """
        后备参数组织逻辑（当主LLM未生成时使用）
        """
        query_params = []
        
        # 为每个基金创建查询
        for fund_code in context.fund_codes:
            if context.file_names and context.file_names != [None]:
                # 有特定文件，为每个文件创建查询
                for file_name in context.file_names:
                    param = {
                        "fund_code": fund_code,
                        "question": user_query.question,
                        "file_name": file_name
                    }
                    query_params.append(param)
            else:
                # 全库检索
                param = {
                    "fund_code": fund_code,
                    "question": user_query.question,
                    "file_name": None
                }
                query_params.append(param)
        
        return query_params
    

# ==================== 全局实例和导出接口 ====================

# 注意：全局实例管理已移至 announcement_agent_wrapper.py
# 请使用 AnnouncementAgentWrapper 进行调用

# 注意：便捷调用接口已移至 announcement_agent_wrapper.py
# 请使用 AnnouncementAgentWrapper 进行调用

# ==================== 测试函数 ====================

async def test_announcement_query_agent():
    """测试公告查询Agent的完整功能"""
    print("🧪 测试公告查询Agent")
    print("=" * 80)
    
    # 测试用例
    test_cases = [
        # {
        #     "description": "📋 测试1: 普通公告信息查询",
        #     "question": "中银中外运仓储物流REIT的网下投资者配售比例是多少？",
        #     "is_prospectus_query": False
        # },
        {
            "description": "📋 测试2: 招募说明书查询",
            "question": "介绍下508036.SH周边竞品情况？",
            "is_prospectus_query": True
        },
        # {
        #     "description": "📋 测试4: 带文件列表的查询",
        #     "question": "这些文件中提到的投资策略是什么？",
        #     "is_prospectus_query": False,
        #     "file_names": ["2024-01-01_508056.SH_某基金年报.pdf", "2024-02-01_508056.SH_某基金季报.pdf"]
        # },
        # {
        #     "description": "📋 测试3: 复杂问题查询",
        #     "question": "中金普洛斯REIT的投资策略和风险控制措施分别是什么？",
        #     "is_prospectus_query": False
        # }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{test_case['description']}")
        print("-" * 60)
        
        try:
            # 直接创建Agent实例进行测试，避免循环导入
            agent = AnnouncementQueryAgent()
            final_answer_text = await agent.process_query(
                question=test_case['question'],
                is_prospectus_query=test_case['is_prospectus_query'],
                file_names=test_case.get('file_names')
            )
            
            print(f"✅ 测试{i}完成")
            print(f"📊 查询结果:")
            print(f"🔍 final_answer_text: {final_answer_text}")
            print(f"📝 final_answer_text类型: {type(final_answer_text)}")
            print(f"📏 final_answer_text长度: {len(final_answer_text) if final_answer_text else 0}")
            
            # 如果文本太长，截取显示
            if final_answer_text and len(final_answer_text) > 5000:
                print(f"📄 final_answer_text内容（前5000字符）:")
                print(final_answer_text[:5000])
                print("...")
            else:
                print(f"📄 final_answer_text完整内容:")
                print(final_answer_text)
            
        except Exception as e:
            print(f"❌ 测试{i}失败: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n" + "=" * 80)
    
    print("\n🎉 Agent1测试完成！")

# 导出接口
__all__ = [
    'AnnouncementQueryAgent',
    'test_announcement_query_agent',
    'UserQuery', 
    'ProcessingContext',
    'ProcessingState'  # 向后兼容别名
]

if __name__ == "__main__":
    asyncio.run(test_announcement_query_agent())

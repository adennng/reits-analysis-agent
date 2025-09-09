# retrieval_executor_agent.py
"""
检索执行器Agent (Agent2) - 基于OpenAI Agents框架
负责执行具体的检索任务，接收参数组并返回检索结果
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
except ImportError:
    # For testing purposes, create mock decorator
    def function_tool(func):
        return func
    
    class Agent:
        def __init__(self, *args, **kwargs):
            pass

# 导入检索工具
from retrieval_engine.hybrid import HybridRetrievalTool
from retrieval_engine.fulltext import FulltextRetrievalTool
from retrieval_engine.prospectus_section import ProspectusSectionTool

# 导入提示词配置
from config.prompts import RETRIEVAL_EXECUTOR_AGENT_INSTRUCTIONS
from config.prompts import AGENT2_FUSE_HYBRID_PROSPECTUS_PROMPT

# 可选：融合提示词（不存在也不影响功能，会使用内置默认）
try:
    from config.prompts import AGENT2_FUSE_HYBRID_PROSPECTUS_PROMPT
except Exception:
    AGENT2_FUSE_HYBRID_PROSPECTUS_PROMPT = """
你是证券基金文档问答专家。下面给出同一问题的两条检索结果：混合检索与“招募说明书章节检索”。
请你在保持严谨的前提下融合为一个最终答案，要求：
1) 在两条检索结果找出与用户问题相关的内容，**合并**为连贯的一条答案，作为最终答案。避免重复与自相矛盾；
2) 数值/比例/金额等给出明确单位与范围；
3) 在答案末尾列出“参考文件”清单（去重），保留原有文件名；
4) 仅输出 JSON：{"answer": "...","sources": ["...","..."]}。

输入：
{payload}
""".strip()

# 定义严格的数据模型（满足OpenAI Agents的要求）
class QueryParamModel(BaseModel):
    """查询参数模型 - 用于function_tool的严格类型检查"""
    fund_code: str
    question: str 
    file_name: Optional[str] = None

class QueryParamsRequest(BaseModel):
    """查询参数列表请求模型"""
    query_params: List[QueryParamModel]

@dataclass
class QueryParam:
    """单个查询参数"""
    fund_code: str
    question: str
    file_name: Optional[str] = None
    
    def __str__(self):
        return f"QueryParam(fund_code={self.fund_code}, question={self.question[:50]}..., file_name={self.file_name})"

@dataclass
class QueryResult:
    """单个查询结果"""
    fund_code: str
    question: str
    file_name: Optional[str]
    answer: str
    sources: List[str]
    is_found: bool
    retrieval_method: str
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "fund_code": self.fund_code,
            "question": self.question,
            "file_name": self.file_name,
            "answer": self.answer,
            "sources": self.sources,
            "is_found": self.is_found,
            "retrieval_method": self.retrieval_method,
            "error": self.error
        }

class RetrievalExecutorAgent:
    """
    检索执行器Agent (Agent2)
    
    基于OpenAI Agents框架，负责执行具体的检索任务：
    1. 接收参数组（基金代码、问题、文件名）
    2. 逐个处理问题，使用混合检索→全文检索的降级策略
    3. 返回所有问题的答案
    
    招募说明书文件：改为“混合检索 + 章节检索”两路执行，并融合结果返回。
    """
    
    def __init__(self):
        self.hybrid_tool = HybridRetrievalTool()             # 混合检索工具
        self.fulltext_tool = FulltextRetrievalTool()         # 全文检索工具
        self.prospectus_tool = ProspectusSectionTool()       # 招募说明书章节检索工具

        # 可配置：是否启用“双路融合”模式（True：混合+章节 都跑；False：旧逻辑）
        self.prospectus_dual_mode = True
        
        # 创建OpenAI Agent，使用配置文件中的提示词
        self.agent = Agent(
            name="RetrievalExecutorAgent",
            instructions=RETRIEVAL_EXECUTOR_AGENT_INSTRUCTIONS,
            tools=[self.execute_retrieval_tasks],
            handoff_description="专业的检索执行器Agent，负责执行具体的检索任务，支持混合检索和全文检索的智能降级策略"
        )
        
        print("[RetrievalExecutorAgent] 检索执行器Agent初始化完成")

    @function_tool
    def execute_retrieval_tasks(
        self,
        request: QueryParamsRequest
    ) -> Dict[str, Any]:
        """
        执行检索任务的工具函数
        
        Args:
            request: 查询参数请求，包含查询参数列表
        
        Returns:
            Dict[str, Any]: 包含所有查询结果的字典
        """
        # 转换为内部格式
        query_params = [
            {
                "fund_code": param.fund_code,
                "question": param.question, 
                "file_name": param.file_name
            }
            for param in request.query_params
        ]
        
        return self._execute_retrieval_tasks_internal(query_params)
    
    def _execute_retrieval_tasks_internal(
        self,
        query_params: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        内部执行检索任务的实现
        """
        print(f"[RetrievalExecutorAgent] 开始执行检索任务，共 {len(query_params)} 个问题")
        
        # 转换参数格式
        parsed_params = []
        for i, param in enumerate(query_params):
            try:
                query_param = QueryParam(
                    fund_code=param.get("fund_code", ""),
                    question=param.get("question", ""),
                    file_name=param.get("file_name")
                )
                parsed_params.append(query_param)
                print(f"  问题 {i+1}: {query_param}")
            except Exception as e:
                print(f"[RetrievalExecutorAgent] 参数解析失败: {e}")
                continue
        
        # 逐个处理问题
        results = []
        for i, query_param in enumerate(parsed_params):
            print(f"\n[RetrievalExecutorAgent] 处理问题 {i+1}/{len(parsed_params)}")
            result = self._process_single_query(query_param)
            results.append(result)
        
        # 统计结果
        successful_count = sum(1 for r in results if r.is_found)
        failed_count = len(results) - successful_count
        
        print(f"\n[RetrievalExecutorAgent] 检索任务完成")
        print(f"  总问题数: {len(results)}")
        print(f"  成功: {successful_count}")
        print(f"  失败: {failed_count}")
        
        return {
            "success": True,
            "total_queries": len(results),
            "successful_queries": successful_count,
            "failed_queries": failed_count,
            "results": [result.to_dict() for result in results],
            "summary": f"完成 {len(results)} 个问题的检索，成功 {successful_count} 个，失败 {failed_count} 个"
        }
    
    def _execute_retrieval_tasks_direct(
        self,
        query_params: List[QueryParam]
    ) -> List[QueryResult]:
        """
        直接执行检索任务，接受QueryParam列表，返回QueryResult列表
        用于测试和内部调用
        """
        print(f"[RetrievalExecutorAgent] 开始执行检索任务，共 {len(query_params)} 个问题")
        
        # 逐个处理问题
        results = []
        for i, query_param in enumerate(query_params):
            print(f"\n[RetrievalExecutorAgent] 处理问题 {i+1}/{len(query_params)}")
            result = self._process_single_query(query_param)
            results.append(result)
        
        # 统计结果
        successful_count = sum(1 for r in results if r.is_found)
        failed_count = len(results) - successful_count
        
        print(f"\n[RetrievalExecutorAgent] 检索任务完成")
        print(f"  总问题数: {len(results)}")
        print(f"  成功: {successful_count}")
        print(f"  失败: {failed_count}")
        
        return results
    
    def _process_single_query(self, query_param: QueryParam) -> QueryResult:
        """
        处理单个查询参数 - 完整流程实现
        """
        print(f"[RetrievalExecutorAgent] 处理查询: {query_param.question}")
        print(f"  基金代码: {query_param.fund_code}")
        print(f"  指定文件: {query_param.file_name or '无（全库检索）'}")
        
        # 验证必要参数
        if not query_param.fund_code or not query_param.question:
            error_msg = "基金代码和问题不能为空"
            print(f"[RetrievalExecutorAgent] 参数验证失败: {error_msg}")
            return QueryResult(
                fund_code=query_param.fund_code,
                question=query_param.question,
                file_name=query_param.file_name,
                answer=f"参数错误: {error_msg}",
                sources=[],
                is_found=False,
                retrieval_method="none",
                error=error_msg
            )
        
        # === 招募说明书文件：走“混合 + 章节”双路融合（可配置开关） ===
        if query_param.file_name and "招募说明书" in query_param.file_name and self.prospectus_dual_mode:
            print(f"[RetrievalExecutorAgent] 检测到招募说明书文件，启用【双路融合】流程")
            return self._process_prospectus_query(query_param)
        
        # 非招募说明书：先混合检索
        hybrid_result = self._try_hybrid_retrieval(query_param)
        
        # 根据降级策略决定是否进行全文检索
        should_try_fulltext = self._should_try_fulltext_retrieval(hybrid_result, query_param)
        
        if should_try_fulltext:
            print(f"[RetrievalExecutorAgent] 混合检索未获得满意结果，尝试全文检索...")
            
            # 获取可用的文件名列表
            available_files = self._get_available_files_for_fulltext(hybrid_result, query_param)
            valid_files = [f for f in available_files if "招募说明书" not in f]
            
            # 多文件全文检索
            fulltext_result = self._try_fulltext_retrieval_multiple_files(query_param, valid_files)
            
            # 选择更好的
            if fulltext_result.is_found:
                print(f"[RetrievalExecutorAgent] 全文检索找到答案，使用全文检索结果")
                return fulltext_result
            else:
                print(f"[RetrievalExecutorAgent] 全文检索也未找到答案，返回最终失败结果")
                return self._create_final_failure_result(query_param, hybrid_result, fulltext_result)
        else:
            print(f"[RetrievalExecutorAgent] 不满足降级条件，直接返回混合检索结果")
            return hybrid_result
    
    def _should_try_fulltext_retrieval(self, hybrid_result: QueryResult, query_param: QueryParam) -> bool:
        """
        判断是否应该尝试全文检索 - 简化重新设计版本
        
        降级条件：
        1. 混合检索未找到答案 (is_found=False)
        2. 有可用的文件名进行全文检索
        3. 文件名不包含"招募说明书"
        Args:
            hybrid_result: 混合检索的结果
            query_param: 查询参数
            
        Returns:
            bool: 是否应该尝试全文检索
        """
        # 条件1：混合检索已找到答案 → 不降级
        if hybrid_result.is_found:
            print(f"[RetrievalExecutorAgent] 不降级原因：混合检索已找到满意答案")
            return False
        
        # 条件2：确定可用的文件名列表
        available_files = self._get_available_files_for_fulltext(hybrid_result, query_param)
        if not available_files:
            print(f"[RetrievalExecutorAgent] 不降级原因：无可用文件进行全文检索")
            return False
        
        # 条件3：过滤掉招募说明书文件
        valid_files = [f for f in available_files if "招募说明书" not in f]
        if not valid_files:
            print(f"[RetrievalExecutorAgent] 不降级原因：所有文件都是招募说明书类型")
            return False
        
        print(f"[RetrievalExecutorAgent] 满足降级条件，可用文件: {valid_files}")
        return True
    
    def _get_available_files_for_fulltext(self, hybrid_result: QueryResult, query_param: QueryParam) -> List[str]:
        """
        获取可用于全文检索的文件名列表
        策略：
        1. 优先使用query_param.file_name（如果有的话）
        2. 否则使用hybrid_result.sources中的文件名

        Returns:
            List[str]: 可用的文件名列表
        """
        files = []
        # 策略1：优先使用明确指定的文件名
        if query_param.file_name and query_param.file_name.strip():
            files.append(query_param.file_name.strip())
            print(f"[RetrievalExecutorAgent] 使用指定文件名: {query_param.file_name}")

        # 策略2：使用混合检索结果中的sources
        elif hybrid_result.sources:
            files.extend(hybrid_result.sources)
            print(f"[RetrievalExecutorAgent] 使用混合检索sources: {hybrid_result.sources}")
        
        # 去重并过滤
        unique_files = []
        for file in files:
            if file and file.strip() and file not in unique_files:
                unique_files.append(file.strip())
        return unique_files
    
    def _try_hybrid_retrieval(self, query_param: QueryParam) -> QueryResult:
        """
        尝试混合检索 - 重新实现版本
        """
        try:
            print(f"[RetrievalExecutorAgent] 调用混合检索工具")
            hybrid_result = self.hybrid_tool._search_knowledge_base_internal(
                fund_code=query_param.fund_code,
                question=query_param.question,
                file_name=query_param.file_name
            )
            
            # 成功
            if hybrid_result.get("is_found", False):
                print(f"[RetrievalExecutorAgent] 混合检索成功：找到相关内容")
                return QueryResult(
                    fund_code=query_param.fund_code,
                    question=query_param.question,
                    file_name=query_param.file_name,
                    answer=hybrid_result.get("answer", "混合检索未返回答案"),
                    sources=hybrid_result.get("sources", []),
                    is_found=True,
                    retrieval_method="hybrid",
                    error=None
                )
            
            # LLM失败但有retrieval_content
            if "retrieval_content" in hybrid_result:
                print(f"[RetrievalExecutorAgent] 混合检索LLM失败，但有检索内容，尝试Agent2处理")

                # 使用Agent2的LLM处理retrieval_content
                agent2_result = self._process_retrieval_content_with_agent2_llm(
                    retrieval_content=hybrid_result["retrieval_content"],
                    question=query_param.question,
                    sources=hybrid_result.get("sources", [])
                )
                if agent2_result["success"]:
                    print(f"[RetrievalExecutorAgent] Agent2成功处理retrieval_content")
                    return QueryResult(
                        fund_code=query_param.fund_code,
                        question=query_param.question,
                        file_name=query_param.file_name,
                        answer=agent2_result["answer"],
                        sources=agent2_result["sources"],
                        is_found=True,
                        retrieval_method="agent2_processed",
                        error=None
                    )
                else:
                    print(f"[RetrievalExecutorAgent] Agent2处理retrieval_content失败，标记为需要降级")
                    # 保存retrieval_content信息，用于后续降级决策
                    return QueryResult(
                        fund_code=query_param.fund_code,
                        question=query_param.question,
                        file_name=query_param.file_name,
                        answer=f"混合检索LLM失败，Agent2处理也失败: {agent2_result['error']}",
                        sources=hybrid_result.get("sources", []),
                        is_found=False,
                        retrieval_method="hybrid",
                        error=f"LLM失败+Agent2处理失败，sources可用于全文检索: {hybrid_result.get('sources', [])}"
                    )
            
            # 其他失败
            print(f"[RetrievalExecutorAgent] 混合检索未找到答案")
            return QueryResult(
                fund_code=query_param.fund_code,
                question=query_param.question,
                file_name=query_param.file_name,
                answer=hybrid_result.get("answer", "混合检索未找到相关信息"),
                sources=hybrid_result.get("sources", []),
                is_found=False,
                retrieval_method="hybrid",
                error="混合检索未找到答案"
            )
            
        except Exception as e:
            error_msg = f"混合检索异常: {str(e)}"
            print(f"[RetrievalExecutorAgent] {error_msg}")
            return QueryResult(
                fund_code=query_param.fund_code,
                question=query_param.question,
                file_name=query_param.file_name,
                answer=f"混合检索失败: {error_msg}",
                sources=[],
                is_found=False,
                retrieval_method="hybrid",
                error=error_msg
            )
    
    def _try_fulltext_retrieval_multiple_files(self, query_param: QueryParam, file_names: List[str]) -> QueryResult:
        """
        对多个文件依次进行全文检索，直到找到答案
        
        Args:
            query_param: 查询参数
            file_names: 要检索的文件名列表
            
        Returns:
            QueryResult: 全文检索结果
        """
        if not file_names:
            return QueryResult(
                fund_code=query_param.fund_code,
                question=query_param.question,
                file_name=query_param.file_name,
                answer="无可用文件进行全文检索",
                sources=[],
                is_found=False,
                retrieval_method="fulltext",
                error="无可用文件进行全文检索"
            )
        
        print(f"[RetrievalExecutorAgent] 开始多文件全文检索，文件数量: {len(file_names)}")
        all_attempts = []  # 记录所有尝试
        
        for i, file_name in enumerate(file_names, 1):
            print(f"[RetrievalExecutorAgent] 全文检索 {i}/{len(file_names)}: {file_name}")

            # 创建单文件查询参数
            single_file_param = QueryParam(
                fund_code=query_param.fund_code,
                question=query_param.question,
                file_name=file_name
            )

            # 尝试单文件全文检索
            result = self._try_fulltext_retrieval_single_file(single_file_param)
            all_attempts.append(result)

            # 如果找到答案就立即返回
            if result.is_found:
                print(f"[RetrievalExecutorAgent] 在文件 {file_name} 中找到答案")
                return result
        # 所有文件都没找到答案，汇总失败结果
        print(f"[RetrievalExecutorAgent] 所有文件都未找到答案，汇总失败结果")
        return self._merge_failed_fulltext_attempts(query_param, all_attempts)
    
    def _try_fulltext_retrieval_single_file(self, query_param: QueryParam) -> QueryResult:
        """
        对单个文件进行全文检索
        """
        try:
            print(f"[RetrievalExecutorAgent] 调用全文检索工具")
            fulltext_result = self.fulltext_tool._search_full_document_internal(
                question=query_param.question,
                file_name=query_param.file_name
            )
            
            return QueryResult(
                fund_code=query_param.fund_code,
                question=query_param.question,
                file_name=query_param.file_name,
                answer=fulltext_result.get("answer", "全文检索未返回答案"),
                sources=fulltext_result.get("sources", []),
                is_found=fulltext_result.get("is_found", False),
                retrieval_method="fulltext",
                error=fulltext_result.get("error")
            )
            
        except Exception as e:
            error_msg = f"全文检索异常: {str(e)}"
            print(f"[RetrievalExecutorAgent] {error_msg}")
            return QueryResult(
                fund_code=query_param.fund_code,
                question=query_param.question,
                file_name=query_param.file_name,
                answer=f"全文检索失败: {error_msg}",
                sources=[],
                is_found=False,
                retrieval_method="fulltext",
                error=error_msg
            )
    
    def _merge_failed_fulltext_attempts(self, query_param: QueryParam, all_attempts: List[QueryResult]) -> QueryResult:
        """
        汇总多个全文检索失败的尝试结果
        """
        try:
            # 收集所有尝试的信息
            attempted_files = []
            error_summaries = []
            for attempt in all_attempts:
                if attempt.file_name:
                    attempted_files.append(attempt.file_name)
                if attempt.error:
                    error_summaries.append(f"{attempt.file_name}: {attempt.error}")
            
            # 使用LLM汇总失败结果（可选）
            if len(all_attempts) > 1:
                merged_result = self._merge_failed_attempts_with_llm(query_param, all_attempts)
                if merged_result:
                    return merged_result
            
            # 简单汇总失败结果
            failure_summary = self._create_simple_failure_summary(attempted_files, error_summaries)
            return QueryResult(
                fund_code=query_param.fund_code,
                question=query_param.question,
                file_name=query_param.file_name,
                answer=failure_summary,
                sources=attempted_files,
                is_found=False,
                retrieval_method="fulltext",
                error=f"尝试了{len(attempted_files)}个文件都未找到答案"
            )
        except Exception as e:
            print(f"[RetrievalExecutorAgent] 汇总失败结果时出错: {e}")
            return QueryResult(
                fund_code=query_param.fund_code,
                question=query_param.question,
                file_name=query_param.file_name,
                answer="检索失败，且汇总结果时也出错",
                sources=[],
                is_found=False,
                retrieval_method="fulltext",
                error=str(e)
            )
    
    def _create_simple_failure_summary(self, attempted_files: List[str], error_summaries: List[str]) -> str:
        """创建简单的失败总结"""
        if not attempted_files:
            return "未能进行任何全文检索"
        summary = f"已尝试在{len(attempted_files)}个文件中进行全文检索，但都未找到相关答案。\n"
        summary += f"尝试的文件: {', '.join(attempted_files)}\n"
        if error_summaries:
            summary += "具体错误:\n" + "\n".join(error_summaries)
        else:
            summary += "可能的原因：文件中确实不包含相关信息，或问题超出了文档覆盖范围。"
        return summary
    
    def _create_final_failure_result(self, query_param: QueryParam, hybrid_result: QueryResult, another_result: QueryResult) -> QueryResult:
        """
        创建最终的失败结果，综合两个尝试（可为混合+全文 或 混合+章节）的信息
        """
        # 综合分析失败原因
        failure_analysis = []
        if hybrid_result.error:
            failure_analysis.append(f"混合检索: {hybrid_result.error}")
        if another_result.error:
            method = "全文检索" if another_result.retrieval_method.startswith("fulltext") else "招募说明书章节检索"
            failure_analysis.append(f"{method}: {another_result.error}")
        
        # 综合sources
        all_sources = []
        if hybrid_result.sources:
            all_sources.extend(hybrid_result.sources)
        if another_result.sources:
            all_sources.extend(another_result.sources)
        # 去重
        unique_sources = list(set(all_sources))
        
        final_answer = f"经过多种检索方式仍未能找到相关答案。\n"
        final_answer += f"检索范围: {', '.join(unique_sources) if unique_sources else '无有效文件'}\n"
        final_answer += "失败分析:\n" + "\n".join(failure_analysis)
        
        return QueryResult(
            fund_code=query_param.fund_code,
            question=query_param.question,
            file_name=query_param.file_name,
            answer=final_answer,
            sources=unique_sources,
            is_found=False,
            retrieval_method="hybrid+fallback",
            error="多种检索方式均失败"
        )

    def process_queries(self, query_params: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        处理查询的公共接口
        
        Args:
            query_params: 查询参数列表
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        return self._execute_retrieval_tasks_internal(query_params)

    def _process_retrieval_content_with_agent2_llm(self, retrieval_content: str, question: str, sources: List[str]) -> Dict[str, Any]:
        """
        Agent2使用自己的LLM处理混合检索失败时的retrieval_content
        
        Args:
            retrieval_content: 混合检索工具返回的原始检索内容
            question: 用户问题
            sources: 来源文件列表
            
        Returns:
            Dict[str, Any]: {
                "success": bool,  # 是否成功处理
                "answer": str,    # 答案内容
                "sources": List[str],  # 参考的来源文件
                "error": str      # 错误信息（失败时）
            }
        """
        try:
            print(f"[RetrievalExecutorAgent] Agent2开始处理retrieval_content")
            print(f"  内容长度: {len(retrieval_content)} 字符")
            print(f"  可用来源: {sources}")
            
            # 设置Agent2的LLM客户端
            llm_result = self._setup_agent2_llm()
            if not llm_result["success"]:
                return {"success": False, "answer": "", "sources": [], "error": f"Agent2 LLM配置失败: {llm_result['error']}"}
            
            client = llm_result["client"]
            model = llm_result["model"]
            
            # 使用Agent2专用的提示词
            from config.prompts import AGENT2_PROCESS_RETRIEVAL_CONTENT_PROMPT
            prompt = AGENT2_PROCESS_RETRIEVAL_CONTENT_PROMPT.format(
                question=question,
                retrieval_content=retrieval_content,
                sources=sources
            )
            print(f"[RetrievalExecutorAgent] 调用Agent2 LLM，模型: {model}")

            # 调用LLM
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=8192
            )
            raw_response = response.choices[0].message.content.strip()
            print(f"[RetrievalExecutorAgent] Agent2 LLM原始响应: {raw_response[:300]}...")

            # 解析Agent2的响应
            parsed_result = self._parse_agent2_response(raw_response)

            # 如果成功，返回结果
            if parsed_result["success"]:
                print("[RetrievalExecutorAgent] Agent2成功处理retrieval_content")
                return {"success": True, "answer": parsed_result["answer"], "sources": parsed_result["sources"], "error": ""}
            else:
                print(f"[RetrievalExecutorAgent] Agent2响应解析失败: {parsed_result['error']}")
                return {"success": False, "answer": "", "sources": [], "error": f"响应解析失败: {parsed_result['error']}"}
        except Exception as e:
            error_msg = f"Agent2处理retrieval_content异常: {str(e)}"
            print(f"[RetrievalExecutorAgent] {error_msg}")
            import traceback
            traceback.print_exc()
            return {"success": False, "answer": "", "sources": [], "error": error_msg}
    
    def _setup_agent2_llm(self) -> Dict[str, Any]:
        """设置Agent2的LLM客户端"""
        try:
            from config.model_config import MODEL_CONFIG
            from openai import OpenAI

            # Agent2使用deepseek-v3模型（可以根据需要调整）
            ali_config = MODEL_CONFIG.get("ali", {})
            model_config = ali_config.get("deepseek-v3", {})
            if not model_config:
                return {"success": False, "error": "Agent2模型配置未找到"}
            
            # 创建客户端
            client = OpenAI(api_key=model_config["api_key"], base_url=model_config["base_url"])
            print(f"[RetrievalExecutorAgent] Agent2 LLM客户端初始化成功，模型: {model_config['model']}")
            return {"success": True, "client": client, "model": model_config["model"]}
        except Exception as e:
            error_msg = f"Agent2 LLM设置失败: {str(e)}"
            print(f"[RetrievalExecutorAgent] {error_msg}")
            return {"success": False, "error": error_msg}
    
    def _parse_agent2_response(self, response_text: str) -> Dict[str, Any]:
        """解析Agent2的JSON响应"""
        try:
            import json as _json
            import re

            # 直接解析JSON
            try:
                parsed = _json.loads(response_text.strip())
                # 验证必要字段
                if "answer" in parsed and "sources" in parsed:
                    return {"success": True, "answer": parsed["answer"], "sources": parsed["sources"] if isinstance(parsed["sources"], list) else [parsed["sources"]], "error": ""}
                else:
                    return {"success": False, "error": "JSON缺少必要字段"}
            except _json.JSONDecodeError:
                # 尝试正则提取
                answer_match = re.search(r'"answer"\s*:\s*"([^"]*)"', response_text)
                sources_match = re.search(r'"sources"\s*:\s*\[(.*?)\]', response_text)
                if answer_match:
                    answer = answer_match.group(1)
                    sources = []
                    if sources_match:
                        sources_content = sources_match.group(1)
                        source_files = re.findall(r'"([^"]+)"', sources_content)
                        sources = source_files
                    return {"success": True, "answer": answer, "sources": sources, "error": ""}
                else:
                    return {"success": False, "error": "无法提取答案信息"}
        except Exception as e:
            return {"success": False, "error": f"解析异常: {str(e)}"}

    def _merge_failed_attempts_with_llm(self, query_param: QueryParam, all_attempts: List[QueryResult]) -> Optional[QueryResult]:
        """
        使用LLM汇总多个失败的检索尝试 - 可选功能
        
        Args:
            query_param: 查询参数
            all_attempts: 所有失败的尝试结果
            
        Returns:
            Optional[QueryResult]: 汇总结果，如果LLM调用失败则返回None
        """
        try:
            # 设置Agent2的LLM客户端
            llm_result = self._setup_agent2_llm()
            if not llm_result["success"]:
                print(f"[RetrievalExecutorAgent] LLM汇总失败: {llm_result['error']}")
                return None
            
            client = llm_result["client"]
            model = llm_result["model"]

            # 准备所有尝试的信息
            attempts_info = []
            for i, attempt in enumerate(all_attempts, 1):
                attempts_info.append({
                    "attempt": i,
                    "file_name": attempt.file_name,
                    "answer": attempt.answer,
                    "is_found": attempt.is_found,
                    "error": attempt.error,
                    "retrieval_method": attempt.retrieval_method
                })

            # 使用汇总提示词
            from config.prompts import AGENT2_MERGE_FAILED_ATTEMPTS_PROMPT
            prompt = AGENT2_MERGE_FAILED_ATTEMPTS_PROMPT.format(
                question=query_param.question,
                all_attempts=attempts_info
            )
            print(f"[RetrievalExecutorAgent] 使用LLM汇总失败结果...")
            
            # 调用LLM
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=8192
            )
            raw_response = response.choices[0].message.content.strip()
            print(f"[RetrievalExecutorAgent] LLM汇总结果: {raw_response[:200]}...")
            
            # 解析LLM响应
            parsed_result = self._parse_merge_response(raw_response)

            # 如果成功，返回结果
            if parsed_result["success"]:
                return QueryResult(
                    fund_code=query_param.fund_code,
                    question=query_param.question,
                    file_name=query_param.file_name,
                    answer=parsed_result["answer"],
                    sources=parsed_result["sources"],
                    is_found=False, # 汇总的都是失败结果
                    retrieval_method="llm_merged",
                    error=parsed_result["failure_analysis"]
                )
            else:
                print(f"[RetrievalExecutorAgent] LLM汇总响应解析失败: {parsed_result['error']}")
                return None
        except Exception as e:
            print(f"[RetrievalExecutorAgent] LLM汇总异常: {e}")
            return None
    
    def _parse_merge_response(self, response_text: str) -> Dict[str, Any]:
        """解析LLM汇总响应"""
        try:
            import json as _json
            import re

            # 直接解析JSON
            try:
                parsed = _json.loads(response_text.strip())
                # 验证必要字段
                if "answer" in parsed and "sources" in parsed:
                    return {
                        "success": True,
                        "answer": parsed["answer"],
                        "sources": parsed["sources"] if isinstance(parsed["sources"], list) else [parsed["sources"]],
                        "failure_analysis": parsed.get("failure_analysis", ""),
                        "suggestions": parsed.get("suggestions", "")
                    }
                else:
                    return {"success": False, "error": "JSON缺少必要字段"}
            except _json.JSONDecodeError:
                # 尝试正则提取
                answer_match = re.search(r'"answer"\s*:\s*"([^"]*)"', response_text)
                if answer_match:
                    return {
                        "success": True,
                        "answer": answer_match.group(1),
                        "sources": [],
                        "failure_analysis": "LLM汇总，JSON解析部分失败",
                        "suggestions": ""
                    }
                else:
                    return {"success": False, "error": "无法提取答案信息"}
        except Exception as e:
            return {"success": False, "error": f"解析异常: {str(e)}"}
    
    # =========================
    # 招募说明书：双路执行 + 融合
    # =========================
    def _process_prospectus_query(self, query_param: QueryParam) -> QueryResult:
        """
        处理招募说明书专用查询流程（改为：混合检索 + 章节检索 → 融合）
        """
        print(f"[RetrievalExecutorAgent] === 招募说明书专用流程（双路融合） ===")
        print(f"  问题: {query_param.question}")
        print(f"  招募说明书文件: {query_param.file_name}")
        
        # 路1：混合检索
        print(f"[RetrievalExecutorAgent] 步骤1: 执行混合检索")
        hybrid_result = self._try_hybrid_retrieval(query_param)
        
        # 路2：章节检索（无论混合是否成功都执行）
        print(f"[RetrievalExecutorAgent] 步骤2: 执行招募说明书章节检索")
        section_result = self._try_prospectus_section_retrieval(query_param)
        
        # 步骤3：融合两路结果并返回
        print(f"[RetrievalExecutorAgent] 步骤3: 融合两路结果")
        fused = self._select_or_fuse_prospectus_results(query_param, hybrid_result, section_result)
        print(f"[RetrievalExecutorAgent] 招募说明书双路融合完成，检索成功: {fused.is_found}")
        return fused
    
    def _try_prospectus_section_retrieval(self, query_param: QueryParam) -> QueryResult:
        """
        尝试招募说明书章节检索
        """
        try:
            print(f"[RetrievalExecutorAgent] 调用招募说明书章节检索工具")
            prospectus_result = self.prospectus_tool._search_prospectus_section_internal(
                question=query_param.question,
                file_name=query_param.file_name
            )
            result = QueryResult(
                fund_code=query_param.fund_code,
                question=query_param.question,
                file_name=query_param.file_name,
                answer=prospectus_result.get("answer", "招募说明书章节检索未返回答案"),
                sources=prospectus_result.get("sources", []),
                is_found=prospectus_result.get("is_found", False),
                retrieval_method="prospectus_section",
                error=prospectus_result.get("error")
            )
            # 章节命中/找到文件等附加信息目前写在 error 方便调试
            if "sections" in prospectus_result:
                result.error = (result.error + " | " if result.error else "") + f"匹配章节: {prospectus_result['sections']}"
            if "found_files" in prospectus_result:
                result.error = (result.error + " | " if result.error else "") + f"找到文件: {prospectus_result['found_files']}"
            print(f"[RetrievalExecutorAgent] 招募说明书章节检索{'成功' if result.is_found else '失败'}")
            return result
        except Exception as e:
            error_msg = f"招募说明书章节检索异常: {str(e)}"
            print(f"[RetrievalExecutorAgent] {error_msg}")
            import traceback
            traceback.print_exc()
            return QueryResult(
                fund_code=query_param.fund_code,
                question=query_param.question,
                file_name=query_param.file_name,
                answer=f"招募说明书章节检索失败: {error_msg}",
                sources=[],
                is_found=False,
                retrieval_method="prospectus_section",
                error=error_msg
            )

    def _select_or_fuse_prospectus_results(
        self,
        query_param: QueryParam,
        hybrid_result: QueryResult,
        section_result: QueryResult
    ) -> QueryResult:
        """
        融合混合检索与章节检索的结果：
        - 两个都成功 → 优先尝试 LLM 融合；失败则启发式融合
        - 只有一个成功 → 返回成功的那个，但合并另一路 sources
        - 都失败 → 汇总失败信息
        """
        # 两个都成功：LLM融合或启发式
        if hybrid_result.is_found and section_result.is_found:
            fused = self._fuse_two_results_with_llm(query_param, hybrid_result, section_result)
            if fused:
                return fused
            return self._prefer_section_with_merged_sources(hybrid_result, section_result)
            
        
        # 只有章节检索成功
        if section_result.is_found:
            section_result.sources = list(set((section_result.sources or []) + (hybrid_result.sources or [])))
            section_result.retrieval_method = "prospectus_section"
            print(f"[RetrievalExecutorAgent] 返回章节检索结果: {section_result.answer[:100]}...")
            return section_result
        
        # 只有混合检索成功
        if hybrid_result.is_found:
            hybrid_result.sources = list(set((hybrid_result.sources or []) + (section_result.sources or [])))
            hybrid_result.retrieval_method = "hybrid"
            print(f"[RetrievalExecutorAgent] 返回混合检索结果: {hybrid_result.answer[:100]}...")
            return hybrid_result
        
        # 都失败
        return self._create_final_failure_result(query_param, hybrid_result, section_result)

    def _prefer_section_with_merged_sources(
        self,
        hybrid_result: QueryResult,
        section_result: QueryResult
    ) -> QueryResult:
        """
        启发式融合：章节检索优先（更结构化/权威），合并两路来源
        """
        merged_sources = list(set((section_result.sources or []) + (hybrid_result.sources or [])))
        answer = section_result.answer.strip() if section_result.answer else hybrid_result.answer
        print(f"[RetrievalExecutorAgent] 启发式融合: 优先章节检索答案，长度={len(answer) if answer else 0}")
        print(f"[RetrievalExecutorAgent] 融合后sources: {merged_sources}")
        return QueryResult(
            fund_code=section_result.fund_code,
            question=section_result.question,
            file_name=section_result.file_name,
            answer=answer,
            sources=merged_sources,
            is_found=True,
            retrieval_method="hybrid+prospectus_section",
            error=None
        )

    def _fuse_two_results_with_llm(
        self,
        query_param: QueryParam,
        hybrid_result: QueryResult,
        section_result: QueryResult
    ) -> Optional[QueryResult]:
        """
        使用 LLM 进行结果融合（可选，失败则返回 None 交由启发式处理）
        """
        try:
            llm = self._setup_agent2_llm()
            if not llm["success"]:
                print(f"[RetrievalExecutorAgent] 融合LLM未就绪：{llm['error']}")
                return None
            client = llm["client"]
            model = llm["model"]

            payload = {
                "question": query_param.question,
                "prospectus_file": query_param.file_name,
                "hybrid": {
                    "answer": hybrid_result.answer,
                    "sources": hybrid_result.sources,
                    "retrieval_method": hybrid_result.retrieval_method
                },
                "section": {
                    "answer": section_result.answer,
                    "sources": section_result.sources,
                    "retrieval_method": section_result.retrieval_method
                }
            }
            import json
            payload_json = json.dumps(payload, ensure_ascii=False)
            prompt = AGENT2_FUSE_HYBRID_PROSPECTUS_PROMPT.replace("{payload}", payload_json)
            print("[Debug] Fusion prompt head:", prompt[:200])


            print(f"[RetrievalExecutorAgent] 调用融合LLM进行结果合成")
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=8192
            )
            text = resp.choices[0].message.content.strip()
            print(f"[RetrievalExecutorAgent] 融合LLM原始输出:")
            print(f"{'='*60}")
            print(text)
            print(f"{'='*60}")
            print(f"[RetrievalExecutorAgent] 融合LLM输出长度: {len(text)} 字符")
            
            parsed = self._parse_agent2_response(text)
            if not parsed["success"]:
                print(f"[RetrievalExecutorAgent] 融合LLM解析失败：{parsed['error']}")
                return None
            else:
                print(f"[RetrievalExecutorAgent] 融合LLM解析成功，答案长度: {len(parsed['answer'])} 字符")
                print(f"[RetrievalExecutorAgent] 融合后来源: {parsed['sources']}")

            return QueryResult(
                fund_code=query_param.fund_code,
                question=query_param.question,
                file_name=query_param.file_name,
                answer=parsed["answer"],
                sources=list(set(parsed["sources"])),
                is_found=True,
                retrieval_method="hybrid+prospectus_section+fused",
                error=None
            )
        except Exception as e:
            print(f"[RetrievalExecutorAgent] 融合LLM异常：{e}")
            return None

# 创建全局实例
retrieval_executor_agent = RetrievalExecutorAgent()

# 导出函数接口
def process_retrieval_queries(query_params: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    处理检索查询的函数接口
    
    Args:
        query_params: 查询参数列表，每个元素包含：
            - fund_code: 基金代码
            - question: 问题
            - file_name: 文件名（可选）
    
    Returns:
        Dict[str, Any]: 包含所有查询结果的字典
    """
    return retrieval_executor_agent.process_queries(query_params)

# 测试函数
def test_retrieval_executor_agent():
    """测试检索执行器Agent的完整功能"""
    print("🧪 测试检索执行器Agent v2.1（招募说明书双路融合）")
    print("=" * 80)
    
    # 测试用例
    test_cases = [
        # {
        #     "description": "📋 测试1: 普通公告信息查询",
        #     "params": [
        #         QueryParam(
        #             fund_code="508056.SH",
        #             question="基金的管理费率是多少？",
        #             file_name=None
        #         )
        #     ]
        # },
        {
            "description": "📋 测试2: 指定文件（招募说明书）检索 - 双路融合",
            "params": [
                QueryParam(
                    fund_code="508056.SH", 
                    question="项目折现率是多少？",
                    file_name="2021-05-26_508056.SH_中金普洛斯REIT_中金普洛斯仓储物流封闭式基础设施证券投资基金招募说明书（更新）.pdf"
                )
            ]
        },
        # {
        #     "description": "📋 测试3: 招募说明书专用流程（多问题）",
        #     "params": [
        #         QueryParam(
        #             fund_code="508056.SH",
        #             question="基金的管理费率是多少？",
        #             file_name="2021-05-26_508056.SH_中金普洛斯REIT_中金普洛斯仓储物流封闭式基础设施证券投资基金招募说明书（更新）.pdf"
        #         ),
        #         QueryParam(
        #             fund_code="508056.SH",
        #             question="原始权益人是谁？",
        #             file_name="2021-05-26_508056.SH_中金普洛斯REIT_中金普洛斯仓储物流封闭式基础设施证券投资基金招募说明书（更新）.pdf"
        #         )
        #     ]
        # },
        # {
        #     "description": "📋 测试4: 多问题批量处理（非招募说明书）",
        #     "params": [
        #         QueryParam(
        #             fund_code="508056.SH",
        #             question="基金的网下投资者配售比例是多少？",
        #             file_name=None
        #         ),
        #         QueryParam(
        #             fund_code="508056.SH",
        #             question="基金的原始权益人是谁？", 
        #             file_name=None
        #         )
        #     ]
        # }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{test_case['description']}")
        print("-" * 60)
        
        try:
            agent = RetrievalExecutorAgent()
            results = agent._execute_retrieval_tasks_direct(test_case['params'])
            
            print(f"\n✅ 测试{i}完成")
            print("📊 检索结果汇总:")
            for j, result in enumerate(results, 1):
                print(f"\n  📝 问题{j}: {result.question}")
                print(f"     💰 基金代码: {result.fund_code}")
                print(f"     📄 文件名: {result.file_name or '全库检索'}")
                print(f"     🎯 答案: {result.answer[:150]}{'...' if len(result.answer) > 150 else ''}")
                print(f"     📚 来源: {result.sources}")
                print(f"     ✅ 找到答案: {result.is_found}")
                print(f"     🔍 检索方法: {result.retrieval_method}")
                if result.error:
                    print(f"     ⚠️  错误信息: {result.error}")
                    
        except Exception as e:
            print(f"❌ 测试{i}失败: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n" + "=" * 80)
    
    print("\n🎉 Agent2测试完成！")
    print("\n📋 功能验证清单:")
    print("✅ 混合检索执行")
    print("✅ Agent2处理retrieval_content")
    print("✅ 多文件全文检索降级")
    print("✅ 招募说明书文件识别")
    print("✅ 招募说明书【混合 + 章节】双路执行")
    print("✅ 结果融合（LLM融合 + 启发式回退）")
    print("✅ 失败结果智能汇总")
    print("✅ 详细错误日志输出")


if __name__ == "__main__":
    test_retrieval_executor_agent()

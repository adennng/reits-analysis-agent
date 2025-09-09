# policy_hybrid_retrieval_tool.py
"""
政策文件混合检索主工具
实现完整的政策文件混合检索流程：
1. 生成检索参数 -> 2. 混合检索 -> 3. 第一次扩展 -> 4. 相关性打分 -> 
5. 过滤4分以上语块 -> 6. 按文件分组 -> 7. 第二次扩展合并 -> 8. 统一LLM问答
"""
import sys
import os
import json
from typing import List, Dict, Optional
from openai import OpenAI

# 设置正确的Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
sys.path.insert(0, project_root)

from knowledge_retrieval.config.prompts import POLICY_UNIFIED_ANSWER_GENERATION_PROMPT
from knowledge_retrieval.config.model_config import MODEL_CONFIG
from .models.policy_data_models import PolicySearchResult, PolicyScoredResult, PolicyFileGroup, PolicyRetrievalResponse
from .tools.policy_params_generator import generate_policy_search_params
from .tools.policy_search_tools import PolicyHybridSearchTool
from .tools.policy_text_processor import PolicyTextProcessor
from .tools.policy_relevance_scorer import PolicyRelevanceScorer

class PolicyHybridRetrievalTool:
    """政策文件混合检索主工具"""
    
    def __init__(self):
        print("[PolicyHybridRetrievalTool] 正在初始化...")
        
        # 初始化各个组件
        self.hybrid_search_tool = PolicyHybridSearchTool()
        self.text_processor = PolicyTextProcessor()
        self.relevance_scorer = PolicyRelevanceScorer()
        
        # 设置LLM客户端
        self._setup_llm()
        
        print("[PolicyHybridRetrievalTool] 初始化完成")
    
    def _setup_llm(self):
        """设置LLM客户端用于最终问答"""
        try:
            llm_config = MODEL_CONFIG["ali"]["deepseek-v3"]
            self.llm_client = OpenAI(
                api_key=llm_config["api_key"],
                base_url=llm_config["base_url"]
            )
            self.model_name = llm_config["model"]
            print(f"[PolicyHybridRetrievalTool] LLM客户端设置完成: {self.model_name}")
            
        except Exception as e:
            print(f"[PolicyHybridRetrievalTool] LLM设置失败: {e}")
            self.llm_client = None
            self.model_name = None
    
    def execute_retrieval(self, question: str) -> PolicyRetrievalResponse:
        """
        执行完整的政策文件混合检索流程
        
        Args:
            question: 用户问题
            
        Returns:
            PolicyRetrievalResponse: 检索响应
        """
        print(f"[PolicyHybridRetrievalTool] 开始执行政策文件检索: {question}")
        
        # 声明用于跟踪进度的变量
        search_results = None
        scores = None
        scored_results = None
        file_groups = None
        
        try:
            # 步骤1: 生成检索参数
            search_params = generate_policy_search_params(question)
            print(f"[PolicyHybridRetrievalTool] 检索参数生成完成:")
            print(f"  向量问题: {search_params.vector_question}")
            print(f"  关键词: {search_params.keywords}")
            
            # 步骤2: 执行混合检索
            search_results = self.hybrid_search_tool.search(
                vector_question=search_params.vector_question,
                keywords=search_params.keywords
            )
            
            # 情况1: 混合检索无结果 🔄 可重试失败
            if not search_results:
                return PolicyRetrievalResponse(
                    question=question,
                    answer="混合检索未找到相关政策文件",
                    reference_files=[],
                    is_found=False,
                    error="混合检索未返回任何结果",
                    failure_type="retryable",  # Agent2可重试
                    debug_info={
                        "step": "hybrid_search", 
                        "search_params": {
                            "vector_question": search_params.vector_question,
                            "keywords": search_params.keywords
                        }
                    }
                )
            
            # 步骤3: 第一次扩展
            expanded_texts = self.text_processor.batch_first_expansion(search_results)
            
            # 步骤4: 相关性打分
            scores = self.relevance_scorer.batch_score_relevance(question, expanded_texts)
            
            # 步骤5: 过滤4分以上语块
            scored_results = []
            for result, score, expanded_text in zip(search_results, scores, expanded_texts):
                if score >= 4:  # 保留4分和5分的语块
                    scored_result = PolicyScoredResult(
                        search_result=result,
                        relevance_score=score,
                        expanded_text_initial=expanded_text,
                        expanded_text_final="",  # 第二次扩展后填入
                        from_methods=result.from_methods,
                        final_score=float(score)
                    )
                    scored_results.append(scored_result)
            
            print(f"[PolicyHybridRetrievalTool] 过滤后保留{len(scored_results)}个4分以上语块")
            
            # 情况2: 无4分以上语块 ❌ 最终失败
            if not scored_results:
                return PolicyRetrievalResponse(
                    question=question,
                    answer="根据检索的政策文件无法找到相关规定",
                    reference_files=[],
                    is_found=False,
                    error="没有找到相关性足够高的内容",
                    failure_type="final",  # 最终失败，不再处理
                    debug_info={
                        "step": "relevance_scoring", 
                        "max_score": max(scores) if scores else 0,
                        "total_results": len(search_results)
                    }
                )
            
            # 步骤6-7: 按文件分组并进行第二次扩展
            file_groups = self.text_processor.group_by_file_and_second_expansion(scored_results)
            
            # 步骤8: 统一LLM问答
            final_response = self._unified_llm_answer(question, file_groups)
            
            return final_response
            
        except Exception as e:
            print(f"[PolicyHybridRetrievalTool] 检索执行失败: {e}")
            
            # 智能异常处理：根据已完成的步骤判断失败类型
            return self._handle_exception_by_progress(
                question, e, search_results, scores, scored_results, file_groups
            )
    
    def _unified_llm_answer(self, question: str, file_groups: List[PolicyFileGroup]) -> PolicyRetrievalResponse:
        """
        统一LLM问答：将所有文件信息一起提供给LLM
        
        Args:
            question: 用户问题
            file_groups: 按文件分组的结果
            
        Returns:
            PolicyRetrievalResponse: 最终响应
        """
        print(f"[PolicyHybridRetrievalTool] 开始统一LLM问答，共{len(file_groups)}个文件")
        
        # 情况3: LLM客户端不可用 🔧 需Agent2处理
        if not self.llm_client:
            # 准备给Agent2的检索内容
            all_texts = []
            all_files = []
            for group in file_groups:
                all_texts.append(f"文件：{group.document_title}\n{group.merged_text}")
                all_files.append({
                    "document_title": group.document_title,
                    "publish_date": group.publish_date,
                    "issuing_agency": group.issuing_agency,
                    "website": group.website
                })
            
            retrieval_content = "\n\n".join(all_texts)
            
            # 🔧 为Agent2截断检索内容，避免传递过长内容
            if len(retrieval_content) > 40000:
                print(f"[PolicyHybridRetrievalTool] 传递给Agent2的内容过长({len(retrieval_content)}字符)，截断至40000字符")
                retrieval_content = retrieval_content[:40000] + "\n\n[内容因长度限制被截断...]"
            
            return PolicyRetrievalResponse(
                question=question,
                answer="检索到相关内容但LLM处理失败",
                reference_files=all_files,
                is_found=False,
                error="LLM处理失败",
                failure_type="needs_agent2",  # 需要Agent2处理
                retrieval_content=retrieval_content,  # 关键：返回截断后的检索内容
                debug_info={"step": "llm_unavailable", "files_count": len(file_groups)}
            )
        
        try:
            # 构建文件内容字符串
            file_contents_parts = []
            file_info_map = {}  # 文件名到详细信息的映射
            
            print(f"[PolicyHybridRetrievalTool] 构建LLM输入内容，文件已按发布日期排序（最新在前）")
            
            for group in file_groups:
                file_content = f"""
文件名：{group.document_title}
发布日期：{group.publish_date}
发布机构：{group.issuing_agency}
网站来源：{group.website}

文件内容：
{group.merged_text}
"""
                file_contents_parts.append(file_content)
                
                # 保存文件信息映射
                file_info_map[group.document_title] = {
                    "document_title": group.document_title,
                    "publish_date": group.publish_date,
                    "issuing_agency": group.issuing_agency,
                    "website": group.website
                }
            
            file_contents_str = "\n" + "="*50 + "\n".join(file_contents_parts)
            
            # 🔧 添加40000字符截断逻辑，避免LLM输入过长
            if len(file_contents_str) > 40000:
                print(f"[PolicyHybridRetrievalTool] 文件内容过长({len(file_contents_str)}字符)，截断至40000字符")
                file_contents_str_for_llm = file_contents_str[:40000] + "\n\n[内容因长度限制被截断...]"
            else:
                file_contents_str_for_llm = file_contents_str
            
            # 构建提示词
            prompt = POLICY_UNIFIED_ANSWER_GENERATION_PROMPT.format(
                question=question,
                file_contents=file_contents_str_for_llm
            )
            
            # 调用LLM
            response = self.llm_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0
            )
            
            llm_output = response.choices[0].message.content.strip()
            print(f"[PolicyHybridRetrievalTool] LLM原始输出: {llm_output}")
            
            # 解析LLM返回的JSON
            parsed_result = self._parse_llm_response(llm_output)
            
            # 情况5: LLM输出解析失败 🔧 需Agent2处理
            if not parsed_result:
                # 🔧 为Agent2截断检索内容，避免传递过长内容
                retrieval_content_for_agent2 = file_contents_str
                if len(retrieval_content_for_agent2) > 40000:
                    print(f"[PolicyHybridRetrievalTool] 传递给Agent2的内容过长({len(retrieval_content_for_agent2)}字符)，截断至40000字符")
                    retrieval_content_for_agent2 = retrieval_content_for_agent2[:40000] + "\n\n[内容因长度限制被截断...]"
                
                return PolicyRetrievalResponse(
                    question=question,
                    answer="检索到相关内容但LLM处理失败",
                    reference_files=list(file_info_map.values()),
                    is_found=False,
                    error="LLM处理失败",
                    failure_type="needs_agent2",  # 需要Agent2处理
                    retrieval_content=retrieval_content_for_agent2,  # 关键：返回截断后的检索内容
                    debug_info={"step": "llm_parsing_failed", "llm_raw_output": llm_output}
                )
            
            # 根据LLM返回的参考文件名，补充详细信息
            reference_files = []
            for file_name in parsed_result.get("sources", []):
                if file_name in file_info_map:
                    reference_files.append(file_info_map[file_name])
                else:
                    print(f"[PolicyHybridRetrievalTool] 警告: LLM返回的文件名 '{file_name}' 未找到对应信息")
            
            answer = parsed_result.get("answer", "")
            
            # 情况6: LLM返回"无法找到相关规定" ❌ 最终失败
            if answer == "根据检索的政策文件无法找到相关规定":
                return PolicyRetrievalResponse(
                    question=question,
                    answer=answer,
                    reference_files=[],  # final类型返回空列表
                    is_found=False,
                    error=None,  # 这不是错误，是正常的"未找到"
                    failure_type="final",  # 最终失败
                    debug_info={"step": "llm_answered", "llm_conclusion": "no_relevant_policy"}
                )
            
            # 情况7: 成功找到答案 ✅
            return PolicyRetrievalResponse(
                question=question,
                answer=answer,
                reference_files=reference_files,
                is_found=True,
                error=None,
                failure_type=None,  # 成功无失败类型
                debug_info={"step": "completed", "files_count": len(file_groups)}
            )
            
        except Exception as e:
            print(f"[PolicyHybridRetrievalTool] 统一LLM问答失败: {e}")
            
            # 情况4: LLM调用异常 🔧 需Agent2处理
            all_files = [
                {
                    "document_title": group.document_title,
                    "publish_date": group.publish_date,
                    "issuing_agency": group.issuing_agency,
                    "website": group.website
                }
                for group in file_groups
            ]
            
            # 准备给Agent2的检索内容
            file_contents_parts = []
            for group in file_groups:
                file_content = f"""
文件名：{group.document_title}
发布日期：{group.publish_date}
发布机构：{group.issuing_agency}
网站来源：{group.website}

文件内容：
{group.merged_text}
"""
                file_contents_parts.append(file_content)
            
            retrieval_content = "\n" + "="*50 + "\n".join(file_contents_parts)
            
            # 🔧 为Agent2截断检索内容，避免传递过长内容
            if len(retrieval_content) > 40000:
                print(f"[PolicyHybridRetrievalTool] 传递给Agent2的内容过长({len(retrieval_content)}字符)，截断至40000字符")
                retrieval_content = retrieval_content[:40000] + "\n\n[内容因长度限制被截断...]"
            
            return PolicyRetrievalResponse(
                question=question,
                answer="检索到相关内容但LLM处理失败",
                reference_files=all_files,
                is_found=False,
                error="LLM处理失败",
                failure_type="needs_agent2",  # 需要Agent2处理
                retrieval_content=retrieval_content,  # 关键：返回截断后的检索内容
                debug_info={"step": "llm_call_failed", "llm_error": str(e)}
            )
    
    def _parse_llm_response(self, llm_output: str) -> Optional[Dict]:
        """
        解析LLM的JSON响应，包含多种解析策略和错误恢复机制 - 增强版
        """
        import re
        import json
        
        # 多级解析逻辑 - 与其他检索工具保持一致且增强
        def robust_json_parse(response_text):
            """Robust JSON解析，包含多级fallback机制"""
            
            # 策略1: 直接解析原始输出
            try:
                return json.loads(response_text.strip())
            except json.JSONDecodeError as e:
                print(f"[PolicyHybridRetrievalTool] 直接JSON解析失败: {e}")
                pass
            
            # 策略1.5: 清理换行符后解析（精确处理JSON字符串值）
            try:
                # 更精确的换行符处理方法
                cleaned_text = response_text
                # 查找JSON对象的边界
                start_idx = cleaned_text.find('{')
                end_idx = cleaned_text.rfind('}')
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    json_part = cleaned_text[start_idx:end_idx+1]
                    
                    # 精确处理JSON字符串值中的换行符
                    def clean_json_value(match):
                        key = match.group(1)
                        value = match.group(2)
                        # 转义换行符和其他控制字符，但保留已转义的
                        value = value.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
                        return f'"{key}": "{value}"'
                    
                    # 处理JSON字符串值 - 修正正则表达式以正确匹配包含换行符的值
                    cleaned_json = re.sub(r'"([^"]+)"\s*:\s*"((?:[^"\\]|\\.)*)"', clean_json_value, json_part, flags=re.DOTALL)
                    # 将清理后的JSON重新组合
                    cleaned_text = cleaned_text[:start_idx] + cleaned_json + cleaned_text[end_idx+1:]
                
                return json.loads(cleaned_text.strip())
            except json.JSONDecodeError as e:
                print(f"[PolicyHybridRetrievalTool] 换行符清理后JSON解析失败: {e}")
                pass
            
            # 策略2: 去除markdown包装
            try:
                # 处理```json包装
                if "```json" in response_text:
                    match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
                    if match:
                        return json.loads(match.group(1).strip())
                
                # 处理普通```包装
                if "```" in response_text:
                    match = re.search(r'```\s*(.*?)\s*```', response_text, re.DOTALL)
                    if match:
                        return json.loads(match.group(1).strip())
            except json.JSONDecodeError as e:
                print(f"[PolicyHybridRetrievalTool] Markdown清理后JSON解析失败: {e}")
                pass
            
            # 策略3: 智能JSON对象提取（支持嵌套结构）
            try:
                # 改进的JSON对象匹配 - 处理嵌套结构
                if '"answer"' in response_text and '"sources"' in response_text:
                    # 找到第一个{的位置
                    start_pos = response_text.find('{')
                    if start_pos != -1:
                        # 从{开始，匹配对应的}
                        brace_count = 0
                        for i, char in enumerate(response_text[start_pos:], start_pos):
                            if char == '{':
                                brace_count += 1
                            elif char == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    # 找到匹配的}
                                    json_str = response_text[start_pos:i+1]
                                    return json.loads(json_str)
                
                # 如果上面方法失败，用简单的正则匹配
                json_match = re.search(r'\{.*?\}', response_text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(0))
            except json.JSONDecodeError as e:
                print(f"[PolicyHybridRetrievalTool] 智能JSON提取后解析失败: {e}")
                pass
            
            # 策略4: 增强的正则表达式逐步匹配关键字段
            try:
                answer = ""
                sources = []
                
                # 提取answer字段 - 支持包含引号和换行的内容
                answer_patterns = [
                    r'"answer"\s*:\s*"((?:[^"\\]|\\.)*)"',  # 处理转义引号
                    r'"answer"\s*:\s*"([^"]*)"',           # 简单情况
                ]
                
                for pattern in answer_patterns:
                    answer_match = re.search(pattern, response_text, re.DOTALL)
                    if answer_match:
                        answer = answer_match.group(1)
                        # 处理转义字符，但保留换行结构
                        answer = answer.replace('\\"', '"').replace('\\\\', '\\')
                        break
                
                # 提取sources字段 - 更robust的匹配
                sources_patterns = [
                    r'"sources"\s*:\s*\[(.*?)\]',          # 基本匹配
                    r'"sources"\s*:\s*\[([^\]]*)\]',       # 更严格的匹配
                ]
                
                for pattern in sources_patterns:
                    sources_match = re.search(pattern, response_text, re.DOTALL)
                    if sources_match:
                        sources_content = sources_match.group(1)
                        # 提取引号中的文件名，处理各种格式
                        file_patterns = [
                            r'"([^"]+)"',                  # 标准格式
                            r"'([^']+)'",                  # 单引号格式
                            r'([^,\[\]\s]+)',             # 无引号格式
                        ]
                        
                        for file_pattern in file_patterns:
                            file_matches = re.findall(file_pattern, sources_content)
                            sources.extend(file_matches)
                        
                        # 去重并清理
                        sources = list(set([s.strip() for s in sources if s.strip()]))
                        break
                
                if answer:  # 只要有answer就返回
                    return {"answer": answer, "sources": sources}
                    
            except Exception as e:
                print(f"[PolicyHybridRetrievalTool] 增强正则表达式解析失败: {e}")
                pass
            
        
        try:
            # 使用robust解析
            result = robust_json_parse(llm_output)
            
            if result and result.get("answer"):
                print(f"[PolicyHybridRetrievalTool] JSON解析成功，answer长度: {len(result['answer'])}, sources: {result.get('sources', [])}")
                return result
            else:
                print(f"[PolicyHybridRetrievalTool] 解析结果缺少有效答案")
                return None
                
        except Exception as e:
            print(f"[PolicyHybridRetrievalTool] JSON解析异常: {e}")
            print(f"原始输出: {llm_output[:500]}...")
            return None
    
    def _handle_exception_by_progress(self, question: str, exception: Exception, 
                                     search_results, scores, scored_results, file_groups) -> PolicyRetrievalResponse:
        """
        根据已完成的步骤智能处理异常，确保正确的失败类型分类
        
        Args:
            question: 用户问题
            exception: 发生的异常
            search_results: 混合检索结果
            scores: 相关性打分结果
            scored_results: 过滤后的高分语块
            file_groups: 按文件分组的结果
            
        Returns:
            PolicyRetrievalResponse: 根据进度分类的响应
        """
        error_msg = str(exception)
        print(f"[PolicyHybridRetrievalTool] 智能异常处理 - 异常: {error_msg}")
        
        # 情况分析：根据已完成的步骤判断应该返回的失败类型
        
        # 如果连检索结果都没有，说明是早期阶段失败 -> retryable
        if search_results is None:
            print(f"[PolicyHybridRetrievalTool] 异常发生在混合检索阶段")
            return PolicyRetrievalResponse(
                question=question,
                answer="政策文件检索过程中发生错误",
                reference_files=[],
                is_found=False,
                error=error_msg,
                failure_type="retryable",  # 早期阶段失败，可重试
                debug_info={"step": "early_stage_error", "exception": error_msg}
            )
        
        # 如果有检索结果但没有打分结果，说明是相关性打分阶段失败 -> retryable
        if scores is None:
            print(f"[PolicyHybridRetrievalTool] 异常发生在相关性打分阶段")
            return PolicyRetrievalResponse(
                question=question,
                answer="政策文件检索过程中发生错误",
                reference_files=[],
                is_found=False,
                error=error_msg,
                failure_type="retryable",  # 相关性打分失败，可重试
                debug_info={"step": "scoring_error", "exception": error_msg, "search_results_count": len(search_results)}
            )
        
        # 关键：如果已经完成打分且没有4分以上语块，说明是情况2 -> final
        if scored_results is not None and len(scored_results) == 0:
            print(f"[PolicyHybridRetrievalTool] 异常发生但已确定无4分以上语块 - 应为最终失败")
            return PolicyRetrievalResponse(
                question=question,
                answer="根据检索的政策文件无法找到相关规定",
                reference_files=[],
                is_found=False,
                error="没有找到相关性足够高的内容",
                failure_type="final",  # 确定无高相关性内容，最终失败
                debug_info={
                    "step": "no_high_relevance_confirmed", 
                    "max_score": max(scores) if scores else 0,
                    "total_results": len(search_results),
                    "original_exception": error_msg
                }
            )
        
        # 如果有高分语块，说明异常发生在LLM处理阶段 -> needs_agent2
        if scored_results is not None and len(scored_results) > 0:
            print(f"[PolicyHybridRetrievalTool] 异常发生在LLM处理阶段，有{len(scored_results)}个高分语块")
            
            # 准备文件信息和检索内容给Agent2
            if file_groups is not None:
                # 如果已经有文件分组
                all_files = [
                    {
                        "document_title": group.document_title,
                        "publish_date": group.publish_date,
                        "issuing_agency": group.issuing_agency,
                        "website": group.website
                    }
                    for group in file_groups
                ]
                
                file_contents_parts = []
                for group in file_groups:
                    file_content = f"""
文件名：{group.document_title}
发布日期：{group.publish_date}
发布机构：{group.issuing_agency}
网站来源：{group.website}

文件内容：
{group.merged_text}
"""
                    file_contents_parts.append(file_content)
                
                retrieval_content = "\n" + "="*50 + "\n".join(file_contents_parts)
            else:
                # 如果还没有分组，从scored_results构建
                all_files = []
                file_contents_parts = []
                
                for scored_result in scored_results:
                    result = scored_result.search_result
                    file_info = {
                        "document_title": result.document_title,
                        "publish_date": result.publish_date,
                        "issuing_agency": result.issuing_agency,
                        "website": result.website
                    }
                    if file_info not in all_files:
                        all_files.append(file_info)
                    
                    file_content = f"""
文件名：{result.document_title}
内容片段：
{scored_result.expanded_text_initial}
"""
                    file_contents_parts.append(file_content)
                
                retrieval_content = "\n".join(file_contents_parts)
            
            # 🔧 为Agent2截断检索内容，避免传递过长内容
            if len(retrieval_content) > 40000:
                print(f"[PolicyHybridRetrievalTool] 传递给Agent2的内容过长({len(retrieval_content)}字符)，截断至40000字符")
                retrieval_content = retrieval_content[:40000] + "\n\n[内容因长度限制被截断...]"
            
            return PolicyRetrievalResponse(
                question=question,
                answer="检索到相关内容但LLM处理失败",
                reference_files=all_files,
                is_found=False,
                error="LLM处理失败",
                failure_type="needs_agent2",  # 需要Agent2处理
                retrieval_content=retrieval_content,
                debug_info={"step": "llm_stage_error", "llm_error": error_msg, "high_score_chunks": len(scored_results)}
            )
        
        # 兜底情况：未知阶段异常 -> retryable
        print(f"[PolicyHybridRetrievalTool] 未知阶段异常，兜底为可重试")
        return PolicyRetrievalResponse(
            question=question,
            answer="政策文件检索过程中发生错误",
            reference_files=[],
            is_found=False,
            error=error_msg,
            failure_type="retryable",  # 未知错误，可重试
            debug_info={"step": "unknown_stage_error", "exception": error_msg}
        )

    def close(self):
        """关闭所有连接"""
        self.hybrid_search_tool.close()
        self.text_processor.close()
        print("[PolicyHybridRetrievalTool] 所有连接已关闭")

# 便捷函数
def execute_policy_retrieval(question: str) -> PolicyRetrievalResponse:
    """执行政策文件检索的便捷函数"""
    tool = PolicyHybridRetrievalTool()
    try:
        return tool.execute_retrieval(question)
    finally:
        tool.close()
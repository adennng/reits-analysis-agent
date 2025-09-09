# hybrid_retrieval_tool.py
"""
混合检索Tool - 基于OpenAI Agents框架，供Agent调用
"""

import sys
import os
from typing import Dict, Any, Optional

# 添加路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
sys.path.insert(0, project_root)

try:
    from agents import function_tool
except ImportError:
    # For testing purposes, create mock decorator
    def function_tool(func):
        return func

from .models.data_models import SearchParams
from .utils.params_generator import generate_search_params
from .tools.expansion_pipeline import ExpansionPipeline
from .tools.search_tools import HybridSearchTool

class HybridRetrievalTool:
    """
    混合检索Tool，供OpenAI Agents框架调用
    """
    
    def __init__(self):
        # 初始化工具组件
        self.hybrid_search_tool = HybridSearchTool()
        self.expansion_pipeline = ExpansionPipeline()
        print("[HybridRetrievalTool] 初始化完成")
    
    @function_tool
    def search_knowledge_base(
        self,
        fund_code: str,
        question: str,
        file_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """OpenAI Agents框架调用接口"""
        return self._search_knowledge_base_internal(fund_code, question, file_name)
    
    def _search_knowledge_base_internal(
        self,
        fund_code: str,
        question: str,
        file_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        在知识库中检索相关信息
        
        Args:
            fund_code: 基金代码，如 "508056.SH"
            question: 要检索的问题，如 "项目折现率是多少？"
            file_name: 指定的文件名称（可选），如果提供则只在该文件中检索
            
        Returns:
            Dict[str, Any]: 包含检索结果、来源信息等的字典
            
            LLM调用成功时：
            {
                "answer": str,           # 大模型生成的智能答案
                "sources": List[str],    # 来源文件名列表
                "is_found": bool,        # 是否找到相关内容
                "retrieval_method": str  # "hybrid"
            }
            
            LLM调用失败时：
            {
                "answer": str,              # fallback答案（如"LLM未配置"）
                "sources": List[str],       # 来源文件名列表
                "is_found": bool,           # 是否找到相关内容
                "retrieval_method": str,    # "hybrid"
                "retrieval_content": str    # 原始检索内容（仅LLM失败时包含）
            }
        """
        print(f"[HybridRetrievalTool] 开始混合检索")
        print(f"  基金代码: {fund_code}")
        print(f"  检索问题: {question}")
        print(f"  指定文件: {file_name or '无（全部文件）'}")
        
        try:
            # 步骤1：生成检索参数
            search_params = self._generate_search_params(question)
            
            # 步骤2：执行混合检索
            retrieval_content = self._execute_retrieval(
                fund_code, question, search_params, file_name
            )
            
            # 步骤3：构造返回结果（新增答案生成）
            result = self._construct_result(retrieval_content, file_name, question)
            
            print(f"[HybridRetrievalTool] 检索完成")
            return result
            
        except Exception as e:
            print(f"[HybridRetrievalTool] 检索异常: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                "answer": "检索过程发生错误，请重试",
                "sources": [],
                "is_found": False,
                "retrieval_method": "hybrid"
                # 保持与正常情况一致的结构，不包含retrieval_content和error
            }
    
    def _generate_search_params(self, question: str) -> SearchParams:
        """生成检索参数"""
        print("[HybridRetrievalTool] 生成检索参数...")
        
        search_params = generate_search_params(question)
        
        print(f"  向量检索问题: {search_params.vector_question}")
        print(f"  关键词: {search_params.keywords}")
        
        return search_params
    
    def _execute_retrieval(
        self,
        fund_code: str,
        question: str,
        search_params: SearchParams,
        file_name: Optional[str] = None
    ) -> str:
        """执行实际的检索逻辑"""
        
        print("[HybridRetrievalTool] 执行混合检索...")
        
        # 混合检索流程
        search_results = self.hybrid_search_tool.search(
            fund_code=fund_code,
            question=search_params.vector_question,
            keywords=search_params.keywords,
            source_file=file_name,  # 如果指定了文件名则过滤，否则为None（不过滤）
            top_k=15
        )
        
        if search_results:
            print(f"[HybridRetrievalTool] 检索到{len(search_results)}条结果，开始扩展和打分...")
            
            # 执行扩展和打分流程
            scored_results = self.expansion_pipeline.process_search_results(
                search_results, question
            )
            
            if scored_results:
                # 格式化输出
                retrieval_content = self.expansion_pipeline.format_final_answer(scored_results)
            else:
                retrieval_content = "未找到满足条件的相关信息。"
        else:
            retrieval_content = "未找到相关信息。"
        
        return retrieval_content
    
    def _construct_result(self, retrieval_content: str, file_name: Optional[str] = None, question: Optional[str] = None) -> Dict[str, Any]:
        """构造返回结果 - 修复逻辑问题的版本"""
        
        # 移除过早的is_found判断，让LLM来判断内容是否有用
        if not question or not question.strip():
            # 只有在没有问题时才直接返回
            sources = self._extract_sources(retrieval_content)
            return {
                "answer": "问题不能为空",
                "sources": sources,
                "is_found": False,
                "retrieval_method": "hybrid"
            }
        
        # 检查检索内容是否完全为空
        if not retrieval_content or retrieval_content.strip() == "":
            return {
                "answer": "未检索到任何内容",
                "sources": [],
                "is_found": False,
                "retrieval_method": "hybrid"
            }
        
        # 始终尝试LLM生成答案，让LLM判断内容质量
        llm_result = self._generate_answer_from_content(question, retrieval_content)
        
        if llm_result["success"]:
            # LLM调用成功 - 基于LLM的答案判断是否找到有用信息
            answer = llm_result["answer"]
            llm_sources = llm_result["sources"]
            
            # 统一的is_found判断逻辑
            is_found_final = self._determine_is_found(answer, llm_sources)
            
            print(f"[HybridRetrievalTool] LLM成功，传递给下一步: answer长度={len(answer)}, sources={llm_sources}, is_found={is_found_final}")
            
            return {
                "answer": answer,
                "sources": llm_sources,
                "is_found": is_found_final,
                "retrieval_method": "hybrid"
            }
        else:
            # LLM调用失败 - 基于检索内容和原始sources重新判断
            original_sources = self._extract_sources(retrieval_content)
            
            # 重新评估is_found，而不是使用之前的粗糙判断
            is_found_final = self._determine_is_found_from_content(retrieval_content, original_sources)
            
            print(f"[HybridRetrievalTool] LLM失败，传递给下一步: 包含retrieval_content, sources={len(original_sources)}个, is_found={is_found_final}")
            
            return {
                "answer": llm_result["answer"],  # fallback答案
                "retrieval_content": retrieval_content,
                "sources": original_sources,
                "is_found": is_found_final,  # 重新评估的结果
                "retrieval_method": "hybrid"
            }
    
    def _determine_is_found(self, answer: str, sources: list) -> bool:
        """统一的is_found判断逻辑 - 基于LLM答案"""
        if not answer or not answer.strip():
            return False
            
        # 检查答案中的否定性表述
        negative_phrases = [
            "根据检索内容无法找到相关信息",
            "无法找到",
            "找不到",
            "没有找到",
            "未找到相关信息",
            "很抱歉，无法",
            "暂时无法确定"
        ]
        
        answer_lower = answer.lower()
        for phrase in negative_phrases:
            if phrase in answer:
                return False
        
        # 检查答案长度（太短可能无效）
        if len(answer.strip()) < 10:
            return False
            
        # 有sources且答案有实质内容，认为找到了
        return len(sources) > 0 or len(answer.strip()) > 20
    
    def _determine_is_found_from_content(self, retrieval_content: str, sources: list) -> bool:
        """从检索内容判断是_found - LLM失败时使用"""
        if not retrieval_content or not retrieval_content.strip():
            return False
            
        # 检查明显的失败标识
        failure_indicators = [
            "未找到相关信息",
            "未找到满足条件的相关信息",
            "很抱歉",
            "没有找到"
        ]
        
        for indicator in failure_indicators:
            if indicator in retrieval_content:
                return False
        
        # 如果有sources且内容长度合理，认为找到了
        content_length = len(retrieval_content.strip())
        return len(sources) > 0 and content_length > 100
    
    def _extract_sources(self, retrieval_content: str) -> list:
        """从检索结果中提取来源信息（只保留文件名）- 完全重写版本"""
        sources_set = set()  # 使用set自动去重
        
        try:
            import re
            
            # 方法1：查找"**来源文件**："格式
            lines = retrieval_content.split('\n')
            for line in lines:
                if "**来源文件**：" in line:
                    source_file = line.replace("**来源文件**：", "").strip()
                    # 清理可能的多余字符
                    source_file = source_file.rstrip('.,;，。；')
                    if source_file and source_file.endswith('.pdf'):
                        sources_set.add(source_file)
            
            # 方法2：使用正则表达式查找所有PDF文件名（排除已有格式的）
            # 匹配独立的PDF文件名，不包括"**来源文件**："开头的行
            clean_content = retrieval_content
            # 先移除所有"**来源文件**："行，避免重复提取
            clean_content = re.sub(r'\*\*来源文件\*\*：[^\n]*\.pdf[^\n]*\n?', '', clean_content)
            
            # 在清理后的内容中查找PDF文件名
            pdf_pattern = r'([^\n\*/：，。；,;:]{10,}\.pdf)'  # 至少10个字符的有效文件名
            pdf_matches = re.findall(pdf_pattern, clean_content)
            
            for pdf_file in pdf_matches:
                # 进一步清理文件名
                clean_file = pdf_file.strip().rstrip('.,;，。；')
                # 验证文件名的合理性（包含日期和基金代码格式）
                if (len(clean_file) > 20 and 
                    '.SH' in clean_file and 
                    clean_file.endswith('.pdf')):
                    sources_set.add(clean_file)
            
            # 转换为列表并排序（保证结果稳定）
            final_sources = sorted(list(sources_set))
            
            print(f"[HybridRetrievalTool] 提取到{len(final_sources)}个有效源文件")
            
            return final_sources
            
        except Exception as e:
            print(f"[HybridRetrievalTool] 提取sources时出错: {e}")
            return []
    
    def _generate_answer_from_content(self, question: str, content: str) -> Dict[str, Any]:
        """基于检索内容生成答案
        
        Returns:
            Dict[str, Any]: {
                "success": bool,  # LLM调用是否成功
                "answer": str,    # 答案内容
                "sources": list,  # 来源文件列表
                "raw_response": str  # 原始LLM响应
            }
        """
        try:
            # 设置LLM客户端
            llm_client, model_name = self._setup_llm()
            
            if not llm_client:
                print("[HybridRetrievalTool] LLM未设置")
                return {
                    "success": False,
                    "answer": "LLM未配置，无法生成智能答案",
                    "sources": [],
                    "raw_response": ""
                }
            
            # 使用统一的提示词模板
            from config.prompts import ANSWER_GENERATION_PROMPT
            prompt = ANSWER_GENERATION_PROMPT.format(question=question, content=content)
            
            print(f"[HybridRetrievalTool] 使用{model_name}生成答案...")
            print(f"[HybridRetrievalTool] 传递给大模型的内容长度: {len(prompt)}字符")
            print(f"[HybridRetrievalTool] 传递给大模型的完整内容:")
            print("=" * 80)
            print(prompt)
            print("=" * 80)
            
            # 调用LLM生成答案
            response = llm_client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,  # 低温度保证一致性
            )
            
            raw_response = response.choices[0].message.content.strip()
            print(f"[HybridRetrievalTool] 大模型返回: {raw_response}")
            
            # 解析JSON响应 - 使用robust解析逻辑
            try:
                import json
                import re
                
                # 多级解析逻辑
                def robust_json_parse(response_text):
                    """Robust JSON解析，包含多级fallback机制"""
                    
                    # 第1级：直接解析
                    try:
                        return json.loads(response_text.strip())
                    except:
                        pass
                    
                    # 第2级：去除markdown包装
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
                    except:
                        pass
                    
                    # 第3级：正则提取JSON对象
                    try:
                        # 改进的JSON对象匹配 - 处理嵌套结构
                        # 首先查找包含answer和sources的JSON
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
                    except:
                        pass
                    
                    # 第4级：智能提取关键信息
                    try:
                        # 改进的字段提取 - 处理复杂内容
                        answer = ""
                        sources = []
                        
                        # 提取answer字段 - 支持包含引号的内容
                        answer_patterns = [
                            r'"answer"\s*:\s*"((?:[^"\\]|\\.)*)"',  # 处理转义引号
                            r'"answer"\s*:\s*"([^"]*)"',           # 简单情况
                        ]
                        
                        for pattern in answer_patterns:
                            answer_match = re.search(pattern, response_text)
                            if answer_match:
                                answer = answer_match.group(1)
                                # 处理转义字符
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
                                    r'"([^"]+\.pdf)"',             # 标准格式
                                    r"'([^']+\.pdf)'",             # 单引号格式
                                    r'([^,\[\]\s]+\.pdf)',         # 无引号格式
                                ]
                                
                                for file_pattern in file_patterns:
                                    file_matches = re.findall(file_pattern, sources_content)
                                    sources.extend(file_matches)
                                
                                # 去重
                                sources = list(set(sources))
                                break
                        
                        if answer:  # 只要有answer就返回
                            return {"answer": answer, "sources": sources}
                    except:
                        pass
                    
                    # 第5级：最后的fallback - 返回原始内容
                    return {"answer": response_text.strip(), "sources": []}
                
                result = robust_json_parse(raw_response)
                
                answer = result.get("answer", "")
                sources = result.get("sources", [])
                
                # 验证答案质量
                if not answer or len(answer.strip()) < 5:
                    print(f"[HybridRetrievalTool] 答案质量不佳")
                    return {
                        "success": False,
                        "answer": "LLM生成的答案质量不佳",
                        "sources": [],
                        "raw_response": raw_response
                    }
                
                print(f"[HybridRetrievalTool] 答案生成成功，参考来源: {sources}")
                return {
                    "success": True,
                    "answer": answer,
                    "sources": sources,
                    "raw_response": raw_response
                }
                
            except Exception as e:
                print(f"[HybridRetrievalTool] JSON解析失败: {e}")
                return {
                    "success": False,
                    "answer": "LLM返回格式解析失败",
                    "sources": [],
                    "raw_response": raw_response
                }
            
        except Exception as e:
            print(f"[HybridRetrievalTool] 答案生成异常: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "answer": f"LLM调用异常: {str(e)}",
                "sources": [],
                "raw_response": ""
            }
    
    def _setup_llm(self):
        """设置LLM客户端"""
        try:
            # 使用绝对导入路径修复导入问题
            import sys
            import os
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
            sys.path.insert(0, project_root)
            
            from config.model_config import MODEL_CONFIG
            from openai import OpenAI
            
            # 使用配置中的LLM设置
            llm_config = MODEL_CONFIG["ali"]["deepseek-v3"]  # 或者使用您配置的其他模型
            llm_client = OpenAI(
                api_key=llm_config["api_key"],
                base_url=llm_config["base_url"]
            )
            model_name = llm_config["model"]
            print(f"[HybridRetrievalTool] LLM客户端设置完成，使用模型: {model_name}")
            
            return llm_client, model_name
            
        except Exception as e:
            print(f"[HybridRetrievalTool] LLM设置失败: {e}")
            import traceback
            traceback.print_exc()
            return None, None


# 便捷函数 - 用于测试和直接调用
def search_knowledge_base(
    fund_code: str,
    question: str,
    file_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    便捷的混合检索函数
    
    Args:
        fund_code: 基金代码
        question: 检索问题
        file_name: 指定文件名（可选）
        
    Returns:
        Dict[str, Any]: 检索结果
    """
    tool = HybridRetrievalTool()
    return tool._search_knowledge_base_internal(fund_code, question, file_name)


# 测试函数
def test_hybrid_retrieval_tool():
    """测试混合检索Tool"""
    print("🧪 测试混合检索Tool")
    print("=" * 60)
    
    test_cases = [
        {
            "fund_code": "508056.SH",
            "question": "基金的管理费率是多少？",
            "file_name": None,
            "description": "管理费率查询测试"
        },
        {
            "fund_code": "508056.SH",
            "question": "项目折现率是多少？",
            "file_name": "2021-05-26_508056.SH_中金普洛斯REIT_中金普洛斯仓储物流封闭式基础设施证券投资基金招募说明书（更新）.pdf",
            "description": "指定文件检索测试"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 测试用例 {i}: {test_case['description']}")
        print("-" * 40)
        
        try:
            # 创建工具实例以便访问内部方法
            tool = HybridRetrievalTool()
            
            # 执行检索
            result = tool._search_knowledge_base_internal(
                fund_code=test_case["fund_code"],
                question=test_case["question"],
                file_name=test_case["file_name"]
            )
            
            print(f"\n✅ 测试完成")
            print("=" * 60)
            print("📊 最终传递给下一步的结果:")
            print(f"   🎯 answer: {result.get('answer', 'N/A')[:2000]}{'...' if len(result.get('answer', '')) > 2000 else ''}")
            print(f"   📚 sources: {result.get('sources', [])}")
            print(f"   ✅ is_found: {result.get('is_found', False)}")
            print(f"   🔍 retrieval_method: {result.get('retrieval_method', 'N/A')}")
            
            # 只有LLM失败时才有retrieval_content
            if 'retrieval_content' in result:
                print(f"   📄 retrieval_content: 包含（长度={len(result['retrieval_content'])}）")
            else:
                print(f"   📄 retrieval_content: 不包含（LLM调用成功）")
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    test_hybrid_retrieval_tool() 
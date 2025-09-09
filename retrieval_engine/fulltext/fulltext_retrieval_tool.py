# fulltext_retrieval_tool.py
"""
全文检索Tool - 基于OpenAI Agents框架，供Agent调用
获取指定文件的完整内容并通过LLM生成答案
"""

import sys
import os
from typing import Dict, Any
import tempfile
import json

# 添加路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

try:
    from agents import function_tool
except ImportError:
    # For testing purposes, create mock decorator
    def function_tool(func):
        return func

from .fulltext_searcher import FulltextSearcher

class FulltextRetrievalTool:
    """
    全文检索Tool，供OpenAI Agents框架调用
    """
    
    def __init__(self):
        # 初始化工具组件
        self.fulltext_searcher = FulltextSearcher()
        print("[FulltextRetrievalTool] 初始化完成")
    
    @function_tool
    def search_full_document(
        self,
        question: str,
        file_name: str
    ) -> Dict[str, Any]:
        """OpenAI Agents框架调用接口
        
        Args:
            question: 要检索的问题
            file_name: 指定的文件名称
        
        Returns:
            检索结果字典
        """
        return self._search_full_document_internal(question, file_name)
    
    def _search_full_document_internal(
        self,
        question: str,
        file_name: str
    ) -> Dict[str, Any]:
        """
        在指定文件中进行全文检索
        
        Args:
            question: 要检索的问题，如 "基金的投资策略是什么？"
            file_name: 指定的文件名称，如 "基金合同.pdf"
            
        Returns:
            Dict[str, Any]: 包含检索结果、来源信息等的字典
            
            成功时：
            {
                "answer": str,           # 大模型生成的智能答案
                "sources": List[str],    # 来源文件名列表
                "is_found": bool,        # 是否找到相关内容
                "retrieval_method": str, # "fulltext"
                "document_analysis": str # 文档内容分析
            }
            
            失败时：
            {
                "answer": str,              # 错误信息或fallback答案
                "sources": List[str],       # 来源文件名列表
                "is_found": bool,           # False
                "retrieval_method": str,    # "fulltext"
                "error": str                # 错误详情
            }
        """
        print(f"[FulltextRetrievalTool] 开始全文检索")
        print(f"  文件名: {file_name}")
        print(f"  检索问题: {question}")
        
        # 验证必要参数
        if not question or not question.strip():
            return {
                "answer": "问题不能为空",
                "sources": [],
                "is_found": False,
                "retrieval_method": "fulltext",
                "error": "Missing required parameter: question"
            }
        
        if not file_name or not file_name.strip():
            return {
                "answer": "文件名不能为空",
                "sources": [],
                "is_found": False,
                "retrieval_method": "fulltext",
                "error": "Missing required parameter: file_name"
            }
        
        try:
            # 步骤1：获取文件全文内容
            full_text = self._get_full_document_text(file_name)
            
            if not full_text:
                return {
                    "answer": f"未找到文件 {file_name} 的内容",
                    "sources": [],
                    "is_found": False,
                    "retrieval_method": "fulltext"
                }
            
            # 步骤2：创建临时txt文件
            txt_file_path = self._create_temp_txt_file(full_text, file_name)
            
            # 步骤3：调用LLM生成答案
            result = self._generate_answer_with_llm(question, file_name, full_text)
            
            # 步骤4：清理临时文件
            self._cleanup_temp_file(txt_file_path)
            
            print(f"[FulltextRetrievalTool] 全文检索完成")
            return result
            
        except Exception as e:
            print(f"[FulltextRetrievalTool] 检索异常: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                "answer": f"检索过程发生错误：{str(e)}",
                "sources": [],
                "is_found": False,
                "retrieval_method": "fulltext",
                "error": str(e)
            }
    
    def _get_full_document_text(self, file_name: str) -> str:
        """获取文档全文内容"""
        print("[FulltextRetrievalTool] 获取文档全文内容...")
        
        full_text = self.fulltext_searcher.get_full_document_text(file_name)
        
        if full_text:
            print(f"[FulltextRetrievalTool] 获取成功，文档长度: {len(full_text)} 字符")
        else:
            print("[FulltextRetrievalTool] 未获取到文档内容")
        
        return full_text
    
    def _create_temp_txt_file(self, content: str, file_name: str) -> str:
        """创建临时txt文件"""
        print("[FulltextRetrievalTool] 创建临时txt文件...")
        
        # 生成临时文件名
        temp_file_name = f"fulltext_{file_name.replace('.', '_').replace(' ', '_')}.txt"
        temp_file_path = os.path.join(tempfile.gettempdir(), temp_file_name)
        
        try:
            with open(temp_file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"[FulltextRetrievalTool] 临时文件创建成功: {temp_file_path}")
            print(f"[FulltextRetrievalTool] 文件大小: {len(content)} 字符")
            return temp_file_path
            
        except Exception as e:
            print(f"[FulltextRetrievalTool] 创建临时文件失败: {e}")
            return ""
    
    def _cleanup_temp_file(self, file_path: str):
        """清理临时文件"""
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"[FulltextRetrievalTool] 临时文件已清理: {file_path}")
            except Exception as e:
                print(f"[FulltextRetrievalTool] 清理临时文件失败: {e}")
    
    def _generate_answer_with_llm(self, question: str, file_name: str, content: str) -> Dict[str, Any]:
        """使用LLM生成答案"""
        print("[FulltextRetrievalTool] 开始调用LLM生成答案...")
        
        # 设置LLM
        llm_result = self._setup_llm()
        if not llm_result["success"]:
            return {
                "answer": "LLM配置失败，无法生成答案",
                "sources": [file_name],
                "is_found": True,  # 文档内容存在，只是LLM调用失败
                "retrieval_method": "fulltext",
                "error": llm_result["error"]
            }
        
        client = llm_result["client"]
        model = llm_result["model"]
        
        # 导入提示词
        try:
            from config.prompts import FULLTEXT_ANSWER_GENERATION_PROMPT
        except ImportError:
            print("[FulltextRetrievalTool] 无法导入提示词，使用默认提示词")
            FULLTEXT_ANSWER_GENERATION_PROMPT = """基于以下文档内容回答问题：

问题：{question}
文件名：{file_name}
文档内容：{content}

请返回JSON格式：{{"answer": "答案", "sources": ["文件名"], "document_analysis": "分析"}}"""
        
        # 构建提示词
        prompt = FULLTEXT_ANSWER_GENERATION_PROMPT.format(
            question=question,
            file_name=file_name,
            content=content
        )
        
        try:
            # 调用LLM
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=8192
            )
            
            response_text = response.choices[0].message.content.strip()
            print(f"[FulltextRetrievalTool] LLM原始响应: {response_text[:500]}...")
            
            # 解析JSON响应
            parsed_result = self._parse_llm_response(response_text)
            
            if parsed_result["success"]:
                result = {
                    "answer": parsed_result["answer"],
                    "sources": parsed_result["sources"],
                    "is_found": True,
                    "retrieval_method": "fulltext",
                    "document_analysis": parsed_result.get("document_analysis", "")
                }
                print("[FulltextRetrievalTool] LLM答案生成成功")
                return result
            else:
                # JSON解析失败，返回原始响应
                return {
                    "answer": response_text,
                    "sources": [file_name],
                    "is_found": True,
                    "retrieval_method": "fulltext",
                    "document_analysis": "LLM响应解析失败"
                }
                
        except Exception as e:
            print(f"[FulltextRetrievalTool] LLM调用失败: {e}")
            return {
                "answer": "LLM调用失败，无法生成答案",
                "sources": [file_name],
                "is_found": True,
                "retrieval_method": "fulltext",
                "error": str(e)
            }
    
    def _parse_llm_response(self, response_text: str) -> Dict[str, Any]:
        """解析LLM的JSON响应"""
        try:
            # 尝试直接解析JSON
            parsed = json.loads(response_text)
            
            # 验证必要字段
            if "answer" in parsed and "sources" in parsed:
                return {
                    "success": True,
                    "answer": parsed["answer"],
                    "sources": parsed["sources"] if isinstance(parsed["sources"], list) else [parsed["sources"]],
                    "document_analysis": parsed.get("document_analysis", "")
                }
            else:
                print("[FulltextRetrievalTool] JSON缺少必要字段")
                return {"success": False, "error": "Missing required fields"}
                
        except json.JSONDecodeError as e:
            print(f"[FulltextRetrievalTool] JSON解析失败: {e}")
            # 尝试简单的字符串提取
            try:
                answer_match = response_text
                return {
                    "success": True,
                    "answer": answer_match,
                    "sources": [],
                    "document_analysis": "JSON格式解析失败，返回原始内容"
                }
            except:
                return {"success": False, "error": str(e)}
    
    def _setup_llm(self) -> Dict[str, Any]:
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
            
            # 获取qwen-long配置
            ali_config = MODEL_CONFIG.get("ali", {})
            qwen_config = ali_config.get("qwen-long", {})
            
            if not qwen_config:
                return {
                    "success": False,
                    "error": "qwen-long模型配置未找到"
                }
            
            # 创建客户端
            client = OpenAI(
                api_key=qwen_config["api_key"],
                base_url=qwen_config["base_url"]
            )
            
            print("[FulltextRetrievalTool] qwen-long客户端初始化成功")
            return {
                "success": True,
                "client": client,
                "model": qwen_config["model"]
            }
            
        except Exception as e:
            print(f"[FulltextRetrievalTool] LLM设置失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }


# 外部调用接口
def search_full_document(
    question: str,
    file_name: str
) -> Dict[str, Any]:
    """
    全文检索的外部调用接口
    
    Args:
        question: 检索问题
        file_name: 文件名
        
    Returns:
        Dict[str, Any]: 检索结果
    """
    tool = FulltextRetrievalTool()
    return tool._search_full_document_internal(question, file_name) 
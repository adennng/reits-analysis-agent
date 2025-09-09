# prospectus_section_tool.py
"""
招募说明书章节检索Tool - 基于OpenAI Agents框架，供Agent调用
根据问题判断章节，查找对应txt文件，生成答案
"""

import sys
import os
from typing import Dict, Any

# 添加路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

try:
    from agents import function_tool
except ImportError:
    # For testing purposes, create mock decorator
    def function_tool(func):
        return func

# 支持直接运行和模块导入两种方式
try:
    # 模块导入方式
    from .section_classifier import SectionClassifier
    from .file_finder import FileFinder
    from .answer_generator import AnswerGenerator
except ImportError:
    # 直接运行方式
    from section_classifier import SectionClassifier
    from file_finder import FileFinder
    from answer_generator import AnswerGenerator


class ProspectusSectionTool:
    """
    招募说明书章节检索Tool，供OpenAI Agents框架调用
    """
    
    def __init__(self):
        """初始化工具组件"""
        self.section_classifier = SectionClassifier()
        self.file_finder = FileFinder()
        self.answer_generator = AnswerGenerator()
        print("[ProspectusSectionTool] 招募说明书章节检索工具初始化完成")
    
    @function_tool
    def search_prospectus_section(
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
        return self._search_prospectus_section_internal(question, file_name)
    
    def _search_prospectus_section_internal(
        self,
        question: str,
        file_name: str
    ) -> Dict[str, Any]:
        """
        在招募说明书中进行章节检索
        
        Args:
            question: 要检索的问题，如 "基金的投资策略是什么？"
            file_name: 指定的文件名称，如 "2025-03-12_180305.SZ_南方顺丰物流REIT_南方顺丰仓储物流封闭式基础设施证券投资基金招募说明书.pdf"
            
        Returns:
            Dict[str, Any]: 包含检索结果、来源信息等的字典
            
            成功时：
            {
                "answer": str,           # 大模型生成的智能答案
                "sources": List[str],    # 来源文件名列表
                "is_found": bool,        # 是否找到相关内容
                "retrieval_method": str, # "prospectus_section"
                "sections": List[str],   # 匹配的章节列表
                "found_files": List[str] # 找到的txt文件列表
            }
            
            失败时：
            {
                "answer": str,              # 错误信息或"无"
                "sources": List[str],       # 来源文件名列表
                "is_found": bool,           # False
                "retrieval_method": str,    # "prospectus_section"
                "error": str                # 错误详情
            }
        """
        print(f"[ProspectusSectionTool] 开始招募说明书章节检索")
        print(f"  文件名: {file_name}")
        print(f"  检索问题: {question}")
        
        # 验证必要参数
        if not question or not question.strip():
            return {
                "answer": "问题不能为空",
                "sources": [],
                "is_found": False,
                "retrieval_method": "prospectus_section",
                "error": "Missing required parameter: question"
            }
        
        if not file_name or not file_name.strip():
            return {
                "answer": "文件名不能为空",
                "sources": [],
                "is_found": False,
                "retrieval_method": "prospectus_section",
                "error": "Missing required parameter: file_name"
            }
        
        try:
            # 步骤1：章节判断
            print("[ProspectusSectionTool] === 步骤1：章节判断 ===")
            classification_result = self.section_classifier.classify_section(question)
            
            if not classification_result["success"]:
                return {
                    "answer": "章节分类失败",
                    "sources": [],
                    "is_found": False,
                    "retrieval_method": "prospectus_section",
                    "error": f"章节分类失败: {classification_result['reason']}"
                }
            
            sections = classification_result["sections"]
            
            # 如果没有匹配的章节，返回"无"
            if not sections:
                print("[ProspectusSectionTool] 未找到匹配的章节，返回'无'")
                return {
                    "answer": "无",
                    "sources": [file_name],
                    "is_found": False,
                    "retrieval_method": "prospectus_section",
                    "sections": [],
                    "reason": "未找到匹配的章节"
                }
            
            print(f"[ProspectusSectionTool] 匹配到章节: {sections}")
            
            # 步骤2：文件查找
            print("[ProspectusSectionTool] === 步骤2：文件查找 ===")
            file_result = self.file_finder.find_section_files(file_name, sections)
            
            if not file_result["success"] or not file_result["found_files"]:
                return {
                    "answer": "无",
                    "sources": [file_name],
                    "is_found": False,
                    "retrieval_method": "prospectus_section",
                    "sections": sections,
                    "error": f"文件查找失败: {file_result.get('error', '未找到相关文件')}"
                }
            
            found_files = file_result["found_files"]
            print(f"[ProspectusSectionTool] 找到文件: {len(found_files)} 个")
            
            # 步骤3：读取文件内容
            print("[ProspectusSectionTool] === 步骤3：读取文件内容 ===")
            combined_content = self.file_finder.get_combined_content(found_files)
            
            if not combined_content or not combined_content.strip():
                return {
                    "answer": "根据检索内容无法找到相关信息",
                    "sources": [file_name],
                    "is_found": False,
                    "retrieval_method": "prospectus_section",
                    "sections": sections,
                    "found_files": found_files,
                    "error": "文件内容为空"
                }
            
            # 步骤4：答案生成
            print("[ProspectusSectionTool] === 步骤4：答案生成 ===")
            answer_result = self.answer_generator.generate_answer(
                question, combined_content, found_files, file_name
            )
            
            if not answer_result["success"]:
                return {
                    "answer": "根据检索内容无法找到相关信息",
                    "sources": [file_name],
                    "is_found": False,
                    "retrieval_method": "prospectus_section",
                    "sections": sections,
                    "found_files": found_files,
                    "error": f"答案生成失败: {answer_result.get('content_analysis', '')}"
                }
            
            # 成功返回结果
            result = {
                "answer": answer_result["answer"],
                "sources": [file_name],  # 使用传入的file_name而不是txt文件名
                "is_found": True,
                "retrieval_method": "prospectus_section",
                "sections": sections,
                "found_files": [os.path.basename(f) for f in found_files],
                "content_analysis": answer_result.get("content_analysis", "")
            }
            
            print(f"[ProspectusSectionTool] 章节检索完成")
            return result
            
        except Exception as e:
            print(f"[ProspectusSectionTool] 检索异常: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                "answer": f"检索过程发生错误：{str(e)}",
                "sources": [file_name],
                "is_found": False,
                "retrieval_method": "prospectus_section",
                "error": str(e)
            }


# 外部调用接口
def search_prospectus_section(
    question: str,
    file_name: str
) -> Dict[str, Any]:
    """
    招募说明书章节检索的外部调用接口
    
    Args:
        question: 检索问题
        file_name: 文件名
        
    Returns:
        Dict[str, Any]: 检索结果
    """
    tool = ProspectusSectionTool()
    return tool._search_prospectus_section_internal(question, file_name)


# 测试函数
if __name__ == "__main__":
    # 测试完整流程
    tool = ProspectusSectionTool()
    
    test_question = "基金的管理费率是多少？"
    test_file_name = "2025-03-12_180305.SZ_南方顺丰物流REIT_南方顺丰仓储物流封闭式基础设施证券投资基金招募说明书.pdf"
    
    print(f"=== 测试招募说明书章节检索 ===")
    print(f"问题: {test_question}")
    print(f"文件: {test_file_name}")
    print()
    
    result = tool._search_prospectus_section_internal(test_question, test_file_name)
    
    print(f"=== 检索结果 ===")
    print(f"成功: {result.get('is_found', False)}")
    print(f"答案: {result.get('answer', '')}")
    print(f"来源: {result.get('sources', [])}")
    print(f"章节: {result.get('sections', [])}")
    if 'error' in result:
        print(f"错误: {result['error']}")
# answer_generator.py
"""
答案生成器 - 使用ali qwen-long模型基于txt文件内容回答问题
"""

import sys
import os
import json
from typing import Dict, Any, List

# 添加路径以便导入配置
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
sys.path.insert(0, project_root)

from openai import OpenAI


class AnswerGenerator:
    """
    答案生成器
    使用ali qwen-long模型基于txt文件内容回答问题
    """
    
    def __init__(self):
        """初始化答案生成器"""
        self.client = None
        self.model = None
        self._setup_llm()
        print("[AnswerGenerator] 答案生成器初始化完成")
    
    def generate_answer(self, question: str, content: str, file_paths: List[str], source_file_name: str = None) -> Dict[str, Any]:
        """
        基于文件内容生成答案
        
        Args:
            question: 用户问题
            content: 合并的文件内容
            file_paths: 文件路径列表
            source_file_name: 原始文件名（用于sources返回）
            
        Returns:
            Dict[str, Any]: 生成结果
            {
                "success": bool,
                "answer": str,          # 生成的答案
                "sources": List[str],   # 来源文件名列表
                "content_analysis": str # 内容分析
            }
        """
        print("[AnswerGenerator] 开始生成答案")
        print(f"  问题: {question}")
        print(f"  原始内容长度: {len(content)} 字符")
        print(f"  文件数量: {len(file_paths)}")
        
        if not self.client:
            return {
                "success": False,
                "answer": "LLM客户端未初始化，无法生成答案",
                "sources": [],
                "content_analysis": ""
            }
        
        if not content or not content.strip():
            return {
                "success": False,
                "answer": "根据检索内容无法找到相关信息",
                "sources": [],
                "content_analysis": "提供的内容为空"
            }
        
        try:
            # 控制内容长度（默认最大字符）
            max_content_length = 300000
            original_length = len(content)
            was_truncated = False
            
            if len(content) > max_content_length:
                content = content[:max_content_length] + "\n\n[注：内容因长度限制已截断]"
                was_truncated = True
                print(f"[AnswerGenerator] 内容已截断：{original_length} -> {len(content)} 字符")
            else:
                print(f"[AnswerGenerator] 内容长度在限制范围内：{len(content)} 字符")
            
            # 构建提示词
            prompt = self._build_answer_prompt(question, content, file_paths, source_file_name)
            
            # 调用LLM
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=8192
            )
            
            response_text = response.choices[0].message.content.strip()
            print(f"[AnswerGenerator] LLM原始响应: {response_text[:500]}{'...' if len(response_text) > 500 else ''}")
            
            # 解析响应
            parsed_result = self._parse_answer_response(response_text, source_file_name)
            
            return parsed_result
            
        except Exception as e:
            print(f"[AnswerGenerator] 答案生成异常: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                "success": False,
                "answer": f"答案生成过程异常: {str(e)}",
                "sources": [],
                "content_analysis": f"异常: {str(e)}"
            }
    
    def _build_answer_prompt(self, question: str, content: str, file_paths: List[str], source_file_name: str = None) -> str:
        """构建答案生成提示词"""
        
        import os
        # 使用原始文件名而不是txt文件名
        file_names = [source_file_name] if source_file_name else [os.path.basename(path) for path in file_paths]
        
        try:
            from config.prompts import PROSPECTUS_SECTION_ANSWER_PROMPT
        except ImportError:
            import sys
            # 添加knowledge_retrieval路径
            kr_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            sys.path.insert(0, kr_path)
            from config.prompts import PROSPECTUS_SECTION_ANSWER_PROMPT
        
        return PROSPECTUS_SECTION_ANSWER_PROMPT.format(
            question=question,
            file_names=file_names,
            content=content
        )
    
    def _parse_answer_response(self, response_text: str, source_file_name: str = None) -> Dict[str, Any]:
        """解析LLM答案响应"""
        try:
            # 尝试直接解析JSON
            parsed = json.loads(response_text)
            
            # 验证必要字段
            if "answer" in parsed:
                # 使用原始文件名
                default_sources = [source_file_name] if source_file_name else []
                
                return {
                    "success": True,
                    "answer": parsed["answer"],
                    "sources": parsed.get("sources", default_sources),
                    "content_analysis": parsed.get("content_analysis", "")
                }
            else:
                print("[AnswerGenerator] JSON缺少必要字段 'answer'")
                return {
                    "success": False,
                    "answer": "根据检索内容无法找到相关信息",
                    "sources": [],
                    "content_analysis": "响应格式错误"
                }
                
        except json.JSONDecodeError as e:
            print(f"[AnswerGenerator] JSON解析失败: {e}")
            
            # 如果JSON解析失败，尝试直接使用响应文本作为答案
            if response_text and response_text.strip():
                default_sources = [source_file_name] if source_file_name else []
                return {
                    "success": True,
                    "answer": response_text.strip(),
                    "sources": default_sources,
                    "content_analysis": "JSON格式解析失败，返回原始内容"
                }
            else:
                return {
                    "success": False,
                    "answer": "根据检索内容无法找到相关信息",
                    "sources": [],
                    "content_analysis": "响应为空或格式错误"
                }
    
    def _setup_llm(self):
        """设置LLM客户端"""
        try:
            # 尝试不同的导入路径
            try:
                from config.model_config import MODEL_CONFIG
            except ImportError:
                import sys
                import os
                # 添加knowledge_retrieval路径
                kr_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                sys.path.insert(0, kr_path)
                from config.model_config import MODEL_CONFIG
            
            # 获取ali qwen-long配置
            ali_config = MODEL_CONFIG.get("ali", {})
            qwen_config = ali_config.get("qwen-long", {})
            
            if not qwen_config:
                print("[AnswerGenerator] ❌ali qwen-long模型配置未找到")
                return
            
            # 创建客户端
            self.client = OpenAI(
                api_key=qwen_config["api_key"],
                base_url=qwen_config["base_url"]
            )
            
            self.model = qwen_config["model"]
            
            print("[AnswerGenerator] ✅ ali qwen-long客户端初始化成功")
            
        except Exception as e:
            print(f"[AnswerGenerator] ❌ LLM设置失败: {e}")
            import traceback
            traceback.print_exc()
            self.client = None
            self.model = None


# 测试函数
if __name__ == "__main__":
    generator = AnswerGenerator()
    
    # 测试答案生成
    test_question = "基金的管理费率是多少？"
    test_content = """
    基金费用与税收
    
    基金管理费按基金资产净值的0.3%年费率计提。
    基金托管费按基金资产净值的0.01%年费率计提。
    """
    test_files = ["基金费用与税收.txt"]
    
    print(f"=== 测试答案生成 ===")
    result = generator.generate_answer(test_question, test_content, test_files)
    print(f"生成结果: {result}")
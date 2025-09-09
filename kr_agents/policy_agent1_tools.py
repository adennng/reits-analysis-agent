# kr_agents/policy_agent1_tools.py
"""
政策文件Agent1专门工具集合
为政策文件主控调度器Agent提供两个核心工具：
1. 政策文件问题拆分工具
2. 政策文件最终答案生成工具
"""

import sys
import os
import json
from typing import Dict, Any, List

# 添加路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

try:
    from agents import function_tool
except ImportError:
    # For testing purposes, create mock decorator
    def function_tool(func):
        return func

# 导入配置和工具
from config.prompts import (
    POLICY_QUESTION_SPLITTING_PROMPT,
    POLICY_FINAL_ANSWER_GENERATION_PROMPT
)
from config.model_config import get_deepseek_v3_model

print("[PolicyAgent1Tools] 开始初始化政策文件Agent1专门工具")

# ==================== 专业化工具类 ====================

class PolicyQuestionSplitter:
    """政策文件专用问题拆分工具"""
    
    def __init__(self, model):
        self.model = model
        self.prompt_template = POLICY_QUESTION_SPLITTING_PROMPT
        self.openai_client = None
        self._initialized = False
        print("[PolicyQuestionSplitter] 政策文件问题拆分工具初始化完成")
    
    def _setup_llm_client(self) -> Dict[str, Any]:
        """设置LLM客户端"""
        try:
            if self.model is None:
                self.model = get_deepseek_v3_model()
                if self.model is None:
                    return {
                        "success": False,
                        "error": "无法创建deepseek-v3模型"
                    }
            
            # 获取底层的OpenAI客户端
            if hasattr(self.model, 'openai_client'):
                self.openai_client = self.model.openai_client
            else:
                from config.model_config import MODEL_CONFIG
                from openai import OpenAI
                
                config = MODEL_CONFIG.get("ali", {}).get("deepseek-v3", {})
                if not config:
                    return {
                        "success": False,
                        "error": "deepseek-v3配置未找到"
                    }
                
                self.openai_client = OpenAI(
                    api_key=config['api_key'],
                    base_url=config['base_url']
                )
            
            self._initialized = True
            print("[PolicyQuestionSplitter] LLM客户端设置成功")
            return {
                "success": True,
                "model": "deepseek-v3"
            }
            
        except Exception as e:
            error_msg = f"LLM客户端设置失败: {str(e)}"
            print(f"[PolicyQuestionSplitter] {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
    def _call_llm(self, prompt: str, max_tokens: int = 4096) -> Dict[str, Any]:
        """调用LLM获取响应"""
        try:
            if not self._initialized:
                setup_result = self._setup_llm_client()
                if not setup_result["success"]:
                    return {
                        "success": False,
                        "error": setup_result["error"]
                    }
            
            response = self.openai_client.chat.completions.create(
                model="deepseek-v3",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=max_tokens
            )
            
            raw_response = response.choices[0].message.content.strip()
            
            return {
                "success": True,
                "response": raw_response
            }
            
        except Exception as e:
            error_msg = f"LLM调用失败: {str(e)}"
            print(f"[PolicyQuestionSplitter] {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """解析JSON响应"""
        try:
            # 尝试直接解析JSON
            try:
                parsed = json.loads(response_text.strip())
                return {
                    "success": True,
                    "data": parsed
                }
            except json.JSONDecodeError:
                # 尝试提取JSON内容
                import re
                
                # 查找JSON块
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    json_text = json_match.group(0)
                    parsed = json.loads(json_text)
                    return {
                        "success": True,
                        "data": parsed
                    }
                else:
                    return {
                        "success": False,
                        "error": "响应中未找到有效的JSON内容"
                    }
                    
        except Exception as e:
            return {
                "success": False,
                "error": f"JSON解析失败: {str(e)}"
            }
    
    async def split(self, question: str) -> dict:
        """
        政策文件问题拆分
        
        Args:
            question: 用户的政策问题
            
        Returns:
            {
                "success": True,
                "questions": ["子问题1", "子问题2", ...],
                "analysis": "拆分分析说明",
                "total_sub_questions": 2
            }
        """
        print(f"[PolicyQuestionSplitter] 开始政策文件问题拆分")
        print(f"  问题: {question}")
        
        try:
            # 构建提示词
            prompt = self.prompt_template.format(question=question)
            
            # 调用LLM进行分析
            llm_result = self._call_llm(prompt, max_tokens=4096)
            if not llm_result["success"]:
                return {
                    "success": False,
                    "error": f"LLM分析失败: {llm_result['error']}",
                    "questions": [question],  # fallback到原问题
                    "analysis": "LLM调用失败，使用原问题",
                    "total_sub_questions": 1
                }
            
            # 解析JSON响应
            parse_result = self._parse_json_response(llm_result["response"])
            if not parse_result["success"]:
                return {
                    "success": False,
                    "error": f"响应解析失败: {parse_result['error']}",
                    "questions": [question],  # fallback到原问题
                    "analysis": "JSON解析失败，使用原问题",
                    "total_sub_questions": 1
                }
            
            result_data = parse_result["data"]
            
            # 验证和格式化结果
            questions = result_data.get("questions", [question])
            analysis = result_data.get("analysis", "")
            total_sub_questions = result_data.get("total_sub_questions", len(questions))
            
            print(f"[PolicyQuestionSplitter] 政策文件问题拆分完成，生成 {len(questions)} 个子问题")
            print(f"[PolicyQuestionSplitter] 拆分分析: {analysis}")
            
            return {
                "success": True,
                "questions": questions,
                "analysis": analysis,
                "total_sub_questions": total_sub_questions
            }
            
        except Exception as e:
            error_msg = f"政策文件问题拆分异常: {str(e)}"
            print(f"[PolicyQuestionSplitter] {error_msg}")
            import traceback
            traceback.print_exc()
            
            return {
                "success": False,
                "error": error_msg,
                "questions": [question],  # fallback到原问题
                "analysis": "拆分过程异常，使用原问题",
                "total_sub_questions": 1
            }

class PolicyFinalAnswerGenerator:
    """政策文件专用最终答案生成工具"""
    
    def __init__(self, model):
        self.model = model
        self.prompt_template = POLICY_FINAL_ANSWER_GENERATION_PROMPT
        self.openai_client = None
        self._initialized = False
        print("[PolicyFinalAnswerGenerator] 政策文件最终答案生成工具初始化完成")
    
    def _setup_llm_client(self) -> Dict[str, Any]:
        """设置LLM客户端"""
        try:
            if self.model is None:
                self.model = get_deepseek_v3_model()
                if self.model is None:
                    return {
                        "success": False,
                        "error": "无法创建deepseek-v3模型"
                    }
            
            # 获取底层的OpenAI客户端
            if hasattr(self.model, 'openai_client'):
                self.openai_client = self.model.openai_client
            else:
                from config.model_config import MODEL_CONFIG
                from openai import OpenAI
                
                config = MODEL_CONFIG.get("ali", {}).get("deepseek-v3", {})
                if not config:
                    return {
                        "success": False,
                        "error": "deepseek-v3配置未找到"
                    }
                
                self.openai_client = OpenAI(
                    api_key=config['api_key'],
                    base_url=config['base_url']
                )
            
            self._initialized = True
            print("[PolicyFinalAnswerGenerator] LLM客户端设置成功")
            return {
                "success": True,
                "model": "deepseek-v3"
            }
            
        except Exception as e:
            error_msg = f"LLM客户端设置失败: {str(e)}"
            print(f"[PolicyFinalAnswerGenerator] {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
    def _call_llm(self, prompt: str, max_tokens: int = 8192) -> Dict[str, Any]:
        """调用LLM获取响应"""
        try:
            if not self._initialized:
                setup_result = self._setup_llm_client()
                if not setup_result["success"]:
                    return {
                        "success": False,
                        "error": setup_result["error"]
                    }
            
            response = self.openai_client.chat.completions.create(
                model="deepseek-v3",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=max_tokens
            )
            
            raw_response = response.choices[0].message.content.strip()
            
            return {
                "success": True,
                "response": raw_response
            }
            
        except Exception as e:
            error_msg = f"LLM调用失败: {str(e)}"
            print(f"[PolicyFinalAnswerGenerator] {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
    def _parse_text_response(self, response_text: str) -> Dict[str, Any]:
        """解析文本响应（不再是JSON）"""
        try:
            # 直接返回文本内容，不需要JSON解析
            if response_text and response_text.strip():
                return {
                    "success": True,
                    "text": response_text.strip()
                }
            else:
                return {
                    "success": False,
                    "error": "响应内容为空"
                }
                    
        except Exception as e:
            return {
                "success": False,
                "error": f"文本解析失败: {str(e)}"
            }
    
    async def generate(self, original_question: str, agent2_result: dict) -> str:
        """
        政策文件最终答案生成 - 现在返回直接的用户可读文本
        
        Args:
            original_question: 用户的原始政策问题
            agent2_result: 政策文件Agent2返回的完整检索结果
            
        Returns:
            str: 直接的用户可读文本，包含答案和格式化的参考文件列表
        """
        print(f"[PolicyFinalAnswerGenerator] 开始生成政策文件最终答案")
        print(f"  原始问题: {original_question}")
        print(f"  Agent2结果成功数: {agent2_result.get('successful_queries', 0)}")
        print(f"  Agent2结果失败数: {agent2_result.get('failed_queries', 0)}")
        
        try:
            # 准备LLM提示词，传递完整的Agent2结果
            import json as json_module
            prompt = self.prompt_template.format(
                original_question=original_question,
                agent2_result=json_module.dumps(agent2_result, ensure_ascii=False, indent=2)
            )
            
            # 调用LLM生成答案
            llm_result = self._call_llm(prompt, max_tokens=8192)
            if not llm_result["success"]:
                # LLM调用失败时的fallback处理
                return self._generate_fallback_text_answer(agent2_result, llm_result["error"])
            
            # 解析文本响应（不再是JSON）
            parse_result = self._parse_text_response(llm_result["response"])
            if not parse_result["success"]:
                # 解析失败时生成备用答案
                return self._generate_fallback_text_answer(agent2_result, f"文本解析失败: {parse_result['error']}")
            
            # 直接返回LLM生成的自然文本
            final_text = parse_result["text"]
            
            print("[PolicyFinalAnswerGenerator] 政策文件最终答案生成完成")
            print(f"  生成文本长度: {len(final_text)}")
            
            return final_text
            
        except Exception as e:
            error_msg = f"政策文件最终答案生成异常: {str(e)}"
            print(f"[PolicyFinalAnswerGenerator] {error_msg}")
            import traceback
            traceback.print_exc()
            
            return self._generate_fallback_text_answer(agent2_result, error_msg)
    
    def _generate_fallback_text_answer(self, agent2_result: dict, error_msg: str) -> str:
        """生成文本格式的fallback答案"""
        print(f"[PolicyFinalAnswerGenerator] 生成文本格式fallback答案，错误: {error_msg}")
        
        # 尝试从Agent2结果中提取有用信息
        try:
            if agent2_result.get("results"):
                successful_results = [r for r in agent2_result["results"] if r.get("is_found")]
                if successful_results:
                    # 有成功的结果，组合答案和参考文件
                    answers = []
                    all_reference_files = []
                    
                    for result in successful_results:
                        if result.get("answer"):
                            answers.append(result["answer"])
                        if result.get("reference_files"):
                            all_reference_files.extend(result["reference_files"])
                    
                    if answers:
                        # 组合答案内容
                        answer_text = "\n\n".join(answers)
                        
                        # 格式化参考文件列表
                        reference_text = self._format_reference_files(all_reference_files)
                        
                        # 组合最终文本
                        if reference_text:
                            return f"{answer_text}\n\n{reference_text}"
                        else:
                            return answer_text
                    else:
                        return "很抱歉，未在政策文件中找到相关答案。"
                else:
                    return "很抱歉，未在政策文件中找到相关答案。"
            else:
                return "很抱歉，未在政策文件中找到相关答案。"
                
        except Exception as e:
            print(f"[PolicyFinalAnswerGenerator] fallback处理异常: {e}")
            return "很抱歉，未在政策文件中找到相关答案。"
    
    def _format_reference_files(self, reference_files: List[dict]) -> str:
        """格式化参考文件列表为文本"""
        if not reference_files:
            return ""
        
        # 去重参考文件
        unique_files = []
        seen_titles = set()
        
        for file_info in reference_files:
            if isinstance(file_info, dict):
                title = file_info.get("document_title", "")
                if title and title not in seen_titles:
                    unique_files.append(file_info)
                    seen_titles.add(title)
        
        if not unique_files:
            return ""
        
        # 格式化为编号列表
        reference_lines = ["参考文件："]
        for i, file_info in enumerate(unique_files, 1):
            document_title = file_info.get("document_title", "未知文件")
            publish_date = file_info.get("publish_date", "未知日期")
            issuing_agency = file_info.get("issuing_agency", "未知机构")
            website = file_info.get("website", "")
            
            # 格式：序号. 文档标题 (发布日期, 发布机构, 来源: 网站链接)
            line = f"{i}. {document_title} ({publish_date}, {issuing_agency}"
            if website:
                line += f", 来源: {website}"
            line += ")"
            
            reference_lines.append(line)
        
        return "\n".join(reference_lines)
    
    def _generate_fallback_answer(self, agent2_result: dict, error_msg: str, raw_response: str = "") -> dict:
        """生成fallback答案 - 保留原有接口兼容性"""
        print(f"[PolicyFinalAnswerGenerator] 生成fallback答案，错误: {error_msg}")
        
        # 尝试从Agent2结果中提取有用信息
        fallback_answer = ""
        reference_files = []
        
        try:
            if agent2_result.get("results"):
                successful_results = [r for r in agent2_result["results"] if r.get("is_found")]
                if successful_results:
                    # 有成功的结果，尝试简单组合
                    answers = []
                    for result in successful_results:
                        if result.get("answer"):
                            answers.append(result["answer"])
                        if result.get("reference_files"):
                            reference_files.extend(result["reference_files"])
                    
                    if answers:
                        fallback_answer = "根据政策文件检索结果：\n\n" + "\n\n".join(answers)
                    else:
                        fallback_answer = "检索到相关政策内容，但答案整合失败"
                else:
                    fallback_answer = "未在政策文件中找到相关规定"
            else:
                fallback_answer = "政策文件检索未返回有效结果"
                
        except Exception as e:
            print(f"[PolicyFinalAnswerGenerator] fallback处理异常: {e}")
            fallback_answer = f"政策文件答案生成失败：{error_msg}"
        
        # 如果有raw_response且不为空，优先使用
        if raw_response and raw_response.strip():
            fallback_answer = raw_response
        
        # 去重参考文件
        unique_files = []
        seen_titles = set()
        for file_info in reference_files:
            if isinstance(file_info, dict):
                title = file_info.get("document_title", "")
                if title and title not in seen_titles:
                    unique_files.append(file_info)
                    seen_titles.add(title)
        
        return {
            "final_answer": fallback_answer,
            "reference_files": unique_files
        }
    

# ==================== 导出接口 ====================

# 导出接口
__all__ = [
    'PolicyQuestionSplitter',
    'PolicyFinalAnswerGenerator'
]

if __name__ == "__main__":
    print("🧪 测试政策文件Agent1工具")
    
    # 简单的初始化测试
    model = get_deepseek_v3_model()
    
    print("\n1. 测试PolicyQuestionSplitter")
    splitter = PolicyQuestionSplitter(model)
    print("✅ PolicyQuestionSplitter初始化成功")
    
    print("\n2. 测试PolicyFinalAnswerGenerator")
    generator = PolicyFinalAnswerGenerator(model)
    print("✅ PolicyFinalAnswerGenerator初始化成功")
    
    print("\n🎉 政策文件Agent1工具测试完成！")
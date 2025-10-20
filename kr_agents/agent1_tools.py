# kr_agents/agent1_tools.py
"""
Agent1专门工具集合
为主控调度器Agent提供三个核心工具：
1. 基金代码识别工具
2. 问题拆分和参数组织工具
3. 最终答案生成工具
"""

import sys
import os
import json
from typing import Dict, Any, List, Optional

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
    FUND_CODE_IDENTIFICATION_PROMPT,
    FINAL_ANSWER_GENERATION_PROMPT,
    QUESTION_SPLITTING_AND_PARAMETER_ORGANIZATION_PROMPT
)
from config.model_config import get_deepseek_v3_model

print("[Agent1Tools] 开始初始化Agent1专门工具")

# ==================== 专业化工具类 ====================

class FundCodeIdentifier:
    """专业的基金代码识别工具"""
    
    def __init__(self, model):
        self.model = model
        self.prompt_template = FUND_CODE_IDENTIFICATION_PROMPT
        self.openai_client = None
        self._initialized = False
        print("[FundCodeIdentifier] 基金代码识别工具初始化完成")
    
    def _get_fund_list_from_announcement(self) -> Dict[str, Any]:
        """
        从announcement数据库获取基金列表
        
        Returns:
            Dict[str, Any]: 包含基金信息列表和状态的字典
        """
        print("[FundCodeIdentifier] 开始从announcement数据库获取基金列表")
        
        try:
            # 导入数据库连接器
            from business_tools import get_database_connector
            
            # 获取数据库连接器
            connector = get_database_connector()
            
            # 执行查询
            sql = "SELECT fund_code, short_name FROM product_info"
            results = connector.execute_query(sql, database="announcement")
            
            # 过滤掉包含None值的记录，确保数据完整性
            if results:
                filtered_results = []
                for fund in results:
                    if (fund.get('fund_code') is not None and 
                        fund.get('short_name') is not None):
                        filtered_results.append(fund)
                
                print(f"[FundCodeIdentifier] 原始查询结果: {len(results)} 只基金")
                print(f"[FundCodeIdentifier] 过滤后有效基金: {len(filtered_results)} 只基金")
                results = filtered_results
            
            result_data = {
                "success": True,
                "data": results,
                "count": len(results),
                "message": f"查询成功，共找到 {len(results)} 只基金"
            }
            
            print(f"[FundCodeIdentifier] 基金信息获取成功，共 {len(results)} 只基金")
            
            return result_data
            
        except Exception as e:
            error_msg = f"从announcement数据库查询基金信息失败: {str(e)}"
            print(f"[FundCodeIdentifier] {error_msg}")
            
            return {
                "success": False,
                "data": [],
                "count": 0,
                "error": error_msg
            }
    
    def _setup_llm_client(self) -> Dict[str, Any]:
        """设置LLM客户端"""
        try:
            if self.model is None:
                self.model = get_deepseek_v3_model()
                if self.model is None:
                    return {
                        "success": False,
                        "error": "无法创建deepseek_v3模型"
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
            print("[FundCodeIdentifier] LLM客户端设置成功")
            return {
                "success": True,
                "model": "deepseek-v3"
            }
            
        except Exception as e:
            error_msg = f"LLM客户端设置失败: {str(e)}"
            print(f"[FundCodeIdentifier] {error_msg}")
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
                temperature=0.0,
                max_tokens=max_tokens
            )
            
            raw_response = response.choices[0].message.content.strip()
            
            return {
                "success": True,
                "response": raw_response
            }
            
        except Exception as e:
            error_msg = f"LLM调用失败: {str(e)}"
            print(f"[FundCodeIdentifier] {error_msg}")
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
    
    async def identify(self, question: str, context: dict) -> dict:
        """
        基金代码识别
        
        Args:
            question: 用户问题
            context: 完整上下文信息
            
        Returns:
            {
                "success": True,
                "fund_codes": ["508056.SH"],
                "matched_funds": [...],
                "analysis": "识别分析说明",
                "confidence": "high/medium/low"
            }
        """
        print(f"[FundCodeIdentifier] 开始基金代码识别")
        print(f"  问题: {question}")
        print(f"  上下文阶段: {context.get('current_stage', 'unknown')}")
        
        try:
            # 步骤1: 从announcement数据库获取所有基金列表
            fund_list_result = self._get_fund_list_from_announcement()
            if not fund_list_result["success"]:
                return {
                    "success": False,
                    "error": f"获取基金列表失败: {fund_list_result.get('error', '未知错误')}",
                    "fund_codes": [],
                    "matched_funds": [],
                    "analysis": "",
                    "confidence": "low"
                }
            
            fund_list = fund_list_result["data"]
            print(f"[FundCodeIdentifier] 获取到 {len(fund_list)} 只基金信息")
            
            # 步骤2: 准备LLM提示词（包含上下文信息）
            fund_list_text = json.dumps(fund_list, ensure_ascii=False, indent=2)
            context_text = json.dumps(context, ensure_ascii=False, indent=2)
            
            prompt = self.prompt_template.format(
                question=question,
                fund_list=fund_list_text,
                context=context_text
            )
            
            # 步骤3: 调用LLM分析
            llm_result = self._call_llm(prompt, max_tokens=4096)
            if not llm_result["success"]:
                return {
                    "success": False,
                    "error": f"LLM分析失败: {llm_result['error']}",
                    "fund_codes": [],
                    "matched_funds": [],
                    "analysis": "",
                    "confidence": "low"
                }
            
            # 步骤4: 解析JSON响应
            parse_result = self._parse_json_response(llm_result["response"])
            if not parse_result["success"]:
                return {
                    "success": False,
                    "error": f"响应解析失败: {parse_result['error']}",
                    "fund_codes": [],
                    "matched_funds": [],
                    "analysis": "",
                    "confidence": "low"
                }
            
            result_data = parse_result["data"]
            
            # 步骤5: 验证和格式化结果
            fund_codes = result_data.get("fund_codes", [])
            matched_funds = result_data.get("matched_funds", [])
            analysis = result_data.get("analysis", "")
            confidence = result_data.get("confidence", "medium")
            
            print(f"[FundCodeIdentifier] 基金代码识别完成，识别到 {len(fund_codes)} 只基金")
            print(f"[FundCodeIdentifier] 基金代码: {fund_codes}")
            print(f"[FundCodeIdentifier] 置信度: {confidence}")
            
            return {
                "success": True,
                "fund_codes": fund_codes,
                "matched_funds": matched_funds,
                "analysis": analysis,
                "confidence": confidence
            }
            
        except Exception as e:
            error_msg = f"基金代码识别异常: {str(e)}"
            print(f"[FundCodeIdentifier] {error_msg}")
            import traceback
            traceback.print_exc()
            
            return {
                "success": False,
                "error": error_msg,
                "fund_codes": [],
                "matched_funds": [],
                "analysis": "",
                "confidence": "low"
            }


class QuestionSplitter:
    """专业的问题拆分和参数组织工具"""
    
    def __init__(self, model):
        self.model = model
        self.prompt_template = QUESTION_SPLITTING_AND_PARAMETER_ORGANIZATION_PROMPT
        self.openai_client = None
        self._initialized = False
        print("[QuestionSplitter] 问题拆分工具初始化完成")
    
    def _setup_llm_client(self) -> Dict[str, Any]:
        """设置LLM客户端"""
        try:
            if self.model is None:
                self.model = get_deepseek_v3_model()
                if self.model is None:
                    return {
                        "success": False,
                        "error": "无法创建deepseek_v3模型"
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
            print("[QuestionSplitter] LLM客户端设置成功")
            return {
                "success": True,
                "model": "deepseek-v3"
            }
            
        except Exception as e:
            error_msg = f"LLM客户端设置失败: {str(e)}"
            print(f"[QuestionSplitter] {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
    def _call_llm(self, prompt: str, max_tokens: int = 6000) -> Dict[str, Any]:
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
                temperature=0.0,
                max_tokens=max_tokens
            )
            
            raw_response = response.choices[0].message.content.strip()
            
            return {
                "success": True,
                "response": raw_response
            }
            
        except Exception as e:
            error_msg = f"LLM调用失败: {str(e)}"
            print(f"[QuestionSplitter] {error_msg}")
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
    
    async def split(self, question: str, fund_codes: list, file_names: list, context: dict) -> dict:
        """
        问题拆分和参数组织
        
        Args:
            question: 原始问题
            fund_codes: 基金代码列表
            file_names: 文件名列表
            context: 完整上下文信息
            
        Returns:
            {
                "success": True,
                "query_params": [...],
                "analysis": "拆分分析说明",
                "total_sub_questions": 4
            }
        """
        print(f"[QuestionSplitter] 开始问题拆分和参数组织")
        print(f"  问题: {question}")
        print(f"  基金代码: {fund_codes}")
        print(f"  基金映射关系: {context.get('fund_mapping', {})}")
        print(f"  文件名列表: {file_names}")
        print(f"  是否招募说明书查询: {context.get('is_prospectus_query', False)}")
        print(f"  上下文阶段: {context.get('current_stage', 'unknown')}")
        
        try:
            # 准备输入参数
            fund_codes_str = json.dumps(fund_codes, ensure_ascii=False)
            fund_mapping_str = json.dumps(context.get('fund_mapping', {}), ensure_ascii=False, indent=2)
            file_names_str = json.dumps(file_names, ensure_ascii=False, indent=2)
            is_prospectus_query = context.get('is_prospectus_query', False)
            
            # 构建提示词
            prompt = self.prompt_template.format(
                original_question=question,
                fund_codes=fund_codes_str,
                fund_mapping=fund_mapping_str,
                file_names=file_names_str,
                is_prospectus_query=is_prospectus_query
            )
            
            # 调用LLM进行分析
            llm_result = self._call_llm(prompt, max_tokens=6000)
            if not llm_result["success"]:
                return {
                    "success": False,
                    "error": f"LLM分析失败: {llm_result['error']}",
                    "query_params": [],
                    "analysis": "",
                    "total_sub_questions": 0
                }
            
            # 解析JSON响应
            parse_result = self._parse_json_response(llm_result["response"])
            if not parse_result["success"]:
                return {
                    "success": False,
                    "error": f"响应解析失败: {parse_result['error']}",
                    "query_params": [],
                    "analysis": "",
                    "total_sub_questions": 0
                }
            
            result_data = parse_result["data"]
            
            # 验证和格式化结果
            if "query_params" in result_data and isinstance(result_data["query_params"], list):
                # 处理参数格式，确保符合Agent2的要求
                formatted_params = []
                for param in result_data["query_params"]:
                    formatted_param = {
                        "fund_code": param.get("fund_code", ""),
                        "question": param.get("question", ""),
                        "file_name": param.get("file_name")
                    }
                    # 处理null字符串
                    if formatted_param["file_name"] == "null":
                        formatted_param["file_name"] = None
                    formatted_params.append(formatted_param)
                
                print(f"[QuestionSplitter] 问题拆分成功，生成 {len(formatted_params)} 个查询参数")
                print(f"[QuestionSplitter] 拆分分析: {result_data.get('analysis', '')}")
                
                return {
                    "success": True,
                    "query_params": formatted_params,
                    "analysis": result_data.get("analysis", ""),
                    "total_sub_questions": result_data.get("total_sub_questions", len(formatted_params))
                }
            else:
                return {
                    "success": False,
                    "error": "解析结果格式不正确: 缺少query_params字段",
                    "query_params": [],
                    "analysis": "",
                    "total_sub_questions": 0
                }
                
        except Exception as e:
            error_msg = f"问题拆分异常: {str(e)}"
            print(f"[QuestionSplitter] {error_msg}")
            import traceback
            traceback.print_exc()
            
            return {
                "success": False,
                "error": error_msg,
                "query_params": [],
                "analysis": "",
                "total_sub_questions": 0
            }

class FileLinkEnhancer:
    """文件链接增强工具 - 为参考文件添加链接"""
    
    def __init__(self):
        self.connector = None
        self._initialized = False
        print("[FileLinkEnhancer] 文件链接增强工具初始化完成")
    
    def _setup_db_connection(self) -> Dict[str, Any]:
        """设置数据库连接"""
        try:
            from business_tools import get_database_connector
            
            self.connector = get_database_connector()
            self._initialized = True
            print("[FileLinkEnhancer] 数据库连接设置成功")
            return {"success": True}
        except Exception as e:
            error_msg = f"数据库连接设置失败: {str(e)}"
            print(f"[FileLinkEnhancer] {error_msg}")
            return {"success": False, "error": error_msg}
    
    def get_file_link(self, file_name: str) -> str:
        """
        根据文件名查询链接
        
        Args:
            file_name: 完整的PDF文件名，如"xxx.pdf"
            
        Returns:
            str: 链接URL，如果查询失败返回空字符串
        """
        try:
            print(f"[FileLinkEnhancer] 🔍 开始查询文件链接: {file_name}")
            
            if not self._initialized:
                print(f"[FileLinkEnhancer] 🔍 首次查询，初始化数据库连接...")
                setup_result = self._setup_db_connection()
                if not setup_result["success"]:
                    print(f"[FileLinkEnhancer] ❌ 数据库连接初始化失败: {setup_result.get('error', '未知错误')}")
                    return ""
                print(f"[FileLinkEnhancer] ✅ 数据库连接初始化成功")
            
            # 查询announcement数据库的processed_files表
            # 注意：需要手动转义文件名中的单引号防止SQL注入
            escaped_file_name = file_name.replace("'", "\\'")
            sql = f"SELECT announcement_link FROM processed_files WHERE file_name = '{escaped_file_name}' LIMIT 1"
            print(f"[FileLinkEnhancer] 🔍 执行SQL查询: {sql}")
            print(f"[FileLinkEnhancer] 🔍 查询数据库: announcement")
            
            results = self.connector.execute_query(sql, database="announcement")
            print(f"[FileLinkEnhancer] 🔍 数据库返回结果数: {len(results) if results else 0}")
            
            if results and len(results) > 0:
                link = results[0].get('announcement_link')
                print(f"[FileLinkEnhancer] 🔍 查询结果详情: {results[0]}")
                
                if link and link.strip():
                    link_cleaned = link.strip()
                    print(f"[FileLinkEnhancer] ✅ 成功找到文件链接:")
                    print(f"[FileLinkEnhancer]    文件名: {file_name}")
                    print(f"[FileLinkEnhancer]    链接: {link_cleaned}")
                    return link_cleaned
                else:
                    print(f"[FileLinkEnhancer] ⚠️ 文件记录存在但链接字段为空: {file_name}")
                    return ""
            else:
                print(f"[FileLinkEnhancer] ⚠️ 数据库中未找到文件记录: {file_name}")
                print(f"[FileLinkEnhancer] 💡 提示：请检查文件名是否准确，或确认文件是否已导入processed_files表")
                return ""
                
        except Exception as e:
            print(f"[FileLinkEnhancer] ❌ 查询文件链接异常: {file_name}")
            print(f"[FileLinkEnhancer] ❌ 错误详情: {str(e)}")
            import traceback
            traceback.print_exc()
            return ""
    
    def enhance_answer_with_links(self, answer_text: str) -> str:
        """
        为答案中的参考文件添加Markdown链接
        
        Args:
            answer_text: 原始答案文本，包含"参考文件："部分
            
        Returns:
            str: 增强后的答案文本，参考文件变为Markdown链接格式
        """
        try:
            print(f"[FileLinkEnhancer] 🔄 开始为参考文件添加链接")
            print(f"[FileLinkEnhancer] 🔍 输入文本长度: {len(answer_text)} 字符")
            print(f"[FileLinkEnhancer] 🔍 输入文本预览:")
            preview_text = answer_text[:200] + "..." if len(answer_text) > 200 else answer_text
            print(f"[FileLinkEnhancer]    {preview_text}")
            
            # 使用正则表达式找到参考文件部分
            import re
            
            # 匹配参考文件部分的模式（支持多种可能的格式）
            # 更灵活的模式：允许"参考文件："后面有空格、制表符等空白字符再换行
            pattern = r'参考文件：\s*\n((?:\d+\.\s+.+(?:\n|$))*)'
            match = re.search(pattern, answer_text)
            
            if not match:
                print("[FileLinkEnhancer] ⚠️ 未找到参考文件部分，返回原文本")
                print("[FileLinkEnhancer] 🔍 搜索的正则模式:", pattern)
                return answer_text
            
            print("[FileLinkEnhancer] ✅ 找到参考文件部分，开始解析")
            print(f"[FileLinkEnhancer] 🔍 匹配的参考文件原始内容:")
            print(f"[FileLinkEnhancer]    {match.group(0)}")
            
            # 提取参考文件列表
            references_section = match.group(1)
            print(f"[FileLinkEnhancer] 🔍 提取的文件列表部分:")
            print(f"[FileLinkEnhancer]    {references_section}")
            
            file_pattern = r'(\d+)\.\s+(.+?)(?=\n\d+\.|\n*$)'
            files = re.findall(file_pattern, references_section, re.MULTILINE | re.DOTALL)
            
            if not files:
                print("[FileLinkEnhancer] ⚠️ 未找到具体文件条目，返回原文本")
                print(f"[FileLinkEnhancer] 🔍 使用的文件提取正则: {file_pattern}")
                return answer_text
            
            print(f"[FileLinkEnhancer] ✅ 成功提取到{len(files)}个文件条目:")
            for i, (num, file_name) in enumerate(files):
                print(f"[FileLinkEnhancer]    {i+1}. 序号={num}, 文件名={file_name.strip()}")
            
            # 为每个文件添加链接
            enhanced_references = []
            print(f"[FileLinkEnhancer] 🔄 开始逐个处理文件并查询链接...")
            
            for i, (num, file_name) in enumerate(files):
                file_name = file_name.strip()
                print(f"\n[FileLinkEnhancer] 📁 处理第{i+1}/{len(files)}个文件:")
                print(f"[FileLinkEnhancer]    序号: {num}")
                print(f"[FileLinkEnhancer]    文件名: {file_name}")
                
                # 确保文件名以.pdf结尾（按你的提示，都是PDF文件）
                if not file_name.endswith('.pdf'):
                    print(f"[FileLinkEnhancer] ⚠️ 警告：文件名不是PDF格式: {file_name}")
                
                # 查询文件链接
                print(f"[FileLinkEnhancer] 🔍 开始查询数据库链接...")
                link = self.get_file_link(file_name)
                
                if link:
                    # 生成Markdown链接格式
                    enhanced_file = f"{num}. [{file_name}]({link})"
                    print(f"[FileLinkEnhancer] ✅ 成功生成Markdown链接:")
                    print(f"[FileLinkEnhancer]    原格式: {num}. {file_name}")
                    print(f"[FileLinkEnhancer]    新格式: {enhanced_file}")
                else:
                    # 无链接时保持原格式
                    enhanced_file = f"{num}. {file_name}"
                    print(f"[FileLinkEnhancer] ⚠️ 未找到链接，保持原格式: {enhanced_file}")
                
                enhanced_references.append(enhanced_file)
            
            # 重建参考文件部分
            new_references = "参考文件：\n" + "\n".join(enhanced_references)
            print(f"\n[FileLinkEnhancer] 🔄 重建参考文件部分:")
            print(f"[FileLinkEnhancer] 🔍 原始参考文件部分:")
            print(f"[FileLinkEnhancer]    {match.group(0)}")
            print(f"[FileLinkEnhancer] 🔍 增强后参考文件部分:")
            print(f"[FileLinkEnhancer]    {new_references}")
            
            # 替换原文本中的参考文件部分
            enhanced_answer = answer_text.replace(match.group(0), new_references)
            
            print(f"\n[FileLinkEnhancer] ✅ 链接增强完成!")
            print(f"[FileLinkEnhancer] 📊 处理统计: 总共{len(enhanced_references)}个文件")
            print(f"[FileLinkEnhancer] 📊 成功添加链接: {sum(1 for ref in enhanced_references if '[' in ref and '](' in ref)}个")
            print(f"[FileLinkEnhancer] 📊 保持原格式: {sum(1 for ref in enhanced_references if '[' not in ref or '](' not in ref)}个")
            
            return enhanced_answer
            
        except Exception as e:
            print(f"[FileLinkEnhancer] 增强文件链接失败: {str(e)}")
            import traceback
            traceback.print_exc()
            # 出错时返回原始文本，确保不影响正常流程
            print("[FileLinkEnhancer] 返回原始文本")
            return answer_text

class FinalAnswerGenerator:
    """专业的最终答案生成工具"""
    
    def __init__(self, model):
        self.model = model
        self.prompt_template = FINAL_ANSWER_GENERATION_PROMPT
        self.openai_client = None
        self._initialized = False
        self.file_link_enhancer = FileLinkEnhancer()  # 添加文件链接增强器
        print("[FinalAnswerGenerator] 最终答案生成工具初始化完成")
    
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
            print("[FinalAnswerGenerator] LLM客户端设置成功")
            return {
                "success": True,
                "model": "deepseek-v3"
            }
            
        except Exception as e:
            error_msg = f"LLM客户端设置失败: {str(e)}"
            print(f"[FinalAnswerGenerator] {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
    def _call_llm(self, prompt: str, max_tokens: int = 8000) -> Dict[str, Any]:
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
                temperature=0.0,
                max_tokens=max_tokens
            )
            
            raw_response = response.choices[0].message.content.strip()
            
            return {
                "success": True,
                "response": raw_response
            }
            
        except Exception as e:
            error_msg = f"LLM调用失败: {str(e)}"
            print(f"[FinalAnswerGenerator] {error_msg}")
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
    
    async def generate(
        self,
        question: str,
        all_results: list,
        context: dict,
        precomposed_answer: Optional[str] = None
    ) -> str:
        """
        最终答案生成 - 返回直接用户可读文本
        
        Args:
            question: 原始问题
            all_results: 所有检索结果
            context: 完整上下文信息
            
        Returns:
            str: 直接的用户可读文本答案（包含答案内容和参考文件）
        """
        print(f"[FinalAnswerGenerator] 开始生成最终答案")
        print(f"  原始问题: {question}")
        print(f"  检索结果数: {len(all_results)}")
        print(f"  上下文阶段: {context.get('current_stage', 'unknown')}")
        
        try:
            prepared_answer = precomposed_answer or context.get("precomposed_answer")
            if isinstance(prepared_answer, str):
                prepared_answer = prepared_answer.strip()
            else:
                prepared_answer = None

            if prepared_answer:
                print("[FinalAnswerGenerator] 检测到预生成答案，跳过LLM生成")
                try:
                    enhanced_prepared = self.file_link_enhancer.enhance_answer_with_links(prepared_answer)
                    print("[FinalAnswerGenerator] 预生成答案链接增强完成")
                    return enhanced_prepared
                except Exception as e:
                    print(f"[FinalAnswerGenerator] 预生成答案链接增强失败: {e}，返回原始答案")
                    return prepared_answer

            # 准备LLM提示词，传递完整的上下文信息
            import json as json_module
            prompt = self.prompt_template.format(
                original_question=question,
                retrieval_results=json_module.dumps(all_results, ensure_ascii=False, indent=2),
                context=json_module.dumps(context, ensure_ascii=False, indent=2)
            )
            
            # 调用LLM生成答案 (DeepSeek API max_tokens限制为8192)
            llm_result = self._call_llm(prompt, max_tokens=8192)
            if not llm_result["success"]:
                # LLM失败时，实现fallback逻辑
                print(f"[FinalAnswerGenerator] LLM调用失败: {llm_result.get('error', '未知错误')}")
                return self._generate_fallback_answer(question, all_results)
            
            # 直接返回LLM生成的自然文本
            raw_response = llm_result["response"].strip()
            if raw_response:
                print("[FinalAnswerGenerator] 最终答案生成完成（LLM生成）")
                print(f"[FinalAnswerGenerator] 🔍 LLM原始返回内容长度: {len(raw_response)} 字符")
                print(f"[FinalAnswerGenerator] 🔍 LLM原始返回内容:\n{'='*50}")
                print(raw_response)
                print("=" * 50)
                
                # 🆕 新增：为参考文件添加链接
                try:
                    enhanced_response = self.file_link_enhancer.enhance_answer_with_links(raw_response)
                    print("[FinalAnswerGenerator] 文件链接增强完成")
                    print(f"[FinalAnswerGenerator] 🎯 最终传出内容长度: {len(enhanced_response)} 字符")
                    print(f"[FinalAnswerGenerator] 🎯 最终传出内容:\n{'='*50}")
                    print(enhanced_response)
                    print("=" * 50)
                    return enhanced_response
                except Exception as e:
                    print(f"[FinalAnswerGenerator] 文件链接增强失败: {e}，返回原始答案")
                    print(f"[FinalAnswerGenerator] 🎯 最终传出内容（原始）:\n{'='*50}")
                    print(raw_response)
                    print("=" * 50)
                    return raw_response
            else:
                # LLM返回空内容，使用fallback逻辑
                return self._generate_fallback_answer(question, all_results)
            
        except Exception as e:
            error_msg = f"最终答案生成异常: {str(e)}"
            print(f"[FinalAnswerGenerator] {error_msg}")
            import traceback
            traceback.print_exc()
            
            # 异常时使用fallback逻辑
            return self._generate_fallback_answer(question, all_results)
    
    def _generate_fallback_answer(self, question: str, all_results: list) -> str:
        """
        生成fallback答案 - 当LLM失败时的备用逻辑
        
        Args:
            question: 原始问题
            all_results: 所有检索结果
            
        Returns:
            str: fallback答案文本
        """
        print("[FinalAnswerGenerator] 使用fallback逻辑生成答案")
        print(f"[FinalAnswerGenerator] 总结果数量: {len(all_results)}")
        
        try:
            # 检查是否有成功的检索结果
            has_successful_results = False
            successful_answers = []
            all_sources = set()
            
            for i, result in enumerate(all_results):
                print(f"[FinalAnswerGenerator] 处理结果{i+1}: type={type(result)}, success={result.get('success') if isinstance(result, dict) else 'N/A'}")
                if isinstance(result, dict) and result.get("success") and result.get("results"):
                    print(f"[FinalAnswerGenerator] 结果{i+1}包含{len(result['results'])}个查询项")
                    for j, item in enumerate(result["results"]):
                        print(f"[FinalAnswerGenerator] 查询项{j+1}: is_found={item.get('is_found')}, answer_length={len(item.get('answer', '')) if item.get('answer') else 0}")
                        # 检查 is_found 字段来判断是否找到答案
                        if item.get("is_found") and item.get("answer") and item.get("answer").strip():
                            has_successful_results = True
                            successful_answers.append(item.get("answer", "").strip())
                            if item.get("sources"):
                                all_sources.update(item["sources"])
                            print(f"[FinalAnswerGenerator] 找到成功结果: {item.get('answer', '')[:100]}...")
            
            if has_successful_results:
                # 有成功结果时，自动解析拼成文字答案
                print("[FinalAnswerGenerator] 发现成功结果，自动拼接答案")
                
                # 去重并整合答案
                unique_answers = []
                for answer in successful_answers:
                    # 简单去重，避免重复内容
                    if answer not in unique_answers:
                        unique_answers.append(answer)
                
                # 拼接答案
                if len(unique_answers) == 1:
                    final_text = unique_answers[0]
                else:
                    # 多个答案时分别列出
                    final_text = "\n\n".join(unique_answers)
                
                # 添加参考文件
                if all_sources:
                    sources_list = list(all_sources)
                    sources_text = "\n\n参考文件：\n" + "\n".join([f"{i+1}. {source}" for i, source in enumerate(sources_list)])
                    final_text += sources_text
                
                print(f"[FinalAnswerGenerator] 🔍 Fallback原始答案长度: {len(final_text)} 字符")
                print(f"[FinalAnswerGenerator] 🔍 Fallback原始答案:\n{'='*50}")
                print(final_text)
                print("=" * 50)
                
                # 🆕 新增：为fallback答案也添加链接增强
                try:
                    enhanced_final_text = self.file_link_enhancer.enhance_answer_with_links(final_text)
                    print("[FinalAnswerGenerator] fallback答案链接增强完成")
                    print(f"[FinalAnswerGenerator] 🎯 最终传出内容（Fallback增强后）长度: {len(enhanced_final_text)} 字符")
                    print(f"[FinalAnswerGenerator] 🎯 最终传出内容（Fallback增强后）:\n{'='*50}")
                    print(enhanced_final_text)
                    print("=" * 50)
                    return enhanced_final_text
                except Exception as e:
                    print(f"[FinalAnswerGenerator] fallback答案链接增强失败: {e}，返回原始答案")
                    print(f"[FinalAnswerGenerator] 🎯 最终传出内容（Fallback原始）:\n{'='*50}")
                    print(final_text)
                    print("=" * 50)
                    return final_text
            else:
                # 没有成功结果时，返回兜底回答
                print("[FinalAnswerGenerator] 未发现成功结果，返回兜底回答")
                return "很抱歉，未找到相关答案。"
                
        except Exception as e:
            print(f"[FinalAnswerGenerator] fallback逻辑异常: {e}")
            return "很抱歉，未找到相关答案。"
    


# 导出工具函数
__all__ = [
    'FundCodeIdentifier',       # 基金代码识别专业化工具类
    'QuestionSplitter',         # 问题拆分专业化工具类
    'FileLinkEnhancer',         # 文件链接增强工具类
    'FinalAnswerGenerator',     # 最终答案生成专业化工具类
]

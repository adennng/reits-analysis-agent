# tools/policy_params_generator.py
"""
政策文件检索参数生成器 - 调用大模型生成VECTOR_QUESTION和KEYWORDS
"""
import sys
import os
import json

# 添加路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))))
sys.path.insert(0, project_root)

from knowledge_retrieval.config.prompts import POLICY_SEARCH_PARAMS_GENERATION_PROMPT

class PolicySearchParams:
    """政策文件检索参数"""
    def __init__(self, vector_question: str, keywords: list):
        self.vector_question = vector_question
        self.keywords = keywords

class PolicySearchParamsGenerator:
    """政策文件检索参数生成器 - 使用LLM生成优化的VECTOR_QUESTION和KEYWORDS"""
    
    def __init__(self):
        print("[PolicySearchParamsGenerator] 初始化完成")
        self._setup_llm()
    
    def _setup_llm(self):
        """设置LLM客户端"""
        try:
            from knowledge_retrieval.config.model_config import MODEL_CONFIG
            from openai import OpenAI
            
            # 使用配置中的LLM设置
            llm_config = MODEL_CONFIG["ali"]["deepseek-v3"]  # 或者使用您配置的其他模型
            self.llm_client = OpenAI(
                api_key=llm_config["api_key"],
                base_url=llm_config["base_url"]
            )
            self.model_name = llm_config["model"]
            print(f"[PolicySearchParamsGenerator] LLM客户端设置完成，使用模型: {self.model_name}")
            
        except Exception as e:
            print(f"[PolicySearchParamsGenerator] LLM设置失败: {e}")
            self.llm_client = None
            self.model_name = None
    
    def generate_search_params(self, question: str, verbose: bool = False) -> PolicySearchParams:
        """
        使用大模型生成政策文件混合检索参数
        
        Args:
            question: 用户问题
            verbose: 是否打印详细信息
            
        Returns:
            PolicySearchParams: 包含vector_question和keywords的参数
        """
        print(f"[PolicySearchParamsGenerator] 开始调用LLM生成检索参数: {question}")
        
        if not self.llm_client:
            print("[PolicySearchParamsGenerator] LLM未设置，使用备用方案")
            return self._fallback_generate_params(question)
        
        try:
            # 构建针对政策文件的提示词
            prompt = POLICY_SEARCH_PARAMS_GENERATION_PROMPT.format(question=question)
            
            if verbose:
                print(f"[PolicySearchParamsGenerator] 📝 完整提示词内容:")
                print("=" * 80)
                print(prompt)
                print("=" * 80)
                print(f"[PolicySearchParamsGenerator] 📥 LLM调用参数:")
                print(f"  - 模型: {self.model_name}")
                print(f"  - 温度: 0.0")
                print(f"  - 提示词长度: {len(prompt)} 字符")
            
            # 调用LLM
            response = self.llm_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0  # 使用确定性输出
            )
            
            llm_output = response.choices[0].message.content.strip()
            
            if verbose:
                print(f"[PolicySearchParamsGenerator] 📤 LLM响应信息:")
                print(f"  - 输出长度: {len(llm_output)} 字符")
                print(f"  - 使用token数: {response.usage.total_tokens if hasattr(response, 'usage') else '未知'}")
                print(f"[PolicySearchParamsGenerator] 🔍 LLM完整原始输出:")
                print("-" * 80)
                print(llm_output)
                print("-" * 80)
            else:
                print(f"[PolicySearchParamsGenerator] LLM原始输出: {llm_output}")
            
            # 解析JSON输出
            params_data = self._parse_llm_output(llm_output)
            
            result = PolicySearchParams(
                vector_question=params_data.get("vector_question", question),
                keywords=params_data.get("keywords", self._extract_fallback_keywords(question))
            )
            
            print(f"[PolicySearchParamsGenerator] 生成结果:")
            print(f"  向量问题: {result.vector_question}")
            print(f"  关键词: {result.keywords}")
            
            return result
            
        except Exception as e:
            print(f"[PolicySearchParamsGenerator] LLM调用失败: {e}")
            return self._fallback_generate_params(question)
    
    
    def _parse_llm_output(self, llm_output: str) -> dict:
        """解析LLM的JSON输出"""
        try:
            # 尝试直接解析JSON
            return json.loads(llm_output)
        except json.JSONDecodeError as e:
            print(f"[PolicySearchParamsGenerator] 直接JSON解析失败: {e}")
            # 如果直接解析失败，尝试提取JSON部分
            import re
            
            # 尝试查找完整的JSON对象
            json_pattern = r'\{[^{}]*"vector_question"[^{}]*"keywords"[^{}]*\}'
            matches = re.findall(json_pattern, llm_output, re.DOTALL | re.MULTILINE)
            
            for match in matches:
                try:
                    print(f"[PolicySearchParamsGenerator] 尝试解析JSON片段: {match}")
                    return json.loads(match)
                except json.JSONDecodeError:
                    continue
            
            # 如果没找到完整JSON，尝试逐字段提取
            print("[PolicySearchParamsGenerator] 尝试逐字段提取...")
            if '"vector_question"' in llm_output and '"keywords"' in llm_output:
                try:
                    # 提取引号内的内容
                    vector_q_match = re.search(r'"vector_question"\s*:\s*"([^"]*)"', llm_output)
                    keywords_match = re.search(r'"keywords"\s*:\s*\[([^\]]*)\]', llm_output)
                    
                    if vector_q_match:
                        vector_question = vector_q_match.group(1)
                        keywords = []
                        
                        if keywords_match:
                            keywords_text = keywords_match.group(1)
                            # 提取关键词
                            keyword_matches = re.findall(r'"([^"]*)"', keywords_text)
                            keywords = keyword_matches
                        
                        result = {
                            "vector_question": vector_question,
                            "keywords": keywords
                        }
                        print(f"[PolicySearchParamsGenerator] 字段提取成功: {result}")
                        return result
                except Exception as e:
                    print(f"[PolicySearchParamsGenerator] 字段提取失败: {e}")
            
            # 如果都失败了，返回空字典
            print(f"[PolicySearchParamsGenerator] 完全解析失败，LLM原始输出:")
            print(f"  输出长度: {len(llm_output)}")
            print(f"  输出内容: {repr(llm_output)}")
            return {}
    
    def _fallback_generate_params(self, question: str) -> PolicySearchParams:
        """备用参数生成方案（当LLM不可用时）"""
        print("[PolicySearchParamsGenerator] 使用备用参数生成方案")
        
        return PolicySearchParams(
            vector_question=question.strip(),  # 直接使用原问题
            keywords=self._extract_fallback_keywords(question)
        )
    
    def _extract_fallback_keywords(self, question: str) -> list:
        """备用关键词提取 - 针对政策文件"""
        import re
        
        # 移除常见停用词
        stop_words = {
            '的', '是', '在', '有', '和', '与', '对', '为', '了', '等', '中', '及', 
            '什么', '如何', '怎样', '请问', '这个', '那个', '政策', '规定', '文件'
        }
        
        # 提取中文词汇（优先政策相关术语）
        words = re.findall(r'[\u4e00-\u9fff]+', question)
        keywords = [w for w in words if len(w) >= 2 and w not in stop_words]
        
        # 提取数字和百分比
        numbers = re.findall(r'\d+\.?\d*%?', question)
        keywords.extend(numbers)
        
        # 提取英文单词（如REITs等）
        english_words = re.findall(r'[A-Za-z]+', question)
        keywords.extend([w for w in english_words if len(w) >= 3])
        
        # 去重并限制数量
        keywords = list(dict.fromkeys(keywords))[:5]  # 最多5个关键词
        
        return keywords

# 便捷函数
def generate_policy_search_params(question: str, verbose: bool = False) -> PolicySearchParams:
    """生成政策文件检索参数"""
    generator = PolicySearchParamsGenerator()
    return generator.generate_search_params(question, verbose=verbose)
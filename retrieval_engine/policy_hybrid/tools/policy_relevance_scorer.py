# tools/policy_relevance_scorer.py
"""
政策文件相关性打分器
基于LLM对政策文件内容进行1-5分的相关性打分
"""
import sys
import os
from typing import List
from openai import OpenAI

# 设置正确的Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))))
sys.path.insert(0, project_root)

from knowledge_retrieval.config.prompts import POLICY_RELEVANCE_SCORING_PROMPT
from knowledge_retrieval.config.model_config import MODEL_CONFIG

class PolicyRelevanceScorer:
    """政策文件相关性打分器"""
    
    def __init__(self):
        print("[PolicyRelevanceScorer] 初始化完成")
        self._setup_llm()
    
    def _setup_llm(self):
        """设置LLM客户端"""
        try:
            # 使用配置中的LLM设置
            llm_config = MODEL_CONFIG["ali"]["deepseek-v3"]  # 或者使用您配置的其他模型
            self.llm_client = OpenAI(
                api_key=llm_config["api_key"],
                base_url=llm_config["base_url"]
            )
            self.model_name = llm_config["model"]
            print(f"[PolicyRelevanceScorer] LLM客户端设置完成，使用模型: {self.model_name}")
            
        except Exception as e:
            print(f"[PolicyRelevanceScorer] LLM设置失败: {e}")
            self.llm_client = None
            self.model_name = None
    
    def score_relevance(self, question: str, content: str) -> int:
        """
        对单个内容进行相关性打分
        
        Args:
            question: 用户问题
            content: 待打分的内容
            
        Returns:
            int: 相关性分数(1-5)
        """
        if not self.llm_client:
            print("[PolicyRelevanceScorer] LLM未设置，使用默认分数3")
            return 3
        
        try:
            # 构建提示词
            prompt = POLICY_RELEVANCE_SCORING_PROMPT.format(
                question=question,
                content=content[:2000]  # 限制内容长度
            )
            
            # 调用LLM
            response = self.llm_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,  # 使用确定性输出
                max_tokens=10     # 只需要返回数字
            )
            
            llm_output = response.choices[0].message.content.strip()
            
            # 解析分数
            score = self._parse_score(llm_output)
            print(f"[PolicyRelevanceScorer] 内容打分: {score}分")
            return score
            
        except Exception as e:
            print(f"[PolicyRelevanceScorer] 打分失败: {e}，使用默认分数3")
            return 3
    
    def batch_score_relevance(self, question: str, contents: List[str]) -> List[int]:
        """
        批量打分
        
        Args:
            question: 用户问题
            contents: 待打分的内容列表
            
        Returns:
            List[int]: 相关性分数列表
        """
        print(f"[PolicyRelevanceScorer] 开始批量打分，共{len(contents)}项")
        
        scores = []
        for i, content in enumerate(contents):
            print(f"[PolicyRelevanceScorer] 正在打分第{i+1}/{len(contents)}项...")
            score = self.score_relevance(question, content)
            scores.append(score)
        
        print(f"[PolicyRelevanceScorer] 批量打分完成")
        return scores
    
    def _parse_score(self, llm_output: str) -> int:
        """
        解析LLM输出的分数
        
        Args:
            llm_output: LLM的原始输出
            
        Returns:
            int: 解析出的分数(1-5)
        """
        try:
            # 尝试直接解析数字
            import re
            
            # 查找数字
            numbers = re.findall(r'\d+', llm_output)
            
            if numbers:
                score = int(numbers[0])
                # 确保分数在1-5范围内
                if 1 <= score <= 5:
                    return score
                else:
                    print(f"[PolicyRelevanceScorer] 分数{score}超出范围，调整为3")
                    return 3
            else:
                print(f"[PolicyRelevanceScorer] 无法解析分数: {llm_output}")
                return 3
                
        except Exception as e:
            print(f"[PolicyRelevanceScorer] 分数解析失败: {e}")
            return 3
# tools/relevance_scorer.py
import sys
import os

# 设置正确的Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
sys.path.insert(0, project_root)
from config.prompts import RELEVANCE_SCORING_PROMPT
from config.model_config import MODEL_CONFIG
from openai import OpenAI
import re

class RelevanceScorer:
    """相关性打分工具 - 使用LLM对检索结果进行1-5分评估"""
    
    def __init__(self, provider="ali", model="deepseek-v3"):
        self.config = MODEL_CONFIG.get(provider, {}).get(model, {})
        if not self.config:
            # 回退到备用配置
            self.config = MODEL_CONFIG["deepseek"]["deepseek-chat"]
        
        self.client = OpenAI(
            api_key=self.config["api_key"],
            base_url=self.config["base_url"]
        )
        print(f"[RelevanceScorer] 初始化完成，使用模型: {self.config['model']}")
    
    def score_relevance(self, question: str, content: str) -> int:
        """
        对文本内容与问题的相关性进行打分
        
        Args:
            question: 用户问题
            content: 要评分的文本内容
            
        Returns:
            int: 相关性分数 (1-5)
        """
        print(f"[RelevanceScorer] 开始打分，问题长度: {len(question)}, 内容长度: {len(content)}")
        
        # 限制内容长度，避免超过LLM限制
        max_content_length = 3000
        if len(content) > max_content_length:
            content = content[:max_content_length] + "..."
        
        # 构建提示词
        prompt = RELEVANCE_SCORING_PROMPT.format(
            question=question,
            content=content
        )
        
        try:
            # 调用LLM进行打分
            response = self.client.chat.completions.create(
                model=self.config["model"],
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,  # 确保结果一致性
                max_tokens=10     # 只需要返回一个数字
            )
            
            score_text = response.choices[0].message.content.strip()
            
            # 提取分数
            score = self._extract_score(score_text)
            
            print(f"[RelevanceScorer] LLM返回: '{score_text}', 解析分数: {score}")
            return score
            
        except Exception as e:
            print(f"[RelevanceScorer] 打分失败: {e}")
            return 3  # 默认中等相关性
    
    def _extract_score(self, score_text: str) -> int:
        """从LLM响应中提取分数"""
        # 查找数字
        numbers = re.findall(r'\d+', score_text)
        
        if numbers:
            score = int(numbers[0])
            # 确保分数在1-5范围内
            if 1 <= score <= 5:
                return score
        
        # 查找文字描述
        if any(word in score_text for word in ['完全', '充分', '准确']):
            return 5
        elif any(word in score_text for word in ['部分', '相关']):
            return 4
        elif any(word in score_text for word in ['一定', '可能']):
            return 3
        elif any(word in score_text for word in ['较弱', '有限']):
            return 2
        elif any(word in score_text for word in ['无关', '没有']):
            return 1
        
        # 默认返回3分
        return 3
    
    def batch_score_relevance(self, question: str, contents: list) -> list:
        """
        批量打分，提高效率
        
        Args:
            question: 用户问题
            contents: 文本内容列表
            
        Returns:
            list: 分数列表
        """
        scores = []
        for i, content in enumerate(contents):
            print(f"[RelevanceScorer] 批量打分进度: {i+1}/{len(contents)}")
            score = self.score_relevance(question, content)
            scores.append(score)
        
        print(f"[RelevanceScorer] 批量打分完成，平均分数: {sum(scores)/len(scores):.2f}")
        return scores
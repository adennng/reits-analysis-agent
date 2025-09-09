# section_classifier.py
"""
招募说明书章节分类器 - 使用deepseek-v3模型判断问题对应的章节
"""

import sys
import os
import json
from typing import Dict, Any, List, Optional

# 添加路径以便导入配置
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
sys.path.insert(0, project_root)

from openai import OpenAI


class SectionClassifier:
    """
    招募说明书章节分类器
    使用deepseek-v3模型判断用户问题对应的章节
    """
    
    def __init__(self):
        """初始化分类器"""
        self.client = None
        self.model = None
        self._setup_llm()
        
        # 定义章节信息
        self.sections = {
            "基础设施项目基本情况": {
                "content": "基础设施项目/资产基本情况（资产类型、所属地点、资产规模等）、项目运行情况（运营模式、运营数据、项目历史收入成本等经营数据）、所属行业介绍（行业政策、行业规划、行业现状、竞争情况）、项目区位情况、可比竞品情况、项目合规情况（相关手续的情况、项目权属及他项权利情况、项目的保险情况）、基础设施资产权属期限及展期安排、项目资产评估情况（资产评估价值、账面价值、评估主要假设条件/参数（折现率、收入成本假设））"
            },
            "基础设施项目财务状况及经营业绩分析": {
                "content": "基础设施项目/资产历史财务报表（资产负债表、利润表）、历史各项收入和成本费用数据"
            },
            "现金流测算分析及未来运营展望": {
                "content": "可供分配金额测算报告、预测可供分配金额数据"
            },
            "原始权益人": {
                "content": "发起人和原始权益人相关信息"
            },
            "基础设施项目运营管理安排": {
                "content": "运营管理机构基本情况、运营管理安排、运营管理费安排"
            },
            "基金费用与税收": {
                "content": "基金费用计提方法、计提标准和支付方式（基金各项管理费、托管费）"
            }
        }
        
        print("[SectionClassifier] 章节分类器初始化完成")
    
    def classify_section(self, question: str) -> Dict[str, Any]:
        """
        对用户问题进行章节分类
        
        Args:
            question: 用户问题
            
        Returns:
            Dict[str, Any]: 分类结果
            {
                "success": bool,
                "sections": List[str],  # 匹配的章节标题列表
                "reason": str,         # 分类原因
                "raw_response": str    # LLM原始响应
            }
        """
        print(f"[SectionClassifier] 开始分类问题: {question}")
        
        if not self.client:
            return {
                "success": False,
                "sections": [],
                "reason": "LLM客户端未初始化",
                "raw_response": ""
            }
        
        try:
            # 构建提示词
            prompt = self._build_classification_prompt(question)
            
            # 调用LLM
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=2048
            )
            
            response_text = response.choices[0].message.content.strip()
            print(f"[SectionClassifier] LLM原始响应: {response_text}")
            
            # 解析响应
            parsed_result = self._parse_classification_response(response_text)
            parsed_result["raw_response"] = response_text
            
            return parsed_result
            
        except Exception as e:
            print(f"[SectionClassifier] 分类异常: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                "success": False,
                "sections": [],
                "reason": f"分类过程异常: {str(e)}",
                "raw_response": ""
            }
    
    def _build_classification_prompt(self, question: str) -> str:
        """构建分类提示词"""
        try:
            from config.prompts import PROSPECTUS_SECTION_CLASSIFICATION_PROMPT
        except ImportError:
            import sys
            import os
            # 添加knowledge_retrieval路径
            kr_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            sys.path.insert(0, kr_path)
            from config.prompts import PROSPECTUS_SECTION_CLASSIFICATION_PROMPT
        
        return PROSPECTUS_SECTION_CLASSIFICATION_PROMPT.format(question=question)
    
    def _parse_classification_response(self, response_text: str) -> Dict[str, Any]:
        """解析LLM分类响应"""
        try:
            response_text = response_text.strip()
            
            # 检查是否为"无"
            if response_text == "无" or "无" in response_text.lower():
                return {
                    "success": True,
                    "sections": [],
                    "reason": "LLM判断没有匹配的章节"
                }
            
            # 解析章节列表
            sections = []
            lines = response_text.split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # 匹配格式：章节：基础设施项目基本情况
                if line.startswith("章节："):
                    section_title = line.replace("章节：", "").strip()
                    if section_title in self.sections:
                        sections.append(section_title)
                # 也支持直接返回章节名称
                elif line in self.sections:
                    sections.append(line)
                # 支持包含章节名称的行
                else:
                    for section_title in self.sections.keys():
                        if section_title in line:
                            sections.append(section_title)
                            break
            
            # 去重
            sections = list(set(sections))
            
            if sections:
                return {
                    "success": True,
                    "sections": sections,
                    "reason": f"识别到{len(sections)}个相关章节"
                }
            else:
                return {
                    "success": True,
                    "sections": [],
                    "reason": "响应格式解析成功但未找到有效章节"
                }
                
        except Exception as e:
            print(f"[SectionClassifier] 响应解析异常: {e}")
            return {
                "success": False,
                "sections": [],
                "reason": f"响应解析异常: {str(e)}"
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
            
            # 获取deepseek-v3配置
            ali_config = MODEL_CONFIG.get("ali", {})
            deepseek_config = ali_config.get("deepseek-v3", {})
            
            if not deepseek_config:
                print("[SectionClassifier] ❌ deepseek-v3模型配置未找到")
                return
            
            # 创建客户端
            self.client = OpenAI(
                api_key=deepseek_config["api_key"],
                base_url=deepseek_config["base_url"]
            )
            
            self.model = deepseek_config["model"]
            
            print("[SectionClassifier] ✅ deepseek-v3客户端初始化成功")
            
        except Exception as e:
            print(f"[SectionClassifier] ❌ LLM设置失败: {e}")
            import traceback
            traceback.print_exc()
            self.client = None
            self.model = None


# 测试函数
if __name__ == "__main__":
    classifier = SectionClassifier()
    
    # 测试问题
    test_questions = [
        "基金的投资策略是什么？",
        "管理费率是多少？",
        "项目的资产评估价值是多少？",
        "今天天气怎么样？"
    ]
    
    for question in test_questions:
        print(f"\n=== 测试问题: {question} ===")
        result = classifier.classify_section(question)
        print(f"成功: {result['success']}")
        print(f"章节: {result['sections']}")
        print(f"原因: {result['reason']}")
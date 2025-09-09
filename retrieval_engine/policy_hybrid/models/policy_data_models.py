# models/policy_data_models.py
"""
政策文件检索数据模型
适配政策文件数据库字段：document_title、publish_date、issuing_agency、website等
"""

from dataclasses import dataclass
from typing import List, Optional

@dataclass
class PolicySearchResult:
    """政策文件检索结果数据模型"""
    
    # 基础字段
    global_id: str                    # 全局唯一ID
    chunk_id: int                     # 分块ID
    text: str                         # 文本内容
    char_count: int                   # 字符数
    
    # 政策文件特有字段
    publish_date: str                 # 发布日期
    issuing_agency: str               # 发布机构
    notice_title: str                 # 公告标题
    document_title: str               # 文档标题
    type: str                         # 文档类型
    document_url: str                 # 文档URL
    website: str                      # 网站来源
    file_name: str                    # 文件名
    
    # 检索相关字段
    score: float = 0.0                # 检索分数
    distance: Optional[float] = None   # 向量距离（仅向量检索）
    from_methods: List[str] = None     # 检索来源方法
    
    def __post_init__(self):
        if self.from_methods is None:
            self.from_methods = []

@dataclass
class PolicyScoredResult:
    """政策文件打分后的检索结果"""
    
    search_result: PolicySearchResult # 原始检索结果
    relevance_score: int              # 相关性分数(1-5)
    expanded_text_initial: str        # 第一次扩展后文本
    expanded_text_final: str          # 第二次扩展后文本
    from_methods: List[str]           # 检索方法来源
    final_score: float                # 最终分数

@dataclass 
class PolicyFileGroup:
    """按文件分组的政策文件结果"""
    
    document_title: str               # 文档标题
    publish_date: str                 # 发布日期
    issuing_agency: str               # 发布机构
    website: str                      # 网站来源
    scored_results: List[PolicyScoredResult]  # 该文件下的所有结果
    merged_text: str = ""             # 第二次扩展合并后的文本

@dataclass
class PolicyRetrievalResponse:
    """政策文件检索响应数据模型"""
    
    question: str                     # 原始问题
    answer: str                       # LLM生成的答案
    reference_files: List[dict]       # 参考文件信息列表
    is_found: bool                    # 是否找到答案
    error: Optional[str] = None       # 错误信息
    
    # 新增故障处理字段
    failure_type: Optional[str] = None        # 失败类型: "retryable", "final", "needs_agent2"
    retrieval_content: Optional[str] = None   # 检索到的原始内容（用于Agent2处理）
    debug_info: Optional[dict] = None         # 调试信息
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "question": self.question,
            "answer": self.answer, 
            "reference_files": self.reference_files,
            "is_found": self.is_found,
            "error": self.error,
            "failure_type": self.failure_type,
            "retrieval_content": self.retrieval_content,
            "debug_info": self.debug_info
        }
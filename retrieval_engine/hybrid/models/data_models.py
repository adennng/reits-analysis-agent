# models/data_models.py
from pydantic import BaseModel, Field
from typing import List, Optional, Union, Dict
from datetime import datetime

class BasicParams(BaseModel):
    """基本参数 - 包含API的三个核心参数"""
    fund_code: str = Field(..., description="基金代码")
    question: str = Field(..., description="检索的核心问题")
    file_name: Optional[str] = Field(None, description="指定的文件名称（可选）")

class SearchParams(BaseModel):
    """混合检索参数"""
    vector_question: str = Field(..., description="向量检索问题")
    keywords: List[str] = Field(..., description="关键词列表")

class SearchResult(BaseModel):
    """检索结果"""
    global_id: str = Field(..., description="全局ID")
    chunk_id: int = Field(..., description="分块ID")
    source_file: str = Field(..., description="源文件名")
    page_num: str = Field(..., description="页码，支持范围格式如'12'、'12-13'、'12-13-14'")
    text: str = Field(..., description="文本内容")
    score: float = Field(..., description="检索分数")
    distance: Optional[float] = Field(None, description="向量距离")
    fund_code: str = Field(..., description="基金代码")
    date: str = Field(..., description="文档日期")
    prev_chunks: List[str] = Field(default_factory=list, description="前置分块")
    next_chunks: List[str] = Field(default_factory=list, description="后置分块")
    from_methods: List[str] = Field(default_factory=list, description="来源检索方法")

class ScoredResult(BaseModel):
    """打分后的检索结果"""
    search_result: SearchResult = Field(..., description="原始检索结果")
    relevance_score: int = Field(..., ge=1, le=5, description="相关性得分(1-5)")
    expanded_text_initial: str = Field(..., description="初步扩展后的文本")
    expanded_text_final: Optional[str] = Field(None, description="最终扩展后的文本")
    from_methods: List[str] = Field(default_factory=list, description="来源检索方法")
    search_ranks: Dict[str, int] = Field(default_factory=dict, description="在各检索方法中的排名")
    final_score: float = Field(default=0.0, description="最终综合得分")

class KnowledgeAnswer(BaseModel):
    """知识库答案"""
    answer: str = Field(..., description="最终答案")
    confidence: float = Field(..., description="答案置信度")
    sources: List[Dict] = Field(..., description="答案来源")
    search_strategy_used: str = Field(..., description="使用的检索策略")
    is_satisfactory: bool = Field(..., description="答案是否满意")
# knowledge_retrieval/retrieval_engine/fulltext/__init__.py

"""
全文检索模块

提供基于ElasticSearch的全文检索功能，获取指定文件的完整内容并通过LLM生成答案。
"""

from .fulltext_retrieval_tool import FulltextRetrievalTool, search_full_document
from .fulltext_searcher import FulltextSearcher

__all__ = [
    "FulltextRetrievalTool",
    "search_full_document", 
    "FulltextSearcher"
]

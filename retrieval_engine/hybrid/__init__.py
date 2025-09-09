# knowledge_retrieval/retrieval_engine/hybrid/__init__.py

"""
混合检索模块

提供向量检索 + 关键词检索的混合检索功能，
包括智能扩展、相关性评分和答案生成。
"""

from .hybrid_retrieval_tool import search_knowledge_base, HybridRetrievalTool

__all__ = [
    'search_knowledge_base',
    'HybridRetrievalTool',
]

__version__ = "1.0.0"
__description__ = "混合检索模块（向量检索 + 关键词检索）" 
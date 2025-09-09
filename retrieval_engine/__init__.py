# knowledge_retrieval/__init__.py
"""
REITs检索引擎

统一的检索引擎接口，支持多种检索方式：
- 混合检索（向量 + 关键词）- 已实现
- 全文检索 - 待实现  
- 纯语义检索 - 待实现

使用方法：
    from knowledge_retrieval.retrieval_engine import search_knowledge_base
    
    result = search_knowledge_base(
        fund_code="508056.SH",
        question="基金的投资策略是什么？",
        method="hybrid"  # 可选: "hybrid", "fulltext", "semantic"
    )
"""

# 导入已实现的检索方式
from .hybrid import search_knowledge_base as hybrid_search, HybridRetrievalTool

# 导入未来的检索方式（占位）
# from .fulltext import search_knowledge_base as fulltext_search
# from .semantic import search_knowledge_base as semantic_search

# 全文检索
from .fulltext import FulltextRetrievalTool, search_full_document

# 招募说明书章节检索
from .prospectus_section import ProspectusSectionTool, search_prospectus_section

# 政策文件混合检索
from .policy_hybrid import PolicyHybridRetrievalTool, execute_policy_retrieval

__all__ = [
    # 统一接口
    'search_knowledge_base',
    'get_available_methods',
    
    # 具体实现
    'hybrid_search',
    'HybridRetrievalTool',
    
    # 全文检索
    'FulltextRetrievalTool',
    'search_full_document',
    
    # 招募说明书章节检索
    'ProspectusSectionTool',
    'search_prospectus_section',
    
    # 政策文件混合检索
    'PolicyHybridRetrievalTool',
    'execute_policy_retrieval',
    
    # 未来功能（占位）
    # 'fulltext_search',
    # 'semantic_search',
]

__version__ = "1.0.0"
__description__ = "REITs检索引擎 - 统一多种检索方式"

def get_available_methods():
    """获取当前可用的检索方法"""
    return {
        "hybrid": {
            "name": "混合检索",
            "description": "向量检索 + 关键词检索，提供最佳的检索精度",
            "status": "available",
            "function": hybrid_search
        },
        "fulltext": {
            "name": "全文检索", 
            "description": "基于全文索引的快速检索",
            "status": "available",
            "function": search_full_document
        },
        "prospectus_section": {
            "name": "招募说明书章节检索",
            "description": "根据问题判断章节，精确检索对应内容",
            "status": "available", 
            "function": search_prospectus_section
        },
        "semantic": {
            "name": "纯语义检索",
            "description": "纯向量语义检索，适合概念性查询", 
            "status": "planned",
            "function": None
        }
    }

def search_knowledge_base(fund_code: str, question: str, method: str = "hybrid", **kwargs):
    """
    统一的检索接口
    
    Args:
        fund_code: 基金代码
        question: 查询问题
        method: 检索方法 ("hybrid", "fulltext", "semantic")
        **kwargs: 其他参数
        
    Returns:
        Dict: 检索结果
        
    Raises:
        ValueError: 当指定的检索方法不可用时
    """
    methods = get_available_methods()
    
    if method not in methods:
        available = [k for k, v in methods.items() if v["status"] == "available"]
        raise ValueError(f"不支持的检索方法: {method}. 可用方法: {available}")
    
    method_info = methods[method]
    if method_info["status"] != "available":
        available = [k for k, v in methods.items() if v["status"] == "available"]
        raise ValueError(f"检索方法 {method} 尚未实现. 可用方法: {available}")
    
    # 调用对应的检索函数
    return method_info["function"](fund_code=fund_code, question=question, **kwargs) 

# 为了向后兼容，提供统一的检索接口
def search_with_method(
    method: str,
    question: str,
    file_name: str = None,
    fund_code: str = None,
    **kwargs
):
    """
    统一的检索接口
    
    Args:
        method: 检索方法 ("hybrid", "fulltext", "semantic")
        question: 检索问题
        file_name: 文件名（对于全文检索是必需的）
        fund_code: 基金代码
        **kwargs: 其他参数
    
    Returns:
        检索结果字典
    """
    if method == "hybrid":
        if not fund_code:
            raise ValueError("混合检索需要提供fund_code参数")
        return search_knowledge_base(fund_code, question, file_name, **kwargs)
    
    elif method == "fulltext":
        if not file_name:
            raise ValueError("全文检索需要提供file_name参数")
        return search_full_document(question, file_name, **kwargs)
    
    elif method == "prospectus_section":
        if not file_name:
            raise ValueError("招募说明书章节检索需要提供file_name参数")
        return search_prospectus_section(question, file_name, **kwargs)
    
    elif method == "semantic":
        raise NotImplementedError("语义检索功能尚未实现")
    
    else:
        raise ValueError(f"不支持的检索方法: {method}")

# 提供快速检索函数
def quick_search(question: str, **kwargs):
    """
    快速检索函数 - 自动选择检索方法
    
    Args:
        question: 检索问题
        **kwargs: 其他参数，可能包含file_name, fund_code等
    
    Returns:
        检索结果字典
    """
    # 如果提供了file_name但没有fund_code，优先使用全文检索
    if kwargs.get('file_name') and not kwargs.get('fund_code'):
        return search_full_document(question, kwargs['file_name'], **kwargs)
    
    # 如果提供了fund_code，使用混合检索
    elif kwargs.get('fund_code'):
        return search_knowledge_base(
            kwargs['fund_code'], 
            question, 
            kwargs.get('file_name'),
            **{k: v for k, v in kwargs.items() if k not in ['fund_code', 'file_name']}
        )
    
    # 如果都没有提供，抛出错误
    else:
        raise ValueError("请提供fund_code（用于混合检索）或file_name（用于全文检索）") 
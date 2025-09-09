# tools/policy_search_tools.py
"""
政策文件混合检索工具
整合向量检索和关键词检索，并去重合并
"""
from typing import List, Optional
from ..models.policy_data_models import PolicySearchResult
from .policy_vector_searcher import PolicyVectorSearcher
from .policy_keyword_searcher import PolicyKeywordSearcher

class PolicyHybridSearchTool:
    """政策文件混合检索工具 - 结合向量和关键词检索"""
    
    def __init__(self):
        self.vector_tool = PolicyVectorSearcher()
        self.keyword_tool = PolicyKeywordSearcher()
        print("[PolicyHybridSearchTool] 初始化完成")
    
    def search(
        self,
        vector_question: str,
        keywords: List[str],
        top_k: int = 15
    ) -> List[PolicySearchResult]:
        """
        执行政策文件混合检索
        
        Args:
            vector_question: 向量检索问题
            keywords: 关键词列表
            top_k: 返回结果数量
            
        Returns:
            List[PolicySearchResult]: 去重后的检索结果
        """
        print(f"[PolicyHybridSearchTool] 开始政策文件混合检索")
        print(f"  向量问题: {vector_question}")
        print(f"  关键词: {keywords}")
        
        # 分别执行向量和关键词检索
        vector_results = self.vector_tool.search(vector_question, top_k)
        keyword_results = self.keyword_tool.search(keywords, top_k)
        
        print(f"[PolicyHybridSearchTool] 向量检索返回 {len(vector_results)} 条结果")
        print(f"[PolicyHybridSearchTool] 关键词检索返回 {len(keyword_results)} 条结果")
        print(f"[PolicyHybridSearchTool] 合计检索到 {len(vector_results) + len(keyword_results)} 条结果")
        
        # 合并结果并去重
        all_results = []
        seen_ids = set()
        duplicate_count = 0
        duplicate_details = []
        
        # 先添加向量检索结果，标记来源
        for result in vector_results:
            if result.global_id not in seen_ids:
                result.from_methods = ["vector"]
                all_results.append(result)
                seen_ids.add(result.global_id)
        
        # 再添加关键词检索结果，标记来源
        for result in keyword_results:
            if result.global_id not in seen_ids:
                result.from_methods = ["keyword"]
                all_results.append(result)
                seen_ids.add(result.global_id)
            else:
                # 如果已存在，标记为重复
                duplicate_count += 1
                duplicate_details.append({
                    "global_id": result.global_id,
                    "document_title": result.document_title,
                    "text_preview": result.text[:100] + "..." if len(result.text) > 100 else result.text
                })
                for existing in all_results:
                    if existing.global_id == result.global_id:
                        existing.from_methods.append("keyword")
                        break
        
        # 打印去重详细信息
        print(f"[PolicyHybridSearchTool] 去重统计:")
        print(f"  - 去重前总数: {len(vector_results) + len(keyword_results)} 条")
        print(f"  - 去重后总数: {len(all_results)} 条")
        print(f"  - 重复项数量: {duplicate_count} 条")
        
        if duplicate_details:
            print(f"[PolicyHybridSearchTool] 重复项详情:")
            for i, dup in enumerate(duplicate_details, 1):
                print(f"  {i}. global_id={dup['global_id']}")
                print(f"     文件={dup['document_title']}")
                print(f"     内容预览={dup['text_preview']}")
        
        # 统计检索来源分布
        vector_only = [r for r in all_results if r.from_methods == ["vector"]]
        keyword_only = [r for r in all_results if r.from_methods == ["keyword"]]
        both_methods = [r for r in all_results if len(r.from_methods) > 1]
        
        print(f"[PolicyHybridSearchTool] 结果来源分布:")
        print(f"  - 仅向量检索: {len(vector_only)} 条")
        print(f"  - 仅关键词检索: {len(keyword_only)} 条")
        print(f"  - 两种方法都命中: {len(both_methods)} 条")
        
        if both_methods:
            print(f"[PolicyHybridSearchTool] 两种方法都命中的语块:")
            for result in both_methods:
                print(f"  - global_id={result.global_id}, 文件={result.document_title}")
        
        print(f"[PolicyHybridSearchTool] 政策文件混合检索完成，返回{len(all_results)}条结果")
        return all_results
    
    def close(self):
        """关闭连接"""
        self.vector_tool.close()
        self.keyword_tool.close()
        print("[PolicyHybridSearchTool] 连接已关闭")
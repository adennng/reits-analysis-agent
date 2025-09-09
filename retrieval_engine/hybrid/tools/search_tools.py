# tools/search_tools.py
import sys
import os
from typing import List, Optional

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from .vector_searcher import VectorSearcher
from .keyword_searcher import KeywordSearcher
from ..models.data_models import SearchResult

class VectorSearchTool:
    """向量检索工具 - 封装现有的VectorSearcher"""
    
    def __init__(self):
        self.searcher = VectorSearcher()
        print("[VectorSearchTool] 初始化完成")
    
    def search(
        self,
        fund_code: str,
        question: str,
        source_file: Optional[str] = None,
        top_k: int = 15
    ) -> List[SearchResult]:
        """
        执行向量检索
        
        Args:
            fund_code: 基金代码
            question: 检索问题
            source_file: 指定源文件（可选）
            top_k: 返回结果数量
            
        Returns:
            List[SearchResult]: 检索结果
        """
        print(f"[VectorSearchTool] 开始向量检索: 基金={fund_code}, 问题={question[:30]}...")
        
        # 构建检索表达式
        if source_file:
            expr = f'fund_code == "{fund_code}" && source_file == "{source_file}"'
        else:
            expr = f'fund_code == "{fund_code}"'
        
        # 生成问题向量
        embedding = self.searcher.get_embedding(question)
        
        # 执行向量检索
        raw_results = self.searcher.vector_search(
            question_embedding=embedding,
            expr=expr,
            top_k=top_k
        )
        
        # 转换为SearchResult对象
        search_results = []
        for i, result in enumerate(raw_results):
            # 保持page_num的原始字符串格式
            page_num = result.get("page_num", "0")
            if not isinstance(page_num, str):
                page_num = str(page_num)
            
            search_result = SearchResult(
                global_id=result.get("global_id", ""),
                chunk_id=result.get("chunk_id", 0),
                source_file=result.get("source_file", ""),
                page_num=page_num,
                text=result.get("text", ""),
                score=1.0 / (1.0 + result.get("distance", 1.0)),  # 转换为相似度分数
                distance=result.get("distance"),
                fund_code=result.get("fund_code", ""),
                date=result.get("date", ""),
                prev_chunks=self._parse_chunks(result.get("prev_chunks", "")),
                next_chunks=self._parse_chunks(result.get("next_chunks", ""))
            )
            search_results.append(search_result)
        
        print(f"[VectorSearchTool] 向量检索完成，返回{len(search_results)}条结果")
        return search_results
    
    def _parse_chunks(self, chunks_str) -> List[str]:
        """解析分块字符串"""
        if not chunks_str:
            return []
        
        try:
            import json
            if isinstance(chunks_str, str) and chunks_str.startswith('['):
                return json.loads(chunks_str)
            elif isinstance(chunks_str, str) and ',' in chunks_str:
                return chunks_str.split(',')
            elif isinstance(chunks_str, list):
                return chunks_str
            else:
                return [str(chunks_str)] if chunks_str else []
        except:
            return []

class KeywordSearchTool:
    """关键词检索工具 - 封装现有的KeywordSearcher"""
    
    def __init__(self):
        self.searcher = KeywordSearcher()
        print("[KeywordSearchTool] 初始化完成")
    
    def search(
        self,
        fund_code: str,
        keywords: List[str],
        source_file: Optional[str] = None,
        top_k: int = 15
    ) -> List[SearchResult]:
        """
        执行关键词检索
        
        Args:
            fund_code: 基金代码
            keywords: 关键词列表
            source_file: 指定源文件（可选）
            top_k: 返回结果数量
            
        Returns:
            List[SearchResult]: 检索结果
        """
        print(f"[KeywordSearchTool] 开始关键词检索: 基金={fund_code}, 关键词={keywords}")
        
        # 执行关键词检索
        raw_results = self.searcher.keyword_search(
            query_str="",
            manual_keywords=keywords,
            fund_code=fund_code,
            top_k=top_k
        )
        
        # 如果指定了源文件，进行过滤
        if source_file:
            raw_results = [r for r in raw_results if r.get("source_file") == source_file]
        
        # 转换为SearchResult对象
        search_results = []
        for result in raw_results:
            # 保持page_num的原始字符串格式
            page_num = result.get("page_num", "0")
            if not isinstance(page_num, str):
                page_num = str(page_num)
            
            search_result = SearchResult(
                global_id=result.get("global_id", ""),
                chunk_id=result.get("chunk_id", 0),
                source_file=result.get("source_file", ""),
                page_num=page_num,
                text=result.get("text", ""),
                score=result.get("score", 0.0),
                fund_code=result.get("fund_code", ""),
                date=result.get("date", ""),
                prev_chunks=self._parse_chunks(result.get("prev_chunks", "")),
                next_chunks=self._parse_chunks(result.get("next_chunks", ""))
            )
            search_results.append(search_result)
        
        print(f"[KeywordSearchTool] 关键词检索完成，返回{len(search_results)}条结果")
        return search_results
    
    def _parse_chunks(self, chunks_str) -> List[str]:
        """解析分块字符串"""
        if not chunks_str:
            return []
        
        try:
            import json
            if isinstance(chunks_str, str) and chunks_str.startswith('['):
                return json.loads(chunks_str)
            elif isinstance(chunks_str, str) and ',' in chunks_str:
                return chunks_str.split(',')
            elif isinstance(chunks_str, list):
                return chunks_str
            else:
                return [str(chunks_str)] if chunks_str else []
        except:
            return []

class HybridSearchTool:
    """混合检索工具 - 结合向量和关键词检索"""
    
    def __init__(self):
        self.vector_tool = VectorSearchTool()
        self.keyword_tool = KeywordSearchTool()
        print("[HybridSearchTool] 初始化完成")
    
    def search(
        self,
        fund_code: str,
        question: str,
        keywords: List[str],
        source_file: Optional[str] = None,
        top_k: int = 15
    ) -> List[SearchResult]:
        """
        执行混合检索
        
        Args:
            fund_code: 基金代码
            question: 检索问题
            keywords: 关键词列表
            source_file: 指定源文件（可选）
            top_k: 返回结果数量
            
        Returns:
            List[SearchResult]: 检索结果
        """
        print(f"[HybridSearchTool] 开始混合检索: 基金={fund_code}")
        
        # 分别执行向量和关键词检索
        vector_results = self.vector_tool.search(fund_code, question, source_file, top_k)
        keyword_results = self.keyword_tool.search(fund_code, keywords, source_file, top_k)
        
        print(f"[HybridSearchTool] 向量检索返回 {len(vector_results)} 条结果")
        print(f"[HybridSearchTool] 关键词检索返回 {len(keyword_results)} 条结果")
        print(f"[HybridSearchTool] 合计检索到 {len(vector_results) + len(keyword_results)} 条结果")
        
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
                    "source_file": result.source_file,
                    "text_preview": result.text[:100] + "..." if len(result.text) > 100 else result.text
                })
                for existing in all_results:
                    if existing.global_id == result.global_id:
                        existing.from_methods.append("keyword")
                        break
        
        # 打印去重详细信息
        print(f"[HybridSearchTool] 去重统计:")
        print(f"  - 去重前总数: {len(vector_results) + len(keyword_results)} 条")
        print(f"  - 去重后总数: {len(all_results)} 条")
        print(f"  - 重复项数量: {duplicate_count} 条")
        
        if duplicate_details:
            print(f"[HybridSearchTool] 重复项详情:")
            for i, dup in enumerate(duplicate_details, 1):
                print(f"  {i}. global_id={dup['global_id']}")
                print(f"     文件={dup['source_file']}")
                print(f"     内容预览={dup['text_preview']}")
        
        # 统计检索来源分布
        vector_only = [r for r in all_results if r.from_methods == ["vector"]]
        keyword_only = [r for r in all_results if r.from_methods == ["keyword"]]
        both_methods = [r for r in all_results if len(r.from_methods) > 1]
        
        print(f"[HybridSearchTool] 结果来源分布:")
        print(f"  - 仅向量检索: {len(vector_only)} 条")
        print(f"  - 仅关键词检索: {len(keyword_only)} 条")
        print(f"  - 两种方法都命中: {len(both_methods)} 条")
        
        if both_methods:
            print(f"[HybridSearchTool] 两种方法都命中的语块:")
            for result in both_methods:
                print(f"  - global_id={result.global_id}, 文件={result.source_file}")
        
        print(f"[HybridSearchTool] 混合检索完成，返回{len(all_results)}条结果")
        return all_results
    

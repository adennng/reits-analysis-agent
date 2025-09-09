# tools/policy_keyword_searcher.py
"""
政策文件关键词检索器
参考keyword_searcher.py的逻辑，在text字段中进行关键词检索
"""
import json
from elasticsearch import Elasticsearch
import sys
import os
from typing import List, Optional

# 设置正确的Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))))
sys.path.insert(0, project_root)
from knowledge_retrieval.config.db_config import get_elasticsearch_config
from ..models.policy_data_models import PolicySearchResult

class PolicyKeywordSearcher:
    """
    政策文件关键词检索器
    查询reits_policy_documents索引，主要在text字段中检索
    """

    def __init__(self, index_name="reits_policy_documents"):
        self._index_name = index_name

        es_config = get_elasticsearch_config()
        print("[PolicyKeywordSearcher] 正在连接 Elasticsearch...")
        self.es = Elasticsearch(
            [f"{es_config['scheme']}://{es_config['host']}:{es_config['port']}"],
            basic_auth=(es_config['username'], es_config['password']),
            verify_certs=False,
            ssl_show_warn=False
        )
        print(f"[PolicyKeywordSearcher] 连接成功，使用索引: {index_name}")

    def keyword_search(
        self,
        query_str="",
        manual_keywords=None,
        top_k=15
    ):
        """
        执行政策文件关键词检索
        
        Args:
            query_str: 查询字符串
            manual_keywords: 手动指定的关键词列表
            top_k: 返回结果数量
            
        Returns:
            list: 检索结果
        """
        # 使用手动关键词或查询字符串
        if manual_keywords:
            keywords = manual_keywords if isinstance(manual_keywords, list) else [manual_keywords]
        else:
            keywords = [query_str] if query_str else []
        
        # 构建查询 - 主要参考原keyword_searcher.py的逻辑
        must_queries = []
        
        # 关键词匹配 - 主要在text字段中检索
        if keywords:
            keyword_query = {
                "multi_match": {
                    "query": " ".join(keywords),
                    "fields": ["text"],  # 主要在text字段中检索
                    "type": "best_fields",
                    "fuzziness": "AUTO"
                }
            }
            must_queries.append(keyword_query)
        
        # 构建完整查询
        if not must_queries:
            # 如果没有任何查询条件，返回空结果
            return []
        
        query = {
            "query": {
                "bool": {
                    "must": must_queries
                }
            },
            "size": top_k,
            "_source": [
                "global_id", "chunk_id", "publish_date", "issuing_agency",
                "notice_title", "document_title", "type", "document_url", 
                "website", "file_name", "char_count", "text"
            ]
        }
        
        print(f"[PolicyKeywordSearcher] 执行检索，关键词={keywords}")
        
        try:
            response = self.es.search(index=self._index_name, body=query)
            results = []
            
            for hit in response['hits']['hits']:
                result = {
                    "global_id": hit['_source'].get('global_id'),
                    "chunk_id": hit['_source'].get('chunk_id'),
                    "publish_date": hit['_source'].get('publish_date'),
                    "issuing_agency": hit['_source'].get('issuing_agency'),
                    "notice_title": hit['_source'].get('notice_title'),
                    "document_title": hit['_source'].get('document_title'),
                    "type": hit['_source'].get('type'),
                    "document_url": hit['_source'].get('document_url'),
                    "website": hit['_source'].get('website'),
                    "file_name": hit['_source'].get('file_name'),
                    "char_count": hit['_source'].get('char_count'),
                    "text": hit['_source'].get('text'),
                    "score": hit['_score']
                }
                results.append(result)
            
            print(f"[PolicyKeywordSearcher] 检索完成，返回{len(results)}条结果")
            return results
            
        except Exception as e:
            print(f"[PolicyKeywordSearcher] 检索失败: {e}")
            return []

    def search(
        self,
        keywords: List[str],
        top_k: int = 15
    ) -> List[PolicySearchResult]:
        """
        便捷的搜索方法
        
        Args:
            keywords: 关键词列表
            top_k: 返回结果数量
            
        Returns:
            List[PolicySearchResult]: 政策文件检索结果
        """
        print(f"[PolicyKeywordSearcher] 开始政策文件关键词检索: {keywords}")
        
        # 执行关键词检索
        raw_results = self.keyword_search(
            manual_keywords=keywords,
            top_k=top_k
        )
        
        # 转换为PolicySearchResult对象
        search_results = []
        for result in raw_results:
            policy_result = PolicySearchResult(
                global_id=result.get("global_id", ""),
                chunk_id=result.get("chunk_id", 0),
                text=result.get("text", ""),
                char_count=result.get("char_count", 0),
                publish_date=result.get("publish_date", ""),
                issuing_agency=result.get("issuing_agency", ""),
                notice_title=result.get("notice_title", ""),
                document_title=result.get("document_title", ""),
                type=result.get("type", ""),
                document_url=result.get("document_url", ""),
                website=result.get("website", ""),
                file_name=result.get("file_name", ""),
                score=result.get("score", 0.0),
                from_methods=["keyword"]
            )
            search_results.append(policy_result)
        
        print(f"[PolicyKeywordSearcher] 政策文件关键词检索完成，返回{len(search_results)}条结果")
        return search_results

    def close(self):
        """关闭连接"""
        try:
            self.es.close()
            print("[PolicyKeywordSearcher] ES连接已关闭")
        except:
            pass
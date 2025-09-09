# tools/keyword_searcher.py
import json
from elasticsearch import Elasticsearch
import sys
import os

# 设置正确的Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
sys.path.insert(0, project_root)
from config.db_config import get_elasticsearch_config

class KeywordSearcher:
    """
    封装关键词检索逻辑，供知识检索系统调用。
    """

    def __init__(self, index_name="reits_announcements"):
        self._index_name = index_name

        es_config = get_elasticsearch_config()
        print("[KeywordSearcher] 正在连接 Elasticsearch...")
        self.es = Elasticsearch(
            [f"{es_config['scheme']}://{es_config['host']}:{es_config['port']}"],
            basic_auth=(es_config['username'], es_config['password']),
            verify_certs=False,
            ssl_show_warn=False
        )
        print(f"[KeywordSearcher] 连接成功，使用索引: {index_name}")

    def keyword_search(
        self,
        query_str="",
        manual_keywords=None,
        fund_code=None,
        top_k=15
    ):
        """
        执行关键词检索
        
        Args:
            query_str: 查询字符串
            manual_keywords: 手动指定的关键词列表
            fund_code: 基金代码过滤
            top_k: 返回结果数量
            
        Returns:
            list: 检索结果
        """
        # 使用手动关键词或查询字符串
        if manual_keywords:
            keywords = manual_keywords if isinstance(manual_keywords, list) else [manual_keywords]
        else:
            keywords = [query_str] if query_str else []
        
        # 构建查询
        must_queries = []
        
        # 关键词匹配
        if keywords:
            keyword_query = {
                "multi_match": {
                    "query": " ".join(keywords),
                    "fields": ["text"],
                    "type": "best_fields",
                    "fuzziness": "AUTO"
                }
            }
            must_queries.append(keyword_query)
        
        # 基金代码过滤
        if fund_code:
            fund_filter = {
                "term": {
                    "fund_code": fund_code
                }
            }
            must_queries.append(fund_filter)
        
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
            "_source": ["global_id", "chunk_id", "source_file", "page_num", "text", 
                       "fund_code", "date", "prev_chunks", "next_chunks"]
        }
        
        print(f"[KeywordSearcher] 执行检索，关键词={keywords}, 基金代码={fund_code}")
        
        try:
            response = self.es.search(index=self._index_name, body=query)
            results = []
            
            for hit in response['hits']['hits']:
                result = {
                    "global_id": hit['_source'].get('global_id'),
                    "chunk_id": hit['_source'].get('chunk_id'),
                    "source_file": hit['_source'].get('source_file'),
                    "page_num": hit['_source'].get('page_num'),
                    "text": hit['_source'].get('text'),
                    "fund_code": hit['_source'].get('fund_code'),
                    "date": hit['_source'].get('date'),
                    "prev_chunks": hit['_source'].get('prev_chunks'),
                    "next_chunks": hit['_source'].get('next_chunks'),
                    "score": hit['_score']
                }
                results.append(result)
            
            print(f"[KeywordSearcher] 检索完成，返回{len(results)}条结果")
            return results
            
        except Exception as e:
            print(f"[KeywordSearcher] 检索失败: {e}")
            return []
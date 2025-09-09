# fulltext_searcher.py
import json
from elasticsearch import Elasticsearch
import sys
import os

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
sys.path.append(project_root)

from knowledge_retrieval.config.db_config import get_elasticsearch_config

class FulltextSearcher:
    """
    全文检索器 - 从ES数据库获取指定文件的全部内容并按chunk_id排序
    """

    def __init__(self, index_name="reits_announcements"):
        self._index_name = index_name

        es_config = get_elasticsearch_config()
        print("[FulltextSearcher] 正在连接 Elasticsearch...")
        self.es = Elasticsearch(
            [f"{es_config['scheme']}://{es_config['host']}:{es_config['port']}"],
            basic_auth=(es_config['username'], es_config['password']),
            verify_certs=False,
            ssl_show_warn=False
        )
        print(f"[FulltextSearcher] 连接成功，使用索引: {index_name}")

    def get_full_document_text(self, file_name: str) -> str:
        """
        获取指定文件的全文内容
        
        Args:
            file_name: 文件名
            
        Returns:
            str: 按chunk_id排序拼接的全文内容
        """
        print(f"[FulltextSearcher] 开始获取文件全文: {file_name}")
        
        # 构建查询条件
        query = {
            "query": {
                "term": {
                    "source_file": file_name
                }
            },
            "size": 10000,  # 设置一个较大的值以获取所有分块
            "sort": [
                {
                    "chunk_id": {
                        "order": "asc"  # 按chunk_id从小到大排序
                    }
                }
            ],
            "_source": ["chunk_id", "text", "source_file", "global_id", "page_num"]
        }
        
        try:
            response = self.es.search(index=self._index_name, body=query)
            hits = response['hits']['hits']
            
            if not hits:
                print(f"[FulltextSearcher] 未找到文件 {file_name} 的任何内容")
                return ""
            
            print(f"[FulltextSearcher] 找到 {len(hits)} 个文本分块")
            
            # 按chunk_id排序并拼接文本
            full_text = ""
            for hit in hits:
                source = hit['_source']
                chunk_text = source.get('text', '')
                full_text += chunk_text
                
                # 打印前几个分块的信息用于调试
                if len(full_text) < 500:  # 只打印前几个分块
                    print(f"[FulltextSearcher] chunk_id={source.get('chunk_id')}, 文本长度={len(chunk_text)}")
            
            print(f"[FulltextSearcher] 全文拼接完成，总长度: {len(full_text)} 字符")
            return full_text
            
        except Exception as e:
            print(f"[FulltextSearcher] 检索失败: {e}")
            return ""

    def get_document_chunks(self, file_name: str) -> list:
        """
        获取指定文件的所有分块信息（包含详细元数据）
        
        Args:
            file_name: 文件名
            
        Returns:
            list: 包含分块信息的列表
        """
        print(f"[FulltextSearcher] 开始获取文件分块信息: {file_name}")
        
        query = {
            "query": {
                "term": {
                    "source_file": file_name
                }
            },
            "size": 10000,
            "sort": [
                {
                    "chunk_id": {
                        "order": "asc"
                    }
                }
            ],
            "_source": ["global_id", "chunk_id", "source_file", "page_num", "text", 
                       "fund_code", "date", "prev_chunks", "next_chunks"]
        }
        
        try:
            response = self.es.search(index=self._index_name, body=query)
            chunks = []
            
            for hit in response['hits']['hits']:
                chunk_info = {
                    "global_id": hit['_source'].get('global_id'),
                    "chunk_id": hit['_source'].get('chunk_id'),
                    "source_file": hit['_source'].get('source_file'),
                    "page_num": hit['_source'].get('page_num'),
                    "text": hit['_source'].get('text'),
                    "fund_code": hit['_source'].get('fund_code'),
                    "date": hit['_source'].get('date'),
                    "prev_chunks": hit['_source'].get('prev_chunks'),
                    "next_chunks": hit['_source'].get('next_chunks')
                }
                chunks.append(chunk_info)
            
            print(f"[FulltextSearcher] 获取到 {len(chunks)} 个分块")
            return chunks
            
        except Exception as e:
            print(f"[FulltextSearcher] 获取分块信息失败: {e}")
            return [] 
# tools/policy_vector_searcher.py
"""
政策文件向量检索器
基于现有VectorSearcher适配政策文件数据库字段
"""
from pymilvus import connections, Collection
from openai import OpenAI
import sys
import os
from typing import List, Optional

# 设置正确的Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))))
sys.path.insert(0, project_root)
from knowledge_retrieval.config.db_config import get_vector_db_config
from knowledge_retrieval.config.model_config import MODEL_CONFIG
from ..models.policy_data_models import PolicySearchResult

class PolicyVectorSearcher:
    """
    政策文件向量检索器
    查询reits_policy_documents集合
    """

    def __init__(
        self,
        collection_name: str = "reits_policy_documents",
        embedding_provider: str = "zhipu",
        embedding_model_name: str = "embedding-3",
        alias_name: str = "policy_vector"
    ):
        # 连接 Milvus
        self._collection_name = collection_name
        self._alias_name = alias_name
        vector_db_config = get_vector_db_config()

        print("[PolicyVectorSearcher] 正在连接 Milvus...")
        try:
            connections.connect(
                alias=alias_name,
                host=vector_db_config['host'],
                port=vector_db_config['port'],
                user=vector_db_config['user'],
                password=vector_db_config['password']
            )
            self.collection = Collection(name=collection_name, using=alias_name)
            self.collection.load()
            print(f"[PolicyVectorSearcher] 已连接到集合: {collection_name}")
        except Exception as e:
            print(f"[PolicyVectorSearcher] Milvus连接失败: {e}")
            print(f"[PolicyVectorSearcher] 请确保:")
            print(f"  1. Milvus服务正在运行")
            print(f"  2. 集合 '{collection_name}' 已经创建")
            print(f"  3. 连接配置正确: {vector_db_config}")
            raise

        # 初始化 Embedding 模型
        self._embedding_config = MODEL_CONFIG[embedding_provider][embedding_model_name]
        print("[PolicyVectorSearcher] 向量生成配置加载完毕:", self._embedding_config)

    def get_embedding(self, text: str):
        """
        使用大模型接口生成文本的向量
        
        Args:
            text: 待生成向量的文本
            
        Returns:
            list: 向量表示
        """
        try:
            client = OpenAI(
                api_key=self._embedding_config["api_key"],
                base_url=self._embedding_config["base_url"]
            )
            
            response = client.embeddings.create(
                model=self._embedding_config["model"],
                input=text
            )
            
            embedding = response.data[0].embedding
            print(f"[PolicyVectorSearcher] 文本向量生成成功，维度: {len(embedding)}")
            return embedding
            
        except Exception as e:
            print(f"[PolicyVectorSearcher] 向量生成失败: {e}")
            raise

    def vector_search(
        self,
        question_embedding: List[float],
        expr: Optional[str] = None,
        top_k: int = 15
    ) -> List[dict]:
        """
        执行向量检索
        
        Args:
            question_embedding: 问题的向量表示
            expr: 过滤表达式
            top_k: 返回结果数量
            
        Returns:
            List[dict]: 检索结果
        """
        try:
            print(f"[PolicyVectorSearcher] 开始向量检索，top_k={top_k}")
            if expr:
                print(f"[PolicyVectorSearcher] 过滤条件: {expr}")
            
            # 政策文件数据库的输出字段
            output_fields = [
                "global_id", "chunk_id", "publish_date", "issuing_agency",
                "notice_title", "document_title", "type", "document_url", 
                "website", "file_name", "char_count", "text"
            ]
            
            search_params = {
                "metric_type": "L2",
                "params": {"nprobe": 32}
            }
            
            results = self.collection.search(
                data=[question_embedding],
                anns_field="embedding",
                param=search_params,
                expr=expr,
                limit=top_k,
                output_fields=output_fields
            )
            
            formatted_results = []
            for hits in results:
                for hit in hits:
                    result_dict = {
                        "global_id": hit.entity.get("global_id"),
                        "chunk_id": hit.entity.get("chunk_id"),
                        "publish_date": hit.entity.get("publish_date"),
                        "issuing_agency": hit.entity.get("issuing_agency"),
                        "notice_title": hit.entity.get("notice_title"),
                        "document_title": hit.entity.get("document_title"),
                        "type": hit.entity.get("type"),
                        "document_url": hit.entity.get("document_url"),
                        "website": hit.entity.get("website"),
                        "file_name": hit.entity.get("file_name"),
                        "char_count": hit.entity.get("char_count"),
                        "text": hit.entity.get("text"),
                        "distance": hit.distance,
                        "score": 1.0 / (1.0 + hit.distance)  # 转换为相似度分数
                    }
                    formatted_results.append(result_dict)
            
            print(f"[PolicyVectorSearcher] 向量检索完成，返回{len(formatted_results)}条结果")
            return formatted_results
            
        except Exception as e:
            print(f"[PolicyVectorSearcher] 向量检索失败: {e}")
            return []

    def search(
        self,
        question: str,
        top_k: int = 15
    ) -> List[PolicySearchResult]:
        """
        便捷的搜索方法
        
        Args:
            question: 检索问题
            top_k: 返回结果数量
            
        Returns:
            List[PolicySearchResult]: 政策文件检索结果
        """
        print(f"[PolicyVectorSearcher] 开始政策文件向量检索: {question[:50]}...")
        
        # 生成问题向量
        embedding = self.get_embedding(question)
        
        # 执行向量检索
        raw_results = self.vector_search(
            question_embedding=embedding,
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
                distance=result.get("distance"),
                from_methods=["vector"]
            )
            search_results.append(policy_result)
        
        print(f"[PolicyVectorSearcher] 政策文件向量检索完成，返回{len(search_results)}条结果")
        return search_results

    def close(self):
        """关闭连接"""
        try:
            connections.disconnect(self._alias_name)
            print("[PolicyVectorSearcher] 连接已关闭")
        except:
            pass
# tools/vector_searcher.py
from pymilvus import connections, Collection
from openai import OpenAI
import sys
import os

# 设置正确的Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
sys.path.insert(0, project_root)
from config.db_config import get_vector_db_config
from config.model_config import MODEL_CONFIG

class VectorSearcher:
    """
    封装向量检索逻辑，供知识检索系统调用。
    """

    def __init__(
        self,
        collection_name: str = "reits_announcement",
        embedding_provider: str = "zhipu",
        embedding_model_name: str = "embedding-3",
        alias_name: str = "default"
    ):
        # 连接 Milvus
        self._collection_name = collection_name
        vector_db_config = get_vector_db_config()

        print("[VectorSearcher] 正在连接 Milvus...")
        connections.connect(
            alias=alias_name,
            host=vector_db_config['host'],
            port=vector_db_config['port'],
            user=vector_db_config['user'],
            password=vector_db_config['password']
        )
        self.collection = Collection(name=collection_name)
        self.collection.load()
        print(f"[VectorSearcher] 已连接到集合: {collection_name}")

        # 初始化 Embedding 模型（通过自定义OpenAI封装）
        self._embedding_config = MODEL_CONFIG[embedding_provider][embedding_model_name]
        print("[VectorSearcher] 向量生成配置加载完毕:", self._embedding_config)

    def get_embedding(self, text: str):
        """
        使用大模型接口生成文本的向量。
        
        Args:
            text (str): 输入文本
            
        Returns:
            list: 向量表示
        """
        client = OpenAI(
            api_key=self._embedding_config["api_key"],
            base_url=self._embedding_config["base_url"]
        )
        
        response = client.embeddings.create(
            model=self._embedding_config["model"],
            input=text
        )
        
        return response.data[0].embedding

    def vector_search(self, question_embedding, expr="", top_k=15):
        """
        执行向量检索
        
        Args:
            question_embedding: 问题的向量表示
            expr: 过滤表达式
            top_k: 返回的结果数量
            
        Returns:
            list: 检索结果
        """
        search_params = {
            "metric_type": "L2",
            "params": {"nprobe": 16}
        }
        
        print(f"[VectorSearcher] 执行向量检索，top_k={top_k}, expr='{expr}'")
        
        results = self.collection.search(
            data=[question_embedding],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=expr,
            output_fields=["global_id", "chunk_id", "source_file", "page_num", "text", 
                          "fund_code", "date", "prev_chunks", "next_chunks"]
        )
        
        # 转换结果格式
        formatted_results = []
        for hits in results:
            for hit in hits:
                result = {
                    "global_id": hit.entity.get("global_id"),
                    "chunk_id": hit.entity.get("chunk_id"),
                    "source_file": hit.entity.get("source_file"),
                    "page_num": hit.entity.get("page_num"),
                    "text": hit.entity.get("text"),
                    "fund_code": hit.entity.get("fund_code"),
                    "date": hit.entity.get("date"),
                    "prev_chunks": hit.entity.get("prev_chunks"),
                    "next_chunks": hit.entity.get("next_chunks"),
                    "distance": hit.distance
                }
                formatted_results.append(result)
        
        print(f"[VectorSearcher] 检索完成，返回{len(formatted_results)}条结果")
        return formatted_results
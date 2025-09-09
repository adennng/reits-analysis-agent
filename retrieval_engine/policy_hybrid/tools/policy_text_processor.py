# tools/policy_text_processor.py
"""
政策文件文本扩展处理器
实现第一次扩展（前1后1）和第二次扩展+合并（前2后2）
"""
from typing import List, Dict
from ..models.policy_data_models import PolicySearchResult, PolicyScoredResult, PolicyFileGroup
from .policy_vector_searcher import PolicyVectorSearcher

class PolicyTextProcessor:
    """政策文件文本扩展处理器"""
    
    def __init__(self):
        self.vector_searcher = PolicyVectorSearcher()
        print("[PolicyTextProcessor] 初始化完成")
    
    def batch_first_expansion(self, search_results: List[PolicySearchResult]) -> List[str]:
        """
        批量第一次扩展：前1后1
        
        Args:
            search_results: 原始检索结果
            
        Returns:
            List[str]: 扩展后的文本列表
        """
        print(f"[PolicyTextProcessor] 开始第一次扩展，处理{len(search_results)}个结果")
        
        expanded_texts = []
        for result in search_results:
            try:
                expanded_text = self._expand_single_result(
                    result, 
                    expand_before=1, 
                    expand_after=1
                )
                expanded_texts.append(expanded_text)
                print(f"[PolicyTextProcessor] chunk_id={result.chunk_id} 第一次扩展完成")
            except Exception as e:
                print(f"[PolicyTextProcessor] chunk_id={result.chunk_id} 第一次扩展失败: {e}")
                expanded_texts.append(result.text)  # 降级使用原文本
        
        print(f"[PolicyTextProcessor] 第一次扩展完成")
        return expanded_texts
    
    def group_by_file_and_second_expansion(
        self, 
        scored_results: List[PolicyScoredResult]
    ) -> List[PolicyFileGroup]:
        """
        按文件分组并进行第二次扩展
        
        Args:
            scored_results: 打分后的结果（已过滤5分）
            
        Returns:
            List[PolicyFileGroup]: 按文件分组的结果
        """
        print(f"[PolicyTextProcessor] 开始按文件分组和第二次扩展")
        
        # 按文件分组
        file_groups = {}
        for result in scored_results:
            document_title = result.search_result.document_title
            if document_title not in file_groups:
                file_groups[document_title] = {
                    'results': [],
                    'publish_date': result.search_result.publish_date,
                    'issuing_agency': result.search_result.issuing_agency,
                    'website': result.search_result.website
                }
            file_groups[document_title]['results'].append(result)
        
        print(f"[PolicyTextProcessor] 分组完成，共{len(file_groups)}个文件")
        
        # 处理每个文件组
        processed_groups = []
        for document_title, group_data in file_groups.items():
            print(f"[PolicyTextProcessor] 处理文件: {document_title}")
            
            file_group = PolicyFileGroup(
                document_title=document_title,
                publish_date=group_data['publish_date'],
                issuing_agency=group_data['issuing_agency'], 
                website=group_data['website'],
                scored_results=group_data['results']
            )
            
            # 为该文件进行第二次扩展和合并
            file_group.merged_text = self._second_expansion_and_merge(group_data['results'])
            processed_groups.append(file_group)
        
        # 按发布日期排序（最新的在前面）
        processed_groups.sort(key=lambda x: x.publish_date, reverse=True)
        
        print(f"[PolicyTextProcessor] 文件分组和第二次扩展完成")
        print(f"[PolicyTextProcessor] 文件已按发布日期排序（最新在前）:")
        for i, group in enumerate(processed_groups, 1):
            print(f"  {i}. {group.document_title} ({group.publish_date})")
        
        return processed_groups
    
    def _second_expansion_and_merge(self, file_results: List[PolicyScoredResult]) -> str:
        """
        对单个文件的结果进行第二次扩展和合并
        
        Args:
            file_results: 同一文件的所有结果
            
        Returns:
            str: 第二次扩展合并后的文本
        """
        if not file_results:
            return ""
        
        document_title = file_results[0].search_result.document_title
        print(f"[PolicyTextProcessor] 文件 {document_title} 进行第二次扩展...")
        
        # 为每个结果进行第二次扩展（前2后2）
        expanded_chunks = []
        for result in file_results:
            try:
                # 计算扩展范围
                center_chunk_id = result.search_result.chunk_id
                start_chunk_id = center_chunk_id - 2
                end_chunk_id = center_chunk_id + 2
                
                # 查询扩展范围内的所有chunk
                chunks = self._query_chunks_range(
                    document_title=document_title,
                    start_chunk_id=start_chunk_id,
                    end_chunk_id=end_chunk_id
                )
                
                expanded_chunks.extend(chunks)
                print(f"[PolicyTextProcessor]   chunk_id={center_chunk_id} 扩展为 {start_chunk_id}-{end_chunk_id}")
                
            except Exception as e:
                print(f"[PolicyTextProcessor]   chunk_id={result.search_result.chunk_id} 第二次扩展失败: {e}")
                # 降级使用原结果
                expanded_chunks.append({
                    'chunk_id': result.search_result.chunk_id,
                    'text': result.search_result.text
                })
        
        # 去重并按chunk_id排序
        unique_chunks = {}
        for chunk in expanded_chunks:
            chunk_id = chunk.get('chunk_id')
            if chunk_id is not None and chunk_id not in unique_chunks:
                unique_chunks[chunk_id] = chunk
        
        sorted_chunks = sorted(unique_chunks.values(), key=lambda x: x.get('chunk_id', 0))
        print(f"[PolicyTextProcessor] 去重排序后共{len(sorted_chunks)}个chunk")
        
        # 合并文本，不连续的chunk_id之间插入省略号
        merged_texts = []
        prev_chunk_id = None
        
        for chunk in sorted_chunks:
            current_chunk_id = chunk.get('chunk_id')
            
            # 检查是否需要插入省略号
            if prev_chunk_id is not None and current_chunk_id != prev_chunk_id + 1:
                merged_texts.append("此处省略...")
                print(f"[PolicyTextProcessor]   在chunk_id={prev_chunk_id}和{current_chunk_id}之间插入省略号")
            
            merged_texts.append(chunk.get('text', ''))
            prev_chunk_id = current_chunk_id
        
        merged_text = "\n".join(merged_texts)
        print(f"[PolicyTextProcessor] 文件 {document_title} 第二次扩展合并完成，总长度: {len(merged_text)}字符")
        
        return merged_text
    
    def _expand_single_result(
        self, 
        result: PolicySearchResult, 
        expand_before: int = 1, 
        expand_after: int = 1
    ) -> str:
        """
        扩展单个检索结果
        
        Args:
            result: 检索结果
            expand_before: 向前扩展数量
            expand_after: 向后扩展数量
            
        Returns:
            str: 扩展后的文本
        """
        center_chunk_id = result.chunk_id
        start_chunk_id = center_chunk_id - expand_before
        end_chunk_id = center_chunk_id + expand_after
        
        # 查询扩展范围内的chunk
        chunks = self._query_chunks_range(
            document_title=result.document_title,
            start_chunk_id=start_chunk_id,
            end_chunk_id=end_chunk_id
        )
        
        # 按chunk_id排序并合并
        chunks.sort(key=lambda x: x.get('chunk_id', 0))
        expanded_text = "\n".join(chunk.get('text', '') for chunk in chunks)
        
        return expanded_text
    
    def _query_chunks_range(
        self,
        document_title: str,
        start_chunk_id: int,
        end_chunk_id: int
    ) -> List[Dict]:
        """
        查询指定范围内的chunk
        
        Args:
            document_title: 文档标题
            start_chunk_id: 起始chunk_id
            end_chunk_id: 结束chunk_id
            
        Returns:
            List[Dict]: chunk列表
        """
        try:
            # 构建查询表达式
            chunk_ids = list(range(start_chunk_id, end_chunk_id + 1))
            chunk_ids_str = ",".join(str(cid) for cid in chunk_ids)
            expr = f'document_title == "{document_title}" && chunk_id in [{chunk_ids_str}]'
            
            results = self.vector_searcher.collection.query(
                expr=expr,
                output_fields=["text", "chunk_id", "global_id"],
                limit=len(chunk_ids) + 5  # 留一些冗余
            )
            
            chunks = []
            for result in results:
                chunks.append({
                    'chunk_id': result.get('chunk_id'),
                    'text': result.get('text', ''),
                    'global_id': result.get('global_id')
                })
            
            return chunks
            
        except Exception as e:
            print(f"[PolicyTextProcessor] 查询chunk范围失败: {e}")
            return []
    
    def close(self):
        """关闭连接"""
        self.vector_searcher.close()
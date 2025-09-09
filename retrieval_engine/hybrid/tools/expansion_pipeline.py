# tools/expansion_pipeline.py
"""
扩展Pipeline工具 - 实现完整的两次扩展-打分-过滤流程
1. 第一次扩展（前1后1）→ 打分 → 过滤3分以下
2. 第二次扩展（前2后2）→ 按分数排序
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from ..models.data_models import SearchResult, ScoredResult
from .text_processor import TextProcessor
from .relevance_scorer import RelevanceScorer
from typing import List, Tuple, Optional

class ExpansionPipeline:
    """扩展Pipeline - 实现完整的两次扩展流程"""
    
    def __init__(self):
        self.text_processor = TextProcessor()
        self.relevance_scorer = RelevanceScorer()
        print("[ExpansionPipeline] 初始化完成")
    
    def process_search_results(
        self, 
        search_results: List[SearchResult], 
        question: str
    ) -> List[ScoredResult]:
        """
        处理检索结果的完整pipeline
        
        Args:
            search_results: 混合检索的原始结果
            question: 用户问题
            
        Returns:
            List[ScoredResult]: 最终处理后的结果（按分数排序）
        """
        print(f"[ExpansionPipeline] 开始处理{len(search_results)}个检索结果")
        
        # 阶段1：第一次扩展 + 打分 + 过滤
        filtered_results = self._stage1_expansion_and_filtering(search_results, question)
        
        if not filtered_results:
            print("[ExpansionPipeline] 第一次扩展后无有效结果，返回空列表")
            return []
        
        # 阶段2：第二次扩展 + 排序
        final_results = self._stage2_expansion_and_ranking(filtered_results, question)
        
        print(f"[ExpansionPipeline] Pipeline完成，最终返回{len(final_results)}个结果")
        return final_results
    

    
    def _stage1_expansion_and_filtering(
        self, 
        search_results: List[SearchResult], 
        question: str
    ) -> List[Tuple[SearchResult, int, str]]:
        """
        阶段1：第一次扩展 + 打分 + 过滤4分以下
        
        Returns:
            List[Tuple[SearchResult, int, str]]: (原始结果, 分数, 第一次扩展文本)
        """
        print(f"[ExpansionPipeline] === 阶段1：第一次扩展+打分+过滤 ===")
        
        # 第一次扩展：前1后1
        print(f"[ExpansionPipeline] 执行第一次扩展（前1后1）...")
        expanded_texts = self.text_processor.batch_first_expansion(search_results)
        
        # 相关性打分
        print(f"[ExpansionPipeline] 执行相关性打分...")
        scores = self.relevance_scorer.batch_score_relevance(question, expanded_texts)
        
        # 过滤4分以下的结果
        print(f"[ExpansionPipeline] 过滤4分以下的结果...")
        filtered_results = []
        for result, score, expanded_text in zip(search_results, scores, expanded_texts):
            if score >= 4:
                filtered_results.append((result, score, expanded_text))
                print(f"[ExpansionPipeline] 保留: global_id={result.global_id}, 分数={score}")
                # 显示原始语块内容和第一次扩展内容
                print(f"[ExpansionPipeline] 原始语块文本: {result.text[:2000]}...")
                print(f"[ExpansionPipeline] 第一次扩展后文本: {expanded_text[:2000]}...")
            else:
                print(f"[ExpansionPipeline] 过滤: global_id={result.global_id}, 分数={score}")
        
        print(f"[ExpansionPipeline] 阶段1完成，保留{len(filtered_results)}/{len(search_results)}个结果")
        return filtered_results
    
    def _stage2_expansion_and_ranking(
        self, 
        filtered_results: List[Tuple[SearchResult, int, str]], 
        question: str
    ) -> List[ScoredResult]:
        """
        阶段2：第二次扩展 + 排序
        
        Args:
            filtered_results: 阶段1过滤后的结果
            
        Returns:
            List[ScoredResult]: 最终结果
        """
        print(f"[ExpansionPipeline] === 阶段2：第二次扩展+排序 ===")
        
        # 提取原始SearchResult用于第二次扩展
        original_results = [item[0] for item in filtered_results]
        
        # 第二次扩展：前2后2（基于原语块的global_id）
        print(f"[ExpansionPipeline] 执行第二次扩展（前2后2）...")
        second_expanded_texts = self.text_processor.batch_second_expansion(original_results)
        
        # 构建最终结果
        final_results = []
        for (original_result, relevance_score, first_expanded_text), second_expanded_text in zip(
            filtered_results, second_expanded_texts
        ):
            scored_result = ScoredResult(
                search_result=original_result,
                relevance_score=relevance_score,
                expanded_text_initial=first_expanded_text,
                expanded_text_final=second_expanded_text,
                from_methods=original_result.from_methods,
                final_score=float(relevance_score)  # 使用相关性分数作为最终分数
            )
            final_results.append(scored_result)
            
            # 显示第二次扩展内容
            print(f"[ExpansionPipeline] global_id={original_result.global_id}, 第二次扩展后文本: {second_expanded_text[:2000]}...")
        
        # 按分数从大到小排序
        final_results.sort(key=lambda x: x.final_score, reverse=True)
        
        print(f"[ExpansionPipeline] 阶段2完成，结果已按分数排序")
        for i, result in enumerate(final_results):
            print(f"[ExpansionPipeline] 排序{i+1}: global_id={result.search_result.global_id}, 分数={result.final_score}")
        
        # 执行智能合并
        merged_results = self.merge_results_by_score_and_continuity(final_results)
        
        return merged_results
    
    def merge_results_by_score_and_continuity(self, scored_results: List[ScoredResult]) -> List[ScoredResult]:
        """
        按分数分组+智能填补的合并方案
        
        Args:
            scored_results: 按分数排序的结果列表
            
        Returns:
            List[ScoredResult]: 合并后的结果（每个source_file一个合并结果）
        """
        print(f"[ExpansionPipeline] === 开始智能合并（按分数分组+连续性填补）===")
        
        # 按source_file分组
        file_groups = {}
        for result in scored_results:
            source_file = result.search_result.source_file
            if source_file not in file_groups:
                file_groups[source_file] = []
            file_groups[source_file].append(result)
        
        merged_results = []
        
        for source_file, results in file_groups.items():
            print(f"[ExpansionPipeline] 处理文件: {source_file}")
            merged_result = self._merge_single_file_results(results, source_file)
            if merged_result:
                merged_results.append(merged_result)
        
        print(f"[ExpansionPipeline] 智能合并完成，从{len(scored_results)}个结果合并为{len(merged_results)}个结果")
        return merged_results
    
    def _merge_single_file_results(self, results: List[ScoredResult], source_file: str) -> ScoredResult:
        """
        合并单个文件的所有结果
        
        Args:
            results: 同一文件的所有结果
            source_file: 文件名
            
        Returns:
            ScoredResult: 合并后的结果
        """
        if not results:
            return None
            
        print(f"[ExpansionPipeline] 文件 {source_file} 有 {len(results)} 个语块需要合并")
        
        # 第1步：按分数分组（不考虑3分）
        score_groups = {5: [], 4: []}
        for result in results:
            score = result.relevance_score
            if score in score_groups:
                score_groups[score].append(result)
                
        # 第2步：为每个结果计算其二次扩展的chunk_id范围
        def get_expansion_range(result: ScoredResult) -> List[int]:
            """获取语块的二次扩展范围（前2后2）"""
            chunk_id = result.search_result.chunk_id
            return list(range(chunk_id - 2, chunk_id + 3))  # 前2后2，共5个
        
        # 第3步：按分数优先级处理，智能填补
        final_chunk_order = []  # 最终的chunk_id顺序
        
        # 处理5分组：建立基础顺序
        if score_groups[5]:
            print(f"[ExpansionPipeline] 处理5分语块({len(score_groups[5])}个)...")
            all_5_chunks = set()
            for result in score_groups[5]:
                chunks = get_expansion_range(result)
                all_5_chunks.update(chunks)
                print(f"[ExpansionPipeline]   语块{result.search_result.chunk_id}(5分) -> 扩展范围{chunks}")
            
            # 去重并排序，形成基础骨架
            final_chunk_order = sorted(list(all_5_chunks))
            print(f"[ExpansionPipeline] 5分组基础顺序: {final_chunk_order}")
        
        # 处理4分组：智能填补
        if score_groups[4]:
            print(f"[ExpansionPipeline] 处理4分语块({len(score_groups[4])}个)...")
            all_4_chunks = set()
            for result in score_groups[4]:
                chunks = get_expansion_range(result)
                all_4_chunks.update(chunks)
                print(f"[ExpansionPipeline]   语块{result.search_result.chunk_id}(4分) -> 扩展范围{chunks}")
            
            final_chunk_order = self._smart_fill_chunks(final_chunk_order, all_4_chunks, "4分")
        
        print(f"[ExpansionPipeline] 最终合并顺序: {final_chunk_order}")
        
        # 第4步：根据最终顺序重新获取文本内容并合并
        merged_text = self._get_merged_text_by_chunks(final_chunk_order, source_file)
        
        # 第5步：创建合并后的结果对象
        # 使用最高分作为合并结果的分数
        max_score = max(result.relevance_score for result in results)
        
        # 使用第一个结果作为模板，更新关键字段
        template_result = results[0]
        merged_result = ScoredResult(
            search_result=SearchResult(
                global_id=f"MERGED_{source_file}_{len(final_chunk_order)}chunks",
                chunk_id=final_chunk_order[0] if final_chunk_order else 0,
                source_file=source_file,
                page_num="merged",
                text=merged_text,
                score=template_result.search_result.score,
                fund_code=template_result.search_result.fund_code,
                date=template_result.search_result.date,
                prev_chunks=[],
                next_chunks=[],
                from_methods=template_result.search_result.from_methods
            ),
            relevance_score=max_score,
            expanded_text_initial=merged_text,  # 合并后就是最终文本
            expanded_text_final=merged_text,
            from_methods=template_result.from_methods,
            final_score=float(max_score)
        )
        
        print(f"[ExpansionPipeline] 文件 {source_file} 合并完成: {len(results)}个语块 -> 1个合并结果")
        return merged_result
    
    def _smart_fill_chunks(self, current_order: List[int], new_chunks: set, group_name: str) -> List[int]:
        """
        智能填补chunk_id到现有顺序中
        
        Args:
            current_order: 当前的chunk_id顺序
            new_chunks: 新要添加的chunk_id集合
            group_name: 分组名称（用于日志）
            
        Returns:
            List[int]: 更新后的chunk_id顺序
        """
        if not new_chunks:
            return current_order
            
        # 去除已存在的chunk_id
        new_chunks = new_chunks - set(current_order)
        if not new_chunks:
            print(f"[ExpansionPipeline] {group_name}组的chunk_id都已存在，无需添加")
            return current_order
        
        # 分离可连接的和独立的chunk_id
        connectable = []  # 能与现有顺序连接的
        independent = []  # 独立的
        
        current_set = set(current_order)
        
        for chunk_id in new_chunks:
            # 检查是否能与现有chunk_id连接（相邻）
            can_connect = False
            for existing_chunk in current_set:
                if abs(chunk_id - existing_chunk) == 1:  # 相邻
                    can_connect = True
                    break
            
            if can_connect:
                connectable.append(chunk_id)
            else:
                independent.append(chunk_id)
        
        print(f"[ExpansionPipeline] {group_name}组: 可连接{len(connectable)}个, 独立{len(independent)}个")
        
        # 先添加可连接的chunk_id
        updated_order = current_order[:]
        for chunk_id in sorted(connectable):
            # 找到合适的插入位置
            inserted = False
            for i in range(len(updated_order) + 1):
                if i == 0:
                    # 插入到开头
                    if not updated_order or chunk_id < updated_order[0]:
                        updated_order.insert(0, chunk_id)
                        inserted = True
                        break
                elif i == len(updated_order):
                    # 插入到末尾
                    if chunk_id > updated_order[-1]:
                        updated_order.append(chunk_id)
                        inserted = True
                        break
                else:
                    # 插入到中间
                    if updated_order[i-1] < chunk_id < updated_order[i]:
                        updated_order.insert(i, chunk_id)
                        inserted = True
                        break
            
            if not inserted:
                # 如果没有找到合适位置，追加到末尾
                updated_order.append(chunk_id)
        
        # 再添加独立的chunk_id（按顺序追加到末尾）
        updated_order.extend(sorted(independent))
        
        print(f"[ExpansionPipeline] {group_name}组填补后顺序: {updated_order}")
        return updated_order
    
    def _get_merged_text_by_chunks(self, chunk_ids: List[int], source_file: str) -> str:
        """
        根据chunk_id列表重新从数据库获取文本并合并
        """
        if not chunk_ids:
            return ""
        print(f"[ExpansionPipeline] 从数据库获取 {len(chunk_ids)} 个chunk的文本...")
        try:
            min_chunk = min(chunk_ids)
            max_chunk = max(chunk_ids)
            expr = f'source_file == "{source_file}" && chunk_id >= {min_chunk} && chunk_id <= {max_chunk}'
            results = self.text_processor.vector_searcher.collection.query(
                expr=expr,
                output_fields=["text", "chunk_id", "global_id"],
                limit=max_chunk - min_chunk + 1 + 10
            )
            print(f"[ExpansionPipeline] 查询到 {len(results)} 个chunk")
            # 只保留需要的chunk_id
            chunk_text_map = {result.get("chunk_id"): result.get("text", "") for result in results if result.get("chunk_id") in chunk_ids}
            merged_texts = []
            for chunk_id in chunk_ids:
                if chunk_id in chunk_text_map:
                    merged_texts.append(chunk_text_map[chunk_id])
                else:
                    print(f"[ExpansionPipeline] 警告: chunk_id={chunk_id} 未找到")
                    merged_texts.append(f"[缺失chunk_id={chunk_id}]")
            merged_text = "\n".join(merged_texts)
            print(f"[ExpansionPipeline] 合并完成: {len(merged_texts)}个chunk, 总长度{len(merged_text)}字符")
            return merged_text
        except Exception as e:
            print(f"[ExpansionPipeline] 合并文本失败: {e}")
            # 降级方案：使用TextProcessor的扩展功能获取相邻文本
            try:
                return self._fallback_get_merged_text(chunk_ids, source_file)
            except Exception as e2:
                print(f"[ExpansionPipeline] 降级方案也失败: {e2}")
                return "合并失败，请查看详细结果"
    
    def _fallback_get_merged_text(self, chunk_ids: List[int], source_file: str) -> str:
        """
        降级方案：使用TextProcessor的查询功能
        """
        print(f"[ExpansionPipeline] 使用降级方案获取文本...")
        
        if not chunk_ids:
            return ""
        
        # 查找一个有效的fund_code（从现有结果中获取）
        fund_code = "default"  # 默认值
        
        # 尝试从第一个chunk_id获取fund_code
        try:
            first_chunk_expr = f'source_file == "{source_file}" && chunk_id == {chunk_ids[0]}'
            first_result = self.text_processor.vector_searcher.collection.query(
                expr=first_chunk_expr,
                output_fields=["fund_code"],
                limit=1
            )
            if first_result and len(first_result) > 0:
                fund_code = first_result[0].get("fund_code", "default")
        except:
            pass
        
        # 使用TextProcessor的查询方法
        min_chunk = min(chunk_ids)
        max_chunk = max(chunk_ids)
        
        try:
            chunks = self.text_processor._query_chunks_from_vector(
                fund_code=fund_code,
                source_file=source_file,
                start_chunk_id=min_chunk,
                end_chunk_id=max_chunk,
                current_chunk_id=-1  # 不排除任何chunk
            )
            
            # 按chunk_id排序并合并
            chunks.sort(key=lambda x: x.chunk_id)
            merged_text = "\n".join(chunk.text for chunk in chunks if chunk.chunk_id in chunk_ids)
            
            print(f"[ExpansionPipeline] 降级方案成功: {len(chunks)}个chunk, 总长度{len(merged_text)}字符")
            return merged_text
            
        except Exception as e:
            print(f"[ExpansionPipeline] 降级方案执行失败: {e}")
            return "文本获取失败"
    
    def format_final_answer(
        self, 
        scored_results: List[ScoredResult]
    ) -> str:
        """
        格式化最终答案 - 通用版本
        
        Args:
            scored_results: 处理后的结果
            
        Returns:
            str: 格式化的答案
        """
        if not scored_results:
            return "未找到相关信息。"
        
        # 使用通用格式
        return self._format_general_answer(scored_results)
    

    
    def _format_general_answer(self, scored_results: List[ScoredResult]) -> str:
        """格式化普通查询答案，只显示第二次扩展后的内容"""
        answer_parts = []
        
        for result in scored_results:
            answer_parts.append(f"**来源文件**：{result.search_result.source_file}")
            answer_parts.append("**检索出的信息**：")
            answer_parts.append(f"\n{result.expanded_text_final}")
            answer_parts.append("")  # 空行分隔
        
        return "\n".join(answer_parts)

# 便捷函数
def process_search_results(
    search_results: List[SearchResult], 
    question: str
) -> List[ScoredResult]:
    """处理检索结果的便捷函数"""
    pipeline = ExpansionPipeline()
    return pipeline.process_search_results(search_results, question)

def format_final_answer(
    scored_results: List[ScoredResult]
) -> str:
    """格式化最终答案的便捷函数 - 通用版本"""
    pipeline = ExpansionPipeline()
    return pipeline.format_final_answer(scored_results) 
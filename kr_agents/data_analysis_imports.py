#!/usr/bin/env python3
"""
数据分析板块专用导入模块

这个模块专门为数据分析板块提供导入，避免触发检索引擎组件的初始化。
通过这种方式，数据分析功能可以独立运行，不会加载VectorSearcher、KeywordSearcher等检索组件。

使用方式：
    from kr_agents.data_analysis_imports import get_python_execution_agent, ReitsAnalysisMainAgent
    
环境变量控制：
    设置 KR_DATA_ANALYSIS_ONLY=true 来启用数据分析专用模式
"""

# 只导入数据分析需要的组件，避免触发检索组件导入

# Python执行Agent - 数据分析的核心组件
from .python_execution_agent import (
    PythonExecutionAgent,
    get_python_execution_agent,
    execute_python_code
)

# 重要：故意不导入以下组件，避免触发检索引擎初始化：
# - retrieval_executor_agent（会触发VectorSearcher、KeywordSearcher初始化）
# - announcement_query_agent（依赖检索组件）
# - agent1_tools（可能依赖检索组件）

# 导出专门用于数据分析的组件
__all__ = [
    # Python执行Agent组件
    "PythonExecutionAgent",
    "get_python_execution_agent", 
    "execute_python_code"
]

__version__ = "1.0.0"
__description__ = """
数据分析板块专用导入模块 - 避免检索组件初始化

🎯 设计目标：
- 让数据分析功能可以独立运行
- 避免加载VectorSearcher、KeywordSearcher、HybridRetrievalTool等检索组件
- 减少不必要的数据库连接和资源占用
- 提高数据分析板块的启动速度

🚫 不包含的组件：
- RetrievalExecutorAgent：会触发Milvus和Elasticsearch连接
- AnnouncementQueryAgent：依赖检索组件
- 各种检索工具：HybridRetrievalTool、FulltextRetrievalTool等

✅ 包含的组件：
- PythonExecutionAgent：数据处理和可视化
- 相关的Python代码执行功能
"""
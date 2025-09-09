# kr_agents/__init__.py
"""
知识检索多智能体模块

基于OpenAI Agents框架的REITs公告信息问答智能体系统
包含Agent1主控调度器和Agent2检索执行器的完整实现

条件导入模式：
- 设置环境变量 KR_DATA_ANALYSIS_ONLY=true 启用数据分析专用模式
- 数据分析专用模式：不加载检索组件，避免Milvus/Elasticsearch连接
- 完整模式（默认）：加载所有组件
"""

import os

# 检查环境变量，决定导入模式
DATA_ANALYSIS_ONLY = os.environ.get('KR_DATA_ANALYSIS_ONLY', 'false').lower() == 'true'

if DATA_ANALYSIS_ONLY:
    # 数据分析专用模式：只导入数据分析相关组件，避免检索组件初始化
    print("🔸 [kr_agents] 数据分析专用模式：跳过检索组件加载")
    
    # 从数据分析专用导入模块导入
    from .data_analysis_imports import *
    
    # 设置有限的 __all__ 列表（仅数据分析组件）
    __all__ = [
        # Python执行Agent组件
        "PythonExecutionAgent",
        "get_python_execution_agent", 
        "execute_python_code"
    ]
    
else:
    # 完整模式：加载所有组件（原有行为）
    print("🔸 [kr_agents] 完整模式：加载所有组件")
    
    # Agent2检索执行器组件
    from .retrieval_executor_agent import (
        RetrievalExecutorAgent,
        QueryParam,
        QueryResult,
        QueryParamModel,
        QueryParamsRequest,
        process_retrieval_queries,
        retrieval_executor_agent
    )

    # Agent1主控调度器组件
    from .announcement_query_agent import (
        AnnouncementQueryAgent,
        UserQuery,
        ProcessingContext,
        ProcessingState,  # 向后兼容别名
        test_announcement_query_agent
    )

    # Agent1专门工具
    from .agent1_tools import (
        FundCodeIdentifier,
        QuestionSplitter,
        FinalAnswerGenerator
    )

    # 已改用新的 PythonExecutionAgent
    from .python_execution_agent import (
        PythonExecutionAgent,
        get_python_execution_agent,
        execute_python_code
    )

    __all__ = [
        # Agent2组件
        "RetrievalExecutorAgent",
        "QueryParam", 
        "QueryResult",
        "QueryParamModel",
        "QueryParamsRequest",
        "process_retrieval_queries",
        "retrieval_executor_agent",
        
        # Agent1组件
        "AnnouncementQueryAgent",
        "UserQuery",
        "ProcessingContext",
        "ProcessingState",  # 向后兼容别名
        "test_announcement_query_agent",
        
            # Agent1工具
        "FundCodeIdentifier",
        "QuestionSplitter",
        "FinalAnswerGenerator",
        
        # 代码执行Agent组件
        "PythonExecutionAgent",
        "get_python_execution_agent",
        "execute_python_code"
    ]

__version__ = "3.0.0"
__description__ = """
REITs公告信息问答多智能体系统 v3.0 - 完整双Agent架构

🚀 核心功能：
- Agent1主控调度器：问题分析、基金识别、流程控制、质量保证
- Agent2检索执行器：混合检索→全文检索降级策略
- OpenAI Agents框架handoff机制：Agent1→Agent2无缝协作
- 直接处理模式：Agent2返回结果后直接生成最终答案
- 专门工具分离：减少token消耗，提升处理效率

🤖 Agent1 - 主控调度器 (AnnouncementQueryAgent)：
- 基金代码智能识别
- 文件范围确定（招募说明书/全库检索）
- 复杂问题拆分和参数组织
- 与Agent2的handoff协作
- 直接处理模式（无重试机制）
- 最终答案生成和用户友好呈现

🔍 Agent2 - 检索执行器 (RetrievalExecutorAgent)：
- 混合检索（向量+关键词）
- 全文检索降级策略
- Agent2自主处理retrieval_content
- 多文件全文检索支持
- 智能失败结果汇总
- 详细的检索日志和错误分析

⚙️ 专门工具集合：
- identify_fund_codes_from_question: 基金代码识别工具
- generate_final_answer: 最终答案生成工具

🔗 集成接口：
- process_announcement_query: 完整查询处理接口
- get_announcement_query_agent: 全局Agent1实例获取
- process_retrieval_queries: Agent2查询执行接口
""" 
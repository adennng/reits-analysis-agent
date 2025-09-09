# kr_agents/announcement_agent_wrapper.py
"""
公告信息问答Agent调用包装器

只提供两种调用方式：
1. Agent as Tool: 被其他Agent的LLM作为工具调用  
2. 直接Python调用: 被其他Agent的Python逻辑直接调用

"""

import sys
import os
from typing import Optional, List

# 添加路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

# OpenAI Agents框架导入
try:
    from agents import Agent, Runner, function_tool
    from agents.models.interface import Model
    _agents_available = True
except ImportError:
    _agents_available = False
    print("⚠️ OpenAI Agents框架不可用，只支持直接Python调用")

# 导入现有的announcement_query_agent（保持原有逻辑不变）
from .announcement_query_agent import AnnouncementQueryAgent

# ==================== Agent as Tool 实现 ====================

@function_tool
async def announcement_query_tool(
    context,
    question: str,
    is_prospectus_query: bool = False, 
    file_names: Optional[List[str]] = None
) -> str:
    """
    公告文件混合检索工具，对特定问题进行向量检索和关键词检索，直接生成答案。
    
    Args:
        context: OpenAI Agents上下文
        question: 用户问题
        is_prospectus_query: 是否为招募说明书查询
        file_names: 文件列表
        
    Returns:
        str: 最终答案
    """
    print("[AnnouncementQueryTool] 收到查询请求")
    print(f"  问题: {question}")
    print(f"  招募说明书查询: {is_prospectus_query}")
    print(f"  文件列表: {file_names}")
    
    try:
        # 直接调用AnnouncementQueryAgent，保持原有逻辑不变
        agent = AnnouncementQueryAgent()
        result = await agent.process_query(
            question=question,
            is_prospectus_query=is_prospectus_query,
            file_names=file_names
        )
        
        print("[AnnouncementQueryTool] 查询完成")
        return result
        
    except Exception as e:
        error_msg = f"公告信息查询失败: {str(e)}"
        print(f"[AnnouncementQueryTool] {error_msg}")
        import traceback
        traceback.print_exc()
        return error_msg

# ==================== 包装器类 ====================

class AnnouncementAgentWrapper:
    """
    公告信息查询Agent包装器
    
    只提供两种调用方式：
    1. as_tool(): 返回供其他Agent使用的工具
    2. process_query(): 直接Python调用
    """
    
    def __init__(self, model: Optional[Model] = None):
        """
        初始化包装器
        
        Args:
            model: 语言模型实例，传递给AnnouncementQueryAgent
        """
        self.model = model
        print("[AnnouncementAgentWrapper] 包装器初始化完成")
    
    def as_tool(self, tool_name: str = None, tool_description: str = None):
        """
        将公告查询功能封装为工具，供其他Agent的LLM调用
        
        Args:
            tool_name: 工具名称，可选
            tool_description: 工具描述，可选
            
        Returns:
            function_tool: 可被其他Agent调用的工具函数
        """
        if not _agents_available:
            raise RuntimeError("OpenAI Agents框架不可用，无法创建工具")
        
        # 返回已定义的工具函数（OpenAI Agents框架中function_tool不支持name和description参数）
        return announcement_query_tool
    
    async def process_query(
        self,
        question: str,
        is_prospectus_query: bool = False,
        file_names: Optional[List[str]] = None
    ) -> str:
        """
        直接Python调用接口
        
        Args:
            question: 用户问题
            is_prospectus_query: 是否为招募说明书查询
            file_names: 文件列表
            
        Returns:
            str: 最终答案
        """
        # 直接调用AnnouncementQueryAgent，不改变任何逻辑
        agent = AnnouncementQueryAgent(self.model)
        return await agent.process_query(
            question=question,
            is_prospectus_query=is_prospectus_query,
            file_names=file_names
        )

# ==================== 便捷接口 ====================

# 全局包装器实例
_global_wrapper = None

def get_announcement_wrapper(model: Optional[Model] = None) -> AnnouncementAgentWrapper:
    """获取公告查询包装器实例（单例模式）"""
    global _global_wrapper
    if _global_wrapper is None:
        _global_wrapper = AnnouncementAgentWrapper(model)
    return _global_wrapper

# ==================== 使用示例 ====================

async def example_direct_call():
    """示例：直接Python调用（与原有方式相同）"""
    print("\n📋 示例1: 直接Python调用")
    
    wrapper = AnnouncementAgentWrapper()
    
    result = await wrapper.process_query(
        question="508056.SH的项目折现率是多少？",
        is_prospectus_query=True
    )
    
    print(f"结果: {result}")

async def example_agent_as_tool():
    """示例：Agent as Tool"""
    if not _agents_available:
        print("⚠️ OpenAI Agents框架不可用，跳过Agent as Tool示例")
        return
        
    print("\n📋 示例2: Agent as Tool")
    
    wrapper = AnnouncementAgentWrapper()
    
    # 创建使用该工具的协调器Agent
    orchestrator_agent = Agent(
        name="OrchestratorAgent",
        instructions="你是一个智能协调器。当用户询问REITs相关问题时，使用公告查询工具来获取准确信息。",
        tools=[wrapper.as_tool()]
    )
    
    # 运行协调器Agent，让LLM决定如何调用工具
    result = await Runner.run(
        orchestrator_agent,
        "请帮我查询508056.SH的项目折现率信息"
    )
    
    print(f"结果: {result.final_output}")

async def main():
    """主函数：演示两种调用方式"""
    print("🧪 公告查询Agent包装器使用示例")
    print("=" * 60)
    
    # 方式1：直接Python调用（原有方式）
    await example_direct_call()
    
    # 方式2：Agent as Tool（新增方式）
    await example_agent_as_tool()
    
    print("\n✅ 示例完成")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
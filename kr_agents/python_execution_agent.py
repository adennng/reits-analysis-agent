# kr_agents/python_execution_agent.py
"""
Python代码执行Agent - 基于OpenAI Agents框架和code-sandbox-mcp

负责安全执行Python代码，包括：
1. 智能使用code-sandbox-mcp工具
2. 动态安装依赖包
3. 文件输入输出处理
4. 结果分析和错误处理
5. 容器生命周期管理
"""

import sys
import os
import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import atexit
import signal

from agents.lifecycle import AgentHooks, RunContextWrapper, RunHooks
from agents.tool import Tool

# 添加路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

# 导入并应用Unicode处理
try:
    from utils.unicode_output_helper import unicode_aware_print, AgentOutputCapture, apply_comprehensive_unicode_fixes
    # 应用全面Unicode修复
    apply_comprehensive_unicode_fixes()
    # 替换print为Unicode感知版本
    print = unicode_aware_print
except ImportError:
    # 如果导入失败，定义备用函数
    def unicode_aware_print(*args, **kwargs):
        __builtins__['print'](*args, **kwargs)
    print = unicode_aware_print

try:
    from agents import Agent
    from agents.models.interface import Model
    from agents.mcp import MCPServerStdio
    _agents_available = True
except ImportError:
    _agents_available = False
    print("⚠️ OpenAI Agents框架不可用")
    
    # 创建模拟类用于开发测试
    class Agent:
        def __init__(self, *args, **kwargs):
            pass
        
        def as_tool(self, **kwargs):
            return None
    
    class MCPServerStdio:
        def __init__(self, *args, **kwargs):
            pass

# 导入配置
from config.model_config import get_glm_4_5_model

# Python执行Agent的专门提示词
PYTHON_EXECUTION_INSTRUCTIONS = """
你是一个专业的Python代码执行专家。你的任务是安全地执行Python代码并返回结果。

## ⚠️ 重要提示
- 如果需要数据而要求中既没有传递具体数据（或数据不全）、也没有提供SQL语句、也没有提供本地文件路径，导致无法执行，则直接返回,要求任务发布者提供完整的数据（或SQL语句、或数据文件路径）。千万不要自己模拟数据！！

## 数据库连接配置

容器中已预置了安全的数据库连接工具，请使用以下方式连接数据库：

```python
from db_utils import get_announcement_connection

# 连接announcement数据库
def fetch_data_from_announcement():
    connection = get_announcement_connection()
    try:
        with connection.cursor() as cursor:
            # 执行SQL查询
            cursor.execute("SELECT ...")
            result = cursor.fetchall()
            return result
    finally:
        connection.close()
```

**重要说明**：
- 请始终使用 `from db_utils import get_announcement_connection` 导入连接函数
- 不要手动配置数据库连接参数
- 务必在finally块中关闭数据库连接

## 你的能力和工具

你拥有以下MCP工具来执行代码：
1. **sandbox_initialize**: 初始化Python执行环境
2. **copy_file**: 将本地单个文件复制到容器中
3. **copy_project**: 将本地目录复制到容器中
4. **write_file_sandbox**: 创建Python代码文件或数据文件
5. **sandbox_exec**: 在沙盒环境中执行命令（包括Python代码）
6. **copy_file_from_sandbox**: 从容器中获取输出文件

## 执行流程

当用户要求执行Python代码时，请严格按照以下步骤：

### 步骤1: 环境初始化
- 使用 `sandbox_initialize` 创建Python执行环境
- **使用本地构建镜像**: {"image": "python-enhanced:latest"}
- 该镜像已预装所有常用数据科学库，无需额外安装
- 记录返回的 container_id

### 步骤2: 确定已经安装的依赖包
- ⚠️ **重要**: python-enhanced:latest镜像已预装如下常用库，请使用如下库完成任务，不要使用pip install自行安装依赖包

#### 📦 预装库详情
**数据处理**:
- pandas 2.3.1, numpy 2.3.1, scipy 1.16.0, scikit-learn 1.7.0

**可视化**:
- matplotlib 3.10.3 (已预配置Noto Sans CJK JP中文字体), seaborn 0.13.2

**文件处理**:
- openpyxl 3.1.5, xlsxwriter 3.2.5, PyPDF2 3.0.1, Pillow 11.3.0

**网络和金融数据**:
- requests 2.32.4, yfinance 0.2.65, websockets 15.0.1

**数据库**:
- PyMySQL 1.1.1, SQLAlchemy 2.0.41, peewee 3.18.2

**实用工具**:
- tqdm 4.67.1, beautifulsoup4 4.13.4, python-dateutil 2.9.0.post0

### 步骤3: 确定数据来源（本地文件或数据库）
- 如果用户提到需要使用本地文件（且提供了文件路径）获取数据，则使用本地文件
- 如果用户提到需要使用数据库（且提供了SQL）获取数据，则使用数据库
- 如果用户对于同一个任务即提供了SQL，又提供了本地文件路径，则先使用本地文件，如果本地文件处理失败，再使用SQL

### 步骤3.5: 本地文件复制（如适用）
**当选择使用本地文件获取数据时：**
- 使用 `copy_file` 复制单个本地文件到容器
- 或使用 `copy_project` 复制整个本地目录到容器
- 复制完成后，文件会出现在容器的/app目录下

**工具调用方式：**
- **copy_file**: 复制单个本地文件
  - 参数: `{"container_id": "容器ID", "local_src_file": "/path/to/local/file.csv"}`
  - 可选参数: `"dest_path"` 指定容器中的文件路径，默认为`/app/原文件名`

- **copy_project**: 复制整个本地目录
  - 参数: `{"container_id": "容器ID", "local_src_dir": "/path/to/local/directory"}`
  - 可选参数: `"dest_dir"` 指定容器中的目录路径，默认为`/app/原目录名`

**重要提醒**：
- **必须先调用`sandbox_initialize`获取container_id**
- 通常情况下不需要指定dest_path/dest_dir，使用默认值即可
- 复制后的文件会自动出现在容器的/app目录下，可直接在Python代码中使用

### 步骤4: 代码文件创建
- 使用 `write_file_sandbox` 创建主代码文件
- 文件名通常为 `main.py` 或根据任务命名
- 如果有输入数据，也要创建相应的数据文件

### 步骤5: 代码执行
- 使用 `sandbox_exec` 执行Python代码
- 命令格式：`["python main.py"]` 或 `["python3 main.py"]`
- 注意捕获输出和错误信息

### 步骤6: 结果处理（**强制执行**）
- 分析执行输出，提取关键信息
- **文件复制要求**: 如果代码生成了文件（如图片、CSV、Excel等），**必须**使用 `copy_file_from_sandbox` 工具复制到指定目录
- **重要**: 调用 `copy_file_from_sandbox` 时必须包含以下参数：
  ```json
  {
    "container_id": "容器ID",
    "container_src_path": "文件在容器中的路径（如：price_trend.png）",
    "local_dest_path": "替换为本地目录"
  }
  ```
- **必须指定完整的 local_dest_path**，否则文件会复制到错误位置
- 整理结果并提供清晰的总结，包含已复制的文件列表

### 步骤7: 结果总结及检查
- 总结全部任务的执行结果，返回前请检查结果中是否包含全部的需求，不要遗漏，如遗漏则补充完成。
- 容器会自动清理，无需手动处理

### Matplotlib绘图最佳实践
**必须遵循的兼容性规则**：
1. **样式使用**: 
   - ❌ 避免使用: `plt.style.use('seaborn')` (新版本不支持)
   - ✅ 推荐使用: `plt.style.use('ggplot')` 或 `plt.style.use('default')`
   - ✅ 或直接不设置样式，使用默认配置

2. **中文字体配置**（推荐添加，镜像已预配置）:
   ```python
   import matplotlib.pyplot as plt
   # 镜像已预配置 Noto Sans CJK JP 字体，通常无需手动设置
   # 如需确保兼容性，可以显式设置：
   plt.rcParams['font.sans-serif'] = ['Noto Sans CJK JP', 'DejaVu Sans']
   plt.rcParams['axes.unicode_minus'] = False
   ```

3. **图表保存**（强制要求）:
   - ❌ 禁止使用: `plt.show()` (容器环境无显示)
   - ✅ 必须使用: `plt.savefig('filename.png', dpi=300, bbox_inches='tight')`

4. **性能优化**:
   - 使用 `figsize=(10, 6)` 而非过大尺寸
   - 添加 `plt.close()` 释放内存
   - 对于复杂图表，使用 `plt.ioff()` 关闭交互模式

5. **图片坐标轴美化（强制要求）**:
   - 当横坐标为日期且数量超过20个时，只显示部分横坐标的标签（例如每隔几个数据点显示一个标签，在matplotib库中，可以使用 xticks 函数来设置横坐标刻度），并且将横坐标标签旋转一定角度。避免出现坐标文字过于拥挤/重叠，影响阅读。

## 最佳实践

1. **性能优化**: 
   - **必须使用python-enhanced:latest镜像**避免安装延迟
   - **跳过不必要的pip install**，利用预装库
   - **编写高效的Python代码**，避免长时间运行
   - **控制执行时间**: 复杂操作应在30秒内完成，避免超时
   - **内存管理**: 及时释放大对象，使用 `del` 和 `gc.collect()`

2. **执行时间控制**:
   - **图表生成**: 控制在10秒内完成

3. **错误处理**: 
   - **总是使用 try-except 包装主要代码**
   - **提供有意义的错误信息**
   - **如果某个步骤失败，分析错误原因并尝试修复**
   - **对于已知兼容性问题，提前规避**

4. **安全考虑**: 所有代码都在隔离环境中运行，但仍要避免恶意代码

5. **资源管理**: 
   - **关闭图形资源**: 使用 `plt.close('all')`
   - **关闭数据库连接**: 使用 `finally` 块确保连接关闭

6. **输出格式**: 
- 提供结构化的执行结果，包括成功状态、输出内容、执行时间等。
- 如果没有完成任务，则不要编造数据，直接返回无法执行的原因

## 每个任务的响应格式

执行完成后，请提供以下信息：
- 执行状态（成功/失败）
- 代码输出结果
- 错误信息（如果有）
- 生成的文件列表
- 执行总结和建议

记住：你的目标是提供安全、可靠、高效的Python代码执行服务。

---
## ⚠️ 系统级约束：工具调用格式要求

**重要：请严格遵循以下格式要求：**

1. **工具调用格式约束**：
   - 使用标准OpenAI function calling格式
   - arguments参数必须是JSON对象，不是字符串
   - 禁止使用自定义标记如 `<｜tool▁call▁end｜>` 或 `<｜tool▁calls▁end｜>`

2. **正确的工具调用示例**：
   ```
   sandbox_initialize: arguments: {{"image": "python-enhanced:latest"}}
   sandbox_exec: arguments: {{"container_id": "abc123", "commands": ["python main.py"]}}
   copy_file: arguments: {{"container_id": "abc123", "local_src_file": "/path/to/file.csv"}}
   ```

3. **严禁的错误格式**：
   ```
   arguments: "\\{{\\"container_id\\": \\"abc123\\"}}"  # ❌ 字符串格式
   <｜tool▁call▁end｜>                                # ❌ 自定义标记
   ```

4. **参数传递规则**：
   - 所有参数直接作为JSON对象传递
   - 避免双重转义或字符串嵌套
   - container_id、commands、文件路径等直接使用，无需额外转义

5. **工具调用机制**：
   - 必须使用标准function calling机制
   - 禁止在文本中直接输出JSON格式的工具调用
   - 禁止使用自定义标记或特殊格式
"""

class PythonExecutionAgent:
    """
    Python代码执行Agent
    
    基于OpenAI Agents框架和code-sandbox-mcp，负责安全执行Python代码
    """
    
    def __init__(self, model: Optional[Model] = None):
        """
        初始化Python代码执行Agent
        
        Args:
            model: 语言模型实例，如果为None则使用默认的get_glm_4_5_model
        """
        self.model = model or get_glm_4_5_model()
        self.mcp_server = None
        self.agent = None
        self._initialized = False
        
        print("[PythonExecutionAgent] Python代码执行Agent初始化开始")
    
    async def _ensure_initialized(self):
        """确保Agent和MCP服务器已初始化"""
        print("[DEBUG] 🔄 开始确保Agent初始化...")
        
        if self._initialized:
            print("[DEBUG] ✅ Agent已经初始化，跳过")
            return
        
        print("[DEBUG] 🔍 检查OpenAI Agents框架可用性...")
        if not _agents_available:
            print("⚠️ OpenAI Agents框架不可用，无法创建Agent")
            return
        print("[DEBUG] ✅ OpenAI Agents框架可用")
        
        print("[DEBUG] 🔍 检查模型初始化状态...")
        if self.model is None:
            print("❌ 模型未正确初始化")
            return
        print(f"[DEBUG] ✅ 模型已初始化: {self.model}")
        
        try:
            # 如果MCP服务器未初始化，则初始化
            if self.mcp_server is None:
                print("[DEBUG] 🔧 开始初始化code-sandbox-mcp服务器...")
                await self._initialize_mcp_server()
                print("[DEBUG] ✅ MCP服务器初始化完成")
            else:
                print("[DEBUG] ✅ MCP服务器已存在，跳过初始化")
            
            # 连接MCP服务器并创建Agent实例
            if self.mcp_server:
                # 检查是否已连接
                if not hasattr(self.mcp_server, '_connected') or not self.mcp_server._connected:
                    print("[DEBUG] 🔗 开始连接MCP服务器...")
                    # 先连接MCP服务器
                    await self.mcp_server.connect()
                    print("[DEBUG] ✅ MCP服务器连接成功")
                else:
                    print("[DEBUG] ✅ MCP服务器已连接，跳过连接")
                
                print("[DEBUG] 🤖 开始创建Agent实例...")
                
                # 设置模型温度值
                if hasattr(self.model, 'temperature'):
                    self.model.temperature = 0.1
                
                self.agent = Agent(
                    name="PythonExecutionAgent",
                    instructions=PYTHON_EXECUTION_INSTRUCTIONS,
                    model=self.model,
                    mcp_servers=[self.mcp_server],
                    handoff_description="执行Python代码进行数据处理、分析、可视化、生产文件。支持数据库查询，需直接提供数据或CSV文件路径或数据查询SQL语句）。"
                )
                print("[DEBUG] ✅ Agent实例创建成功")
                
                # 安装容器清理钩子和文件复制钩子
                self.cleanup_hooks = ContainerCleanupAgentHooks(self.mcp_server)
                self.file_copy_hooks = FileCopyAgentHooks(self.mcp_server)
                
                # 创建复合钩子，包含清理和文件复制功能
                self.agent.hooks = CompositeAgentHooks([self.cleanup_hooks, self.file_copy_hooks])

                # 进程级兜底：退出或收到信号时仍尝试清理
                atexit.register(self.cleanup_hooks.cleanup_sync)
                for sig in (signal.SIGINT, signal.SIGTERM):
                    try:
                        signal.signal(sig, lambda *_: self.cleanup_hooks.cleanup_sync())
                    except Exception:
                        pass

                self._initialized = True
                print("[PythonExecutionAgent] Agent初始化完成")
            else:
                print("❌ MCP服务器初始化失败")
                
        except Exception as e:
            print(f"❌ 初始化失败: {e}")
            import traceback
            traceback.print_exc()
    
    async def _initialize_mcp_server(self):
        """初始化code-sandbox-mcp服务器"""
        try:
            print("[DEBUG] 🔍 开始查找code-sandbox-mcp二进制文件...")
            # 检查code-sandbox-mcp二进制文件是否存在
            mcp_binary_paths = [
                "../mcp_servers/code-sandbox-mcp-main/bin/code-sandbox-mcp",  # 本地构建路径
                "替换为本地目录",  # 默认安装路径
                "code-sandbox-mcp"  # 系统PATH中
            ]
            
            mcp_binary = None
            for i, path in enumerate(mcp_binary_paths):
                print(f"[DEBUG] 📁 检查路径 {i+1}/{len(mcp_binary_paths)}: {path}")
                if os.path.exists(path) and os.access(path, os.X_OK):
                    mcp_binary = path
                    print(f"[DEBUG] ✅ 找到可执行文件: {path}")
                    break
                else:
                    print(f"[DEBUG] ❌ 路径不存在或不可执行: {path}")
            
            if not mcp_binary:
                print("[DEBUG] ⚠️ 未找到二进制文件，尝试下载...")
                print("⚠️ code-sandbox-mcp二进制文件未找到，尝试使用GitHub下载的版本")
                # 如果没有找到，尝试下载
                await self._download_mcp_binary()
                mcp_binary = "替换为本地目录"
            
            if mcp_binary and os.path.exists(mcp_binary):
                print(f"[DEBUG] 🔧 开始创建MCPServerStdio实例...")
                print(f"[DEBUG] 📝 配置参数: command={mcp_binary}, timeout=120s")
                
                # 创建MCP服务器连接
                self.mcp_server = MCPServerStdio(
                    name="code-sandbox-mcp",
                    params={
                        "command": mcp_binary,
                        "args": [],
                    },
                    cache_tools_list=True,  # 缓存工具列表以提高性能
                    client_session_timeout_seconds=120  # 增加超时时间到120秒以适应Docker操作
                )
                
                print(f"[PythonExecutionAgent] MCP服务器配置完成: {mcp_binary}")
                print(f"[DEBUG] ✅ MCPServerStdio实例创建成功")
            else:
                print("❌ 无法找到可执行的code-sandbox-mcp二进制文件")
                
        except Exception as e:
            print(f"❌ MCP服务器初始化失败: {e}")
            import traceback
            traceback.print_exc()
    
    async def _download_mcp_binary(self):
        """下载code-sandbox-mcp二进制文件"""
        try:
            import subprocess
            import platform
            
            # 确保目标目录存在
            target_dir = "替换为本地目录"
            os.makedirs(target_dir, exist_ok=True)
            
            # 根据系统架构确定下载URL
            system = platform.system().lower()
            machine = platform.machine().lower()
            
            if system == "linux" and "x86_64" in machine:
                download_url = "https://github.com/Automata-Labs-team/code-sandbox-mcp/releases/latest/download/code-sandbox-mcp-linux-amd64"
            else:
                print(f"⚠️ 不支持的系统架构: {system}/{machine}")
                return
            
            # 下载二进制文件
            target_file = os.path.join(target_dir, "code-sandbox-mcp")
            subprocess.run([
                "curl", "-L", "-o", target_file, download_url
            ], check=True)
            
            # 设置执行权限
            os.chmod(target_file, 0o755)
            
            print(f"[PythonExecutionAgent] 成功下载MCP二进制文件: {target_file}")
            
        except Exception as e:
            print(f"❌ 下载MCP二进制文件失败: {e}")
    
    def as_tool(
        self, 
        tool_name: str = "execute_python", 
        tool_description: str = "执行Python代码并返回结果"
    ):
        """
        将Agent转换为工具，供其他Agent调用
        
        Args:
            tool_name: 工具名称
            tool_description: 工具描述
            
        Returns:
            工具函数，可被其他Agent使用
        """
        if not _agents_available or not self.agent:
            print("⚠️ Agent未初始化，无法转换为工具")
            return None

        # 如果已经生成过包装后的工具，直接复用提升性能
        if hasattr(self, "_wrapped_tool"):
            return self._wrapped_tool

        from agents.tool import FunctionTool
        from agents import Runner

        import re, asyncio

        async def _invoke(context, input_data):
            """调用 Code Agent 执行任务并确保最后清理容器。
            如果 LLM 未显式复制文件，则尝试根据输出中提取的文件名自动 copy。"""

            container_id: str | None = None
            try:
                result = await Runner.run(
                    starting_agent=self.agent,
                    input=input_data,
                    max_turns=40,
                )

                output_text = str(result.final_output)

                # 获取本轮 container_id（最后一个）
                if hasattr(self, "cleanup_hooks") and self.cleanup_hooks._cids:
                    container_id = self.cleanup_hooks._cids[-1]

                # 自动复制：匹配常见文件名并复制到本地目录
                if container_id:
                    # 创建目标目录
                    target_dir = "替换为本地目录"
                    os.makedirs(target_dir, exist_ok=True)
                    
                    # 扩展文件类型匹配模式（排除代码文件）
                    file_candidates = re.findall(r"[\w\-\.]+\.(?:csv|png|xlsx|txt|json|html|pdf|jpg|jpeg|gif|svg)", output_text)
                    copied_files = []
                    
                    for fname in set(file_candidates):
                        try:
                            # 调用MCP工具复制文件（可能的工具名称）
                            copy_tools = ["copy_file_from_sandbox", "copy_file", "get_file"]
                            success = False
                            
                            for tool_name in copy_tools:
                                try:
                                    result = await self.mcp_server.call_tool(
                                        tool_name,
                                        {
                                            "container_id": container_id,
                                            "container_src_path": f"/app/{fname}",
                                            "local_dest_path": f"{target_dir}/{fname}"
                                        }
                                    )
                                    copied_files.append(f"{target_dir}/{fname}")
                                    print(f"[DEBUG] ✅ 成功复制文件: {fname} -> {target_dir}/{fname}")
                                    success = True
                                    break
                                except Exception as e:
                                    continue
                            
                            if not success:
                                print(f"[DEBUG] ⚠️ 无法复制文件: {fname}")
                                
                        except Exception as e:
                            print(f"[DEBUG] ❌ 复制文件 {fname} 时出错: {e}")
                    
                    if copied_files:
                        output_text += f"\n\n📁 已复制文件到本地:\n" + "\n".join(f"- {f}" for f in copied_files)

                return output_text
            finally:
                # 清理容器
                if hasattr(self, "cleanup_hooks"):
                    try:
                        await self.cleanup_hooks._cleanup()
                    except Exception:
                        pass

        self._wrapped_tool = FunctionTool(
            name=tool_name,
            description=tool_description,
            params_json_schema={
                "type": "object",
                "properties": {
                    "input": {"type": "string", "description": "任务描述"}
                },
                "required": ["input"],
            },
            on_invoke_tool=_invoke,
        )

        return self._wrapped_tool
    
    async def execute_code_directly(
        self,
        code: str,
        requirements: Optional[str] = None,
        input_files: Optional[List[Dict[str, Any]]] = None,
        timeout: int = 60
    ) -> Dict[str, Any]:
        """
        直接执行Python代码（不通过Agent工具调用）
        
        Args:
            code: Python代码字符串
            requirements: pip requirements字符串
            input_files: 输入文件列表 [{"name": "data.csv", "content": "..."}]
            timeout: 执行超时时间（秒）
            
        Returns:
            Dict[str, Any]: 执行结果
        """
        print(f"[DEBUG] 🚀 开始直接执行Python代码")
        print(f"[DEBUG] 📝 代码长度: {len(code)} 字符")
        print(f"[DEBUG] 📦 依赖包: {requirements}")
        print(f"[DEBUG] ⏱️ 超时时间: {timeout}秒")
        
        try:
            print("[DEBUG] 🔄 开始确保Agent初始化...")
            # 确保初始化
            await self._ensure_initialized()
            
            if not self._initialized:
                print("[DEBUG] ❌ Agent未正确初始化")
                return {
                    "success": False,
                    "error": "Agent未正确初始化",
                    "output": "",
                    "files": []
                }
            
            print("[DEBUG] ✅ Agent初始化完成，开始构造执行请求...")
            
            # 构造执行请求
            request = f"""
请执行以下Python代码：

```python
{code}
```

"""
            
            if requirements:
                request += f"\n需要安装的依赖包：\n{requirements}\n"
            
            if input_files:
                request += f"\n输入文件：\n"
                for file_info in input_files:
                    request += f"- {file_info.get('name', 'unknown')}\n"
            
            request += f"\n执行超时限制：{timeout}秒"
            
            print(f"[DEBUG] 📋 构造的请求长度: {len(request)} 字符")
            print(f"[DEBUG] 🤖 开始调用Agent执行...")
            print(f"[DEBUG] 📝 发送给Agent的完整请求:")
            print("=" * 50)
            print(request)
            print("=" * 50)
            
            # 使用Agent执行
            from agents import Runner
            print("[DEBUG] 🔄 导入Runner成功，开始运行...")
            print("[DEBUG] 📞 调用 Runner.run() 启动Agent...")
            result = await Runner.run(
                starting_agent=self.agent,
                input=request
            )
            print("[DEBUG] ✅ Runner执行完成")
            print(f"[DEBUG] 📊 Runner返回结果类型: {type(result)}")
            
            # 解析结果
            final_output = result.final_output if hasattr(result, 'final_output') else str(result)
            print(f"[DEBUG] 📊 最终输出长度: {len(final_output)} 字符")
            
            # 尝试复制生成的文件
            copied_files = []
            try:
                if hasattr(self, "cleanup_hooks") and self.cleanup_hooks._cids:
                    container_id = self.cleanup_hooks._cids[-1]
                    print(f"[DEBUG] 🔍 检测到容器ID: {container_id}，开始复制文件...")
                    
                    # 创建目标目录
                    target_dir = "替换为本地目录"
                    os.makedirs(target_dir, exist_ok=True)
                    
                    # 从输出中提取文件名
                    import re
                    file_candidates = re.findall(r"[\w\-\.]+\.(?:csv|png|xlsx|txt|json|html|pdf|jpg|jpeg|gif|svg|py|ipynb)", final_output)
                    print(f"[DEBUG] 📁 检测到的文件候选: {file_candidates}")
                    
                    for fname in set(file_candidates):
                        try:
                            # 尝试不同的MCP工具名称复制文件
                            copy_tools = ["copy_file_from_sandbox", "copy_file", "get_file"]
                            success = False
                            
                            for tool_name in copy_tools:
                                try:
                                    # 使用正确的参数格式
                                    params = {
                                        "container_id": container_id,
                                        "container_src_path": f"/app/{fname}",
                                        "local_dest_path": f"{target_dir}/{fname}"
                                    }
                                    print(f"[DEBUG] 📋 调用 {tool_name} 参数: {params}")
                                    
                                    result_copy = await self.mcp_server.call_tool(tool_name, params)
                                    print(f"[DEBUG] 📄 复制结果: {result_copy}")
                                    
                                    # 检查文件是否确实复制成功
                                    target_file = f"{target_dir}/{fname}"
                                    if os.path.exists(target_file):
                                        copied_files.append(target_file)
                                        print(f"[DEBUG] ✅ 成功复制文件: {fname} -> {target_file}")
                                        success = True
                                        break
                                    else:
                                        print(f"[DEBUG] ⚠️ 文件复制后未出现在目标位置: {target_file}")
                                        
                                except Exception as e:
                                    print(f"[DEBUG] ⚠️ 工具 {tool_name} 复制失败: {e}")
                                    continue
                            
                            if not success:
                                print(f"[DEBUG] ⚠️ 无法复制文件: {fname}")
                                
                        except Exception as e:
                            print(f"[DEBUG] ❌ 复制文件 {fname} 时出错: {e}")
                    
                    if copied_files:
                        final_output += f"\n\n📁 已复制文件到本地:\n" + "\n".join(f"- {f}" for f in copied_files)
                        
            except Exception as e:
                print(f"[DEBUG] ❌ 文件复制过程出错: {e}")
            
            return {
                "success": True,
                "output": final_output,
                "execution_time": getattr(result, 'execution_time', None),
                "files": copied_files,  # 返回已复制的文件列表
                "raw_result": result
            }
            
        except Exception as e:
            error_msg = f"代码执行失败: {str(e)}"
            print(f"[DEBUG] ❌ 执行异常: {error_msg}")
            print(f"[PythonExecutionAgent] {error_msg}")
            import traceback
            traceback.print_exc()
            
            return {
                "success": False,
                "error": error_msg,
                "output": "",
                "files": []
            }

# -----------------------------------------------------------
# 容器清理钩子：记录 sandbox_initialize 创建的 container_id，并在
# agent 正常结束或异常结束时自动调用 sandbox_stop 清理。
# -----------------------------------------------------------


class ContainerCleanupAgentHooks(AgentHooks):
    """保证本次 Agent run 期间创建的容器最终被删除。"""

    def __init__(self, mcp_server: "MCPServerStdio"):
        super().__init__()
        self.mcp_server = mcp_server
        self._cids: list[str] = []

    async def on_tool_end(
        self,
        context: RunContextWrapper[Any],
        agent: "Agent",
        tool: Tool,
        result: str,
    ) -> None:
        # 只跟踪 sandbox_initialize 返回的 container_id
        if tool.name == "sandbox_initialize" and isinstance(result, str):
            print(f"[DEBUG] 🔍 sandbox_initialize 工具返回结果: {result}")
            
            # 尝试多种格式解析容器ID
            cid = None
            
            # 格式1: "container_id: <id>" - 修复解析逻辑
            if "container_id:" in result:
                import re
                # 使用正则表达式精确提取64位容器ID
                matches = re.search(r'container_id:\s*([a-f0-9]{64})', result)
                if matches:
                    cid = matches.group(1)
            
            # 格式2: 直接是ID（64位十六进制）
            elif len(result.strip()) == 64 and all(c in '0123456789abcdef' for c in result.strip().lower()):
                cid = result.strip()
            
            # 格式3: JSON格式中包含container_id
            elif "container_id" in result and "{" in result:
                try:
                    import json
                    import re
                    
                    # 尝试解析整个JSON
                    try:
                        json_obj = json.loads(result)
                        # 检查是否有text字段包含container_id
                        if isinstance(json_obj, dict) and "text" in json_obj:
                            text_content = json_obj["text"]
                            if "container_id:" in text_content:
                                parts = text_content.split("container_id:", 1)
                                if len(parts) == 2:
                                    cid = parts[1].strip().strip('"').strip("'")
                    except:
                        # 如果JSON解析失败，使用正则表达式
                        matches = re.findall(r'container_id[":]+\s*([a-f0-9]{64})', result)
                        if matches:
                            cid = matches[0]
                except:
                    pass
            
            if cid and len(cid) == 64:
                print(f"[DEBUG] ✅ 成功解析容器ID: {cid}")
                self._cids.append(cid)
            else:
                print(f"[DEBUG] ❌ 无法解析容器ID from: {result}")
                print(f"[DEBUG] 📝 解析到的cid: '{cid}', 长度: {len(cid) if cid else 'None'}")
                # 尝试更宽松的解析
                import re
                matches = re.findall(r'([a-f0-9]{64})', result)
                if matches:
                    cid = matches[0]
                    print(f"[DEBUG] 🔄 通过正则表达式找到容器ID: {cid}")
                    self._cids.append(cid)

    async def on_end(
        self,
        context: RunContextWrapper[Any],
        agent: "Agent",
        output: Any,
    ) -> None:
        # 正常结束也清理
        await self._cleanup()

    async def _cleanup(self):
        """调用 sandbox_stop 清理所有已记录的容器。"""
        if not self._cids:
            return
        
        import logging
        logger = logging.getLogger(__name__)
        
        for cid in list(self._cids):
            try:
                # 添加超时保护，避免清理过程阻塞
                import asyncio
                await asyncio.wait_for(
                    self.mcp_server.call_tool("sandbox_stop", {"container_id": cid}),
                    timeout=30.0  # 30秒超时
                )
                logger.debug(f"成功清理容器: {cid}")
            except asyncio.TimeoutError:
                logger.warning(f"清理容器超时: {cid}")
            except Exception as e:
                logger.warning(f"清理容器失败: {cid}, 错误: {e}")
            finally:
                # 无论成功与否都尝试移除，避免重复
                try:
                    self._cids.remove(cid)
                except ValueError:
                    pass  # 已经被移除了

    # 供外部兜底调用（同步上下文）
    def cleanup_sync(self):
        import asyncio
        import logging

        logger = logging.getLogger(__name__)
        
        try:
            # 检查是否已经在事件循环中
            try:
                loop = asyncio.get_running_loop()
                # 如果已经在事件循环中，创建任务但不等待
                logger.debug("已在事件循环中，创建清理任务")
                task = asyncio.create_task(self._cleanup())
                # 不等待任务完成，避免阻塞
                task.add_done_callback(lambda t: logger.debug(f"清理任务完成: {t.exception() if t.exception() else '成功'}"))
            except RuntimeError:
                # 没有运行中的事件循环，可以安全使用 asyncio.run
                logger.debug("不在事件循环中，使用 asyncio.run")
                asyncio.run(self._cleanup())
        except Exception as e:
            logger.error(f"清理过程中发生错误: {e}")
            # 静默处理错误，避免影响主程序


class FileCopyAgentHooks(AgentHooks):
    """自动复制生成的文件到指定目录的钩子"""

    def __init__(self, mcp_server: "MCPServerStdio"):
        super().__init__()
        self.mcp_server = mcp_server
        self._container_ids: list[str] = []
        self._generated_files: list[str] = []
        self._manually_copied_files: set[str] = set()  # 记录已经手动复制的文件

    async def on_tool_end(
        self,
        context: RunContextWrapper[Any],
        agent: "Agent",
        tool: Tool,
        result: str,
    ) -> None:
        # 记录容器ID
        if tool.name == "sandbox_initialize" and isinstance(result, str):
            cid = self._extract_container_id(result)
            if cid:
                self._container_ids.append(cid)
                print(f"[FileCopyHooks] 🔍 记录容器ID: {cid}")

        # 检测文件生成或复制操作
        if tool.name == "copy_file_from_sandbox" and "Successfully copied" in result:
            # 记录手动复制的文件，避免重复复制
            import re
            matches = re.findall(r'Successfully copied /app/([^/\s]+)', result)
            if matches:
                self._manually_copied_files.update(matches)
                print(f"[FileCopyHooks] 📝 记录手动复制文件: {matches}")
        
        # 只在代码执行后进行自动复制检测
        elif tool.name in ["sandbox_exec"]:
            await self._detect_and_copy_files(result)

    def _extract_container_id(self, result: str) -> Optional[str]:
        """从结果中提取容器ID"""
        import re
        # 使用与ContainerCleanupAgentHooks一致的解析逻辑
        
        # 格式1: "container_id: <id>" - 使用正则表达式精确提取
        if "container_id:" in result:
            matches = re.search(r'container_id:\s*([a-f0-9]{64})', result)
            if matches:
                return matches.group(1)
        
        # 格式2: 直接是ID（64位十六进制）
        if len(result.strip()) == 64 and all(c in '0123456789abcdef' for c in result.strip().lower()):
            return result.strip()
        
        # 格式3: JSON格式中包含container_id
        if "container_id" in result and "{" in result:
            try:
                import json
                # 尝试解析整个JSON
                try:
                    json_obj = json.loads(result)
                    # 检查是否有text字段包含container_id
                    if isinstance(json_obj, dict) and "text" in json_obj:
                        text_content = json_obj["text"]
                        if "container_id:" in text_content:
                            matches = re.search(r'container_id:\s*([a-f0-9]{64})', text_content)
                            if matches:
                                return matches.group(1)
                except:
                    # 如果JSON解析失败，使用正则表达式
                    matches = re.findall(r'container_id[":]+\s*([a-f0-9]{64})', result)
                    if matches:
                        return matches[0]
            except:
                pass
        
        # 最后尝试: 直接查找64位十六进制字符串
        matches = re.findall(r'([a-f0-9]{64})', result.lower())
        if matches:
            return matches[0]
        return None

    async def _detect_and_copy_files(self, result: str):
        """检测并复制生成的文件"""
        if not self._container_ids:
            return

        container_id = self._container_ids[-1]  # 使用最新的容器ID
        
        # 从结果中提取可能的文件名（排除代码文件）
        import re
        file_patterns = [
            r"[\w\-\.]+\.(?:csv|png|xlsx|txt|json|html|pdf|jpg|jpeg|gif|svg)",  # 移除了 py|ipynb
            r"保存为\s*['\"]([^'\"]+)['\"]",
            r"saved.*as\s*['\"]([^'\"]+)['\"]",
            r"图片.*保存.*['\"]([^'\"]+)['\"]"
        ]
        
        files_to_copy = set()
        for pattern in file_patterns:
            matches = re.findall(pattern, result, re.IGNORECASE)
            files_to_copy.update(matches)

        print(f"[FileCopyHooks] 📁 检测到潜在文件: {list(files_to_copy)}")

        # 复制文件到指定目录
        target_dir = "替换为本地目录"
        os.makedirs(target_dir, exist_ok=True)

        for fname in files_to_copy:
            # 跳过已经手动复制的文件
            if fname in self._manually_copied_files:
                print(f"[FileCopyHooks] ⏭️ 跳过已手动复制的文件: {fname}")
                continue
                
            try:
                await self._copy_file_from_container(container_id, fname, target_dir)
            except Exception as e:
                print(f"[FileCopyHooks] ⚠️ 复制文件 {fname} 失败: {e}")

    async def _copy_file_from_container(self, container_id: str, filename: str, target_dir: str):
        """从容器中复制文件"""
        copy_tools = ["copy_file_from_sandbox", "copy_file", "get_file"]
        
        for tool_name in copy_tools:
            try:
                params = {
                    "container_id": container_id,
                    "container_src_path": f"/app/{filename}",
                    "local_dest_path": f"{target_dir}/{filename}"
                }
                
                result = await self.mcp_server.call_tool(tool_name, params)
                
                # 验证文件是否真的复制成功
                target_file = f"{target_dir}/{filename}"
                if os.path.exists(target_file):
                    self._generated_files.append(target_file)
                    print(f"[FileCopyHooks] ✅ 成功复制文件: {filename} -> {target_file}")
                    return True
                else:
                    print(f"[FileCopyHooks] ⚠️ 工具 {tool_name} 执行但文件未出现: {target_file}")
                    
            except Exception as e:
                print(f"[FileCopyHooks] ⚠️ 工具 {tool_name} 执行失败: {e}")
                continue
        
        return False

    async def on_end(
        self,
        context: RunContextWrapper[Any], 
        agent: "Agent",
        output: Any,
    ) -> None:
        """在Agent执行结束时报告复制的文件"""
        if self._generated_files:
            print(f"[FileCopyHooks] 📋 本次执行共复制了 {len(self._generated_files)} 个文件:")
            for file_path in self._generated_files:
                print(f"  - {file_path}")


class CompositeAgentHooks(AgentHooks):
    """组合多个AgentHooks的复合钩子"""
    
    def __init__(self, hooks_list: List[AgentHooks]):
        super().__init__()
        self.hooks = hooks_list

    async def on_agent_start(self, context: RunContextWrapper[Any], agent: "Agent") -> None:
        for hook in self.hooks:
            if hasattr(hook, 'on_agent_start'):
                await hook.on_agent_start(context, agent)

    async def on_tool_start(self, context: RunContextWrapper[Any], agent: "Agent", tool: Tool) -> None:
        for hook in self.hooks:
            if hasattr(hook, 'on_tool_start'):
                await hook.on_tool_start(context, agent, tool)

    async def on_tool_end(self, context: RunContextWrapper[Any], agent: "Agent", tool: Tool, result: str) -> None:
        for hook in self.hooks:
            if hasattr(hook, 'on_tool_end'):
                await hook.on_tool_end(context, agent, tool, result)

    async def on_end(self, context: RunContextWrapper[Any], agent: "Agent", output: Any) -> None:
        for hook in self.hooks:
            if hasattr(hook, 'on_end'):
                await hook.on_end(context, agent, output)

# ==================== 全局实例和导出接口 ====================

# 创建全局实例
_global_python_agent = None

async def get_python_execution_agent(model: Optional[Model] = None) -> PythonExecutionAgent:
    """
    获取全局Python执行Agent实例
    
    Args:
        model: 语言模型实例
        
    Returns:
        PythonExecutionAgent: Agent实例
    """
    global _global_python_agent
    
    print("[DEBUG] 🔍 获取全局Python执行Agent实例...")
    
    if _global_python_agent is None:
        print("[DEBUG] 🆕 创建新的PythonExecutionAgent实例...")
        _global_python_agent = PythonExecutionAgent(model)
        print("[DEBUG] 🔄 开始初始化全局Agent...")
        await _global_python_agent._ensure_initialized()
        print("[DEBUG] ✅ 全局Agent初始化完成")
    else:
        print("[DEBUG] ✅ 使用现有的全局Agent实例")
    
    return _global_python_agent

async def execute_python_code(
    code: str,
    requirements: Optional[str] = None,
    input_files: Optional[List[Dict[str, Any]]] = None,
    timeout: int = 60,
    model: Optional[Model] = None
) -> Dict[str, Any]:
    """
    执行Python代码的便捷接口
    
    Args:
        code: Python代码字符串
        requirements: pip requirements字符串
        input_files: 输入文件列表
        timeout: 执行超时时间
        model: 语言模型实例
        
    Returns:
        Dict[str, Any]: 执行结果
    """
    agent = await get_python_execution_agent(model)
    return await agent.execute_code_directly(
        code=code,
        requirements=requirements,
        input_files=input_files,
        timeout=timeout
    )

# ==================== 测试函数 ====================

async def test_python_execution_agent():
    """测试Python执行Agent的完整功能"""
    print("🧪 测试Python执行Agent")
    print("=" * 80)
    
    # 测试用例
    test_cases = [
        {
            "description": "📋 测试1: 简单Python代码执行",
            "code": """
print("Hello, World!")
print("Python版本信息:")
import sys
print(f"Python {sys.version}")

# 简单计算
result = 2 + 2
print(f"2 + 2 = {result}")
""",
            "requirements": None
        },
        {
            "description": "📋 测试2: 数据分析代码（需要安装pandas）",
            "code": """
import pandas as pd
import numpy as np

# 创建示例数据
data = {
    'name': ['Alice', 'Bob', 'Charlie', 'Diana'],
    'age': [25, 30, 35, 28],
    'salary': [50000, 60000, 70000, 55000]
}

df = pd.DataFrame(data)
print("数据框:")
print(df)

print("\\n统计信息:")
print(df.describe())

print("\\n平均工资:")
print(f"${df['salary'].mean():.2f}")
""",
            "requirements": "pandas numpy"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\\n{test_case['description']}")
        print("-" * 60)
        
        try:
            result = await execute_python_code(
                code=test_case['code'],
                requirements=test_case['requirements']
            )
            
            print(f"✅ 测试{i}完成")
            print(f"📊 执行结果:")
            print(f"🔍 成功状态: {result['success']}")
            
            if result['success']:
                print(f"📝 输出内容:")
                print(result['output'])
                if result.get('files'):
                    print(f"📁 生成文件: {result['files']}")
            else:
                print(f"❌ 错误信息: {result['error']}")
            
        except Exception as e:
            print(f"❌ 测试{i}失败: {e}")
            import traceback
            traceback.print_exc()
        
        print("\\n" + "=" * 80)
    
    print("\\n🎉 Python执行Agent测试完成！")

# 导出接口
__all__ = [
    'PythonExecutionAgent',
    'get_python_execution_agent', 
    'execute_python_code',
    'test_python_execution_agent'
]

if __name__ == "__main__":
    asyncio.run(test_python_execution_agent())
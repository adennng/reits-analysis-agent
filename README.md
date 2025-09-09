# 中国基础设施公募REITs多智能体分析系统

本项目是基于 OpenAI Agent 框架的多智能体项目，是公募 REITs 专属 AI 智能查询平台，提供多板块公募 REITs 信息查询服务。大模型选用 glm-4.5、deepseek-v3、deepseek-r1 等。

## 🌐 在线体验

**前端应用地址**: [www.reitschat.com.cn](https://www.reitschat.com.cn)

## 📊 四大功能查询板块

1. 📈 二级市场数据查询分析

【数据范围】包含已上市公募 REITs、中证 REITs 全收益指数的价格数据

【功能类型】

- 查询特定 REITs 价格数据
- 基于价格数据的指标计算（涨跌幅、波动率等）
- 智能绘制图表
- 生成 excel、csv 等多种格式文件

【agent 特点】应用代码编写及执行 mcp（code-sandbox-mcp）、数据库查询 mcp（mysql_mcp_server），LLM 自主查询 REITs 价格数据并编写代码执行任务，可生成图表、excel 等各类文件。

2. 📢 公告信息一键获取

【数据范围】覆盖全部公募 REITs 已发布的公告内容

【功能类型】

- 可概括特定一段时间发布的公募 REITs 公告信息
- 查询特定 REITs 特定公告中的具体信息

【agent 特点】应用数据库查询 mcp（mysql_mcp_server）、混合检索（向量数据库/Elasticsearch）、全文检索，LLM 自主查询 MySQL 数据库、调用检索工具（混合检索、全文检索）检索答案。

3. 📑 招募说明书信息解析

【数据范围】囊括全部公募 REITs 的招募说明书文本信息

【功能类型】

- 查询特定 REITs 招募说明书中的特定信息

【agent 特点】应用混合检索（向量数据库/Elasticsearch）、全文检索。

4. ⚖️ 政策法规精准查询

【数据范围】收录公募 REITs 相关政策法规文件内容（证监会、交易所、发改委）

【功能类型】

- 查询公募 REITs 政策法规文件内容

【agent 特点】应用混合检索（向量数据库/Elasticsearch）、全文检索。

## 🎬 功能演示

### 📈 二级市场数据查询分析
![二级市场数据查询分析演示](mp4/二级市场v2.gif)

### 📢 公告信息一键获取  
![公告信息一键获取演示](mp4/公告信息v2.gif)

### 📑 招募说明书信息解析
![招募说明书信息解析演示](mp4/招募说明书v2.gif)

### ⚖️ 政策法规精准查询
![政策法规精准查询演示](mp4/政策v2.gif)



## 🚀 快速开始

### 环境要求
- Python 3.8+
- MySQL 数据库
- Milvus 向量数据库
- Elasticsearch

### 安装与运行

1. 克隆本仓库并安装依赖：
   - `pip install -r requirements.txt`
2. 复制 `.env.example` 为 `.env`，填写数据库、向量库、Elasticsearch 以及各模型 API Key：
   - `cp .env.example .env`
3. 运行你需要的 Agent 或调用相应的工具（示例见 `kr_agents/`）。

## 🏗️ 项目结构

```
agent/
├── kr_agents/              # 四大核心智能体
├── business_tools/         # 业务工具层
├── config/                 # 配置管理（从环境变量/.env 读取）
├── database/               # 数据库与 MCP 工具
├── retrieval_engine/       # 检索引擎（全文/混合/招募说明书）
├── mcp_servers/            # MCP 服务器（code-sandbox、MySQL 等）
├── docker/                 # Dockerfile 与运行辅助
├── mp4/                    # 演示视频
├── utils/                  # 工具库
├── requirements.txt
└── README.md
```

联系方式：412447958@qq.com

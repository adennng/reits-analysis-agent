"""
announcement数据库架构信息提供器

为 announcement 数据库的 MCP 查询提供统一的公告信息相关的数据库结构信息，帮助 Agent 准确编写 SQL 语句。
专门针对 announcement 数据库的公告信息相关的结构说明，支持大模型自主查询分析。
"""

# announcement数据库公告信息相关完整架构说明
announcement_DATABASE_SCHEMA = """
# announcement 数据库公告信息相关架构说明

### 🏢 announcement 数据库 - 存储REITs基金全部公告信息数据
---
## 📊 announcement 数据库详细结构

### 核心表结构

#### 1. **`product_info`** - 基金产品信息（数据量：2021年6月21日至今，不超过100个基金）
- `fund_code` (varchar(50)): 基金代码（带后缀），如：180301.SZ
- `short_name` (varchar(50)): 基金简称
- `found_date` (date): 成立日期
- `list_date` (date): 上市日期
- `issue_date` (date): 发行日期

#### 2. **`v_processed_files`** - 全部公告信息表（数据量：2021年6月21日至今，约100个基金全部公告，一共4000多行）
**主要字段**：
- `file_name` (VARCHAR): 完整文件名，格式：xxx.pdf
- `fund_code` (VARCHAR): 基金代码（带后缀，如：180301.SZ
- `date` (DATE): 公告日期
- `doc_type_1` (VARCHAR): 文档类型一级分类
- `doc_type_2` (VARCHAR): 文档类型二级分类
- `announcement_link` (VARCHAR): 公告链接
- `summary` (text): 公告内容摘要

#### 3
#### 4 
...

---
## 🔍 重要注意事项
- SQL语句只允许只读查询（SELECT、SHOW、DESCRIBE、EXPLAIN）,不允许窗口函数。
- 每次查询只允许执行一条只读 SQL 语句，而不能一次执行多条 SELECT 语句。请将多个查询拆分为多次单独执行，或合并为一条合法的单条查询语句。
- mysql数据库版本:5.7.40-log

"""

def get_announcement_database_schema_info() -> str:
    """
    获取announcement数据库架构信息
    
    Returns:
        str: 包含announcement数据库完整结构信息的说明
    """
    return announcement_DATABASE_SCHEMA
"""
announcement数据库中价格数据架构信息提供器

为 announcement数据库中价格数据的 MCP 查询提供统一的数据库结构信息，帮助 Agent 准确编写 SQL 语句。
专门针对 announcement数据库中价格数据结构说明，支持大模型自主查询分析。
"""

# announcement数据库中价格数据完整架构说明
reitstrading_DATABASE_SCHEMA = """
# 数据分析平台数据库架构说明

---

## 📊 announcement数据库中价格数据详细结构

### 核心表结构

#### 1. **`price_data`** - 公募REITs交易数据（数据量：2021年6月21日至今，一共2万多行，约100个基金，单个基金最多1000多行）
- `fund_code` (varchar(50)): 基金代码（有后缀，如：180301.SZ）
- `trade_date` (date): 交易日期
- `open` (decimal(18,4)): 开盘价
- `high` (decimal(18,4)): 最高价
- `low` (decimal(18,4)): 最低价
- `close` (decimal(18,4)): 收盘价
- `change_amt` (decimal(18,4)): 涨跌额
- `pct_chg` (decimal(18,4)): 涨跌幅
- `vol` (bigint): 成交量（手）
- `amount` (decimal(20,2)): 成交额（千元）

#### 2. **`index_price_data`** -指数行情（数据量：2021年6月21日至今，约1000多行）
- `trade_date` (date): 交易日期
- `中证REITs全收益` (decimal(18,4)): 中证REITs全收益指数（932047.CSI）收盘价，

#### 3. **`product_info`** - 公募REITs基金产品信息（数据量：2021年6月21日至今，不超过100个基金）
- `fund_code` (varchar(50)): 基金代码（带后缀），如：180301.SZ
- `short_name` (varchar(50)): 基金简称
- `found_date` (date): 成立日期
- `list_date` (date): 上市日期
- `issue_date` (date): 发行日期

#### 4
#### 5 
...

---

## 🔍 SQL 查询规范与技巧

### 1. 重要注意事项
- SQL语句只允许只读查询（SELECT、SHOW、DESCRIBE、EXPLAIN）,不允许窗口函数。
- fund_code字段是公募REITs基金的唯一标识。
- 每次查询只允许执行一条只读 SQL 语句，而不能一次执行多条 SELECT 语句。请将多个查询拆分为多次单独执行，或合并为一条合法的单条查询语句。
- mysql数据库版本:5.7.40-log
- trade_date字段 (date类型)是交易日期，不包含节假日。如需确认当前日期可取其最大值。如需确定其他具体日期可取目标时间点最近的交易日期。也可考虑大致的交易日数量，比如，最近一年，可考虑大致250个交易日。


这个架构说明帮助你准确理解announcement数据库中关于价格相关的表的数据结构，编写正确的查询语句。

"""

def get_reitstrading_database_schema_info() -> str:
    """
    获取announcement数据库中关于价格架构信息
    
    Returns:
        str: 包含announcement数据库中关于价格完整结构信息的说明
    """
    return reitstrading_DATABASE_SCHEMA
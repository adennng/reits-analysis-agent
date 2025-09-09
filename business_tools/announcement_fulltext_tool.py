#!/usr/bin/env python3
"""
获取公告文件全文信息工具

基于OpenAI Agent框架的工具，用于从announcement数据库的page_data表获取指定文件的完整文本内容。

核心功能：
1. 接收file_name参数
2. 连接announcement数据库
3. 从page_data表获取所有页面文本内容
4. 按页码排序并拼接文本信息
5. 超长阈值自动截断
6. 返回完整的文本信息
"""

import logging
import sys
import os
from typing import Optional

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

try:
    from agents import function_tool
    _agents_available = True
except ImportError:
    _agents_available = False
    function_tool = None

logger = logging.getLogger(__name__)

# 默认配置
DEFAULT_MAX_LENGTH = 20000  # 默认最大字符长度，可根据需要调整

def _get_announcement_db_connection():
    """
    创建announcement数据库连接
    
    Returns:
        connection: 数据库连接对象，失败时返回None
    """
    try:
        import pymysql
        from config.db_config import get_db_announcement_config
        
        config = get_db_announcement_config()
        connection = pymysql.connect(
            host=config["host"],
            port=config["port"],
            user=config["user"],
            password=config["password"],
            database=config["database"],
            charset=config["charset"],
            cursorclass=pymysql.cursors.DictCursor
        )
        return connection
    except Exception as e:
        logger.error(f"创建announcement数据库连接失败: {e}")
        return None

def _get_page_text_content_from_db(file_name: str, max_length: int = DEFAULT_MAX_LENGTH) -> str:
    """
    从page_data表获取指定文件的所有页面文本内容，按页码排序并拼接
    
    Args:
        file_name: 文件名
        max_length: 最大字符长度，超过将被截断
        
    Returns:
        str: 拼接后的完整文本内容，失败时返回空字符串
    """
    try:
        conn = _get_announcement_db_connection()
        if not conn:
            logger.error("无法建立数据库连接")
            return ""
        
        with conn.cursor() as cursor:
            # 查询指定文件的所有页面文本，按页码排序
            sql = """
            SELECT page_num, text
            FROM page_data 
            WHERE file_name = %s
            ORDER BY CAST(page_num AS UNSIGNED)
            """
            cursor.execute(sql, (file_name,))
            results = cursor.fetchall()
        
        conn.close()
        
        if not results:
            logger.warning(f"未找到文件 {file_name} 的页面数据")
            return ""
        
        # 拼接所有页面的文本内容
        full_text = ""
        page_count = 0
        
        for row in results:
            text_content = row.get('text', '')
            if text_content:
                full_text += text_content
                page_count += 1
                
                # 检查是否超过长度限制，提前截断以提高性能
                if len(full_text) > max_length:
                    full_text = full_text[:max_length]
                    logger.info(f"文件 {file_name} 文本内容超过 {max_length} 字符，已截断")
                    break
        
        logger.info(f"成功获取文件 {file_name} 的文本内容，共 {page_count} 页，{len(full_text)} 字符")
        return full_text
        
    except Exception as e:
        logger.error(f"获取页面文本失败，文件: {file_name}, 错误: {e}")
        return ""

@function_tool
def get_announcement_fulltext(file_name: str, max_length: Optional[int] = None) -> str:
    """
    获取指定公告文件的完整文本内容，支持超长内容自动截断。
    
    Args:
        file_name: 要获取文本的文件名（必须包含.pdf等扩展名）
        max_length: 最大字符长度限制，超过将被截断。默认20000字符
        
    Returns:
        str: 拼接后的完整文本内容。如果文件不存在或获取失败，返回空字符串
        
    Example:
        ```python
        # 获取指定公告文件的完整文本
        full_text = get_announcement_fulltext("某基金2024年半年报.pdf")
        
        # 获取文本并限制最大长度
        full_text = get_announcement_fulltext("某基金2024年半年报.pdf", max_length=15000)
        ```
        
    Note:
        - 文件名必须与数据库中page_data表的file_name字段完全匹配
        - 页面按照page_num字段的数值大小排序
        - 空页面内容会被跳过
        - 超长内容会被自动截断，不会抛出异常
    """
    if not _agents_available:
        return "错误：OpenAI Agents框架未安装，无法使用此工具"
    
    if not file_name:
        return "错误：文件名不能为空"
    
    if not file_name.strip():
        return "错误：文件名不能为空白字符"
    
    # 使用默认长度限制
    actual_max_length = max_length if max_length is not None else DEFAULT_MAX_LENGTH
    
    if actual_max_length <= 0:
        return "错误：最大长度限制必须大于0"
    
    try:
        logger.info(f"开始获取文件 {file_name} 的完整文本内容，最大长度限制: {actual_max_length}")
        
        # 获取文本内容
        full_text = _get_page_text_content_from_db(file_name, actual_max_length)
        
        if not full_text:
            return f"未找到文件 {file_name} 的文本内容，请检查文件名是否正确"
        
        return full_text
        
    except Exception as e:
        error_msg = f"获取文件 {file_name} 的文本内容时发生异常: {e}"
        logger.error(error_msg)
        return f"错误：{error_msg}"

# 为了向后兼容，提供一个不使用装饰器的版本
def get_announcement_fulltext_raw(file_name: str, max_length: Optional[int] = None) -> str:
    """
    获取指定公告文件的完整文本内容（原始版本，不使用function_tool装饰器）
    
    Args:
        file_name: 要获取文本的文件名
        max_length: 最大字符长度限制，默认20000字符
        
    Returns:
        str: 拼接后的完整文本内容
    """
    if not file_name or not file_name.strip():
        return "错误：文件名不能为空"
    
    actual_max_length = max_length if max_length is not None else DEFAULT_MAX_LENGTH
    
    if actual_max_length <= 0:
        return "错误：最大长度限制必须大于0"
    
    try:
        full_text = _get_page_text_content_from_db(file_name, actual_max_length)
        
        if not full_text:
            return f"未找到文件 {file_name} 的文本内容，请检查文件名是否正确"
        
        return full_text
        
    except Exception as e:
        error_msg = f"获取文件 {file_name} 的文本内容时发生异常: {e}"
        logger.error(error_msg)
        return f"错误：{error_msg}"

def check_announcement_fulltext_dependencies() -> dict:
    """
    检查工具的依赖项
    
    Returns:
        dict: 依赖检查结果
    """
    result = {
        "agents_framework": _agents_available,
        "pymysql": False,
        "db_config": False,
        "database_connection": False
    }
    
    # 检查pymysql
    try:
        import pymysql
        result["pymysql"] = True
    except ImportError:
        pass
    
    # 检查数据库配置
    try:
        from config.db_config import get_db_announcement_config
        get_db_announcement_config()
        result["db_config"] = True
    except Exception:
        pass
    
    # 检查数据库连接
    if result["pymysql"] and result["db_config"]:
        conn = _get_announcement_db_connection()
        if conn:
            result["database_connection"] = True
            conn.close()
    
    return result

if __name__ == "__main__":
    # 测试工具功能
    print("测试announcement fulltext工具...")
    
    # 检查依赖
    deps = check_announcement_fulltext_dependencies()
    print("依赖检查结果:", deps)
    
    if all(deps.values()):
        print("所有依赖正常，工具可以使用")
    else:
        print("部分依赖缺失，请检查配置")
        for dep, status in deps.items():
            if not status:
                print(f"  ❌ {dep}: 不可用")
            else:
                print(f"  ✅ {dep}: 可用")
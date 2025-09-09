import asyncio
import logging
import os
import sys
import csv
from datetime import datetime
from mysql.connector import connect, Error
from mcp.server import Server
from mcp.types import Resource, Tool, TextContent
from pydantic import AnyUrl

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mysql_mcp_server")

def get_db_config():
    """Get database configuration from environment variables."""
    config = {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER"),
        "password": os.getenv("MYSQL_PASSWORD"),
        "database": os.getenv("MYSQL_DATABASE"),
        # Add charset and collation to avoid utf8mb4_0900_ai_ci issues with older MySQL versions
        # These can be overridden via environment variables for specific MySQL versions
        "charset": os.getenv("MYSQL_CHARSET", "utf8mb4"),
        "collation": os.getenv("MYSQL_COLLATION", "utf8mb4_unicode_ci"),
        # Disable autocommit for better transaction control
        "autocommit": True,
        # Set SQL mode for better compatibility - can be overridden
        "sql_mode": os.getenv("MYSQL_SQL_MODE", "TRADITIONAL")
    }

    # Remove None values to let MySQL connector use defaults if not specified
    config = {k: v for k, v in config.items() if v is not None}

    if not all([config.get("user"), config.get("password"), config.get("database")]):
        logger.error("Missing required database configuration. Please check environment variables:")
        logger.error("MYSQL_USER, MYSQL_PASSWORD, and MYSQL_DATABASE are required")
        raise ValueError("Missing required database configuration")

    return config

# Initialize server
app = Server("mysql_mcp_server")

@app.list_resources()
async def list_resources() -> list[Resource]:
    """List MySQL tables as resources."""
    config = get_db_config()
    try:
        logger.info(f"Connecting to MySQL with charset: {config.get('charset')}, collation: {config.get('collation')}")
        with connect(**config) as conn:
            logger.info(f"Successfully connected to MySQL server version: {conn.get_server_info()}")
            with conn.cursor() as cursor:
                cursor.execute("SHOW TABLES")
                tables = cursor.fetchall()
                logger.info(f"Found tables: {tables}")

                resources = []
                for table in tables:
                    resources.append(
                        Resource(
                            uri=f"mysql://{table[0]}/data",
                            name=f"Table: {table[0]}",
                            mimeType="text/plain",
                            description=f"Data in table: {table[0]}"
                        )
                    )
                return resources
    except Error as e:
        logger.error(f"Failed to list resources: {str(e)}")
        logger.error(f"Error code: {e.errno}, SQL state: {e.sqlstate}")
        return []

@app.read_resource()
async def read_resource(uri: AnyUrl) -> str:
    """Read table contents."""
    config = get_db_config()
    uri_str = str(uri)
    logger.info(f"Reading resource: {uri_str}")

    if not uri_str.startswith("mysql://"):
        raise ValueError(f"Invalid URI scheme: {uri_str}")

    parts = uri_str[8:].split('/')
    table = parts[0]

    try:
        logger.info(f"Connecting to MySQL with charset: {config.get('charset')}, collation: {config.get('collation')}")
        with connect(**config) as conn:
            logger.info(f"Successfully connected to MySQL server version: {conn.get_server_info()}")
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT * FROM {table} LIMIT 100")
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                result = [",".join(map(str, row)) for row in rows]
                return "\n".join([",".join(columns)] + result)

    except Error as e:
        logger.error(f"Database error reading resource {uri}: {str(e)}")
        logger.error(f"Error code: {e.errno}, SQL state: {e.sqlstate}")
        raise RuntimeError(f"Database error: {str(e)}")

@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available MySQL tools."""
    logger.info("Listing tools...")
    return [
        Tool(
            name="execute_sql",
            description="Execute an SQL query on the MySQL server",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The SQL query to execute"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="save_csv_file",
            description="Execute SQL query and save results directly to CSV file, bypassing LLM context limits",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The SQL query to execute"
                    },
                    "filename_prefix": {
                        "type": "string",
                        "description": "Prefix for the CSV filename (optional, default: 'query')"
                    },
                    "export_dir": {
                        "type": "string",
                        "description": "Directory to save the CSV file (optional, default: '替换为本地目录')"
                    }
                },
                "required": ["query"]
            }
        )
    ]

def save_csv_file_impl(query: str, filename_prefix: str = "query", export_dir: str = None) -> dict:
    """Execute SQL query and save results to CSV file."""
    config = get_db_config()
    
    # 设置默认导出目录
    if export_dir is None:
        export_dir = "替换为本地目录"
    
    # 确保目录存在
    os.makedirs(export_dir, exist_ok=True)
    
    # 生成带时间戳的文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{filename_prefix}_{timestamp}.csv"
    filepath = os.path.join(export_dir, filename)
    
    logger.info(f"Saving CSV file: {filepath}")
    
    try:
        with connect(**config) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query)
                
                if cursor.description is None:
                    raise ValueError("Query did not return any results")
                
                # 获取列名和数据
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                
                # 处理数据并保存前几行用于预览
                preview_rows = []
                processed_rows_for_file = []
                
                for i, row in enumerate(rows):
                    # 处理特殊类型
                    processed_row = []
                    for value in row:
                        if value is None:
                            processed_row.append('')
                        elif hasattr(value, 'strftime'):  # datetime/date objects
                            processed_row.append(value.strftime('%Y-%m-%d'))
                        else:
                            processed_row.append(str(value))
                    
                    processed_rows_for_file.append(processed_row)
                    
                    # 保存前5行作为预览
                    if i < 5:
                        preview_rows.append(processed_row)
                
                # 写入CSV文件
                with open(filepath, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(columns)  # 写入列标题
                    for processed_row in processed_rows_for_file:
                        writer.writerow(processed_row)
                
                # 获取文件大小
                file_size = os.path.getsize(filepath)
                file_size_str = f"{file_size/1024:.2f}KB" if file_size > 1024 else f"{file_size}B"
                
                result = {
                    "success": True,
                    "filename": filename,
                    "file_path": filepath,
                    "row_count": len(rows),
                    "column_count": len(columns),
                    "columns": columns,
                    "preview_rows": preview_rows,
                    "preview_count": len(preview_rows),
                    "file_size": file_size_str,
                    "file_size_bytes": file_size,
                    "created_at": timestamp,
                    "export_dir": export_dir,
                    "query": query
                }
                
                logger.info(f"CSV file saved successfully: {filename}, {len(rows)} rows, {len(columns)} columns")
                return result
                
    except Error as e:
        logger.error(f"Database error saving CSV file: {e}")
        return {
            "success": False,
            "error": f"Database error: {str(e)}",
            "query": query
        }
    except Exception as e:
        logger.error(f"Error saving CSV file: {e}")
        return {
            "success": False,
            "error": f"File operation error: {str(e)}",
            "query": query
        }

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute SQL commands."""
    config = get_db_config()
    logger.info(f"Calling tool: {name} with arguments: {arguments}")

    if name == "execute_sql":
        query = arguments.get("query")
        if not query:
            raise ValueError("Query is required")

        try:
            logger.info(f"Connecting to MySQL with charset: {config.get('charset')}, collation: {config.get('collation')}")
            with connect(**config) as conn:
                logger.info(f"Successfully connected to MySQL server version: {conn.get_server_info()}")
                with conn.cursor() as cursor:
                    cursor.execute(query)

                    # Special handling for SHOW TABLES
                    if query.strip().upper().startswith("SHOW TABLES"):
                        tables = cursor.fetchall()
                        result = ["Tables_in_" + config["database"]]  # Header
                        result.extend([table[0] for table in tables])
                        return [TextContent(type="text", text="\n".join(result))]

                    # Handle all other queries that return result sets (SELECT, SHOW, DESCRIBE etc.)
                    elif cursor.description is not None:
                        columns = [desc[0] for desc in cursor.description]
                        try:
                            rows = cursor.fetchall()
                            result_rows = [",".join(map(str, row)) for row in rows]
                            return [TextContent(type="text", text="SQL: " + query + "\n" + "\n".join([",".join(columns)] + result_rows))]
                        except Error as e:
                            logger.warning(f"Error fetching results: {str(e)}")
                            return [TextContent(type="text", text=f"Query executed but error fetching results: {str(e)}")]

                    # Non-SELECT queries
                    else:
                        conn.commit()
                        return [TextContent(type="text", text=f"Query executed successfully. Rows affected: {cursor.rowcount}")]

        except Error as e:
            logger.error(f"Error executing SQL '{query}': {e}")
            logger.error(f"Error code: {e.errno}, SQL state: {e.sqlstate}")
            return [TextContent(type="text", text=f"Error executing query: {str(e)}")]
    
    elif name == "save_csv_file":
        query = arguments.get("query")
        if not query:
            raise ValueError("Query is required")
        
        filename_prefix = arguments.get("filename_prefix", "query")
        export_dir = arguments.get("export_dir")
        
        # 执行CSV文件保存
        result = save_csv_file_impl(query, filename_prefix, export_dir)
        
        if result["success"]:
            # 构建预览数据文本
            preview_text = ""
            if result.get("preview_rows"):
                preview_text = "\n数据预览（前{}行）：\n".format(result.get("preview_count", 0))
                # 添加列标题
                preview_text += ",".join(result['columns']) + "\n"
                # 添加数据行
                for row in result["preview_rows"]:
                    preview_text += ",".join(row) + "\n"
            
            response_text = f"""CSV文件保存成功：
文件名：{result['filename']}
文件路径：{result['file_path']}
数据行数：{result['row_count']}
列数：{result['column_count']}
列名：{', '.join(result['columns'])}
文件大小：{result['file_size']}
创建时间：{result['created_at']}
SQL语句：{result['query']}{preview_text}"""
        else:
            response_text = f"CSV文件保存失败：{result['error']}"
        
        return [TextContent(type="text", text=response_text)]
    
    else:
        raise ValueError(f"Unknown tool: {name}")

async def main():
    """Main entry point to run the MCP server."""
    from mcp.server.stdio import stdio_server

    # Add additional debug output
    print("Starting MySQL MCP server with config:", file=sys.stderr)
    config = get_db_config()
    print(f"Host: {config['host']}", file=sys.stderr)
    print(f"Port: {config['port']}", file=sys.stderr)
    print(f"User: {config['user']}", file=sys.stderr)
    print(f"Database: {config['database']}", file=sys.stderr)

    logger.info("Starting MySQL MCP server...")
    logger.info(f"Database config: {config['host']}/{config['database']} as {config['user']}")

    async with stdio_server() as (read_stream, write_stream):
        try:
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options()
            )
        except Exception as e:
            logger.error(f"Server error: {str(e)}", exc_info=True)
            raise

if __name__ == "__main__":
    asyncio.run(main())
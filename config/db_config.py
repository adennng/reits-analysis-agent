# config/db_config.py
# 数据库配置

import os


def get_db_announcement_config():
    """
    返回 MySQL 数据库 announcement 连接的配置信息（优先读取环境变量）。
    环境变量：
      - DB_ANNOUNCEMENT_HOST, DB_ANNOUNCEMENT_PORT, DB_ANNOUNCEMENT_USER,
        DB_ANNOUNCEMENT_PASSWORD, DB_ANNOUNCEMENT_DATABASE
    """
    db_announcement_config = {
        'host': os.getenv('DB_ANNOUNCEMENT_HOST', '**'),
        'port': int(os.getenv('DB_ANNOUNCEMENT_PORT', '3306')),
        'user': os.getenv('DB_ANNOUNCEMENT_USER', '**'),
        'password': os.getenv('DB_ANNOUNCEMENT_PASSWORD', '**'),
        'database': os.getenv('DB_ANNOUNCEMENT_DATABASE', 'announcement'),
        'charset': 'utf8mb4',
        'init_command': "SET SESSION collation_connection = 'utf8mb4_unicode_ci'"
    }
    return db_announcement_config


def get_vector_db_config():
    """
    返回向量数据库（Milvus）的连接配置信息（优先读取环境变量）。
    环境变量：VECTOR_DB_HOST, VECTOR_DB_PORT, VECTOR_DB_USER, VECTOR_DB_PASSWORD
    """
    vector_db_config = {
        'host': os.getenv('VECTOR_DB_HOST', '**'),
        'port': int(os.getenv('VECTOR_DB_PORT', '19530')),
        'user': os.getenv('VECTOR_DB_USER', '**'),
        'password': os.getenv('VECTOR_DB_PASSWORD', '**')
    }
    return vector_db_config

def get_elasticsearch_config():
    """
    返回 Elasticsearch 数据库的连接配置信息（优先读取环境变量）。
    环境变量：ES_HOST, ES_PORT, ES_USERNAME, ES_PASSWORD, ES_SCHEME
    """
    elasticsearch_config = {
        'host': os.getenv('ES_HOST', '**'),
        'port': int(os.getenv('ES_PORT', '9200')),
        'username': os.getenv('ES_USERNAME', '**'),
        'password': os.getenv('ES_PASSWORD', '**'),
        'scheme': os.getenv('ES_SCHEME', 'http')
    }
    return elasticsearch_config
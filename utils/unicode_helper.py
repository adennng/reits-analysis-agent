#!/usr/bin/env python3
"""
Unicode处理助手

解决中文字符在终端和日志中的显示问题
"""

import json
import re
import sys
import os

def ensure_utf8_environment():
    """确保UTF-8环境设置"""
    utf8_vars = {
        'LANG': 'zh_CN.utf8',
        'LC_ALL': 'zh_CN.utf8', 
        'LC_CTYPE': 'zh_CN.utf8',
        'PYTHONIOENCODING': 'utf-8'
    }
    
    for var, value in utf8_vars.items():
        if os.environ.get(var) != value:
            os.environ[var] = value
            print(f"设置环境变量 {var}={value}")

def decode_unicode_escapes(text):
    """解码Unicode转义序列"""
    if not isinstance(text, str):
        text = str(text)
    
    try:
        # 处理 \uXXXX 格式的Unicode转义
        def replace_unicode(match):
            code = match.group(1)
            try:
                return chr(int(code, 16))
            except ValueError:
                return match.group(0)
        
        # 查找并替换Unicode转义序列
        unicode_pattern = r'\\u([0-9a-fA-F]{4})'
        decoded = re.sub(unicode_pattern, replace_unicode, text)
        return decoded
    except Exception as e:
        print(f"Unicode解码失败: {e}")
        return text

def aggressive_unicode_decode(text):
    """更强力的Unicode解码，专门处理复杂情况"""
    if not isinstance(text, str):
        text = str(text)
    
    # 首先尝试标准的Unicode解码
    original_text = text
    
    try:
        # 先处理双重转义：\\u -> \u
        text = text.replace('\\\\u', '\\u')
        
        # 处理所有可能的Unicode转义格式
        patterns = [
            r'\\u([0-9a-fA-F]{4})',  # 标准格式 \uXXXX
        ]
        
        for pattern in patterns:
            def replace_match(match):
                hex_code = match.group(1)
                try:
                    return chr(int(hex_code, 16))
                except (ValueError, OverflowError):
                    return match.group(0)
            
            # 重复解码直到没有变化
            prev_text = ""
            max_iterations = 5
            iteration = 0
            while prev_text != text and iteration < max_iterations:
                prev_text = text
                text = re.sub(pattern, replace_match, text)
                iteration += 1
        
        # 如果文本发生了变化，说明解码成功
        if text != original_text:
            return text
        else:
            return original_text
            
    except Exception as e:
        # 解码失败时返回原始文本
        return original_text

def format_json_with_chinese(data):
    """格式化包含中文的JSON数据"""
    try:
        if isinstance(data, str):
            # 尝试解析JSON字符串
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                return decode_unicode_escapes(data)
        
        # 格式化JSON，确保中文不被转义
        formatted = json.dumps(
            data, 
            ensure_ascii=False, 
            indent=2, 
            separators=(',', ': '),
            sort_keys=False
        )
        return formatted
    except Exception as e:
        print(f"JSON格式化失败: {e}")
        return str(data)

def clean_debug_output(text):
    """清理调试输出，使中文正确显示"""
    if not text:
        return ""
    
    # 转换为字符串
    text = str(text)
    
    # 递归解码Unicode转义序列，直到没有更多转义
    prev_text = ""
    max_iterations = 10  # 防止无限循环
    iteration = 0
    while prev_text != text and iteration < max_iterations:
        prev_text = text
        text = decode_unicode_escapes(text)
        iteration += 1
    
    # 处理JSON格式的Unicode转义
    if '{' in text and '}' in text:
        # 使用更强的正则表达式匹配JSON
        json_pattern = r'\{(?:[^{}]|{[^{}]*})*\}'
        def format_json_match(match):
            json_str = match.group(0)
            try:
                # 先解码Unicode再解析JSON
                decoded_json = decode_unicode_escapes(json_str)
                parsed = json.loads(decoded_json)
                return format_json_with_chinese(parsed)
            except:
                # 如果JSON解析失败，至少解码Unicode
                return decode_unicode_escapes(json_str)
        
        text = re.sub(json_pattern, format_json_match, text, flags=re.DOTALL)
    
    # 处理其他常见的Unicode编码问题
    text = text.replace('\\\\u', '\\u')  # 双重转义
    
    # 最后再次确保所有Unicode转义都被处理
    text = decode_unicode_escapes(text)
    
    return text

def setup_console_encoding():
    """设置控制台编码"""
    try:
        # 设置标准输出编码
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')
        
        # 设置环境变量
        ensure_utf8_environment()
        
        print("✅ 控制台UTF-8编码设置完成")
        return True
    except Exception as e:
        print(f"⚠️ 控制台编码设置失败: {e}")
        return False

def test_chinese_display():
    """测试中文显示效果"""
    test_texts = [
        "测试中文显示：你好世界！",
        "Unicode转义测试：\\u4f60\\u597d\\u4e16\\u754c",
        '{"name": "\\u6d4b\\u8bd5", "description": "\\u4e2d\\u6587\\u63cf\\u8ff0"}',
        "混合文本：Hello 世界 \\u4f60\\u597d!"
    ]
    
    print("🧪 中文显示测试：")
    print("=" * 50)
    
    for i, text in enumerate(test_texts, 1):
        print(f"原始文本 {i}: {text}")
        cleaned = clean_debug_output(text)
        print(f"清理后   {i}: {cleaned}")
        print("-" * 30)
    
    print("✅ 测试完成")

if __name__ == "__main__":
    setup_console_encoding()
    test_chinese_display()
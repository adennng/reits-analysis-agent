#!/usr/bin/env python3
"""
统一的Unicode输出处理模块

为所有Agent提供统一的Unicode处理功能，确保中文正确显示。
"""

import sys
import os
import builtins

# 保存原始print函数以避免递归
_original_print = builtins.print

# 导入现有的Unicode处理函数
try:
    from utils.unicode_helper import aggressive_unicode_decode, clean_debug_output, ensure_utf8_environment
except ImportError:
    def aggressive_unicode_decode(text):
        """后备的Unicode解码函数"""
        if not isinstance(text, str):
            return str(text)
        try:
            import re
            pattern = r'\\u([0-9a-fA-F]{4})'
            def replace_match(match):
                hex_code = match.group(1)
                try:
                    return chr(int(hex_code, 16))
                except (ValueError, OverflowError):
                    return match.group(0)
            
            # 重复解码直到没有变化
            prev_text = ""
            max_iterations = 3
            iteration = 0
            while prev_text != text and iteration < max_iterations and '\\u' in text:
                prev_text = text
                text = re.sub(pattern, replace_match, text)
                iteration += 1
            
            return text
        except Exception:
            return str(text)
    
    def clean_debug_output(text):
        return str(text)
    
    def ensure_utf8_environment():
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        if 'LC_CTYPE' not in os.environ:
            os.environ['LC_CTYPE'] = 'zh_CN.UTF-8'

def unicode_aware_print(*args, **kwargs):
    """全局的Unicode感知print函数"""
    processed_args = []
    for arg in args:
        if isinstance(arg, str) and '\\u' in arg:
            processed_arg = aggressive_unicode_decode(arg)
            processed_args.append(processed_arg)
        else:
            processed_args.append(arg)
    
    # 使用原始print函数避免递归
    _original_print(*processed_args, **kwargs)

def setup_unicode_environment_for_agents():
    """为所有Agent设置Unicode环境"""
    # 设置基础Unicode环境
    ensure_utf8_environment()
    
    # 设置Python输出编码
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    
    # 设置环境变量
    os.environ['PYTHONIOENCODING'] = 'utf-8:replace'
    os.environ['LC_CTYPE'] = 'zh_CN.UTF-8'
    
    _original_print("✅ [Unicode] 所有Agent的Unicode环境设置完成")

def apply_global_unicode_fixes():
    """应用全局Unicode修复"""
    setup_unicode_environment_for_agents()
    
    # 替换内置print
    builtins.print = unicode_aware_print
    
    _original_print("🔧 [Unicode] 全局Unicode修复已应用")

class AgentOutputCapture:
    """Agent输出捕获和Unicode处理器"""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.captured_outputs = []
        
    def capture_and_decode(self, output) -> str:
        """捕获并解码Agent输出"""
        if not output:
            return ""
            
        output_str = str(output)
        
        # 如果包含Unicode转义，进行解码
        if '\\u' in output_str:
            decoded_output = aggressive_unicode_decode(output_str)
            self.captured_outputs.append({
                'original': output_str,
                'decoded': decoded_output,
                'agent': self.agent_name
            })
            return decoded_output
        
        return output_str

def decode_agent_output(text):
    """简单的Agent输出解码函数"""
    if isinstance(text, str) and '\\u' in text:
        return aggressive_unicode_decode(text)
    return str(text)

def patch_json_encoder():
    """修补JSON编码器以处理Unicode转义"""
    import json
    import builtins
    
    # 保存原始的json.dumps
    original_json_dumps = json.dumps
    
    def unicode_aware_json_dumps(obj, *args, **kwargs):
        """Unicode感知的JSON dumps"""
        # 确保ensure_ascii=False，避免中文被转义
        kwargs.setdefault('ensure_ascii', False)
        result = original_json_dumps(obj, *args, **kwargs)
        
        # 如果结果仍然包含Unicode转义，进行解码
        if isinstance(result, str) and '\\u' in result:
            try:
                result = aggressive_unicode_decode(result)
            except:
                pass  # 如果解码失败，返回原始结果
                
        return result
    
    # 替换全局的json.dumps
    json.dumps = unicode_aware_json_dumps
    
    # 也要替换内置的json模块
    try:
        import sys
        if 'json' in sys.modules:
            sys.modules['json'].dumps = unicode_aware_json_dumps
    except:
        pass

def patch_agent_serialization():
    """修补Agent框架的序列化过程"""
    try:
        # 尝试修补openai-agents的序列化
        from agents.tool import Tool
        from agents import Agent
        
        # 保存原始方法
        if hasattr(Tool, '_original_to_dict'):
            return  # 已经修补过了
        
        # 修补Tool的序列化
        if hasattr(Tool, 'to_dict'):
            Tool._original_to_dict = Tool.to_dict
            
            def unicode_aware_to_dict(self):
                result = self._original_to_dict()
                # 处理结果中的Unicode转义
                if isinstance(result, dict):
                    for key, value in result.items():
                        if isinstance(value, str) and '\\u' in value:
                            result[key] = aggressive_unicode_decode(value)
                        elif isinstance(value, dict):
                            for sub_key, sub_value in value.items():
                                if isinstance(sub_value, str) and '\\u' in sub_value:
                                    value[sub_key] = aggressive_unicode_decode(sub_value)
                return result
            
            Tool.to_dict = unicode_aware_to_dict
        
        # 修补Agent的序列化
        if hasattr(Agent, '_serialize_tools'):
            Agent._original_serialize_tools = Agent._serialize_tools
            
            def unicode_aware_serialize_tools(self):
                result = self._original_serialize_tools()
                # 处理工具序列化结果中的Unicode
                if isinstance(result, list):
                    for tool_info in result:
                        if isinstance(tool_info, dict):
                            for key, value in tool_info.items():
                                if isinstance(value, str) and '\\u' in value:
                                    tool_info[key] = aggressive_unicode_decode(value)
                                elif isinstance(value, dict) and 'description' in value:
                                    if '\\u' in value['description']:
                                        value['description'] = aggressive_unicode_decode(value['description'])
                return result
            
            Agent._serialize_tools = unicode_aware_serialize_tools
            
    except ImportError:
        pass  # agents模块不可用
    except Exception as e:
        _original_print(f"⚠️ [Unicode] Agent序列化修补失败: {e}")

def apply_comprehensive_unicode_fixes():
    """应用全面的Unicode修复"""
    setup_unicode_environment_for_agents()
    
    # 修补JSON编码器
    patch_json_encoder()
    
    # 修补Agent框架序列化
    patch_agent_serialization()
    
    # 替换内置print
    import builtins
    builtins.print = unicode_aware_print
    
    _original_print("🔧 [Unicode] 全面Unicode修复已应用（包含JSON和Agent序列化修补）")

if __name__ == "__main__":
    # 测试Unicode处理功能
    test_cases = [
        "\\u4f60\\u597d\\u4e16\\u754c",  # 你好世界
        "\\u57fa\\u91d1\\u4ee3\\u7801: 508089",  # 基金代码: 508089
        '{"name": "\\u534e\\u590f\\u57fa\\u91d1"}',  # {"name": "华夏基金"}
    ]
    
    _original_print("🧪 测试Unicode输出处理器...")
    for i, test_case in enumerate(test_cases, 1):
        _original_print(f"测试 {i}: {test_case}")
        decoded = aggressive_unicode_decode(test_case)
        _original_print(f"解码结果: {decoded}")
        _original_print("-" * 50)
    
    _original_print("✅ Unicode输出处理器测试完成") 
# config/model_config.py
# LLM模型配置

import os

MODEL_CONFIG = {
    "zhipu": {
        "embedding-3": {
            "model": "embedding-3",
            "api_key": os.getenv("ZHIPU_API_KEY", "**"),
            "base_url": os.getenv("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/")
        },
        "glm-4.5": {
            "model": "glm-4.5",
            "api_key": os.getenv("ZHIPU_API_KEY", "**"),
            "base_url": os.getenv("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/")
        },
    },
    "ali": {
        "deepseek-v3": {
            "model": "deepseek-v3",
            "api_key": os.getenv("ALI_API_KEY", "**"),
            "base_url": os.getenv("ALI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        },
        "qwen-long": {
            "model": "qwen-long",
            "api_key": os.getenv("ALI_API_KEY", "**"),
            "base_url": os.getenv("ALI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        },
         "deepseek-r1": {
                  "model": "deepseek-r1",
                  "api_key": os.getenv("ALI_API_KEY", "**"),
                  "base_url": os.getenv("ALI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
         },
    },
    "deepseek": {
        "deepseek-chat": {
            "model": "deepseek-chat",
            "api_key": os.getenv("DEEPSEEK_API_KEY", "**"),
            "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        },
        "deepseek-reasoner": {
            "model": "deepseek-reasoner",
            "api_key": os.getenv("DEEPSEEK_API_KEY", "**"),
            "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        },
    }
}

# 模型创建功能
def create_model(provider: str = "ali", model_name: str = "deepseek-v3"):
    """
    根据配置创建模型实例
    
    Args:
        provider: 提供商名称，默认 "ali"
        model_name: 模型名称，默认 "deepseek-v3"
        
    Returns:
        OpenAIChatCompletionsModel 或 None
    """
    try:
        from openai import AsyncOpenAI
        from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
        
        # 获取配置
        config = MODEL_CONFIG.get(provider, {}).get(model_name)
        if not config:
            print(f"❌ 未找到 {provider}/{model_name} 配置")
            return None
        
        print(f"🤖 使用 {provider}/{model_name} 模型")
        
        # 创建客户端和模型
        openai_client = AsyncOpenAI(
            api_key=config['api_key'],
            base_url=config['base_url']
        )
        
        return OpenAIChatCompletionsModel(
            model=config['model'],
            openai_client=openai_client
        )
        
    except ImportError as e:
        print(f"⚠️ OpenAI Agents框架不可用: {e}")
        return None
    except Exception as e:
        print(f"❌ 创建模型失败: {e}")
        return None

def get_deepseek_v3_model():
    """快捷方式：获取deepseek-v3模型"""
    return create_model("ali", "deepseek-v3")

def get_deepseek_r1_model():
    """快捷方式：获取deepseek-r1模型"""
    return create_model("ali", "deepseek-r1")
  
def get_deepseek_reasoner_model():
    """快捷方式：获取deepseek-reasoner模型"""
    return create_model("deepseek", "deepseek-reasoner")    

def get_deepseek_chat_model():
    """快捷方式：获取deepseek-reasoner模型"""
    return create_model("deepseek", "deepseek-chat")   

def get_glm_4_5_model():
    """快捷方式：获取glm-4.5模型"""
    return create_model("zhipu", "glm-4.5")   


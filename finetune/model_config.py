# LLM模型配置

MODEL_CONFIG = {
    "zhipu": {
        "embedding-3": {
            "model": "embedding-3",
            "api_key": "***",
            "base_url": "https://open.bigmodel.cn/api/paas/v4/"
        },
        "glm-4.5": {
            "model": "glm-4.5",
            "api_key": "***",
            "base_url": "https://open.bigmodel.cn/api/paas/v4/"
        },
        "glm-4.6": {
            "model": "glm-4.6",
            "api_key": "***",
            "base_url": "https://open.bigmodel.cn/api/paas/v4/"
        },
    },
    "gpt": {
        "gpt-5-pro": {
            "model": "gpt-5-pro",
            "api_key": "***",
            "base_url": "https://jeniya.top/v1"
        },
        "gpt-5-2025-08-07": {
            "model": "gpt-5-2025-08-07",
            "api_key": "***",
            "base_url": "https://jeniya.top/v1"
        },
        "o3": {
            "model": "o3",
            "api_key": "***",
            "base_url": "https://jeniya.top/v1"
        },
    },
    "ali": {
        "qwen3-14b": {
            "model": "qwen3-14b",
            "api_key": "***",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"
        },
        "qwen3-8b": {
            "model": "qwen3-8b",
            "api_key": "***",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"
        },
         "qwen3-235b-a22b": {
                  "model": "qwen3-235b-a22b",
                  "api_key": "***",
                  "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"
         },
    },
    "deepseek": {
        "deepseek-chat": {
            "model": "deepseek-chat",
            "api_key": "***",
            "base_url": "https://api.deepseek.com"
        },
        "deepseek-reasoner": {
            "model": "deepseek-reasoner",
            "api_key": "***",
            "base_url": "https://api.deepseek.com"
        },
    }
}


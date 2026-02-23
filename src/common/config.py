"""共享配置读取

从 config/config.yaml 中读取全局配置项，供各模块复用。
"""

import yaml

_CONFIG_PATH = "config/config.yaml"
_cache: dict | None = None


def _load() -> dict:
    global _cache
    if _cache is None:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            _cache = yaml.safe_load(f)
    return _cache


def reset_cache() -> None:
    """重置配置缓存，主要供测试使用。"""
    global _cache
    _cache = None


def get_llm_config() -> dict:
    """获取 LLM 配置，自动识别 GROK_API_KEY 或 OPENAI_API_KEY。

    优先级：GROK_API_KEY > OPENAI_API_KEY
    - GROK_API_KEY 设置时，base_url 默认为 https://api.x.ai/v1（可通过 GROK_BASE_URL 覆盖）
    - OPENAI_API_KEY 设置时，base_url 由 OPENAI_BASE_URL 控制（不设则走 OpenAI 官方）

    Returns:
        dict: api_key, model, max_completion_tokens, base_url (可选)
    """
    import os

    api_key = os.getenv("GROK_API_KEY", "").strip()
    base_url = None

    if api_key:
        base_url = os.getenv("GROK_BASE_URL", "https://api.x.ai/v1").strip()
    else:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        env_base_url = os.getenv("OPENAI_BASE_URL", "").strip()
        if env_base_url:
            base_url = env_base_url

    cfg = _load()
    openai_cfg = cfg.get("openai", {})
    config = {
        "api_key": api_key,
        "model": openai_cfg.get("model", "gpt-5"),
        "max_completion_tokens": openai_cfg.get("max_completion_tokens", 16000),
    }
    if base_url:
        config["base_url"] = base_url
    return config


# 向后兼容别名
get_openai_config = get_llm_config


def get_llm_model() -> str:
    """获取 LLM 模型名称（便捷方法）"""
    return get_llm_config()["model"]

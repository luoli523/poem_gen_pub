"""Tests for the tale-specific LLM config overlay."""

from src.common import config as cfg


def _patch_cfg(monkeypatch, data: dict):
    monkeypatch.setattr(cfg, "_load", lambda: data)


BASE = {"openai": {"model": "grok-4", "max_completion_tokens": 16000}}


def test_no_tale_section_uses_main_config(monkeypatch):
    monkeypatch.setenv("GROK_API_KEY", "grok-key")
    _patch_cfg(monkeypatch, dict(BASE))
    c = cfg.get_tale_llm_config()
    assert c["model"] == "grok-4" and c["api_key"] == "grok-key"
    assert c["base_url"] == "https://api.x.ai/v1"


def test_model_override_only(monkeypatch):
    monkeypatch.setenv("GROK_API_KEY", "grok-key")
    _patch_cfg(monkeypatch, dict(BASE, tale={"model": "deepseek-chat"}))
    c = cfg.get_tale_llm_config()
    assert c["model"] == "deepseek-chat"
    assert c["api_key"] == "grok-key"          # key 未覆盖


def test_full_override_switches_key_and_base_url(monkeypatch):
    monkeypatch.setenv("GROK_API_KEY", "grok-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-key")
    _patch_cfg(monkeypatch, dict(BASE, tale={
        "model": "deepseek-chat", "api_key_env": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com", "max_completion_tokens": 8000,
    }))
    c = cfg.get_tale_llm_config()
    assert c == {"api_key": "ds-key", "model": "deepseek-chat",
                 "max_completion_tokens": 8000, "base_url": "https://api.deepseek.com"}


def test_missing_override_key_falls_back_to_main(monkeypatch):
    monkeypatch.setenv("GROK_API_KEY", "grok-key")
    _patch_cfg(monkeypatch, dict(BASE, tale={"api_key_env": "DEEPSEEK_API_KEY",
                                              "base_url": "https://api.deepseek.com"}))
    c = cfg.get_tale_llm_config()
    assert c["api_key"] == "grok-key"
    assert c["base_url"] == "https://api.x.ai/v1"   # base_url 不随未生效的 key 切换


def test_override_key_without_base_url_drops_base_url(monkeypatch):
    monkeypatch.setenv("GROK_API_KEY", "grok-key")
    monkeypatch.setenv("OPENAI_KEY2", "oa-key")
    _patch_cfg(monkeypatch, dict(BASE, tale={"api_key_env": "OPENAI_KEY2"}))
    c = cfg.get_tale_llm_config()
    assert c["api_key"] == "oa-key" and "base_url" not in c

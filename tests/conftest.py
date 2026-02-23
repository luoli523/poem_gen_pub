"""Shared test fixtures for poem_gen_pub tests."""

import pytest


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """Ensure tests don't leak env vars or trigger real API calls."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("GROK_API_KEY", raising=False)
    monkeypatch.delenv("GROK_BASE_URL", raising=False)
    monkeypatch.delenv("TELEGRAM_ENABLED", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.delenv("IG_ENABLED", raising=False)
    monkeypatch.delenv("XHS_ENABLED", raising=False)

    from src.common.config import reset_cache
    reset_cache()


@pytest.fixture
def sample_solar_term():
    return {
        "name": "雨水",
        "date": "2026-02-18",
        "season": "春",
        "meaning": "雨水是二十四节气之第二个节气，意味着降雨开始",
        "description": "雨水节气标志着气温回升、冰雪融化、降水增多。",
        "customs": ["接寿", "回娘屋", "拉保保", "撞拜寄"],
        "food": "春笋、荠菜、韭菜等时令蔬菜",
        "health_tip": "春季养生以养肝为主，宜清淡饮食",
        "infographic_prompt": "中国风水墨画信息图...",
    }


@pytest.fixture
def sample_poem():
    return {
        "has_poem": True,
        "title": "水调歌头·明月几时有",
        "author": "苏轼",
        "dynasty": "宋",
        "full_text": "明月几时有？把酒问青天。不知天上宫阙，今夕是何年...",
        "meaning": "这首词是苏轼在中秋之夜所作，表达了对亲人的思念。",
        "customs": ["赏月", "吃月饼", "猜灯谜"],
        "occasion": "中秋节",
        "date": "2026-10-04",
        "infographic_prompt": "中国风信息图...",
    }

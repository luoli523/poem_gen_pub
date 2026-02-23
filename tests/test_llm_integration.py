"""Integration tests for LLM-dependent modules with mocked API."""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


MOCK_SOLAR_TERM_RESPONSE = {
    "meaning": "雨水节气，降水开始增多",
    "description": "雨水是二十四节气的第二个节气，标志着气温回升。",
    "customs": ["接寿", "回娘屋", "拉保保"],
    "food": "春笋、荠菜",
    "health_tip": "春季养肝为主",
    "infographic_prompt": "生成一张中国风水墨画...",
}

MOCK_POEM_RESPONSE = {
    "has_poem": True,
    "title": "春夜喜雨",
    "author": "杜甫",
    "dynasty": "唐",
    "full_text": "好雨知时节，当春乃发生。随风潜入夜，润物细无声。",
    "meaning": "这首诗描写了春雨的细腻...",
    "customs": ["踏春", "赏花"],
    "occasion": "雨水（二十四节气）",
    "infographic_prompt": "生成一张中国风信息图...",
}

MOCK_POEM_NO_MATCH = {
    "has_poem": False,
    "occasion": "",
    "title": "",
    "author": "",
    "dynasty": "",
    "full_text": "",
    "meaning": "",
    "customs": [],
    "infographic_prompt": "",
}

MOCK_RANDOM_POEM_RESPONSE = {
    "title": "春望",
    "author": "杜甫",
    "dynasty": "唐",
    "full_text": "国破山河在，城春草木深。感时花溅泪，恨别鸟惊心。",
    "meaning": "这首诗写于安史之乱期间...",
    "customs": ["春日登高", "怀古"],
    "occasion": "春日即景",
    "infographic_prompt": "生成一张中国风信息图...",
}


def _mock_llm_response(content: dict):
    """Build a mock LLM ChatCompletion response (OpenAI-compatible format)."""
    mock_message = MagicMock()
    mock_message.content = json.dumps(content, ensure_ascii=False)

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    return mock_response


class TestSolarTermDetector:

    @pytest.mark.asyncio
    async def test_non_solar_term_day(self):
        """Non-solar-term days should return None."""
        from src.solar_term.detector import get_solar_term
        result = await get_solar_term("2026-02-10")
        assert result is None

    @pytest.mark.asyncio
    async def test_solar_term_with_llm(self, monkeypatch):
        """When LLM returns valid data, it should be merged into result."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        mock_create = AsyncMock(return_value=_mock_llm_response(MOCK_SOLAR_TERM_RESPONSE))
        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create = mock_create

        with patch("openai.AsyncOpenAI", return_value=mock_client_instance):
            from src.solar_term.detector import get_solar_term
            result = await get_solar_term("2026-02-18")

        if result is not None:
            assert result["name"] == "雨水"
            assert result["season"] == "春"
            assert result["meaning"] == MOCK_SOLAR_TERM_RESPONSE["meaning"]
            assert isinstance(result["customs"], list)

    @pytest.mark.asyncio
    async def test_solar_term_llm_failure_falls_back(self, monkeypatch):
        """When LLM fails, fallback data should be used."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        mock_create = AsyncMock(side_effect=Exception("API error"))
        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create = mock_create

        with patch("openai.AsyncOpenAI", return_value=mock_client_instance):
            from src.solar_term.detector import get_solar_term
            result = await get_solar_term("2026-02-18")

        if result is not None:
            assert result["name"] == "雨水"
            assert "二十四节气" in result["meaning"]


class TestPoetryDetector:

    @pytest.mark.asyncio
    async def test_no_api_key_returns_none(self):
        from src.poetry.detector import get_poem
        result = await get_poem("2026-02-18")
        assert result is None

    @pytest.mark.asyncio
    async def test_poem_found(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        mock_create = AsyncMock(return_value=_mock_llm_response(MOCK_POEM_RESPONSE))
        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create = mock_create

        with patch("openai.AsyncOpenAI", return_value=mock_client_instance):
            from src.poetry.detector import get_poem
            result = await get_poem("2026-02-18")

        assert result is not None
        assert result["title"] == "春夜喜雨"
        assert result["author"] == "杜甫"
        assert result["date"] == "2026-02-18"

    @pytest.mark.asyncio
    async def test_no_match_falls_back_to_random(self, monkeypatch):
        """When no date-related poem, should fall back to random recommendation."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        mock_create = AsyncMock(side_effect=[
            _mock_llm_response(MOCK_POEM_NO_MATCH),
            _mock_llm_response(MOCK_RANDOM_POEM_RESPONSE),
        ])
        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create = mock_create

        with patch("openai.AsyncOpenAI", return_value=mock_client_instance):
            from src.poetry.detector import get_poem
            result = await get_poem("2026-03-15")

        assert result is not None
        assert result["title"] == "春望"
        assert result["occasion"] == "春日即景"
        assert mock_create.call_count == 2

    @pytest.mark.asyncio
    async def test_llm_error_returns_none(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        mock_create = AsyncMock(side_effect=Exception("timeout"))
        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create = mock_create

        with patch("openai.AsyncOpenAI", return_value=mock_client_instance):
            from src.poetry.detector import get_poem
            result = await get_poem("2026-02-18")

        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_json_returns_none(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        mock_message = MagicMock()
        mock_message.content = "not valid json"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_create = AsyncMock(return_value=mock_response)
        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create = mock_create

        with patch("openai.AsyncOpenAI", return_value=mock_client_instance):
            from src.poetry.detector import get_poem
            result = await get_poem("2026-02-18")

        assert result is None

    @pytest.mark.asyncio
    async def test_customs_string_is_normalized_to_list(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        content = {**MOCK_POEM_RESPONSE, "customs": "踏春"}

        mock_create = AsyncMock(return_value=_mock_llm_response(content))
        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create = mock_create

        with patch("openai.AsyncOpenAI", return_value=mock_client_instance):
            from src.poetry.detector import get_poem
            result = await get_poem("2026-02-18")

        assert result is not None
        assert result["customs"] == ["踏春"]


class TestPoetryExtraContext:
    """Test the context builder that feeds LLM."""

    def test_lunar_date_included(self):
        from src.poetry.detector import _build_extra_context
        ctx = _build_extra_context("2026-02-18")
        assert "农历" in ctx

    def test_solar_term_included(self):
        from src.poetry.detector import _build_extra_context
        ctx = _build_extra_context("2026-02-18")
        assert "节气" in ctx or "农历" in ctx

    def test_invalid_date_returns_empty(self):
        from src.poetry.detector import _build_extra_context
        ctx = _build_extra_context("not-a-date")
        assert ctx == ""

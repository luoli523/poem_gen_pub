"""Tests for the poem story module (LLM mocked)."""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.poetry.story import _validate_and_normalize, get_story, SECTION_LABELS


MOCK_STORY_RESPONSE = {
    "summary": "苏轼写下此词时，正与弟弟苏辙七年未见。",
    "sections": {
        "author_anecdote": [
            {"text": "苏轼与苏辙兄弟情深，屡屡以诗词相寄。", "kind": "史实", "source": "《宋史·苏轼传》"},
        ],
        "composition": [
            {"text": "丙辰中秋，欢饮达旦，大醉作此篇，兼怀子由。", "kind": "史实", "source": "词前小序"},
        ],
        "era_context": [],
        "customs": [
            {"text": "宋人中秋夜市通宵，玩月至晓。", "kind": "史实", "source": "《东京梦华录》卷八"},
        ],
        "legends": [
            {"text": "民间传说此词一出，中秋词尽废。", "kind": "传说", "source": "《苕溪渔隐丛话》"},
        ],
        "allusions": [
            {"text": "琼楼玉宇，指月宫。", "kind": "史实", "source": ""},
        ],
    },
}


def _mock_llm_response(content: dict):
    mock_message = MagicMock()
    mock_message.content = json.dumps(content, ensure_ascii=False)
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    return mock_response


class TestNormalize:

    def test_valid_response_keeps_items(self):
        result = _validate_and_normalize(json.loads(json.dumps(MOCK_STORY_RESPONSE)))
        assert result is not None
        assert result["summary"].startswith("苏轼")
        assert len(result["sections"]["author_anecdote"]) == 1
        assert result["sections"]["era_context"] == []
        assert set(result["sections"]) == set(SECTION_LABELS)

    def test_fact_without_source_downgraded(self):
        result = _validate_and_normalize(json.loads(json.dumps(MOCK_STORY_RESPONSE)))
        item = result["sections"]["allusions"][0]
        assert item["kind"] == "存疑"

    def test_unknown_kind_becomes_uncertain(self):
        data = {"summary": "x", "sections": {"legends": [{"text": "t", "kind": "野史", "source": "s"}]}}
        result = _validate_and_normalize(data)
        assert result["sections"]["legends"][0]["kind"] == "存疑"

    def test_plain_string_item_accepted(self):
        data = {"summary": "", "sections": {"customs": ["宋人中秋玩月"]}}
        result = _validate_and_normalize(data)
        assert result["sections"]["customs"] == [{"text": "宋人中秋玩月", "kind": "存疑", "source": ""}]

    def test_empty_text_dropped(self):
        data = {"summary": "x", "sections": {"customs": [{"text": "  ", "kind": "史实", "source": "s"}, None, 3]}}
        result = _validate_and_normalize(data)
        assert result["sections"]["customs"] == []

    def test_missing_sections_and_summary_is_invalid(self):
        assert _validate_and_normalize({}) is None
        assert _validate_and_normalize({"summary": "", "sections": {"customs": []}}) is None

    def test_sections_not_dict_tolerated(self):
        result = _validate_and_normalize({"summary": "只有引子", "sections": "oops"})
        assert result["summary"] == "只有引子"
        assert all(v == [] for v in result["sections"].values())


class TestGetStory:

    @pytest.mark.asyncio
    async def test_no_api_key_returns_none(self, sample_poem):
        assert await get_story(sample_poem) is None

    @pytest.mark.asyncio
    async def test_success(self, monkeypatch, sample_poem):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        mock_create = AsyncMock(return_value=_mock_llm_response(MOCK_STORY_RESPONSE))
        mock_client = MagicMock()
        mock_client.chat.completions.create = mock_create

        with patch("openai.AsyncOpenAI", return_value=mock_client):
            result = await get_story(sample_poem)

        assert result is not None
        assert len(result["sections"]["customs"]) == 1
        user_msg = mock_create.call_args.kwargs["messages"][1]["content"]
        assert "水调歌头" in user_msg
        assert sample_poem["full_text"] in user_msg

    @pytest.mark.asyncio
    async def test_llm_error_returns_none(self, monkeypatch, sample_poem):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("boom"))

        with patch("openai.AsyncOpenAI", return_value=mock_client):
            assert await get_story(sample_poem) is None

    @pytest.mark.asyncio
    async def test_invalid_json_returns_none(self, monkeypatch, sample_poem):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        resp = _mock_llm_response({})
        resp.choices[0].message.content = "not json {"
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=resp)

        with patch("openai.AsyncOpenAI", return_value=mock_client):
            assert await get_story(sample_poem) is None

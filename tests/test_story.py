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


# ── 衍生一则 ──

from src.poetry.story import _validate_tale, _covered_points, get_tale, PIVOT_TYPES  # noqa: E402

MOCK_TALE_RESPONSE = {
    "pivot": "扬州盐商",
    "pivot_type": "地域",
    "title": "程氏义仓",
    "tale": "乾隆年间，扬州盐商程某……" * 20,
    "connection": "杜牧诗中的扬州繁华，正建立在盐运之上。",
    "kind": "史实",
    "source": "《扬州画舫录·卷九》",
}


class TestValidateTale:

    def test_valid(self):
        t = _validate_tale(dict(MOCK_TALE_RESPONSE))
        assert t["pivot_type"] == "地域"
        assert t["kind"] == "史实"
        assert t["title"] == "程氏义仓"

    def test_empty_tale_invalid(self):
        assert _validate_tale(dict(MOCK_TALE_RESPONSE, tale="  ")) is None
        assert _validate_tale({}) is None

    def test_bad_pivot_type_falls_back(self):
        t = _validate_tale(dict(MOCK_TALE_RESPONSE, pivot_type="职业"))
        assert t["pivot_type"] == "风俗"
        assert t["pivot_type"] in PIVOT_TYPES

    def test_fact_without_source_downgraded(self):
        t = _validate_tale(dict(MOCK_TALE_RESPONSE, source=""))
        assert t["kind"] == "存疑"

    def test_non_string_fields_tolerated(self):
        t = _validate_tale(dict(MOCK_TALE_RESPONSE, pivot=None, title=3, connection=[]))
        assert t["pivot"] == "" and t["title"] == "" and t["connection"] == ""


class TestCoveredPoints:

    def test_none_story(self):
        assert _covered_points(None) == "（无）"

    def test_lists_items_with_labels(self):
        story = _validate_and_normalize(json.loads(json.dumps(MOCK_STORY_RESPONSE)))
        text = _covered_points(story)
        assert "[作者轶事]" in text
        assert "苏轼与苏辙兄弟情深" in text

    def test_all_empty_sections(self):
        story = {"summary": "x", "sections": {k: [] for k in SECTION_LABELS}}
        assert _covered_points(story) == "（无）"


class TestGetTale:

    @pytest.mark.asyncio
    async def test_no_api_key(self, sample_poem):
        assert await get_tale(sample_poem, None, []) is None

    @pytest.mark.asyncio
    async def test_success_and_prompt_contents(self, monkeypatch, sample_poem):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        mock_create = AsyncMock(return_value=_mock_llm_response(MOCK_TALE_RESPONSE))
        mock_client = MagicMock()
        mock_client.chat.completions.create = mock_create
        story = _validate_and_normalize(json.loads(json.dumps(MOCK_STORY_RESPONSE)))

        with patch("openai.AsyncOpenAI", return_value=mock_client):
            tale = await get_tale(sample_poem, story, ["地域", "时节"])

        assert tale["pivot"] == "扬州盐商"
        user_msg = mock_create.call_args.kwargs["messages"][1]["content"]
        assert "水调歌头" in user_msg
        assert "[作者轶事]" in user_msg           # 已覆盖要点被喂入
        assert "地域、时节" in user_msg            # 近期类型被喂入

    @pytest.mark.asyncio
    async def test_llm_error(self, monkeypatch, sample_poem):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("boom"))
        with patch("openai.AsyncOpenAI", return_value=mock_client):
            assert await get_tale(sample_poem, None, []) is None


class TestPivotHistory:

    def test_record_and_recent(self, sample_poem):
        from src.poetry import detector as det
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        poem = dict(sample_poem, date=today)
        det._save_to_history(poem)
        det.record_pivot_type(poem, "地域")
        assert det.recent_pivot_types() == ["地域"]

    def test_record_unknown_poem_is_noop(self, sample_poem):
        from src.poetry import detector as det
        det.record_pivot_type(sample_poem, "地域")
        assert not det._HISTORY_PATH.exists()

    def test_recent_dedup_and_window(self, sample_poem):
        from src.poetry import detector as det
        from datetime import datetime, timedelta
        d0 = datetime.now()
        for delta, pt in [(0, "地域"), (1, "时节"), (2, "地域"), (10, "朝代")]:
            p = dict(sample_poem, title=f"t{delta}", date=(d0 - timedelta(days=delta)).strftime("%Y-%m-%d"))
            det._save_to_history(p)
            det.record_pivot_type(p, pt)
        assert set(det.recent_pivot_types()) == {"地域", "时节"}   # 10 天前的不算
        assert len(det.recent_pivot_types()) == 2                # 去重

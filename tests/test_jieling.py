"""Tests for 节令 story generation, content pages, and previous-year exclusion."""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from src.jieling.story import _validate_and_normalize, format_previous_points, get_jieling_story, SECTION_LABELS
from src.jieling import content as jc


@pytest.fixture
def bailu():
    return {"name": "白露", "category": "节气", "ethnic": "", "date": "2026-09-07", "season": "秋", "lunar": ""}


@pytest.fixture
def huoba():
    return {"name": "火把节", "category": "民族节日", "ethnic": "彝族", "date": "2026-08-06", "season": "", "lunar": "六月廿四"}


@pytest.fixture
def story():
    return {
        "summary": "白露一到，秋气始肃。",
        "sections": {
            "origin": [{"text": "《月令七十二候集解》：水土湿气凝而为露。", "kind": "史实", "source": "《月令七十二候集解》"}],
            "customs": [{"text": "太湖渔民祭禹王。", "kind": "传说", "source": "流传于太湖一带"}],
            "food_objects": [], "in_poetry": [], "figures_legends": [], "gazetteers": [],
        },
        "infographic_prompt": "水墨白露信息图……",
    }


def _mock_resp(content: dict):
    m = MagicMock(); m.choices = [MagicMock()]
    m.choices[0].message.content = json.dumps(content, ensure_ascii=False); return m


class TestNormalize:

    def test_valid(self, story):
        out = _validate_and_normalize(json.loads(json.dumps(story)))
        assert out["summary"] == story["summary"]
        assert out["infographic_prompt"].startswith("水墨")
        assert set(out["sections"]) == set(SECTION_LABELS)
        assert out["sections"]["customs"][0]["kind"] == "传说"

    def test_all_empty_is_invalid(self):
        assert _validate_and_normalize({"summary": "x", "sections": {}, "infographic_prompt": "p"}) is None

    def test_missing_prompt_tolerated(self, story):
        s = dict(story); s.pop("infographic_prompt")
        assert _validate_and_normalize(s)["infographic_prompt"] == ""


class TestPreviousPoints:

    def test_none(self):
        assert format_previous_points([]) == "（无，这是第一年）"

    def test_lists_year_and_label(self, story):
        text = format_previous_points([dict(story, year="2025")])
        assert "[2025 名义与物候]" in text and "祭禹王" in text


class TestContent:

    def test_page_dir_by_name_and_year(self, tmp_path, bailu):
        assert jc.page_dir(tmp_path, bailu) == tmp_path / "白露" / "2026"

    def test_json_roundtrip_and_previous_excludes_current_year(self, tmp_path, bailu, story):
        jc.save_story_json(tmp_path / "白露" / "2025", story)
        jc.save_story_json(tmp_path / "白露" / "2026", story)          # 今年的不算往年
        prev = jc.load_previous_stories(tmp_path, bailu)
        assert [p["year"] for p in prev] == ["2025"]
        assert prev[0]["sections"]["origin"][0]["source"] == "《月令七十二候集解》"

    def test_page_url(self, bailu):
        assert jc.page_url("https://x.io/p/", bailu) == "https://x.io/p/terms/%E7%99%BD%E9%9C%B2/2026/"

    def test_previous_missing_dir(self, tmp_path, bailu):
        assert jc.load_previous_stories(tmp_path, bailu) == []

    def test_page_frontmatter_and_body(self, bailu, story):
        import yaml
        page = jc.generate_site_page(bailu, story, infographic="infographic.webp")
        _, front_text, body = page.split("---\n", 2)
        front = yaml.safe_load(front_text)
        assert front["title"] == "白露 · 2026" and front["jieling"] == ["白露"]
        assert front["jieling_categories"] == ["节气"] and front["season"] == "秋"
        assert front["categories"] == ["名义与物候", "历代风俗"] and front["kinds"] == ["传说", "史实"]
        assert "![白露 2026 信息图](infographic.webp)" in body
        assert "### 名义与物候" in body and "〔传说 · 流传于太湖一带〕" in body
        assert "### 饮食与器物" not in body

    def test_ethnic_page(self, huoba, story):
        import yaml
        page = jc.generate_site_page(huoba, story)
        front = yaml.safe_load(page.split("---\n", 2)[1])
        assert front["jieling_categories"] == ["民族节日", "彝族"]
        assert "**彝族·民族节日** · 2026-08-06（六月廿四）" in page

    def test_page_without_story(self, bailu):
        assert "暂未生成" in jc.generate_site_page(bailu, None)

    def test_nlm_markdown_has_no_kind_tags(self, bailu, story):
        md = jc.generate_nlm_markdown(bailu, story)
        assert "# 白露（2026）— 节气" in md and "祭禹王" in md and "〔" not in md

    def test_captions(self, huoba, story):
        ig = jc.build_ig_caption(huoba, story)
        assert "🌿 火把节 · 2026" in ig and "#彝族" in ig and "#传统节日" in ig
        tg = jc.build_telegram_caption(huoba, story)
        assert "<b>🌿 火把节</b>" in tg and "彝族·民族节日" in tg


class TestGetJielingStory:

    @pytest.mark.asyncio
    async def test_no_key(self, bailu):
        assert await get_jieling_story(bailu, []) is None

    @pytest.mark.asyncio
    async def test_success_and_prompt(self, monkeypatch, bailu, story):
        monkeypatch.setenv("OPENAI_API_KEY", "k")
        create = AsyncMock(return_value=_mock_resp(story))
        client = MagicMock(); client.chat.completions.create = create
        with patch("openai.AsyncOpenAI", return_value=client):
            out = await get_jieling_story(bailu, [dict(story, year="2025")])
        assert out is not None
        user = create.call_args.kwargs["messages"][1]["content"]
        assert "节令：白露（节气）" in user and "秋季" in user and "[2025 历代风俗]" in user

    @pytest.mark.asyncio
    async def test_ethnic_prompt_line(self, monkeypatch, huoba, story):
        monkeypatch.setenv("OPENAI_API_KEY", "k")
        create = AsyncMock(return_value=_mock_resp(story))
        client = MagicMock(); client.chat.completions.create = create
        with patch("openai.AsyncOpenAI", return_value=client):
            await get_jieling_story(huoba, [])
        user = create.call_args.kwargs["messages"][1]["content"]
        assert "火把节（民族节日·彝族）" in user and "农历六月廿四" in user and "（无，这是第一年）" in user

    @pytest.mark.asyncio
    async def test_error_returns_none(self, monkeypatch, bailu):
        monkeypatch.setenv("OPENAI_API_KEY", "k")
        client = MagicMock(); client.chat.completions.create = AsyncMock(side_effect=Exception("x"))
        with patch("openai.AsyncOpenAI", return_value=client):
            assert await get_jieling_story(bailu, []) is None

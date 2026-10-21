"""Tests for main.py degradation paths: NotebookLM errors are contained and reported, never fatal."""

import json
from pathlib import Path

import pytest
from unittest.mock import AsyncMock, patch

import main
from src.jieling.content import page_url as jieling_page_url
from src.poetry.content import page_url as poetry_page_url, site_page_dir


def _pipeline_kwargs(tmp_path, **over):
    kw = dict(
        label="诗词", data={"infographic_prompt": "p", "title": "t"}, today="2026-09-15",
        output_dir=tmp_path, skip_notebooklm=False, skip_ig=True,
        generate_markdown_fn=lambda d: "# md", build_caption_fn=lambda d: "cap",
        md_filename="x.md", artifact_name="a", ratio="4:5",
    )
    kw.update(over); return kw


class TestContentPipeline:

    @pytest.mark.asyncio
    async def test_nlm_exception_returns_none(self, tmp_path):
        with patch.object(main, "nlm_run_pipeline", AsyncMock(side_effect=RuntimeError("quota"))):
            assert await main._run_content_pipeline(**_pipeline_kwargs(tmp_path)) is None
        assert (tmp_path / "x.md").exists()           # Markdown 仍然落地

    @pytest.mark.asyncio
    async def test_nlm_none_returns_none(self, tmp_path):
        with patch.object(main, "nlm_run_pipeline", AsyncMock(return_value=None)):
            assert await main._run_content_pipeline(**_pipeline_kwargs(tmp_path)) is None

    @pytest.mark.asyncio
    async def test_skip_returns_none_without_calling_nlm(self, tmp_path):
        m = AsyncMock()
        with patch.object(main, "nlm_run_pipeline", m):
            assert await main._run_content_pipeline(**_pipeline_kwargs(tmp_path, skip_notebooklm=True)) is None
        m.assert_not_called()


class TestPoemFlowProblems:

    async def _run(self, tmp_path, sample_poem, story, image, skip_nlm=False):
        problems: list[str] = []
        with patch.object(main, "_build_poem_story", AsyncMock(return_value=(story, None))), \
             patch.object(main, "_run_content_pipeline", AsyncMock(return_value=image)), \
             patch.object(main, "save_infographic_webp", lambda src, dst: dst):
            await main._run_poem_flow(
                sample_poem, name_key="k", today=sample_poem["date"], output_dir=tmp_path / "out",
                site_dir=tmp_path / "site", skip_notebooklm=skip_nlm, skip_ig=True,
                tale_enabled=False, ratio="4:5", problems=problems,
            )
        return problems

    @pytest.mark.asyncio
    async def test_all_good_no_problems(self, tmp_path, sample_poem):
        story = {"summary": "s", "sections": {}}
        assert await self._run(tmp_path, sample_poem, story, "img.png") == []

    @pytest.mark.asyncio
    async def test_story_failure_recorded_page_still_written(self, tmp_path, sample_poem):
        problems = await self._run(tmp_path, sample_poem, None, "img.png")
        assert len(problems) == 1 and "背后的故事生成失败" in problems[0]
        assert (tmp_path / "site" / "2026-10-04-水调歌头明月几时有" / "index.md").exists()

    @pytest.mark.asyncio
    async def test_image_failure_recorded(self, tmp_path, sample_poem):
        problems = await self._run(tmp_path, sample_poem, {"summary": "s", "sections": {}}, None)
        assert len(problems) == 1 and "信息图未生成" in problems[0]

    @pytest.mark.asyncio
    async def test_image_skipped_not_a_problem(self, tmp_path, sample_poem):
        problems = await self._run(tmp_path, sample_poem, {"summary": "s", "sections": {}}, None, skip_nlm=True)
        assert problems == []

    @pytest.mark.asyncio
    async def test_manifest_for_poem_even_when_nlm_skipped(self, tmp_path, sample_poem, monkeypatch):
        monkeypatch.chdir(tmp_path)
        story = {"summary": "s", "sections": {}}
        base = "https://guige.ai/poem_gen_pub/"
        with patch.object(main, "_build_poem_story", AsyncMock(return_value=(story, None))), \
             patch.object(main, "_run_content_pipeline", AsyncMock(return_value=None)):
            await main._run_poem_flow(
                sample_poem, name_key="k", today=sample_poem["date"], output_dir=Path("output"),
                site_dir=Path("site/content/poems"), skip_notebooklm=True, skip_ig=True,
                tale_enabled=False, ratio="4:5", problems=[], base_url=base,
                image_overwrite=True,
            )
        data = json.loads(next(Path("output/infographic-manifests").glob("*.json")).read_text(encoding="utf-8"))
        assert data["date"] == sample_poem["date"]
        assert data["prompt"] == sample_poem["infographic_prompt"]
        assert data["content_dir"] == f"site/content/poems/{site_page_dir(sample_poem)}"
        assert data["upload_path"] == data["content_dir"] + "/infographic.webp"
        assert data["page_url"] == poetry_page_url(base, sample_poem)
        assert data["overwrite"] is True

    @pytest.mark.asyncio
    async def test_blank_poem_prompt_skips_manifest(self, tmp_path, sample_poem, monkeypatch):
        monkeypatch.chdir(tmp_path)
        poem = dict(sample_poem)
        poem["infographic_prompt"] = "  "
        with patch.object(main, "_build_poem_story", AsyncMock(return_value=({"summary": "s", "sections": {}}, None))), \
             patch.object(main, "_run_content_pipeline", AsyncMock(return_value=None)):
            await main._run_poem_flow(
                poem, name_key="k", today=poem["date"], output_dir=Path("output"),
                site_dir=Path("site/content/poems"), skip_notebooklm=True, skip_ig=True,
                tale_enabled=False, ratio="4:5", problems=[],
            )
        assert list(Path("output").glob("infographic-manifests/*.json")) == []


class TestPageNotification:

    async def _poem(self, tmp_path, sample_poem, base_url, skip_nlm):
        story = {"summary": "引子", "sections": {}}
        with patch.object(main, "_build_poem_story", AsyncMock(return_value=(story, None))), \
             patch.object(main, "_run_content_pipeline", AsyncMock(return_value=None)), \
             patch.object(main, "_notify_page", AsyncMock()) as notify:
            await main._run_poem_flow(
                sample_poem, name_key="k", today=sample_poem["date"], output_dir=tmp_path / "o",
                site_dir=tmp_path / "s", skip_notebooklm=skip_nlm, skip_ig=True, tale_enabled=False,
                ratio="4:5", problems=[], base_url=base_url,
            )
        return notify

    @pytest.mark.asyncio
    async def test_poem_link_sent(self, tmp_path, sample_poem):
        notify = await self._poem(tmp_path, sample_poem, "https://x.io/p/", skip_nlm=False)
        notify.assert_called_once()
        text = notify.call_args.args[0]
        assert "<b>水调歌头·明月几时有</b>" in text and "宋·苏轼" in text and "引子" in text
        assert 'href="https://x.io/p/poems/2026-10-04-' in text

    @pytest.mark.asyncio
    async def test_dry_run_sends_nothing(self, tmp_path, sample_poem):
        notify = await self._poem(tmp_path, sample_poem, "https://x.io/p/", skip_nlm=True)
        notify.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_base_url_sends_nothing(self, tmp_path, sample_poem):
        notify = await self._poem(tmp_path, sample_poem, "", skip_nlm=False)
        notify.assert_not_called()

    @pytest.mark.asyncio
    async def test_jieling_link_sent(self, tmp_path):
        item = {"name": "白露", "category": "节气", "ethnic": "", "date": "2026-09-07", "season": "秋", "lunar": ""}
        story = {"summary": "s", "infographic_prompt": "p",
                 "sections": {"origin": [{"text": "t", "kind": "史实", "source": "《x》"}], "customs": [],
                              "food_objects": [], "in_poetry": [], "figures_legends": [], "gazetteers": []}}
        with patch.object(main, "get_jieling_story", AsyncMock(return_value=story)), \
             patch.object(main, "_run_content_pipeline", AsyncMock(return_value=None)), \
             patch.object(main, "_notify_page", AsyncMock()) as notify:
            await main._run_jieling_flow(item, today=item["date"], output_dir=tmp_path / "o",
                                         terms_dir=tmp_path / "t", skip_notebooklm=False, skip_ig=True,
                                         ratio="4:5", problems=[], base_url="https://x.io/p/")
        text = notify.call_args.args[0]
        assert "<b>白露</b>" in text and 'href="https://x.io/p/terms/%E7%99%BD%E9%9C%B2/2026/"' in text


class TestImageOverwriteFlag:

    def test_default_false(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["main.py"])
        assert main.parse_args().image_overwrite is False

    def test_flag_sets_true(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["main.py", "--image-overwrite"])
        assert main.parse_args().image_overwrite is True


class TestReportProblems:

    @pytest.mark.asyncio
    async def test_sends_one_telegram_summary(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_ENABLED", "true")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "c")
        send = AsyncMock(return_value=True)
        with patch.object(main, "telegram_send_message", send):
            await main._report_problems("2026-09-15", ["甲", "乙"])
        send.assert_called_once()
        text = send.call_args.args[2]
        assert "今日流水线降级" in text and "• 甲" in text and "• 乙" in text

    @pytest.mark.asyncio
    async def test_no_telegram_configured_is_quiet(self):
        send = AsyncMock()
        with patch.object(main, "telegram_send_message", send):
            await main._report_problems("2026-09-15", ["甲"])
        send.assert_not_called()


class TestJielingFlow:

    @pytest.fixture
    def item(self):
        return {"name": "白露", "category": "节气", "ethnic": "", "date": "2026-09-07", "season": "秋", "lunar": ""}

    @pytest.fixture
    def story(self):
        return {"summary": "s", "infographic_prompt": "p",
                "sections": {"origin": [{"text": "t", "kind": "史实", "source": "《x》"}], "customs": [],
                             "food_objects": [], "in_poetry": [], "figures_legends": [], "gazetteers": []}}

    async def _run(self, tmp_path, item, story, image, skip_nlm=False):
        problems: list[str] = []
        with patch.object(main, "get_jieling_story", AsyncMock(return_value=story)) as gs, \
             patch.object(main, "_run_content_pipeline", AsyncMock(return_value=image)), \
             patch.object(main, "save_infographic_webp", lambda src, dst: dst):
            await main._run_jieling_flow(item, today=item["date"], output_dir=tmp_path / "out",
                                         terms_dir=tmp_path / "terms", skip_notebooklm=skip_nlm,
                                         skip_ig=True, ratio="4:5", problems=problems)
        return problems, gs

    @pytest.mark.asyncio
    async def test_page_json_and_image(self, tmp_path, item, story):
        problems, _ = await self._run(tmp_path, item, story, "img.png")
        d = tmp_path / "terms" / "白露" / "2026"
        assert problems == [] and (d / "story.json").exists()
        assert "infographic: infographic.webp" in (d / "index.md").read_text(encoding="utf-8")

    @pytest.mark.asyncio
    async def test_story_failure_writes_stub(self, tmp_path, item):
        problems, _ = await self._run(tmp_path, item, None, None)
        d = tmp_path / "terms" / "白露" / "2026"
        assert "素材生成失败" in problems[0] and (d / "index.md").exists() and not (d / "story.json").exists()
        assert not (tmp_path / "out" / "infographic-manifests").exists()

    @pytest.mark.asyncio
    async def test_jieling_manifest(self, tmp_path, item, story, monkeypatch):
        monkeypatch.chdir(tmp_path)
        base = "https://guige.ai/poem_gen_pub/"
        problems: list[str] = []
        with patch.object(main, "get_jieling_story", AsyncMock(return_value=story)), \
             patch.object(main, "_run_content_pipeline", AsyncMock(return_value=None)):
            await main._run_jieling_flow(
                item, today=item["date"], output_dir=Path("output"),
                terms_dir=Path("site/content/terms"), skip_notebooklm=True, skip_ig=True,
                ratio="4:5", problems=problems, base_url=base,
            )
        data = json.loads(next(Path("output/infographic-manifests").glob("*.json")).read_text(encoding="utf-8"))
        assert problems == []
        assert data["date"] == "2026-09-07"
        assert data["prompt"] == "p"
        assert data["content_dir"] == "site/content/terms/白露/2026"
        assert data["upload_path"] == "site/content/terms/白露/2026/infographic.webp"
        assert data["page_url"] == jieling_page_url(base, item)
        assert data["overwrite"] is False

    @pytest.mark.asyncio
    async def test_empty_jieling_prompt_skips_manifest(self, tmp_path, item, story, monkeypatch):
        monkeypatch.chdir(tmp_path)
        story = dict(story)
        story["infographic_prompt"] = ""
        with patch.object(main, "get_jieling_story", AsyncMock(return_value=story)), \
             patch.object(main, "_run_content_pipeline", AsyncMock(return_value=None)):
            await main._run_jieling_flow(
                item, today=item["date"], output_dir=Path("output"),
                terms_dir=Path("site/content/terms"), skip_notebooklm=True, skip_ig=True,
                ratio="4:5", problems=[],
            )
        assert list(Path("output").glob("infographic-manifests/*.json")) == []

    @pytest.mark.asyncio
    async def test_previous_year_fed_to_llm(self, tmp_path, item, story):
        from src.jieling.content import save_story_json
        save_story_json(tmp_path / "terms" / "白露" / "2025", story)
        _, gs = await self._run(tmp_path, item, story, None, skip_nlm=True)
        assert [p["year"] for p in gs.call_args.args[1]] == ["2025"]

    @pytest.mark.asyncio
    async def test_image_failure_recorded(self, tmp_path, item, story):
        problems, _ = await self._run(tmp_path, item, story, None)
        assert len(problems) == 1 and "信息图未生成" in problems[0]

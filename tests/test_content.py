"""Tests for content generation across solar_term and poetry modules."""

import pytest
from src.solar_term.content import (
    generate_markdown as solar_term_markdown,
    build_telegram_caption as solar_term_tg,
    build_ig_caption as solar_term_ig,
)
from src.poetry.content import (
    generate_markdown as poetry_markdown,
    build_telegram_caption as poetry_tg,
    build_ig_caption as poetry_ig,
)


class TestSolarTermContent:

    def test_markdown_structure(self, sample_solar_term):
        md = solar_term_markdown(sample_solar_term)
        assert "# 雨水" in md
        assert "春" in md
        assert "节气介绍" in md
        assert "传统习俗" in md
        assert "养生提示" in md

    def test_telegram_caption(self, sample_solar_term):
        caption = solar_term_tg(sample_solar_term)
        assert "雨水" in caption
        assert "<b>" in caption  # HTML format

    def test_ig_caption(self, sample_solar_term):
        caption = solar_term_ig(sample_solar_term)
        assert "雨水" in caption
        assert "#二十四节气" in caption

    def test_customs_in_markdown(self, sample_solar_term):
        md = solar_term_markdown(sample_solar_term)
        assert "接寿" in md


class TestPoetryContent:

    def test_markdown_structure(self, sample_poem):
        md = poetry_markdown(sample_poem)
        assert "水调歌头" in md
        assert "苏轼" in md
        assert "宋" in md
        assert "诗词赏析" in md

    def test_telegram_caption(self, sample_poem):
        caption = poetry_tg(sample_poem)
        assert "水调歌头" in caption
        assert "苏轼" in caption
        assert "<b>" in caption

    def test_ig_caption(self, sample_poem):
        caption = poetry_ig(sample_poem)
        assert "水调歌头" in caption
        assert "#唐诗宋词" in caption
        assert "#苏轼" in caption

    def test_customs_in_ig(self, sample_poem):
        caption = poetry_ig(sample_poem)
        assert "赏月" in caption

    def test_ig_caption_no_empty_hashtag_when_occasion_missing(self, sample_poem):
        poem = {**sample_poem, "occasion": "   "}
        caption = poetry_ig(poem)
        assert "# #" not in caption
        assert "#唐诗宋词" in caption

    def test_long_meaning_truncated_in_xhs(self, sample_poem):
        from src.poetry.content import build_xhs_content
        poem = {**sample_poem, "meaning": "赏析" * 200}
        _, content, _ = build_xhs_content(poem)
        assert "……" in content

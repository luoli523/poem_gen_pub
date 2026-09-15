"""Tests for poetry content generation."""

import pytest
from src.poetry.content import (
    generate_markdown as poetry_markdown,
    build_telegram_caption as poetry_tg,
    build_ig_caption as poetry_ig,
)


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

    def test_long_meaning_truncated_in_ig(self, sample_poem):
        poem = {**sample_poem, "meaning": "赏析" * 200}
        caption = poetry_ig(poem)
        assert "……" in caption


class TestPoetrySitePage:

    @pytest.fixture
    def sample_story(self):
        return {
            "summary": "丙辰中秋，苏轼大醉，兼怀子由。",
            "sections": {
                "author_anecdote": [{"text": "兄弟情深。", "kind": "史实", "source": "《宋史》"}],
                "composition": [],
                "era_context": [],
                "customs": [{"text": "宋人玩月至晓。", "kind": "传说", "source": ""}],
                "legends": [],
                "allusions": [],
            },
        }

    def test_dir_strips_unsafe_chars(self, sample_poem):
        from src.poetry.content import site_page_dir
        poem = dict(sample_poem, title="水调歌头·明月几时有 / 试:题？（甲）")
        assert site_page_dir(poem) == "2026-10-04-水调歌头明月几时有试题甲"   # · 与中文标点一并去掉，与 Hugo URL 一致

    def test_page_url(self, sample_poem):
        from src.poetry.content import page_url
        url = page_url("https://x.io/poem_gen_pub/", dict(sample_poem, title="饮酒·其五"))
        assert url == "https://x.io/poem_gen_pub/poems/2026-10-04-%E9%A5%AE%E9%85%92%E5%85%B6%E4%BA%94/"

    def test_dir_empty_title(self, sample_poem):
        from src.poetry.content import site_page_dir
        assert site_page_dir(dict(sample_poem, title="???")) == "2026-10-04-untitled"

    def test_page_with_infographic(self, sample_poem, sample_story):
        import yaml
        from src.poetry.content import generate_site_page
        page = generate_site_page(sample_poem, sample_story, infographic="infographic.webp")
        _, front_text, body = page.split("---\n", 2)
        assert yaml.safe_load(front_text)["infographic"] == "infographic.webp"
        assert "![水调歌头·明月几时有 信息图](infographic.webp)" in body
        assert body.index("信息图](") < body.index("## 诗词全文")   # 图在正文之前

    def test_page_without_infographic(self, sample_poem, sample_story):
        import yaml
        from src.poetry.content import generate_site_page
        page = generate_site_page(sample_poem, sample_story)
        _, front_text, body = page.split("---\n", 2)
        assert yaml.safe_load(front_text)["infographic"] == ""
        assert "![" not in body

    def test_save_infographic_webp(self, tmp_path):
        from PIL import Image
        from src.poetry.content import save_infographic_webp
        src = tmp_path / "in.png"
        Image.new("RGBA", (64, 96), (200, 30, 30, 255)).save(src)
        dst = save_infographic_webp(str(src), tmp_path / "bundle" / "infographic.webp")
        assert dst.exists()
        with Image.open(dst) as im:
            assert im.format == "WEBP" and im.size == (64, 96)

    def test_page_with_story(self, sample_poem, sample_story):
        import yaml
        from src.poetry.content import generate_site_page
        page = generate_site_page(sample_poem, sample_story)

        _, front_text, body = page.split("---\n", 2)
        front = yaml.safe_load(front_text)
        assert front["title"] == "水调歌头·明月几时有"
        assert front["authors"] == ["苏轼"]
        assert front["dynasties"] == ["宋"]
        assert front["occasions"] == ["中秋节"]
        assert front["categories"] == ["作者轶事", "风土人情"]
        assert front["kinds"] == ["传说", "史实"]
        assert front["summary"] == sample_story["summary"]

        assert "## 诗词全文" in body
        assert "## 赏析" in body
        assert "- 赏月" in body
        assert "> 丙辰中秋" in body
        assert "### 作者轶事" in body
        assert "〔史实 · 《宋史》〕" in body
        assert "〔传说〕" in body
        assert "### 本事与创作背景" not in body  # 空分类不渲染

    def test_page_without_story(self, sample_poem):
        import yaml
        from src.poetry.content import generate_site_page
        page = generate_site_page(sample_poem, None)
        _, front_text, body = page.split("---\n", 2)
        front = yaml.safe_load(front_text)
        assert front["categories"] == []
        assert front["kinds"] == []
        assert front["summary"] == ""
        assert "暂未生成" in body

    def test_page_with_tale(self, sample_poem, sample_story):
        import yaml
        from src.poetry.content import generate_site_page
        tale = {
            "pivot": "扬州盐商", "pivot_type": "地域", "title": "程氏义仓",
            "tale": "乾隆年间，扬州盐商程某……", "connection": "扬州繁华建立在盐运之上。",
            "kind": "史实", "source": "《扬州画舫录·卷九》",
        }
        page = generate_site_page(sample_poem, sample_story, tale)
        _, front_text, body = page.split("---\n", 2)
        front = yaml.safe_load(front_text)
        assert front["pivot_types"] == ["地域"]
        assert front["tale_title"] == "程氏义仓"
        assert "## 衍生一则：程氏义仓" in body
        assert "_衍生自：扬州盐商（地域）_" in body
        assert "乾隆年间" in body
        assert "**与本诗的关联**：扬州繁华" in body
        assert body.rstrip().endswith("〔史实 · 《扬州画舫录·卷九》〕")

    def test_page_without_tale_has_no_section(self, sample_poem, sample_story):
        import yaml
        from src.poetry.content import generate_site_page
        page = generate_site_page(sample_poem, sample_story, None)
        _, front_text, body = page.split("---\n", 2)
        assert yaml.safe_load(front_text)["pivot_types"] == []
        assert "衍生一则" not in body


class TestComposedDisplay:

    def test_exact(self):
        from src.poetry.content import composed_lines
        assert composed_lines({"era": "唐 开元十五年", "year": 727, "certainty": "确切", "note": ""}) == \
            ["唐 开元十五年", "公元 727 年", "丁卯年（兔）"]

    def test_approx_and_bc(self):
        from src.poetry.content import composed_lines
        assert composed_lines({"era": "秦", "year": -221, "certainty": "约", "note": ""}) == \
            ["约 秦", "约 公元前 221 年", "庚辰年（龙）"]

    def test_unknown(self):
        from src.poetry.content import composed_lines
        assert composed_lines({"era": "唐", "year": None, "certainty": "不详", "note": "x"}) == ["唐", "作年不详"]
        assert composed_lines(None) == []

    def test_frontmatter_fields(self, sample_poem):
        import yaml
        from src.poetry.content import generate_site_page
        story = {"summary": "s", "sections": {}, "composed": {"era": "宋 元丰五年", "year": 1082, "certainty": "确切", "note": "n"}}
        front = yaml.safe_load(generate_site_page(sample_poem, story).split("---\n", 2)[1])
        assert front["composed_year"] == 1082 and front["composed_lines"][2] == "壬戌年（狗）"

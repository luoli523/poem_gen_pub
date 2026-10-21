"""信息图 manifest：有 prompt 才写，路径相对仓库根，overwrite 默认 false。"""

import json
from pathlib import Path

from src.common.infographic_manifest import (
    INFOGRAPHIC_FILENAME,
    repo_relative,
    write_infographic_manifest,
)
from src.poetry.content import INFOGRAPHIC_FILENAME as SITE_INFOGRAPHIC_FILENAME


def test_filename_matches_site_asset():
    assert INFOGRAPHIC_FILENAME == SITE_INFOGRAPHIC_FILENAME == "infographic.webp"


def test_repo_relative_under_root(tmp_path):
    content = tmp_path / "site/content/poems/2026-10-21-偶成"
    assert repo_relative(content, tmp_path) == "site/content/poems/2026-10-21-偶成"


def test_writes_poem_payload(tmp_path):
    content = tmp_path / "site/content/poems/2026-10-21-偶成"
    dest = write_infographic_manifest(
        tmp_path / "output",
        date="2026-10-21",
        prompt="  画一张偶成的信息图。  ",
        content_dir=content,
        page_url="https://guige.ai/poem_gen_pub/poems/2026-10-21-%E5%81%B6%E6%88%90/",
        kind="poetry",
        name="偶成",
        repo_root=tmp_path,
    )
    assert dest == tmp_path / "output/infographic-manifests/poetry_2026-10-21_偶成.json"
    data = json.loads(dest.read_text(encoding="utf-8"))
    assert data == {
        "date": "2026-10-21",
        "prompt": "画一张偶成的信息图。",
        "content_dir": "site/content/poems/2026-10-21-偶成",
        "upload_path": "site/content/poems/2026-10-21-偶成/infographic.webp",
        "page_url": "https://guige.ai/poem_gen_pub/poems/2026-10-21-%E5%81%B6%E6%88%90/",
        "overwrite": False,
    }
    # 中文 prompt 原样落地，不转成 \\uXXXX
    assert "画一张偶成" in dest.read_text(encoding="utf-8")


def test_omits_page_url_and_can_set_overwrite(tmp_path):
    content = tmp_path / "site/content/terms/白露/2026"
    dest = write_infographic_manifest(
        tmp_path / "output",
        date="2026-09-07",
        prompt="水墨白露",
        content_dir=content,
        page_url="  ",
        overwrite=True,
        kind="jieling",
        name="白露",
        repo_root=tmp_path,
    )
    data = json.loads(dest.read_text(encoding="utf-8"))
    assert "page_url" not in data
    assert data["overwrite"] is True
    assert data["content_dir"] == "site/content/terms/白露/2026"
    assert data["upload_path"] == data["content_dir"] + "/infographic.webp"


def test_blank_or_non_string_prompt_writes_nothing(tmp_path):
    content = tmp_path / "site/content/poems/x"
    for prompt in ("", "   ", None, 12):
        assert write_infographic_manifest(
            tmp_path / "output", date="2026-10-21", prompt=prompt, content_dir=content,
            kind="poetry", name="偶成", repo_root=tmp_path,
        ) is None
    assert not (tmp_path / "output/infographic-manifests").exists()


def test_filename_strips_path_separators(tmp_path):
    dest = write_infographic_manifest(
        tmp_path / "output",
        date="2026-10-21",
        prompt="p",
        content_dir=tmp_path / "site/content/poems/x",
        kind="poetry",
        name="a/b:c",
        repo_root=tmp_path,
    )
    assert dest.name == "poetry_2026-10-21_abc.json"
    assert dest.parent == tmp_path / "output/infographic-manifests"

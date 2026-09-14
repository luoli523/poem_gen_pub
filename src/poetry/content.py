"""诗词内容生成模块

从 LLM 返回的诗词数据构建 Markdown（NotebookLM source）、
Instagram 文案和 Telegram 消息文案。

注意：infographic prompt 由 LLM 动态生成，不在此模块中构建。
"""

import re
from pathlib import Path

import yaml

from src.poetry.story import SECTION_LABELS


# ── Markdown 生成（作为 NotebookLM Source）──


def generate_markdown(poem: dict) -> str:
    """生成诗词介绍 Markdown 文本，用于上传到 NotebookLM 作为 source。"""
    customs_text = "\n".join(f"- {c}" for c in poem.get("customs", []))

    md = f"""# {poem['title']} — {poem['dynasty']}·{poem['author']}

**日期**：{poem.get('date', '')}
**节日/场景**：{poem.get('occasion', '')}
**朝代**：{poem['dynasty']}
**作者**：{poem['author']}

## 诗词全文

{poem['full_text']}

## 诗词赏析

{poem['meaning']}

## 相关风俗与文化

{customs_text}
"""
    return md


def save_markdown(content: str, output_path: str) -> str:
    """保存诗词 Markdown 文件"""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    return output_path


# ── Instagram 帖子文案 ──


def build_ig_caption(poem: dict) -> str:
    """构建诗词 Instagram 帖子文案。"""
    customs_text = "\n".join(f"  • {c}" for c in poem.get("customs", [])[:4])

    lines = [
        f"📜 {poem['title']}",
        f"    —— {poem['dynasty']}·{poem['author']}",
        "",
        poem["full_text"],
        "",
        f"📖 {poem['meaning'][:200]}{'……' if len(poem['meaning']) > 200 else ''}",
        "",
    ]

    if customs_text:
        lines.extend([
            "🎎 风俗知识",
            customs_text,
            "",
        ])

    occasion = poem.get("occasion", "").strip()
    hashtag_terms = [
        occasion,
        "唐诗宋词",
        "古典诗词",
        "ChinesePoetry",
        poem["author"],
        "传统文化",
        "中国文化",
        "ChineseCulture",
    ]
    hashtags = " ".join(f"#{term}" for term in hashtag_terms if term)
    lines.append(hashtags)

    return "\n".join(lines)


# ── Telegram 消息文案 ──


def build_telegram_caption(poem: dict) -> str:
    """构建诗词 Telegram 图片说明文案"""
    occasion = poem.get("occasion", "")
    customs_short = "、".join(
        c.split("：")[0] if "：" in c else c[:10]
        for c in poem.get("customs", [])[:3]
    )

    return (
        f"<b>📜 {poem['title']}</b>\n"
        f"    —— {poem['dynasty']}·{poem['author']}\n\n"
        f"🏷 {occasion}\n"
        f"🎎 风俗：{customs_short}\n"
    )


# ── 站点内容页（Hugo）──

_UNSAFE_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\s]+')


INFOGRAPHIC_FILENAME = "infographic.webp"
_INFOGRAPHIC_WEBP_QUALITY = 85


def site_page_dir(poem: dict) -> str:
    """站点内容页目录名（Hugo leaf bundle）：YYYY-MM-DD-诗题，去掉非法字符与空白。
    页面写为 <dir>/index.md，信息图与之同目录。"""
    title = _UNSAFE_FILENAME_CHARS.sub("", poem.get("title", "")) or "untitled"
    return f"{poem.get('date', '')}-{title}"


def save_infographic_webp(src_image: str, dst_path: Path) -> Path:
    """把 NotebookLM 下载的 PNG 转成 WebP 存入页面目录（原尺寸，q85 约 350KB，
    直接存 PNG 每张 5MB 会让 repo 一年长 2GB）。"""
    from PIL import Image

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src_image) as im:
        im.convert("RGB").save(dst_path, "WEBP", quality=_INFOGRAPHIC_WEBP_QUALITY, method=6)
    return dst_path


def generate_site_page(
    poem: dict,
    story: dict | None,
    tale: dict | None = None,
    infographic: str | None = None,
    jieling: list[str] | None = None,
) -> str:
    """生成 Hugo 内容页：frontmatter（分类索引用）+ 信息图 + 诗 + 赏析 + 背后的故事 + 衍生一则。

    story / tale 为 None 时仍生成页面，缺的部分留待以后用 --poem 回补。
    infographic 为同目录内的图片文件名，None 表示尚未生成。
    jieling 为当天的节令名（如 ["中秋"]），用于与节令档案页互链。
    """
    sections = (story or {}).get("sections", {})
    summary = (story or {}).get("summary", "")

    present_categories = [SECTION_LABELS[k] for k, items in sections.items() if items]
    present_kinds = sorted({i["kind"] for items in sections.values() for i in items})

    front = {
        "title": poem["title"],
        "date": poem.get("date", ""),
        "author": poem["author"],
        "dynasty": poem["dynasty"],
        "occasion": poem.get("occasion", ""),
        "authors": [poem["author"]],
        "dynasties": [poem["dynasty"]],
        "occasions": [poem["occasion"]] if poem.get("occasion") else [],
        "categories": present_categories,
        "kinds": present_kinds,
        "pivot_types": [tale["pivot_type"]] if tale else [],
        "tale_title": tale["title"] if tale else "",
        "infographic": infographic or "",
        "jieling": list(jieling or []),
        "summary": summary,
    }
    front_text = yaml.safe_dump(front, allow_unicode=True, sort_keys=False).rstrip()

    customs_text = "\n".join(f"- {c}" for c in poem.get("customs", []))

    body = [
        f"---\n{front_text}\n---",
        "",
        f"**{poem['dynasty']}·{poem['author']}** · {poem.get('occasion', '')}",
        "",
    ]
    if infographic:
        body += [f"![{poem['title']} 信息图]({infographic})", ""]
    body += [
        "## 诗词全文",
        "",
        poem["full_text"],
        "",
        "## 赏析",
        "",
        poem["meaning"],
    ]
    if customs_text:
        body += ["", "## 相关风俗", "", customs_text]

    body += ["", "## 背后的故事", ""]
    if story is None:
        body.append("_暂未生成，可用 `--poem` 回补。_")
    else:
        if summary:
            body += [f"> {summary}", ""]
        for key, label in SECTION_LABELS.items():
            items = sections.get(key, [])
            if not items:
                continue
            body += [f"### {label}", ""]
            for item in items:
                tag = f"〔{item['kind']}"
                if item["source"]:
                    tag += f" · {item['source']}"
                tag += "〕"
                body.append(f"- {item['text']} {tag}")
            body.append("")

    if tale:
        heading = "## 衍生一则"
        if tale["title"]:
            heading += f"：{tale['title']}"
        body += [heading, ""]
        if tale["pivot"]:
            body += [f"_衍生自：{tale['pivot']}（{tale['pivot_type']}）_", ""]
        body += [tale["tale"], ""]
        if tale["connection"]:
            body += [f"**与本诗的关联**：{tale['connection']}", ""]
        tag = f"〔{tale['kind']}"
        if tale["source"]:
            tag += f" · {tale['source']}"
        body.append(tag + "〕")

    return "\n".join(body).rstrip() + "\n"

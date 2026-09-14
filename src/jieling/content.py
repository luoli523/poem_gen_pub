"""节令内容：站点页面（按节令 / 年积累）、结构化 story.json、NotebookLM source、推送文案"""

import json
from pathlib import Path

import yaml

from src.jieling.story import SECTION_LABELS

STORY_JSON = "story.json"


def page_dir(site_dir: Path, item: dict) -> Path:
    """site/content/terms/<节令名>/<年>/ —— 每个节令一年一页。"""
    return site_dir / item["name"] / item["date"][:4]


def page_url(base_url: str, item: dict) -> str:
    """节令档案页 URL：terms/<节令名>/<年>/。"""
    from urllib.parse import quote
    return f"{base_url.rstrip('/')}/terms/{quote(item['name'])}/{item['date'][:4]}/"


def load_previous_stories(site_dir: Path, item: dict) -> list[dict]:
    """读同名节令往年（不含今年）的 story.json，供生成时排除。"""
    root = site_dir / item["name"]
    if not root.exists():
        return []
    out = []
    for f in sorted(root.glob(f"*/{STORY_JSON}")):
        year = f.parent.name
        if year == item["date"][:4]:
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            data["year"] = year
            out.append(data)
        except Exception:
            continue
    return out


def save_story_json(dir_: Path, story: dict) -> Path:
    dir_.mkdir(parents=True, exist_ok=True)
    p = dir_ / STORY_JSON
    p.write_text(json.dumps({"summary": story["summary"], "sections": story["sections"]},
                            ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def generate_site_page(item: dict, story: dict | None, infographic: str | None = None) -> str:
    """Hugo 内容页。story 为 None 时页面只有基本信息，待回补。"""
    sections = (story or {}).get("sections", {})
    summary = (story or {}).get("summary", "")
    year = item["date"][:4]

    front = {
        "title": f"{item['name']} · {year}",
        "date": item["date"],
        "jieling_name": item["name"],
        "year": year,
        "category": item["category"],
        "ethnic": item.get("ethnic", ""),
        "lunar": item.get("lunar", ""),
        "season": item.get("season", ""),
        "jieling": [item["name"]],
        "jieling_categories": [item["category"]] + ([item["ethnic"]] if item.get("ethnic") else []),
        "categories": [SECTION_LABELS[k] for k, v in sections.items() if v],
        "kinds": sorted({i["kind"] for v in sections.values() for i in v}),
        "infographic": infographic or "",
        "summary": summary,
    }
    front_text = yaml.safe_dump(front, allow_unicode=True, sort_keys=False).rstrip()

    who = item["category"] if not item.get("ethnic") else f"{item['ethnic']}·{item['category']}"
    when = "，".join(x for x in [item.get("lunar", ""), f"{item['season']}季" if item.get("season") else ""] if x)
    body = [f"---\n{front_text}\n---", "", f"**{who}** · {item['date']}{'（' + when + '）' if when else ''}", ""]
    if infographic:
        body += [f"![{item['name']} {year} 信息图]({infographic})", ""]

    body += ["## 节令素材", ""]
    if story is None:
        body.append("_暂未生成，可用 `--date` 回补。_")
    else:
        if summary:
            body += [f"> {summary}", ""]
        for key, label in SECTION_LABELS.items():
            items = sections.get(key, [])
            if not items:
                continue
            body += [f"### {label}", ""]
            for it in items:
                tag = f"〔{it['kind']}" + (f" · {it['source']}" if it["source"] else "") + "〕"
                body.append(f"- {it['text']} {tag}")
            body.append("")
    return "\n".join(body).rstrip() + "\n"


def generate_nlm_markdown(item: dict, story: dict) -> str:
    """NotebookLM source：节令基本信息 + 六类素材正文（不带可信度标记，避免进入信息图）。"""
    year = item["date"][:4]
    who = item["category"] if not item.get("ethnic") else f"{item['ethnic']}·{item['category']}"
    lines = [f"# {item['name']}（{year}）— {who}", "", f"**日期**：{item['date']}"]
    if item.get("lunar"):
        lines.append(f"**农历**：{item['lunar']}")
    lines += ["", "## 引子", "", story.get("summary", "")]
    for key, label in SECTION_LABELS.items():
        items = story["sections"].get(key, [])
        if not items:
            continue
        lines += ["", f"## {label}", ""]
        lines += [f"- {it['text']}" for it in items]
    return "\n".join(lines) + "\n"


def build_ig_caption(item: dict, story: dict) -> str:
    who = item["category"] if not item.get("ethnic") else f"{item['ethnic']}·{item['category']}"
    lines = [f"🌿 {item['name']} · {item['date'][:4]}", f"    —— {who}", ""]
    if story.get("summary"):
        lines += [story["summary"], ""]
    picks = [it["text"] for key in ("customs", "figures_legends", "food_objects")
             for it in story["sections"].get(key, [])][:3]
    if picks:
        lines += ["📜 " + "\n\n📜 ".join(p[:120] + ("……" if len(p) > 120 else "") for p in picks), ""]
    tags = [item["name"], item.get("ethnic", ""), "节令", "二十四节气" if item["category"] == "节气" else "传统节日",
            "民俗", "传统文化", "ChineseCulture"]
    lines.append(" ".join(f"#{t}" for t in tags if t))
    return "\n".join(lines)


def build_telegram_caption(item: dict, story: dict) -> str:
    who = item["category"] if not item.get("ethnic") else f"{item['ethnic']}·{item['category']}"
    return f"<b>🌿 {item['name']}</b>\n    —— {who}\n\n{story.get('summary', '')}\n"

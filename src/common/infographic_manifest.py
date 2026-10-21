"""把当日信息图请求写成 JSON，供 daily-run 在内容提交后 POST 给外部图片机器人。

诗词的 prompt 来自 detector 返回的 infographic_prompt；节令的来自 jieling.story。
prompt 为空时不写文件：没有可交给机器人的指令。
"""

import json
import re
from pathlib import Path

# 与站点页面里的文件名一致（src.poetry.content.INFOGRAPHIC_FILENAME）
INFOGRAPHIC_FILENAME = "infographic.webp"

_FILENAME_UNSAFE = re.compile(r'[\x00-\x1f\\/:*?"<>|\s]+')


def repo_relative(path: Path, root: Path | None = None) -> str:
    """把内容目录收成相对仓库根的 posix 路径，例如 site/content/poems/2026-10-21-偶成。"""
    root = (root or Path.cwd()).resolve()
    candidate = path if path.is_absolute() else (root / path)
    try:
        rel = candidate.resolve().relative_to(root)
    except ValueError:
        rel = Path(path)
    text = rel.as_posix()
    if text.startswith("./"):
        text = text[2:]
    return text.rstrip("/")


def write_infographic_manifest(
    output_dir: Path,
    *,
    date: str,
    prompt: str,
    content_dir: Path,
    page_url: str = "",
    overwrite: bool = False,
    kind: str,
    name: str,
    repo_root: Path | None = None,
) -> Path | None:
    """写入 output/infographic-manifests/<kind>_<date>_<name>.json。

    无有效 prompt 时返回 None，不创建文件。overwrite 默认 false。
    page_url 为空时省略该字段。
    """
    text = prompt.strip() if isinstance(prompt, str) else ""
    if not text:
        return None

    rel = repo_relative(content_dir, repo_root)
    upload_path = f"{rel}/{INFOGRAPHIC_FILENAME}"
    payload: dict = {
        "date": date,
        "prompt": text,
        "content_dir": rel,
        "upload_path": upload_path,
    }
    url = page_url.strip() if isinstance(page_url, str) else ""
    if url:
        payload["page_url"] = url
    payload["overwrite"] = bool(overwrite)

    safe_name = _FILENAME_UNSAFE.sub("", name) or "item"
    safe_kind = _FILENAME_UNSAFE.sub("", kind) or "item"
    dest_dir = output_dir / "infographic-manifests"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{safe_kind}_{date}_{safe_name}.json"
    dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return dest

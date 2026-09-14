"""给已有的诗词页面补生成信息图（不重跑 LLM、不推送 Telegram / Instagram）

用于 dry_run 生成的页面，或 NotebookLM 当天失败的页面。需要该次运行 artifact 里的
NotebookLM source Markdown 与 .prompt.txt（Actions 保留 7 天：gh run download <id>）。

用法：
  python scripts/backfill_infographic.py \\
      --page "site/content/poems/2026-09-14-九日齐山登高" \\
      --md   output/poetry_秋日登高怀古_2026-09-14.md \\
      --prompt output/poetry_秋日登高怀古_2026-09-14.prompt.txt
"""

import argparse
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml
from dotenv import load_dotenv

from src.common.notebooklm import run_pipeline as nlm_run_pipeline
from src.poetry.content import save_infographic_webp, INFOGRAPHIC_FILENAME

load_dotenv()


def attach_infographic(index_md: Path, filename: str) -> None:
    """在已有页面里写入 frontmatter 的 infographic 字段，并在作者行之后插入图片。"""
    text = index_md.read_text(encoding="utf-8")
    _, front_text, body = text.split("---\n", 2)
    front = yaml.safe_load(front_text)
    front["infographic"] = filename

    img_line = f"![{front['title']} 信息图]({filename})"
    if img_line not in body:
        # 作者行形如 "**宋·李清照** · 中秋节"，图紧随其后（与 generate_site_page 一致）
        body = re.sub(r"(\*\*[^\n]*\*\*[^\n]*\n)", rf"\1\n{img_line}\n", body, count=1)
        if img_line not in body:
            body = f"{img_line}\n\n{body}"

    index_md.write_text(
        "---\n" + yaml.safe_dump(front, allow_unicode=True, sort_keys=False) + "---\n" + body,
        encoding="utf-8",
    )


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", required=True, help="页面目录（含 index.md）")
    ap.add_argument("--md", required=True, help="NotebookLM source Markdown")
    ap.add_argument("--prompt", required=True, help="infographic prompt 文件")
    ap.add_argument("--ratio", default="4:5", choices=["4:5", "9:16", "1:1", "16:9"])
    args = ap.parse_args()

    page = Path(args.page)
    index_md = page / "index.md"
    if not index_md.exists():
        sys.exit(f"找不到 {index_md}")

    title = yaml.safe_load(index_md.read_text(encoding="utf-8").split("---\n", 2)[1])["title"]
    prompt = Path(args.prompt).read_text(encoding="utf-8").strip()

    image = await nlm_run_pipeline(
        label="诗词", md_file=args.md, prompt=prompt,
        artifact_name=f"诗词_{title}_{page.name[:10]}", output_dir="output", ratio=args.ratio,
    )
    if not image:
        sys.exit("infographic 生成失败")

    webp = save_infographic_webp(image, page / INFOGRAPHIC_FILENAME)
    attach_infographic(index_md, INFOGRAPHIC_FILENAME)
    print(f"✅ {title}: {webp} ({webp.stat().st_size // 1024} KB)，页面已更新")


if __name__ == "__main__":
    asyncio.run(main())

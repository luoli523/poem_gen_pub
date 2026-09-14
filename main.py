"""古诗词与节气内容生成系统

主流程：节气检测 → 节气 infographic → 推送 Telegram → 发布 Instagram
     → 诗词检测（LLM）→ 诗词 infographic → 推送 Telegram → 发布 Instagram
"""

import asyncio
import argparse
import sys
from pathlib import Path
from typing import Callable

import yaml
from dotenv import load_dotenv

# ── 共享模块 ──
from src.common.telegram import send_photo as telegram_send_photo, send_message as telegram_send_message, get_telegram_config
from src.common.instagram import get_ig_config, publish_album as ig_publish_album
from src.common.notebooklm import check_auth as check_nlm_auth, run_pipeline as nlm_run_pipeline
from src.common.constants import beijing_today

# ── 节令模块（节气 + 汉族节日 + 少数民族节日）──
from src.jieling.calendar import get_jieling
from src.jieling.story import get_jieling_story
from src.jieling import content as jieling_content

# ── 诗词模块 ──
from src.poetry.detector import get_poem, get_poem_by_name, record_pivot_type, recent_pivot_types
from src.poetry.story import get_story, get_tale
from src.poetry.content import (
    generate_markdown as poetry_generate_markdown,
    build_ig_caption as poetry_build_ig_caption,
    generate_site_page as poetry_generate_site_page,
    site_page_dir as poetry_site_page_dir,
    save_infographic_webp,
    INFOGRAPHIC_FILENAME,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="古诗词与节气内容生成系统")
    parser.add_argument("--no-nlm", action="store_true", help="跳过 NotebookLM 生成流程")
    parser.add_argument("--no-ig", action="store_true", help="跳过 Instagram 发布")

    poem_group = parser.add_mutually_exclusive_group()
    poem_group.add_argument("--no-poetry", action="store_true", help="跳过诗词模块（不调用 LLM）")
    poem_group.add_argument("--poem", type=str, default=None,
                            help="指定诗词名称或关键词（如 '静夜思'、'水调歌头'）")

    parser.add_argument("--date", type=str, default=None,
                        help="指定日期 YYYY-MM-DD（默认北京时间今天）；用于测试或回补某个节令日")
    parser.add_argument("--ratio", type=str, default="4:5",
                        choices=["4:5", "9:16", "1:1", "16:9"],
                        help="信息图长宽比例（默认 4:5）")

    return parser.parse_args()


def load_config(config_path: str = "config/config.yaml") -> dict:
    """加载配置文件"""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── 通用内容管线 ──


async def _run_content_pipeline(
    label: str,
    data: dict,
    today: str,
    output_dir: Path,
    skip_notebooklm: bool,
    skip_ig: bool,
    generate_markdown_fn: Callable[[dict], str],
    build_caption_fn: Callable[[dict], str],
    md_filename: str,
    artifact_name: str,
    ratio: str = "4:5",
) -> str | None:
    """通用内容管线：生成 Markdown → NotebookLM infographic → Telegram → Instagram

    Returns:
        生成的信息图路径；未生成（跳过 / 失败）时返回 None
    """

    # 1. 生成 Markdown
    md_content = generate_markdown_fn(data)
    md_file = output_dir / md_filename
    md_file.parent.mkdir(parents=True, exist_ok=True)
    md_file.write_text(md_content, encoding="utf-8")
    print(f"  📄 {label} Markdown: {md_file}")

    # 输出 infographic prompt 全文并保存到文件
    prompt = data.get("infographic_prompt", "")
    if prompt:
        prompt_file = md_file.with_suffix(".prompt.txt")
        prompt_file.write_text(prompt, encoding="utf-8")
        print(f"  🖼 {label} Infographic Prompt: {prompt_file}")
        print(f"{'─' * 60}")
        print(prompt)
        print(f"{'─' * 60}")
    else:
        print(f"  ⚠ LLM 未返回{label} infographic prompt")

    if skip_notebooklm:
        print("  ⏭ 跳过 NotebookLM（--no-nlm）")
        return None

    # 2. NotebookLM 生成 infographic
    if not prompt:
        return None

    try:
        image = await nlm_run_pipeline(
            label=label,
            md_file=str(md_file),
            prompt=prompt,
            artifact_name=artifact_name,
            output_dir=str(output_dir),
            ratio=ratio,
        )
    except Exception as e:
        # 网络 / 配额 / 等待超时都在这里收住：当天文字内容已落地，只丢图
        print(f"  ❌ {label} infographic 生成出错: {type(e).__name__}: {e}")
        return None

    if not image:
        print(f"  ❌ {label} infographic 生成失败")
        return None

    print(f"  🎨 {label}图片: {image}")

    # 3. Telegram 发送图片 + 完整文案
    tg_config = get_telegram_config()
    if tg_config:
        bot_token, chat_id = tg_config
        print(f"  📱 推送{label}图片到 Telegram...")
        ok = await telegram_send_photo(bot_token, chat_id, image, caption="")
        if ok:
            full_caption = build_caption_fn(data)
            await telegram_send_message(bot_token, chat_id, full_caption, parse_mode="")
            print(f"  ✅ {label}图片及完整文案已推送到 Telegram")
        else:
            print(f"  ⚠ {label}图片 Telegram 推送失败")
    else:
        print(f"  ⏭ Telegram 未配置，跳过{label}推送")

    # 4. Instagram 发布帖子
    if skip_ig:
        print("  ⏭ 跳过 Instagram（--no-ig）")
    else:
        ig_config = get_ig_config()
        if ig_config:
            caption = build_caption_fn(data)
            print(f"  📷 发布{label}帖子到 Instagram...")
            success = await ig_publish_album(
                image_files=[image],
                caption=caption,
                config=ig_config,
            )
            if success:
                print(f"  ✅ {label}帖子已发布到 Instagram")
            else:
                print(f"  ⚠ {label}帖子 Instagram 发布失败")
        else:
            print(f"  ⏭ Instagram 未配置，跳过{label}发布")

    return image


# ── 诗词：故事 + 站点内容页 + 信息图 ──


async def _build_poem_story(poem: dict, tale_enabled: bool) -> tuple[dict | None, dict | None]:
    """生成诗词背后的故事（与可选的衍生一则）。任一失败返回 None，不阻塞主流程。"""
    print("\n📖 正在生成诗词背后的故事...")
    story = await get_story(poem)
    if story:
        n = sum(len(v) for v in story["sections"].values())
        print(f"  ✅ 故事生成完成：{n} 条素材")
    else:
        print("  ⚠ 故事生成失败，内容页将不含故事")

    tale = None
    if tale_enabled:
        print("📚 正在生成衍生一则...")
        tale = await get_tale(poem, story, recent_pivot_types())
        if tale:
            print(f"  ✅ 衍生一则：《{tale['title']}》—— 自「{tale['pivot']}」（{tale['pivot_type']}）衍生")
            record_pivot_type(poem, tale["pivot_type"])
        else:
            print("  ⚠ 衍生故事生成失败，内容页将不含此节")
    else:
        print("  ⏭ 衍生一则已关闭（config tale.enabled）")

    return story, tale


def _write_poem_page(
    poem: dict, site_dir: Path, story: dict | None, tale: dict | None,
    infographic: str | None = None, jieling: list[str] | None = None,
) -> Path:
    """写 Hugo leaf bundle：<site_dir>/<日期-诗题>/index.md。"""
    page_file = site_dir / poetry_site_page_dir(poem) / "index.md"
    page_file.parent.mkdir(parents=True, exist_ok=True)
    page_file.write_text(
        poetry_generate_site_page(poem, story, tale, infographic=infographic, jieling=jieling),
        encoding="utf-8",
    )
    print(f"  📄 站点内容页: {page_file}")
    return page_file


async def _run_poem_flow(
    poem: dict, name_key: str, today: str, output_dir: Path, site_dir: Path,
    skip_notebooklm: bool, skip_ig: bool, tale_enabled: bool, ratio: str,
    problems: list[str], jieling: list[str] | None = None,
) -> None:
    """诗词完整流程：故事 → 先落一版无图页面 → 信息图/推送 → 图转 WebP 存入页面目录并重写页面。

    页面先写再补图，是为了 NotebookLM 失败或超时也不丢当天的文字内容。
    降级情况追加到 problems，由 main 统一汇报。
    """
    story, tale = await _build_poem_story(poem, tale_enabled)
    if story is None:
        problems.append(f"《{poem['title']}》背后的故事生成失败，页面已落地但无故事（可用 --poem 回补）")
    _write_poem_page(poem, site_dir, story, tale, jieling=jieling)

    image = await _run_content_pipeline(
        label="诗词",
        data=poem,
        today=today,
        output_dir=output_dir,
        skip_notebooklm=skip_notebooklm,
        skip_ig=skip_ig,
        generate_markdown_fn=poetry_generate_markdown,
        build_caption_fn=poetry_build_ig_caption,
        md_filename=f"poetry_{name_key}_{today}.md",
        artifact_name=f"诗词_{name_key}_{today}",
        ratio=ratio,
    )
    if image:
        webp = save_infographic_webp(image, site_dir / poetry_site_page_dir(poem) / INFOGRAPHIC_FILENAME)
        print(f"  🖼 信息图已存入站点: {webp}")
        _write_poem_page(poem, site_dir, story, tale, infographic=INFOGRAPHIC_FILENAME, jieling=jieling)
    elif not skip_notebooklm:
        problems.append(f"《{poem['title']}》信息图未生成（NotebookLM 失败），页面无图")


NLM_AUTH_HINT = (
    "检查 secret NOTEBOOKLM_MASTER_TOKEN；若 master token 已被吊销，本地重新执行 "
    "notebooklm login --master-token --account <邮箱>，然后 "
    "base64 -i ~/.notebooklm/profiles/default/master_token.json | gh secret set NOTEBOOKLM_MASTER_TOKEN"
)


async def _report_problems(today: str, problems: list[str]) -> None:
    """把当天所有降级项汇总成一条 Telegram 消息并打印；由 main 决定退出码。"""
    lines = "\n".join(f"• {p}" for p in problems)
    print(f"\n⚠ 本次运行有 {len(problems)} 项降级：\n{lines}")
    tg_config = get_telegram_config()
    if not tg_config:
        return
    bot_token, chat_id = tg_config
    await telegram_send_message(
        bot_token, chat_id,
        f"⚠️ <b>今日流水线降级</b>\n\n📅 {today}\n\n{lines}",
    )
    print("📱 已通过 Telegram 发送降级汇总")


# ── 节令：素材 + 档案页 + 信息图 ──


async def _run_jieling_flow(
    item: dict, today: str, output_dir: Path, terms_dir: Path,
    skip_notebooklm: bool, skip_ig: bool, ratio: str, problems: list[str],
) -> None:
    """一个节令的完整流程：读往年 → 生成素材 → 先落页面 + story.json → 信息图/推送 → 补图。

    每个节令按年积累（terms/<名>/<年>/），往年要点喂给 LLM 作排除。
    """
    label = f"节令·{item['name']}"
    previous = jieling_content.load_previous_stories(terms_dir, item)
    if previous:
        print(f"  📚 往年已有 {len(previous)} 页，生成时排除已写要点")

    print(f"\n🌿 正在生成「{item['name']}」素材...")
    story = await get_jieling_story(item, previous)
    page_dir = jieling_content.page_dir(terms_dir, item)
    page_dir.mkdir(parents=True, exist_ok=True)
    if story is None:
        problems.append(f"节令「{item['name']}」素材生成失败，页面已落地但无内容（可用 --date 回补）")
        (page_dir / "index.md").write_text(jieling_content.generate_site_page(item, None), encoding="utf-8")
        return
    n = sum(len(v) for v in story["sections"].values())
    print(f"  ✅ 素材生成完成：{n} 条")
    jieling_content.save_story_json(page_dir, story)
    (page_dir / "index.md").write_text(jieling_content.generate_site_page(item, story), encoding="utf-8")
    print(f"  📄 节令档案页: {page_dir / 'index.md'}")

    data = {**item, "infographic_prompt": story["infographic_prompt"]}
    image = await _run_content_pipeline(
        label=label, data=data, today=today, output_dir=output_dir,
        skip_notebooklm=skip_notebooklm, skip_ig=skip_ig,
        generate_markdown_fn=lambda _d: jieling_content.generate_nlm_markdown(item, story),
        build_caption_fn=lambda _d: jieling_content.build_ig_caption(item, story),
        md_filename=f"jieling_{item['name']}_{today}.md",
        artifact_name=f"节令_{item['name']}_{today}",
        ratio=ratio,
    )
    if image:
        webp = save_infographic_webp(image, page_dir / INFOGRAPHIC_FILENAME)
        print(f"  🖼 信息图已存入站点: {webp}")
        (page_dir / "index.md").write_text(
            jieling_content.generate_site_page(item, story, infographic=INFOGRAPHIC_FILENAME), encoding="utf-8")
    elif not skip_notebooklm:
        problems.append(f"节令「{item['name']}」信息图未生成（NotebookLM 失败），页面无图")


# ── 主流程 ──


async def main():
    args = parse_args()
    skip_notebooklm = args.no_nlm

    print("=== 古诗词与节气内容生成系统 ===\n")

    load_dotenv()
    today = args.date or beijing_today()

    from src.common.config import get_llm_config, get_llm_model
    llm_config = get_llm_config()
    if not llm_config["api_key"]:
        print("⚠ LLM API Key 未配置（GROK_API_KEY 或 OPENAI_API_KEY），跳过当日全部生成流程")
        tg_config = get_telegram_config()
        if tg_config:
            bot_token, chat_id = tg_config
            await telegram_send_message(
                bot_token, chat_id,
                f"⚠️ <b>当日未执行通知</b>\n\n"
                f"📅 日期：{today}\n"
                f"❌ 原因：LLM API Key 未配置\n"
                f"💡 请在 .env 中配置 GROK_API_KEY 或 OPENAI_API_KEY",
            )
            print("📱 已通过 Telegram 发送未执行通知")
        else:
            print("⚠ Telegram 也未配置，无法发送通知")
        sys.exit(1)

    config = load_config()
    output_dir = Path(config["output"]["dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    site_dir = Path(config["site"]["content_dir"])
    terms_dir = Path(config["site"]["terms_dir"])
    tale_enabled = bool(config.get("tale", {}).get("enabled", False))

    # 降级项：任一环节失败都记在这里，结尾统一汇报并把 run 标红
    problems: list[str] = []

    # NotebookLM 认证检测
    if not skip_notebooklm:
        print("\n🔑 检测 NotebookLM 认证...")
        nlm_auth_ok = await check_nlm_auth()
        if not nlm_auth_ok:
            print("❌ NotebookLM 认证失效，跳过所有 infographic 生成")
            skip_notebooklm = True
            problems.append(f"NotebookLM 认证失效，今日所有信息图跳过。{NLM_AUTH_HINT}")

    # ── 1. 节令（节气 / 汉族节日 / 少数民族节日，可能同日多个）──
    jieling_items = get_jieling(today)
    jieling_names = [j["name"] for j in jieling_items]
    if jieling_items:
        print(f"\n🌿 今日节令：{'、'.join(jieling_names)}")
        for i, item in enumerate(jieling_items):
            if i and not skip_notebooklm:
                print("\n⏳ 等待 30s（避免 NotebookLM 限流）...")
                await asyncio.sleep(30)
            await _run_jieling_flow(
                item, today=today, output_dir=output_dir, terms_dir=terms_dir,
                skip_notebooklm=skip_notebooklm, skip_ig=args.no_ig, ratio=args.ratio, problems=problems,
            )
    else:
        print(f"\n🌿 今日无节令")

    # ── 2. 诗词检测（LLM 动态匹配）与内容生成 ──
    if jieling_items and not skip_notebooklm:
        print("\n⏳ 等待 30s 后继续（避免 NotebookLM 限流）...")
        await asyncio.sleep(30)

    if args.no_poetry:
        print(f"\n📜 跳过诗词模块（--no-poetry）")
    elif args.poem:
        print(f"\n📜 正在获取指定诗词：「{args.poem}」...")
        poem = await get_poem_by_name(args.poem, today)
        if poem:
            print(f"📜 诗词：《{poem['title']}》（{poem['dynasty']}·{poem['author']}）")
            await _run_poem_flow(
                poem, name_key=poem["title"], today=today, output_dir=output_dir, site_dir=site_dir,
                skip_notebooklm=skip_notebooklm, skip_ig=args.no_ig, tale_enabled=tale_enabled,
                ratio=args.ratio, problems=problems, jieling=jieling_names,
            )
        else:
            print(f"📜 诗词「{args.poem}」获取失败，跳过")
            problems.append(f"指定诗词「{args.poem}」获取失败，今日无诗词内容")
    else:
        print(f"\n📜 正在调用 LLM 获取今日诗词...")
        poem = await get_poem(today)
        if poem:
            occasion = poem.get("occasion", "诗词")
            print(f"📜 今日诗词：《{poem['title']}》（{poem['dynasty']}·{poem['author']}）— {occasion}")
            await _run_poem_flow(
                poem, name_key=occasion, today=today, output_dir=output_dir, site_dir=site_dir,
                skip_notebooklm=skip_notebooklm, skip_ig=args.no_ig, tale_enabled=tale_enabled,
                ratio=args.ratio, problems=problems, jieling=jieling_names,
            )
        else:
            print(f"📜 诗词获取失败，跳过")
            problems.append(
                "今日诗词获取失败（LLM 无返回 / JSON 解析失败 / 模型不可用），今日无诗词内容。"
                f"当前模型：{get_llm_model()}"
            )

    if problems:
        await _report_problems(today, problems)
        sys.exit(1)

    print("\n✅ 全部完成！")


if __name__ == "__main__":
    asyncio.run(main())

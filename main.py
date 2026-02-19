"""古诗词与节气内容生成系统

主流程：节气检测 → 节气 infographic → 推送 Telegram → 发布 Instagram
     → 诗词检测（GPT）→ 诗词 infographic → 推送 Telegram → 发布 Instagram
"""

import asyncio
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

# ── 共享模块 ──
from src.common.telegram import send_photo as telegram_send_photo, send_message as telegram_send_message, get_telegram_config
from src.common.instagram import get_ig_config, publish_album as ig_publish_album
from src.common.notebooklm import check_auth as check_nlm_auth

# ── 节气模块 ──
from src.solar_term.detector import get_solar_term
from src.solar_term.content import (
    generate_markdown as solar_term_generate_markdown,
    save_markdown as solar_term_save_markdown,
    build_ig_caption as solar_term_build_ig_caption,
)

# ── 诗词模块 ──
from src.poetry.detector import get_poem
from src.poetry.content import (
    generate_markdown as poetry_generate_markdown,
    save_markdown as poetry_save_markdown,
    build_ig_caption as poetry_build_ig_caption,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="古诗词与节气内容生成系统")
    parser.add_argument("--no-nlm", action="store_true", help="跳过 NotebookLM 生成流程")
    parser.add_argument("--no-ig", action="store_true", help="跳过 Instagram 发布")
    parser.add_argument("--no-poetry", action="store_true", help="跳过诗词模块（不调用 GPT）")
    return parser.parse_args()


def load_config(config_path: str = "config/config.yaml") -> dict:
    """加载配置文件"""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── 节气专属流程 ──


async def _run_solar_term_pipeline(
    solar_term: dict,
    today: str,
    output_dir: Path,
    skip_notebooklm: bool,
    args: argparse.Namespace,
):
    """节气专属流程：生成 Markdown → NotebookLM infographic → Telegram → Instagram"""

    # 1a. 生成节气 Markdown
    md_content = solar_term_generate_markdown(solar_term)
    md_file = output_dir / f"solar_term_{solar_term['name']}_{today}.md"
    solar_term_save_markdown(md_content, str(md_file))
    print(f"  📄 节气 Markdown: {md_file}")

    if skip_notebooklm:
        print("  ⏭ 跳过 NotebookLM（--no-nlm）")
        return

    # 1b. NotebookLM 生成节气 infographic
    try:
        from src.solar_term.notebooklm import run_pipeline as solar_term_run_pipeline
    except ImportError as e:
        print(f"  ❌ NotebookLM 依赖未安装: {e}")
        return

    prompt = solar_term.get("infographic_prompt", "")
    if not prompt:
        print("  ⚠ GPT 未返回节气 infographic prompt，跳过 infographic 生成")
        return

    artifact_name = f"{solar_term['name']}_{today}"

    solar_image = await solar_term_run_pipeline(
        md_file=str(md_file),
        prompt=prompt,
        artifact_name=artifact_name,
        output_dir=str(output_dir),
    )

    if not solar_image:
        print("  ❌ 节气 infographic 生成失败")
        return

    print(f"  🎨 节气图片: {solar_image}")

    # 1c. Telegram 发送节气图片 + 完整文案
    tg_config = get_telegram_config()
    if tg_config:
        bot_token, chat_id = tg_config
        print(f"  📱 推送节气图片到 Telegram...")
        ok = await telegram_send_photo(bot_token, chat_id, solar_image, caption="")
        if ok:
            full_caption = solar_term_build_ig_caption(solar_term)
            await telegram_send_message(bot_token, chat_id, full_caption, parse_mode="")
            print(f"  ✅ 节气图片及完整文案已推送到 Telegram")
        else:
            print(f"  ⚠ 节气图片 Telegram 推送失败")
    else:
        print("  ⏭ Telegram 未配置，跳过节气推送")

    # 1d. Instagram 发布节气帖子
    if hasattr(args, "no_ig") and args.no_ig:
        print("  ⏭ 跳过 Instagram（--no-ig）")
    else:
        ig_config = get_ig_config()
        if ig_config:
            caption = solar_term_build_ig_caption(solar_term)
            print(f"  📷 发布节气帖子到 Instagram...")
            success = await ig_publish_album(
                image_files=[solar_image],
                caption=caption,
                config=ig_config,
            )
            if success:
                print(f"  ✅ 节气帖子已发布到 Instagram")
            else:
                print(f"  ⚠ 节气帖子 Instagram 发布失败")
        else:
            print("  ⏭ Instagram 未配置，跳过节气发布")


# ── 诗词专属流程 ──


async def _run_poetry_pipeline(
    poem: dict,
    today: str,
    output_dir: Path,
    skip_notebooklm: bool,
    args: argparse.Namespace,
):
    """诗词专属流程：生成 Markdown → NotebookLM infographic → Telegram → Instagram"""

    occasion = poem.get("occasion", "诗词")

    # 2a. 生成诗词 Markdown
    md_content = poetry_generate_markdown(poem)
    md_file = output_dir / f"poetry_{occasion}_{today}.md"
    poetry_save_markdown(md_content, str(md_file))
    print(f"  📄 诗词 Markdown: {md_file}")

    if skip_notebooklm:
        print("  ⏭ 跳过 NotebookLM（--no-nlm）")
        return

    # 2b. NotebookLM 生成诗词 infographic
    try:
        from src.poetry.notebooklm import run_pipeline as poetry_run_pipeline
    except ImportError as e:
        print(f"  ❌ NotebookLM 依赖未安装: {e}")
        return

    prompt = poem.get("infographic_prompt", "")
    if not prompt:
        print("  ⚠ GPT 未返回 infographic prompt，跳过")
        return

    artifact_name = f"诗词_{occasion}_{today}"

    poetry_image = await poetry_run_pipeline(
        md_file=str(md_file),
        prompt=prompt,
        artifact_name=artifact_name,
        output_dir=str(output_dir),
    )

    if not poetry_image:
        print("  ❌ 诗词 infographic 生成失败")
        return

    print(f"  🎨 诗词图片: {poetry_image}")

    # 2c. Telegram 发送诗词图片 + 完整文案
    tg_config = get_telegram_config()
    if tg_config:
        bot_token, chat_id = tg_config
        print(f"  📱 推送诗词图片到 Telegram...")
        ok = await telegram_send_photo(bot_token, chat_id, poetry_image, caption="")
        if ok:
            full_caption = poetry_build_ig_caption(poem)
            await telegram_send_message(bot_token, chat_id, full_caption, parse_mode="")
            print(f"  ✅ 诗词图片及完整文案已推送到 Telegram")
        else:
            print(f"  ⚠ 诗词图片 Telegram 推送失败")
    else:
        print("  ⏭ Telegram 未配置，跳过诗词推送")

    # 2d. Instagram 发布诗词帖子
    if hasattr(args, "no_ig") and args.no_ig:
        print("  ⏭ 跳过 Instagram（--no-ig）")
    else:
        ig_config = get_ig_config()
        if ig_config:
            caption = poetry_build_ig_caption(poem)
            print(f"  📷 发布诗词帖子到 Instagram...")
            success = await ig_publish_album(
                image_files=[poetry_image],
                caption=caption,
                config=ig_config,
            )
            if success:
                print(f"  ✅ 诗词帖子已发布到 Instagram")
            else:
                print(f"  ⚠ 诗词帖子 Instagram 发布失败")
        else:
            print("  ⏭ Instagram 未配置，跳过诗词发布")


# ── 主流程 ──


async def main():
    args = parse_args()
    skip_notebooklm = args.no_nlm

    print("=== 古诗词与节气内容生成系统 ===\n")

    load_dotenv()
    today = datetime.now().strftime("%Y-%m-%d")

    if not os.getenv("OPENAI_API_KEY", "").strip():
        print("⚠ OPENAI_API_KEY 未配置，跳过当日全部生成流程")
        tg_config = get_telegram_config()
        if tg_config:
            bot_token, chat_id = tg_config
            await telegram_send_message(
                bot_token, chat_id,
                f"⚠️ <b>当日未执行通知</b>\n\n"
                f"📅 日期：{today}\n"
                f"❌ 原因：OPENAI_API_KEY 未配置\n"
                f"💡 请在 .env 或 GitHub Secrets 中配置后重试",
            )
            print("📱 已通过 Telegram 发送未执行通知")
        else:
            print("⚠ Telegram 也未配置，无法发送通知")
        return

    config = load_config()
    output_dir = Path(config["output"]["dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    # NotebookLM 认证检测
    if not skip_notebooklm:
        print("\n🔑 检测 NotebookLM 认证...")
        nlm_auth_ok = await check_nlm_auth()
        if not nlm_auth_ok:
            print("❌ NotebookLM 认证失效，跳过所有 infographic 生成")
            skip_notebooklm = True
            tg_config = get_telegram_config()
            if tg_config:
                bot_token, chat_id = tg_config
                await telegram_send_message(
                    bot_token, chat_id,
                    f"⚠️ <b>NotebookLM 认证失效</b>\n\n"
                    f"📅 日期：{today}\n"
                    f"❌ 无法生成 infographic，已跳过\n"
                    f"💡 请执行 <code>notebooklm login</code> 重新登录，\n"
                    f"然后更新 GitHub Secret：\n"
                    f"<code>base64 &lt; ~/.notebooklm/storage_state.json | gh secret set NOTEBOOKLM_STORAGE_STATE</code>",
                )
                print("📱 已通过 Telegram 发送认证失效通知")

    # ── 1. 节气检测与专属内容生成 ──
    solar_term = await get_solar_term(today)
    if solar_term:
        print(f"\n🌿 今日节气：{solar_term['name']}！启动节气内容生成流程...")
        await _run_solar_term_pipeline(solar_term, today, output_dir, skip_notebooklm, args)
    else:
        print(f"\n🌿 今日非节气日，跳过节气内容生成")

    # ── 2. 诗词检测（GPT 动态匹配）与专属内容生成 ──
    if solar_term and not skip_notebooklm:
        print("\n⏳ 等待 30s 后继续（避免 NotebookLM 限流）...")
        await asyncio.sleep(30)

    if args.no_poetry:
        print(f"\n📜 跳过诗词模块（--no-poetry）")
    else:
        print(f"\n📜 正在调用 GPT 检测今日诗词...")
        poem = await get_poem(today)
        if poem:
            print(f"📜 今日诗词：《{poem['title']}》（{poem['dynasty']}·{poem['author']}）— {poem.get('occasion', '')}")
            await _run_poetry_pipeline(poem, today, output_dir, skip_notebooklm, args)
        else:
            print(f"📜 今日无匹配诗词，跳过")

    print("\n✅ 全部完成！")


if __name__ == "__main__":
    asyncio.run(main())

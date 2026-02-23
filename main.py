"""古诗词与节气内容生成系统

主流程：节气检测 → 节气 infographic → 推送 Telegram → 发布 Instagram
     → 诗词检测（GPT）→ 诗词 infographic → 推送 Telegram → 发布 Instagram
"""

import asyncio
import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

import yaml
from dotenv import load_dotenv

# ── 共享模块 ──
from src.common.telegram import send_photo as telegram_send_photo, send_message as telegram_send_message, get_telegram_config
from src.common.instagram import get_ig_config, publish_album as ig_publish_album
from src.common.notebooklm import check_auth as check_nlm_auth, run_pipeline as nlm_run_pipeline

# ── 节气模块 ──
from src.solar_term.detector import get_solar_term
from src.solar_term.content import (
    generate_markdown as solar_term_generate_markdown,
    build_ig_caption as solar_term_build_ig_caption,
)

# ── 诗词模块 ──
from src.poetry.detector import get_poem
from src.poetry.content import (
    generate_markdown as poetry_generate_markdown,
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
):
    """通用内容管线：生成 Markdown → NotebookLM infographic → Telegram → Instagram"""

    # 1. 生成 Markdown
    md_content = generate_markdown_fn(data)
    md_file = output_dir / md_filename
    md_file.parent.mkdir(parents=True, exist_ok=True)
    md_file.write_text(md_content, encoding="utf-8")
    print(f"  📄 {label} Markdown: {md_file}")

    if skip_notebooklm:
        print("  ⏭ 跳过 NotebookLM（--no-nlm）")
        return

    # 2. NotebookLM 生成 infographic
    prompt = data.get("infographic_prompt", "")
    if not prompt:
        print(f"  ⚠ GPT 未返回{label} infographic prompt，跳过 infographic 生成")
        return

    image = await nlm_run_pipeline(
        label=label,
        md_file=str(md_file),
        prompt=prompt,
        artifact_name=artifact_name,
        output_dir=str(output_dir),
    )

    if not image:
        print(f"  ❌ {label} infographic 生成失败")
        return

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


# ── 主流程 ──


async def main():
    args = parse_args()
    skip_notebooklm = args.no_nlm

    print("=== 古诗词与节气内容生成系统 ===\n")

    load_dotenv()
    today = datetime.now().strftime("%Y-%m-%d")

    from src.common.config import get_llm_config
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

    # ── 1. 节气检测与内容生成 ──
    solar_term = await get_solar_term(today)
    if solar_term:
        print(f"\n🌿 今日节气：{solar_term['name']}！启动节气内容生成流程...")
        await _run_content_pipeline(
            label="节气",
            data=solar_term,
            today=today,
            output_dir=output_dir,
            skip_notebooklm=skip_notebooklm,
            skip_ig=args.no_ig,
            generate_markdown_fn=solar_term_generate_markdown,
            build_caption_fn=solar_term_build_ig_caption,
            md_filename=f"solar_term_{solar_term['name']}_{today}.md",
            artifact_name=f"{solar_term['name']}_{today}",
        )
    else:
        print(f"\n🌿 今日非节气日，跳过节气内容生成")

    # ── 2. 诗词检测（GPT 动态匹配）与内容生成 ──
    if solar_term and not skip_notebooklm:
        print("\n⏳ 等待 30s 后继续（避免 NotebookLM 限流）...")
        await asyncio.sleep(30)

    if args.no_poetry:
        print(f"\n📜 跳过诗词模块（--no-poetry）")
    else:
        print(f"\n📜 正在调用 GPT 检测今日诗词...")
        poem = await get_poem(today)
        if poem:
            occasion = poem.get("occasion", "诗词")
            print(f"📜 今日诗词：《{poem['title']}》（{poem['dynasty']}·{poem['author']}）— {occasion}")
            await _run_content_pipeline(
                label="诗词",
                data=poem,
                today=today,
                output_dir=output_dir,
                skip_notebooklm=skip_notebooklm,
                skip_ig=args.no_ig,
                generate_markdown_fn=poetry_generate_markdown,
                build_caption_fn=poetry_build_ig_caption,
                md_filename=f"poetry_{occasion}_{today}.md",
                artifact_name=f"诗词_{occasion}_{today}",
            )
        else:
            print(f"📜 今日无匹配诗词，跳过")

    print("\n✅ 全部完成！")


if __name__ == "__main__":
    asyncio.run(main())

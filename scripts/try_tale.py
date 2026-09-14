"""衍生一则 · 模型对比实验

对内置的几首诗各跑一次 get_tale，打印结果，便于对比不同模型的材料真实性。
模型由 config.yaml 的 tale 段决定（或用 --model/--base-url/--key-env 临时覆盖）。

用法：
  python scripts/try_tale.py                          # 用 config.yaml 的 tale 配置
  python scripts/try_tale.py --model deepseek-chat --base-url https://api.deepseek.com --key-env DEEPSEEK_API_KEY
  python scripts/try_tale.py --only 锦瑟 -n 2
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

POEMS = [
    {
        "title": "锦瑟", "author": "李商隐", "dynasty": "唐", "occasion": "秋日感怀",
        "full_text": "锦瑟无端五十弦，一弦一柱思华年。\n庄生晓梦迷蝴蝶，望帝春心托杜鹃。\n"
                     "沧海月明珠有泪，蓝田日暖玉生烟。\n此情可待成追忆，只是当时已惘然。",
    },
    {
        "title": "寄扬州韩绰判官", "author": "杜牧", "dynasty": "唐", "occasion": "秋日怀远",
        "full_text": "青山隐隐水迢迢，秋尽江南草未凋。\n二十四桥明月夜，玉人何处教吹箫。",
    },
    {
        "title": "秋夜曲", "author": "王昌龄", "dynasty": "唐", "occasion": "秋夜怀远",
        "full_text": "桂魄初生秋露微，轻罗已薄未更衣。\n银筝夜久殷勤弄，心怯空房不忍归。",
    },
]


def _apply_overrides(args: argparse.Namespace) -> None:
    """把命令行覆盖写进 config 缓存，避免改文件。"""
    import src.common.config as cfg
    data = cfg._load()
    tale = data.setdefault("tale", {})
    if args.model:
        tale["model"] = args.model
    if args.base_url:
        tale["base_url"] = args.base_url
    if args.key_env:
        tale["api_key_env"] = args.key_env
    if args.max_tokens:
        tale["max_completion_tokens"] = args.max_tokens


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model")
    ap.add_argument("--base-url")
    ap.add_argument("--key-env")
    ap.add_argument("--max-tokens", type=int)
    ap.add_argument("--only", help="只跑标题包含此关键词的诗")
    ap.add_argument("-n", type=int, default=1, help="每首跑几次")
    args = ap.parse_args()
    _apply_overrides(args)

    from src.common.config import get_tale_llm_config
    from src.poetry.story import get_tale

    llm = get_tale_llm_config()
    print(f"模型: {llm['model']}   base_url: {llm.get('base_url', '(OpenAI 默认)')}   "
          f"key: {'已配置' if llm['api_key'] else '缺失'}\n")

    for poem in POEMS:
        if args.only and args.only not in poem["title"]:
            continue
        for i in range(args.n):
            print("=" * 70)
            print(f"《{poem['title']}》{poem['dynasty']}·{poem['author']}   第 {i + 1} 次")
            print("=" * 70)
            tale = await get_tale(poem, None, [])
            if not tale:
                print("(无结果)\n")
                continue
            print(f"标题：{tale['title']}    衍生自：{tale['pivot']}（{tale['pivot_type']}）")
            print(f"可信度：{tale['kind']}    出处：{tale['source'] or '(无)'}")
            print(f"字数：{len(tale['tale'])}\n")
            print(tale["tale"])
            print(f"\n关联：{tale['connection']}\n")


if __name__ == "__main__":
    asyncio.run(main())

"""诗词背后的故事 — 第二次 LLM 调用，生成结构化的人物、本事、风俗与传说素材

与 detector 分开调用：诗词匹配的 prompt 已承载严格 schema + 赏析 + 信息图 prompt，
再塞进千余字故事会挤压所有字段的质量。

每条素材都要求标注可信度（kind）与出处（source），便于日后写作引用时查证。
"""

import json

SECTION_LABELS = {
    "author_anecdote": "作者轶事",
    "composition": "本事与创作背景",
    "era_context": "时代背景",
    "customs": "风土人情",
    "legends": "民间传说与后世演绎",
    "allusions": "典故与名物",
}

KINDS = ("史实", "传说", "附会", "存疑")
_DEFAULT_KIND = "存疑"

SYSTEM_PROMPT = """\
你是一位中国古典文学与文化史学者，同时熟悉笔记小说、地方志与民俗材料。
给定一首诗词，请整理它背后可作为写作素材的杂学知识，按六类输出：

- author_anecdote  作者轶事：生平片段、性格、交游、逸闻
- composition      本事与创作背景：这首作品因何而作、写给谁、在什么处境下写成
- era_context      时代背景：政局、制度、社会风气——解释诗中的用词与情绪为何如此
- customs          风土人情：地域、节令、饮食、服饰、礼俗、市井生活
- legends          民间传说与后世演绎：戏曲、话本、地方传说、名胜附会
- allusions        典故与名物：诗中用典的出处，器物、地名、官职的考据

写作要求：
1. 每类 1-3 条，每条 80-200 字，总量 1000-2000 字；择要而写，不求面面俱到
2. 某一类确实无可靠材料时，返回空数组，绝不为凑数而编造
3. 每条必须标注 kind（可信度）与 source（出处）：
   - 史实：正史、可靠文集、碑刻等有据可查，必须给出典籍名与篇卷
   - 传说：笔记小说、地方志、民间口传中有记载的故事，给出记载它的书名
   - 附会：后世明显牵强的演绎或旅游传说，说明其来源或流行时期
   - 存疑：你无法确定出处的内容，source 可为空
   无法给出典籍出处的内容一律标"存疑"，不得虚构书名或篇卷
   source 统一写作《书名·篇卷》格式，如《旧唐书·杜牧传》《东京梦华录·卷八》
4. 文字面向有文学素养的读者，具体、有画面感，避免泛泛的赞美之词
5. summary 为 100-150 字引子：点出这首诗背后最有料的一件事，引人想读全文

你必须以严格的 JSON 格式返回，schema 如下：
{
  "summary": string,
  "sections": {
    "author_anecdote": [ {"text": string, "kind": string, "source": string} ],
    "composition":     [ {"text": string, "kind": string, "source": string} ],
    "era_context":     [ {"text": string, "kind": string, "source": string} ],
    "customs":         [ {"text": string, "kind": string, "source": string} ],
    "legends":         [ {"text": string, "kind": string, "source": string} ],
    "allusions":       [ {"text": string, "kind": string, "source": string} ]
  }
}
kind 只能取："史实"、"传说"、"附会"、"存疑" 四者之一。"""

USER_PROMPT_TEMPLATE = """\
诗词：《{title}》
作者：{dynasty}·{author}
场景：{occasion}

全文：
{full_text}

请整理这首作品背后的故事与杂学素材。"""


def _normalize_item(item) -> dict | None:
    """归一化单条素材。接受 dict 或纯字符串；text 为空则丢弃。"""
    if isinstance(item, str):
        item = {"text": item}
    if not isinstance(item, dict):
        return None

    text = item.get("text")
    if not isinstance(text, str) or not text.strip():
        return None

    kind = item.get("kind")
    if kind not in KINDS:
        kind = _DEFAULT_KIND

    source = item.get("source")
    source = source.strip() if isinstance(source, str) else ""

    # 自称史实却给不出出处，降级为存疑
    if kind == "史实" and not source:
        kind = _DEFAULT_KIND

    return {"text": text.strip(), "kind": kind, "source": source}


def _validate_and_normalize(data: dict) -> dict | None:
    """校验 LLM 返回的故事数据。六类全空且无 summary 时视为无效，返回 None。"""
    summary = data.get("summary")
    summary = summary.strip() if isinstance(summary, str) else ""

    raw_sections = data.get("sections")
    if not isinstance(raw_sections, dict):
        raw_sections = {}

    sections: dict[str, list[dict]] = {}
    for key in SECTION_LABELS:
        items = raw_sections.get(key, [])
        if not isinstance(items, list):
            items = [items]
        normalized = [n for n in (_normalize_item(i) for i in items) if n]
        sections[key] = normalized

    if not summary and not any(sections.values()):
        print("  ⚠ LLM 返回的故事内容为空")
        return None

    return {"summary": summary, "sections": sections}


async def get_story(poem: dict) -> dict | None:
    """调用 LLM 生成诗词背后的故事。失败返回 None，不影响主流程。

    Returns:
        {"summary": str, "sections": {key: [{"text", "kind", "source"}]}} 或 None
    """
    from src.common.config import get_llm_config
    llm = get_llm_config()
    if not llm["api_key"]:
        return None

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=llm["api_key"], base_url=llm.get("base_url"))
        response = await client.chat.completions.create(
            model=llm["model"],
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT_TEMPLATE.format(
                    title=poem.get("title", ""),
                    author=poem.get("author", ""),
                    dynasty=poem.get("dynasty", ""),
                    occasion=poem.get("occasion", ""),
                    full_text=poem.get("full_text", ""),
                )},
            ],
            response_format={"type": "json_object"},
            max_completion_tokens=llm["max_completion_tokens"],
        )

        content = response.choices[0].message.content
        if not content:
            print("  ⚠ LLM 故事生成返回为空")
            return None

        return _validate_and_normalize(json.loads(content))

    except ImportError:
        print("  ⚠ openai 库未安装，无法生成故事")
        return None
    except json.JSONDecodeError as e:
        print(f"  ⚠ 故事 JSON 解析失败: {e}")
        return None
    except Exception as e:
        print(f"  ⚠ 故事生成出错: {type(e).__name__}: {e}")
        return None

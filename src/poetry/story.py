"""诗词背后的故事 — 第二次 LLM 调用，生成结构化的人物、本事、风俗与传说素材

与 detector 分开调用：诗词匹配的 prompt 已承载严格 schema + 赏析 + 信息图 prompt，
再塞进千余字故事会挤压所有字段的质量。

每条素材都要求标注可信度（kind）与出处（source），便于日后写作引用时查证。
"""

import json

from src.common.llm import log_usage
import re

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
        log_usage("故事", response)

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


# ── 衍生一则：从诗中任一点跳出去的叙事性民间故事 / 方志记载 ──

PIVOT_TYPES = ("地域", "时节", "朝代", "民族", "风俗", "名物")
_ANONYMOUS_PROTAGONIST = re.compile(r"[\u4e00-\u9fff]某(?![年月日时])")

TALE_SYSTEM_PROMPT = """\
你是一位熟读笔记小说、史传与地方志的文化史学者，正在为一位写作者搜集素材。
给定一首诗词，以及围绕它已经整理过的考据要点，请从诗中**任意一个点**跳出去——
一个地名、一个节令、一个朝代、一个民族、一种风俗、一件器物——讲一则你**确实熟知**的故事。

【最重要的一条】惊喜来自"选点刁"，不来自"材料冷"。
- 选点要出人意料：从"锦瑟"可以跳到唐代乐工的行会，从"扬州"可以跳到盐商家里的一个婢女
- 但选定之后，只讲你真正读过、能说清出处的故事；把握不足的冷门材料不要碰
- 也避开中学课本级别人尽皆知的故事（屈原投江、李白捉月、兰亭雅集之类）；
  目标读者是文学爱好者，要让他觉得"原来还有这一段"——笔记小说里的次要人物、
  正史列传里的一桩小事、名人身边的无名者，往往正是这样的材料
- 你不熟的书不要引，记不清的事不要讲；不确定某书是否真有此条，就不要写成"载于某书"
- 绝不虚构：不得编造人物、情节、书名、篇卷；不得给一个现编的故事配上像真的出处
- 匿名主角（"王某""一少年"）的故事不得标"史实"，最高只能标"传说"

素材来源，按你的把握程度取用：
1. 你熟知的史传与笔记：《史记》《汉书》《世说新语》《太平广记》《酉阳杂俎》《夷坚志》
   《东京梦华录》《武林旧事》《扬州画舫录》《阅微草堂笔记》《子不语》等
2. 地方志与地域笔记中你确有把握的名条目（如《清嘉录》的节令、《帝京景物略》的古迹）
3. 广为流传的民间故事、戏曲话本（注明流传地域或剧目）

取材要求：
1. 有活人：具名或有明确身份的人物，具体的年代、地点、一段具体的经历，有情节转折
   拒绝"古人常常……""当地流行……"这类泛写
2. 避开随题给出的已整理要点，从别的点衍生；尽量避开近期已用过的衍生类型
3. 凡适合做写作题材的都可以：奇人、冤案、异事、一桩买卖、一场迁徙、一个手艺、
   一次水旱、一段婚姻、一件器物的来历——不限于"传说"

写法要求：
- 叙事口吻，400-800 字，可有对话与细节，像讲给朋友听
- 不美化、不煽情、不下道德评语；把细节留给读者
- connection 用一两句说清它与这首诗的关联点，不必牵强

你必须以严格的 JSON 格式返回，schema 如下：
{
  "pivot": string,        // 衍生点，如"扬州盐商"、"寒食禁火"、"契丹捺钵"
  "pivot_type": string,   // 只能取："地域"、"时节"、"朝代"、"民族"、"风俗"、"名物"
  "title": string,        // 故事标题，8 字以内
  "tale": string,         // 400-800 字叙事正文
  "connection": string,   // 与本诗的关联，1-2 句
  "kind": string,         // 只能取："史实"、"传说"、"附会"、"存疑"
  "source": string        // 《书名·篇卷》，或"流传于××一带"
}"""

TALE_USER_TEMPLATE = """\
诗词：《{title}》（{dynasty}·{author}）
场景：{occasion}

全文：
{full_text}

已整理过的考据要点（请避开，从别处衍生）：
{covered}

近期已用过的衍生类型（请尽量避开）：{recent_pivot_types}

请讲一则衍生出来的故事。"""


TALE_MIN_CHARS = 350

TALE_EXPAND_TEMPLATE = """\
下面这稿只有 {n} 字，不到要求的 400-800 字。请保持同一个故事、同一出处、同一 kind，
扩写到 400-800 字：补足人物的处境与动机、具体的时间地点、一两处对话或细节、情节的转折。
不得为凑字数添加你没有把握的情节。仍按同一 JSON schema 返回。

上一稿：
{draft}"""


def _validate_tale(data: dict) -> dict | None:
    """校验衍生故事。tale 正文为空即无效；pivot_type / kind 非法则归为兜底值。"""
    tale = data.get("tale")
    if not isinstance(tale, str) or not tale.strip():
        print("  ⚠ LLM 返回的衍生故事正文为空")
        return None

    def _str(key: str) -> str:
        v = data.get(key)
        return v.strip() if isinstance(v, str) else ""

    pivot_type = _str("pivot_type")
    if pivot_type not in PIVOT_TYPES:
        pivot_type = "风俗"

    kind = _str("kind")
    if kind not in KINDS:
        kind = _DEFAULT_KIND
    source = _str("source")
    if kind == "史实" and not source:
        kind = _DEFAULT_KIND
    # 匿名主角（"王某"）却自称史实：降级为传说
    if kind == "史实" and _ANONYMOUS_PROTAGONIST.search(tale):
        kind = "传说"

    return {
        "pivot": _str("pivot"),
        "pivot_type": pivot_type,
        "title": _str("title"),
        "tale": tale.strip(),
        "connection": _str("connection"),
        "kind": kind,
        "source": source,
    }


def _covered_points(story: dict | None) -> str:
    """把六类素材压成一行一条的要点清单，供衍生故事避开。"""
    if not story:
        return "（无）"
    lines = []
    for key, items in story.get("sections", {}).items():
        for item in items:
            lines.append(f"- [{SECTION_LABELS[key]}] {item['text'][:60]}")
    return "\n".join(lines) or "（无）"


async def get_tale(poem: dict, story: dict | None, recent_pivot_types: list[str]) -> dict | None:
    """调用 LLM 生成一则衍生故事。失败返回 None，不影响主流程。"""
    from src.common.config import get_tale_llm_config
    llm = get_tale_llm_config()
    if not llm["api_key"]:
        return None

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=llm["api_key"], base_url=llm.get("base_url"))
        response = await client.chat.completions.create(
            model=llm["model"],
            messages=[
                {"role": "system", "content": TALE_SYSTEM_PROMPT},
                {"role": "user", "content": TALE_USER_TEMPLATE.format(
                    title=poem.get("title", ""),
                    author=poem.get("author", ""),
                    dynasty=poem.get("dynasty", ""),
                    occasion=poem.get("occasion", ""),
                    full_text=poem.get("full_text", ""),
                    covered=_covered_points(story),
                    recent_pivot_types="、".join(recent_pivot_types) or "（无）",
                )},
            ],
            response_format={"type": "json_object"},
            max_completion_tokens=llm["max_completion_tokens"],
        )
        log_usage("衍生一则", response)

        content = response.choices[0].message.content
        if not content:
            print("  ⚠ LLM 衍生故事返回为空")
            return None

        tale = _validate_tale(json.loads(content))
        if tale and len(tale["tale"]) < TALE_MIN_CHARS:
            # 模型常忽略篇幅要求；带着上一稿要求扩写一次
            print(f"  ↻ 衍生故事仅 {len(tale['tale'])} 字，要求扩写...")
            response = await client.chat.completions.create(
                model=llm["model"],
                messages=[
                    {"role": "system", "content": TALE_SYSTEM_PROMPT},
                    {"role": "user", "content": TALE_EXPAND_TEMPLATE.format(
                        n=len(tale["tale"]), draft=json.dumps(tale, ensure_ascii=False),
                    )},
                ],
                response_format={"type": "json_object"},
                max_completion_tokens=llm["max_completion_tokens"],
            )
            log_usage("衍生一则·扩写", response)
            content = response.choices[0].message.content
            expanded = _validate_tale(json.loads(content)) if content else None
            if expanded and len(expanded["tale"]) > len(tale["tale"]):
                tale = expanded
        return tale

    except ImportError:
        print("  ⚠ openai 库未安装，无法生成衍生故事")
        return None
    except json.JSONDecodeError as e:
        print(f"  ⚠ 衍生故事 JSON 解析失败: {e}")
        return None
    except Exception as e:
        print(f"  ⚠ 衍生故事生成出错: {type(e).__name__}: {e}")
        return None

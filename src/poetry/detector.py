"""诗词检测模块 — 使用 LLM 动态匹配当天日期相关的唐诗宋词

流程：
  1. 计算当天的农历日期、节气等上下文
  2. 调用 LLM，让模型判断今天是否有相关经典诗词
  3. 如有，返回结构化的诗词数据（全文、赏析、风俗、infographic prompt）
  4. 如无匹配，再次调用 LLM 随机推荐一首应季经典诗词
"""

import json
from datetime import datetime

WEEKDAY_NAMES = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

# ── System Prompt ──

SYSTEM_PROMPT = """\
你是一位中国古典文学专家和文化学者。给定一个日期，
请判断这个日期是否与某首著名的唐诗宋词（或极经典的先秦/魏晋诗词）有特殊关联。

你会收到以下经过精确计算的日期信息（来自天文历法库，请直接信任）：
- 公历日期和星期
- 农历日期（由 zhdate 库计算，精确可靠）
- 当日节气（由寿星天文历 sxtwl 计算，仅在节气日提供）

请根据这些精确的日期事实，结合你的知识自行判断当天涉及的节日、纪念日或文化场景，
包括但不限于：
- 传统农历节日（春节、元宵、清明、端午、七夕、中秋、重阳、除夕、寒食等）
- 二十四节气
- 公历节日（元旦、情人节、母亲节、教师节等，含浮动日期节日）
- 现代节日的古典诗词呼应（情人节→鹊桥仙、母亲节→游子吟、教师节→绿野堂等）
- 历史事件纪念日、诗人诞辰/忌日等

判断规则：
1. 如果有多首相关诗词，选择最著名、传颂度最高的那一首
2. 如果当天确实没有任何相关的著名诗词，返回 has_poem: false
3. 诗词全文必须完整准确，不得删减或篡改
4. 赏析要通俗易懂，300-500字，兼顾文学性和科普性
5. 风俗科普要具体实用，每条30-60字

当 has_poem 为 true 时，你还需要生成一段用于 NotebookLM 生成信息图的 prompt（infographic_prompt 字段）。
生成 infographic_prompt 时请遵循以下视觉风格指引：
- 中国古典书画风（水墨/工笔）与现代信息图融合
- 诗词全文以书法形式呈现，作为视觉焦点
- 配合诗词意境和节日场景的插画元素（如中秋配月亮、元宵配灯笼、清明配杏花雨）
- 包含诗词赏析摘要和风俗知识的信息区块
- 整体配色契合诗词的季节和情感基调
- 印章、窗棂、山水等中国传统元素作为点缀
- 竖版排版（PORTRAIT），印刷级清晰度，典雅精致
- infographic_prompt 应为完整的、可直接提交给信息图生成工具的指令，300-500字

你必须以严格的 JSON 格式返回，schema 如下：
{
  "has_poem": boolean,
  "occasion": string,       // 节日/节气/纪念日名称，has_poem=false 时为空字符串
  "title": string,          // 诗词标题，如"水调歌头·明月几时有"
  "author": string,         // 作者
  "dynasty": string,        // 朝代
  "full_text": string,      // 诗词完整全文
  "meaning": string,        // 诗词赏析（300-500字）
  "customs": [string],      // 相关风俗科普（3-5条）
  "infographic_prompt": string  // NotebookLM 信息图生成 prompt
}

has_poem=false 时，除 has_poem 和 occasion 外的字段用空字符串或空数组。"""

# ── 随机推荐 Prompt ──

RANDOM_POEM_SYSTEM_PROMPT = """\
你是一位中国古典文学专家。今天没有特定节日或纪念日与经典诗词关联，
请你随机推荐一首著名的唐诗宋词（或极经典的先秦/魏晋诗词），要求：

选诗规则：
1. 优先选择与当前季节、时令、天气氛围契合的诗词
2. 必须是广为传颂的经典作品，不要冷僻之作
3. 诗词全文必须完整准确，不得删减或篡改
4. 每次推荐应有随机性，不要总是推荐同一首

内容要求：
1. occasion 字段填写推荐理由的简要概括（如"春日即景"、"秋思怀远"、"冬日暖意"等）
2. 赏析要通俗易懂，300-500字，兼顾文学性和科普性
3. customs 字段填写与诗词主题相关的文化知识（3-5条，每条30-60字）

你还需要生成一段用于 NotebookLM 生成信息图的 prompt（infographic_prompt 字段）。
生成 infographic_prompt 时请遵循以下视觉风格指引：
- 中国古典书画风（水墨/工笔）与现代信息图融合
- 诗词全文以书法形式呈现，作为视觉焦点
- 配合诗词意境的插画元素
- 包含诗词赏析摘要和文化知识的信息区块
- 整体配色契合诗词的季节和情感基调
- 印章、窗棂、山水等中国传统元素作为点缀
- 竖版排版（PORTRAIT），印刷级清晰度，典雅精致
- infographic_prompt 应为完整的、可直接提交给信息图生成工具的指令，300-500字

你必须以严格的 JSON 格式返回，schema 如下：
{
  "title": string,
  "author": string,
  "dynasty": string,
  "full_text": string,
  "occasion": string,
  "meaning": string,
  "customs": [string],
  "infographic_prompt": string
}"""

RANDOM_POEM_USER_TEMPLATE = """\
今天是 {date}（{weekday}）。
{extra_context}
请随机推荐一首适合今天阅读的经典诗词。"""

# ── User Prompt Template ──

USER_PROMPT_TEMPLATE = """\
今天是 {date}（{weekday}）。
{extra_context}
请判断今天是否有相关的经典唐诗宋词，如果有，请返回完整信息。"""


def _build_extra_context(date_str: str) -> str:
    """构建经精确计算的日期事实（农历、节气），供 LLM 自行判断关联。"""
    parts = []

    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return ""

    try:
        from zhdate import ZhDate

        zh = ZhDate.from_datetime(dt)
        parts.append(f"农历：{zh.lunar_month}月{zh.lunar_day}日")
    except ImportError:
        pass
    except Exception:
        pass

    try:
        import sxtwl
        from src.common.constants import JIEQI_NAMES

        day = sxtwl.fromSolar(dt.year, dt.month, dt.day)
        if day.hasJieQi():
            jq_name = JIEQI_NAMES[day.getJieQi()]
            parts.append(f"节气：{jq_name}")
    except ImportError:
        pass
    except Exception:
        pass

    return "\n".join(parts)


def _validate_and_normalize(data: dict, date_str: str) -> dict | None:
    """校验 LLM 返回的诗词数据，归一化字段类型。校验失败返回 None。"""
    data["date"] = date_str

    required_fields = ["title", "author", "dynasty", "full_text", "meaning",
                       "customs", "infographic_prompt", "occasion"]
    for field in required_fields:
        if field not in data:
            print(f"  ⚠ LLM 返回缺少字段: {field}")
            return None

    text_fields = ["title", "author", "dynasty", "full_text", "meaning", "infographic_prompt", "occasion"]
    for field in text_fields:
        value = data.get(field, "")
        if value is None:
            data[field] = ""
        elif not isinstance(value, str):
            data[field] = str(value)

    customs = data.get("customs", [])
    if isinstance(customs, list):
        data["customs"] = [str(item) for item in customs if item is not None]
    elif isinstance(customs, str):
        data["customs"] = [customs] if customs.strip() else []
    else:
        data["customs"] = []

    return data


async def get_poem(date_str: str) -> dict | None:
    """调用 LLM 获取当天诗词。优先匹配日期关联诗词，无匹配时随机推荐。

    Args:
        date_str: 日期字符串（YYYY-MM-DD）

    Returns:
        诗词信息字典（含 title, author, dynasty, full_text, meaning,
        customs, infographic_prompt, occasion, date）或 None
    """
    from src.common.config import get_llm_config
    llm = get_llm_config()
    if not llm["api_key"]:
        return None

    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None

    weekday = WEEKDAY_NAMES[dt.weekday()]
    extra_context = _build_extra_context(date_str)

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=llm["api_key"], base_url=llm.get("base_url"))

        # 第一步：尝试匹配日期关联诗词
        response = await client.chat.completions.create(
            model=llm["model"],
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT_TEMPLATE.format(
                    date=date_str, weekday=weekday, extra_context=extra_context,
                )},
            ],
            response_format={"type": "json_object"},
            max_completion_tokens=llm["max_completion_tokens"],
        )

        content = response.choices[0].message.content
        if content:
            data = json.loads(content)
            if data.get("has_poem", False):
                result = _validate_and_normalize(data, date_str)
                if result:
                    return result

        # 第二步：无匹配，随机推荐一首
        print("  📝 无日期关联诗词，随机推荐...")
        response = await client.chat.completions.create(
            model=llm["model"],
            messages=[
                {"role": "system", "content": RANDOM_POEM_SYSTEM_PROMPT},
                {"role": "user", "content": RANDOM_POEM_USER_TEMPLATE.format(
                    date=date_str, weekday=weekday, extra_context=extra_context,
                )},
            ],
            response_format={"type": "json_object"},
            max_completion_tokens=llm["max_completion_tokens"],
        )

        content = response.choices[0].message.content
        if not content:
            print("  ⚠ LLM 随机推荐返回为空")
            return None

        data = json.loads(content)
        return _validate_and_normalize(data, date_str)

    except ImportError:
        print("  ⚠ openai 库未安装，无法使用诗词模块")
        return None
    except json.JSONDecodeError as e:
        print(f"  ⚠ LLM 返回 JSON 解析失败: {e}")
        return None
    except Exception as e:
        print(f"  ⚠ 诗词检测出错: {type(e).__name__}: {e}")
        return None

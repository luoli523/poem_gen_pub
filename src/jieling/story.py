"""节令素材生成：一次 LLM 调用，产出六类素材 + 引子 + 信息图 prompt

每个节令按年积累一页；生成时把往年已写过的要点喂入 prompt 作排除，
让白露这一页一年比一年厚，而不是每年重复。
"""

import json

from src.common.llm import log_usage
from src.poetry.story import normalize_item

SECTION_LABELS = {
    "origin": "名义与物候",
    "customs": "历代风俗",
    "food_objects": "饮食与器物",
    "in_poetry": "诗文中的它",
    "figures_legends": "人物与传说",
    "gazetteers": "方志记载",
}

SYSTEM_PROMPT = """\
你是一位熟读历代岁时记、地方志、民族志与笔记小说的文化史学者，正在为一位写作者搜集节令素材。
给定一个节令（二十四节气、汉族传统节日或少数民族节日），请按六类整理可作写作素材的知识：

- origin           名义与物候：名称由来、三候、天文历法上的定义、别称
- customs          历代风俗：按朝代 / 地域的具体做法——不写"赏菊"，写"宋代汴京重阳……《东京梦华录》载"
- food_objects     饮食与器物：时令食物与节令用具的做法、来历、名称演变
- in_poetry        诗文中的它：历代名句怎么写这个节令，用词与意象的演变
- figures_legends  人物与传说：附着在这个节令上的故事、有名有姓的人物、起源传说
- gazetteers       方志记载：地方志、民族志里的地域差异与奇特做法

写作要求：
1. 每类 1-3 条，每条 80-200 字，总量 1200-2500 字；有则写，无可靠材料则留空数组，绝不凑数
2. 每条必须标注 kind（可信度）与 source（出处）：
   - 史实：正史、岁时记（《荆楚岁时记》《东京梦华录》《梦粱录》《帝京景物略》《清嘉录》）、
     可靠文集与地方志可查，须给出《书名·篇卷》
   - 传说：笔记小说、民族口传、地方传说中有记载或有流传的，给出书名或"流传于××一带"
   - 附会：后世明显牵强的演绎或旅游宣传，说明来源
   - 存疑：无法确定出处的内容，source 可为空
   不得虚构书名篇卷；给不出出处一律标"存疑"
3. 少数民族节日：写明民族、地域、仪式的具体做法（时间、地点、人物、器物、禁忌），
   优先有名有姓的人物与起源传说；来源可以是民族志、地方志，以及《蛮书》《百夷传》《滇略》
   《桂海虞衡志》《岭外代答》等古籍；口传材料标"传说·流传于××一带"
4. 面向有文学素养的读者，具体、有画面感，不写养生建议、不写泛泛的赞美
5. summary 为 100-150 字引子：点出这个节令最有料的一件事
6. 如果随题给出了往年已写过的要点，请避开它们，从别的材料、别的朝代、别的地域写

你还需要生成一段用于 NotebookLM 生成信息图的 prompt（infographic_prompt，300-500 字）：
- 中国古典书画风（水墨 / 工笔）与现代信息图融合；少数民族节令则融入该民族的纹样、服饰与器物色彩
- 节令名称以书法或印章形式呈现，作为视觉焦点
- 配合当季物候与节令场景的插画元素
- 包含 3-5 个核心知识点的信息区块（取自上面六类中最有料的条目）
- 整体配色契合季节与情感基调，竖版排版（PORTRAIT），印刷级清晰度
- 应为完整的、可直接提交给信息图生成工具的指令

你必须以严格的 JSON 格式返回，schema 如下：
{
  "summary": string,
  "sections": {
    "origin":          [ {"text": string, "kind": string, "source": string} ],
    "customs":         [ {"text": string, "kind": string, "source": string} ],
    "food_objects":    [ {"text": string, "kind": string, "source": string} ],
    "in_poetry":       [ {"text": string, "kind": string, "source": string} ],
    "figures_legends": [ {"text": string, "kind": string, "source": string} ],
    "gazetteers":      [ {"text": string, "kind": string, "source": string} ]
  },
  "infographic_prompt": string
}
kind 只能取："史实"、"传说"、"附会"、"存疑" 四者之一。"""

USER_TEMPLATE = """\
节令：{name}（{category}{ethnic_part}）
日期：{date}{lunar_part}{season_part}

往年已写过的要点（请避开，写别的材料）：
{previous}

请整理这个节令的素材，并生成信息图 prompt。"""


def format_previous_points(previous: list[dict]) -> str:
    """把往年各页的 sections 压成一行一条的清单，供 prompt 排除。"""
    lines = []
    for story in previous:
        year = story.get("year", "")
        for key, items in story.get("sections", {}).items():
            label = SECTION_LABELS.get(key, key)
            for item in items:
                lines.append(f"- [{year} {label}] {item['text'][:60]}")
    return "\n".join(lines) or "（无，这是第一年）"


def _validate_and_normalize(data: dict) -> dict | None:
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
        sections[key] = [n for n in (normalize_item(i) for i in items) if n]

    prompt = data.get("infographic_prompt")
    prompt = prompt.strip() if isinstance(prompt, str) else ""

    if not any(sections.values()):
        print("  ⚠ LLM 返回的节令素材为空")
        return None
    return {"summary": summary, "sections": sections, "infographic_prompt": prompt}


async def get_jieling_story(item: dict, previous: list[dict]) -> dict | None:
    """为一个节令生成素材。失败返回 None，不影响主流程。

    Args:
        item: calendar.get_jieling 返回的一项
        previous: 往年同名节令的 story（含 year / sections），用于排除
    """
    from src.common.config import get_llm_config
    llm = get_llm_config()
    if not llm["api_key"]:
        return None

    user = USER_TEMPLATE.format(
        name=item["name"], category=item["category"],
        ethnic_part=f"·{item['ethnic']}" if item.get("ethnic") else "",
        date=item["date"],
        lunar_part=f"，农历{item['lunar']}" if item.get("lunar") else "",
        season_part=f"，{item['season']}季" if item.get("season") else "",
        previous=format_previous_points(previous),
    )
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=llm["api_key"], base_url=llm.get("base_url"))
        response = await client.chat.completions.create(
            model=llm["model"],
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": user}],
            response_format={"type": "json_object"},
            max_completion_tokens=llm["max_completion_tokens"],
        )
        log_usage(f"节令·{item['name']}", response)
        content = response.choices[0].message.content
        if not content:
            print("  ⚠ LLM 节令素材返回为空")
            return None
        return _validate_and_normalize(json.loads(content))
    except ImportError:
        print("  ⚠ openai 库未安装，无法生成节令素材")
        return None
    except json.JSONDecodeError as e:
        print(f"  ⚠ 节令素材 JSON 解析失败: {e}")
        return None
    except Exception as e:
        print(f"  ⚠ 节令素材生成出错: {type(e).__name__}: {e}")
        return None

"""节令日历：判断某一天是哪些节令（二十四节气、汉族传统节日、少数民族节日）

三类判断方式：
- 节气：sxtwl 天文历
- 农历定日节日：zhdate 换算农历后查表（闰月不算）
- 相对节日 / 公历定日 / 依民族历法（藏历、伊斯兰历）按年硬编码

同一天可能命中多个节令（清明既是节气也是节日；上巳与壮族三月三同日），全部返回。
"""

from datetime import datetime, timedelta

from src.common.constants import JIEQI_NAMES

# 类别常量
JIEQI = "节气"
HAN = "汉族节日"
ETHNIC = "民族节日"

_SEASON_MAP = {
    "立春": "春", "雨水": "春", "惊蛰": "春", "春分": "春", "清明": "春", "谷雨": "春",
    "立夏": "夏", "小满": "夏", "芒种": "夏", "夏至": "夏", "小暑": "夏", "大暑": "夏",
    "立秋": "秋", "处暑": "秋", "白露": "秋", "秋分": "秋", "寒露": "秋", "霜降": "秋",
    "立冬": "冬", "小雪": "冬", "大雪": "冬", "冬至": "冬", "小寒": "冬", "大寒": "冬",
}

# 农历定日：(月, 日) -> [(名称, 类别, 民族)]
_LUNAR_FIXED: dict[tuple[int, int], list[tuple[str, str, str]]] = {
    (1, 1):   [("春节", HAN, "")],
    (1, 15):  [("元宵", HAN, "")],
    (2, 2):   [("龙抬头", HAN, "")],
    (2, 8):   [("刀杆节", ETHNIC, "傈僳族")],
    (2, 12):  [("花朝", HAN, "")],
    (3, 3):   [("上巳", HAN, ""), ("三月三", ETHNIC, "壮族")],
    (3, 15):  [("三月街", ETHNIC, "白族")],
    (4, 8):   [("四月八", ETHNIC, "苗族")],
    (5, 5):   [("端午", HAN, "")],
    (6, 6):   [("六月六", ETHNIC, "布依族")],
    (6, 24):  [("火把节", ETHNIC, "彝族")],
    (7, 7):   [("七夕", HAN, "")],
    (7, 15):  [("中元", HAN, "")],
    (8, 15):  [("中秋", HAN, "")],
    (9, 9):   [("重阳", HAN, "")],
    (10, 1):  [("寒衣", HAN, ""), ("羌年", ETHNIC, "羌族")],
    (10, 15): [("下元", HAN, "")],
    (10, 16): [("盘王节", ETHNIC, "瑶族")],
    (12, 8):  [("腊八", HAN, "")],
    (12, 23): [("小年", HAN, "")],
}

# 公历定日：(月, 日) -> [(名称, 类别, 民族)]
_SOLAR_FIXED: dict[tuple[int, int], list[tuple[str, str, str]]] = {
    (4, 13): [("泼水节", ETHNIC, "傣族")],
}

# 依民族历法、无法公式计算的节日：按年硬编码，年底据官方公告补下一年
# 来源：西藏文旅厅（藏历新年 2026-02-18）；伊斯兰历节日可能因新月观测 ±1 天
_BY_YEAR: dict[str, list[tuple[str, str, str]]] = {
    "2026-02-18": [("藏历新年", ETHNIC, "藏族")],
    "2026-03-20": [("开斋节", ETHNIC, "回族")],
    "2026-05-27": [("古尔邦节", ETHNIC, "回族")],
    "2027-02-06": [("藏历新年", ETHNIC, "藏族")],   # 待官方公告确认
}


def _jieqi_name(dt: datetime) -> str | None:
    try:
        import sxtwl
    except ImportError:
        return None
    day = sxtwl.fromSolar(dt.year, dt.month, dt.day)
    return JIEQI_NAMES[day.getJieQi()] if day.hasJieQi() else None


def _lunar(dt: datetime):
    """返回 (月, 日, 是否闰月)，zhdate 不可用或超出范围时返回 None。"""
    try:
        from zhdate import ZhDate
        z = ZhDate.from_datetime(dt)
        return z.lunar_month, z.lunar_day, bool(z.leap_month)
    except Exception:
        return None


def _lunar_label(month: int, day: int) -> str:
    months = ["正", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "腊"]
    if day == 10:
        d = "初十"
    elif day < 10:
        d = "初" + "一二三四五六七八九"[day - 1]
    elif day < 20:
        d = "十" + "一二三四五六七八九"[day - 11]
    elif day == 20:
        d = "二十"
    elif day < 30:
        d = "廿" + "一二三四五六七八九"[day - 21]
    else:
        d = "三十"
    return f"{months[month - 1]}月{d}"


def get_jieling(date_str: str) -> list[dict]:
    """返回当天全部节令，每项：name / category / ethnic / date / season / lunar。

    season 仅节气有；lunar 为农历日期标签（如"八月十五"），公历定日与按年硬编码的节日为空。
    """
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return []

    found: list[dict] = []

    def add(name: str, category: str, ethnic: str, lunar: str = "", season: str = ""):
        found.append({"name": name, "category": category, "ethnic": ethnic,
                      "date": date_str, "season": season, "lunar": lunar})

    jq = _jieqi_name(dt)
    if jq:
        add(jq, JIEQI, "", season=_SEASON_MAP.get(jq, ""))
    if _jieqi_name(dt + timedelta(days=1)) == "清明":
        add("寒食", HAN, "")

    lunar = _lunar(dt)
    if lunar:
        month, day, leap = lunar
        label = _lunar_label(month, day)
        if not leap:
            for name, category, ethnic in _LUNAR_FIXED.get((month, day), []):
                add(name, category, ethnic, lunar=label)
        nxt = _lunar(dt + timedelta(days=1))
        if nxt and nxt[0] == 1 and nxt[1] == 1 and not nxt[2]:
            add("除夕", HAN, "", lunar=label)

    for name, category, ethnic in _SOLAR_FIXED.get((dt.month, dt.day), []):
        add(name, category, ethnic)
    for name, category, ethnic in _BY_YEAR.get(date_str, []):
        add(name, category, ethnic)

    return found

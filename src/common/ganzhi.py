"""干支纪年与生肖

年份按天文纪年计算：公元 y 年即 y；公元前 n 年记为 1-n（公元前 1 年 = 0）。
公元 4 年为甲子，故 (y-4) 对 10、12 取模。
"""

STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
ZODIAC = "鼠牛虎兔龙蛇马羊猴鸡狗猪"


def ganzhi_year(year: int) -> tuple[str, str]:
    """返回 (干支, 生肖)。year 为天文纪年（公元前 n 年传 1-n）。"""
    idx = year - 4
    return STEMS[idx % 10] + BRANCHES[idx % 12], ZODIAC[idx % 12]


def ce_label(year: int) -> str:
    """天文纪年 → "公元 727 年" / "公元前 221 年"。"""
    return f"公元 {year} 年" if year > 0 else f"公元前 {1 - year} 年"


def ganzhi_label(year: int) -> str:
    """"丁卯年（兔）"。"""
    gz, zo = ganzhi_year(year)
    return f"{gz}年（{zo}）"

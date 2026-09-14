"""Tests for the 节令 calendar."""

from src.jieling.calendar import get_jieling, JIEQI, HAN, ETHNIC


def _names(date):
    return [(j["name"], j["category"], j["ethnic"]) for j in get_jieling(date)]


def test_jieqi_with_season():
    js = get_jieling("2026-09-23")
    assert [(j["name"], j["category"]) for j in js] == [("秋分", JIEQI)]
    assert js[0]["season"] == "秋" and js[0]["lunar"] == ""


def test_lunar_han_festival():
    js = get_jieling("2026-09-25")           # 农历八月十五
    assert _names("2026-09-25") == [("中秋", HAN, "")]
    assert js[0]["lunar"] == "八月十五"


def test_spring_festival_and_eve():
    assert ("春节", HAN, "") in _names("2026-02-17")
    assert ("除夕", HAN, "") in _names("2026-02-16")   # 2026 腊月无三十，廿九即除夕
    assert get_jieling("2026-02-16")[0]["lunar"] == "腊月廿九"


def test_hanshi_is_day_before_qingming():
    assert ("寒食", HAN, "") in _names("2026-04-04")
    assert ("清明", JIEQI, "") in _names("2026-04-05")
    assert ("寒食", HAN, "") not in _names("2026-04-05")


def test_same_day_multiple():
    names = _names("2026-04-19")               # 农历三月初三
    assert ("上巳", HAN, "") in names and ("三月三", ETHNIC, "壮族") in names


def test_ethnic_lunar_fixed():
    # 2026 农历六月廿四 → 火把节
    from zhdate import ZhDate
    d = ZhDate(2026, 6, 24).to_datetime().strftime("%Y-%m-%d")
    assert ("火把节", ETHNIC, "彝族") in _names(d)


def test_solar_fixed_and_by_year():
    assert ("泼水节", ETHNIC, "傣族") in _names("2026-04-13")
    assert ("藏历新年", ETHNIC, "藏族") in _names("2026-02-18")
    assert ("开斋节", ETHNIC, "回族") in _names("2026-03-20")


def test_ordinary_day_empty():
    assert get_jieling("2026-09-14") == []


def test_bad_date():
    assert get_jieling("nope") == []

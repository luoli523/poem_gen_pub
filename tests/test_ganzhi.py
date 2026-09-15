from src.common.ganzhi import ganzhi_year, ce_label, ganzhi_label


def test_known_years():
    assert ganzhi_year(727) == ("丁卯", "兔")      # 唐开元十五年
    assert ganzhi_year(2026) == ("丙午", "马")
    assert ganzhi_year(1084) == ("甲子", "鼠")     # 宋元丰七年
    assert ganzhi_year(4) == ("甲子", "鼠")


def test_bc_astronomical():
    # 公元前 1 年 = 天文年 0 = 庚申；秦始皇二十六年 公元前 221 年 = 天文年 -220 = 庚辰
    assert ganzhi_year(0) == ("庚申", "猴")
    assert ganzhi_year(-220) == ("庚辰", "龙")


def test_labels():
    assert ce_label(727) == "公元 727 年"
    assert ce_label(-220) == "公元前 221 年"
    assert ganzhi_label(727) == "丁卯年（兔）"

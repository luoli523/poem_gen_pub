"""共享常量"""

# sxtwl 节气名称顺序（索引 0~23）
JIEQI_NAMES = [
    "冬至", "小寒", "大寒", "立春", "雨水", "惊蛰",
    "春分", "清明", "谷雨", "立夏", "小满", "芒种",
    "夏至", "小暑", "大暑", "立秋", "处暑", "白露",
    "秋分", "寒露", "霜降", "立冬", "小雪", "大雪",
]


# 流水线跑在 GitHub runner（UTC）上，cron 定在 UTC 23:00 = 北京 7:00；
# 所有"今天"必须按北京时间算，否则准点触发时日期会差一天（节气尤其危险）
from datetime import datetime
from zoneinfo import ZoneInfo

BEIJING = ZoneInfo("Asia/Shanghai")


def beijing_now() -> datetime:
    return datetime.now(BEIJING)


def beijing_today() -> str:
    return beijing_now().strftime("%Y-%m-%d")

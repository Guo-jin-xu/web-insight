from datetime import datetime

from langchain_core.tools import tool


@tool
def get_current_time() -> str:
    """获取当前的精确日期和时间。

    返回当前日期（年月日）、星期几和精确时间（时分秒）。
    用于需要知道当前时间的场景，如判断时效性、计算时间差等。
    """
    now = datetime.now()
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    return now.strftime(f"%Y年%m月%d日 {weekdays[now.weekday()]} %H:%M:%S")
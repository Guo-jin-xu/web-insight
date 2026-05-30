"""任务路由器 — 区分"网页操作任务"和"日常对话"。

用于 main.py 交互循环中决定走 Agent 流程还是直接 LLM 回复。
"""

from __future__ import annotations

import re
from enum import Enum


class QueryType(str, Enum):
    WEB_TASK = "web_task"
    CONVERSATION = "conversation"


_WEB_SEARCH_KEYWORDS = (
    "搜索", "搜一下", "查找", "查一下", "帮我查", "帮我搜",
    "百度", "bing", "google", "谷歌",
)

_WEB_NAVIGATE_KEYWORDS = (
    "打开", "访问", "导航", "浏览", "去", "前往",
)

_WEB_FORM_KEYWORDS = (
    "填写", "表单", "提交", "注册", "登录",
)

_WEB_ACTION_KEYWORDS = (
    "点击", "输入", "滚动", "提取", "截图", "截屏",
    "翻页", "下一页", "上一页",
)

_URL_PATTERN = re.compile(r"https?://[^\s]+")


def classify_query(query: str) -> QueryType:
    """判断用户输入是需要网页操作还是日常对话。

    Args:
        query: 用户输入字符串（已 strip）

    Returns:
        QueryType.WEB_TASK 或 QueryType.CONVERSATION
    """
    if not query or not query.strip():
        return QueryType.CONVERSATION

    query_lower = query.strip().lower()

    if _URL_PATTERN.search(query):
        return QueryType.WEB_TASK

    for kw in _WEB_SEARCH_KEYWORDS:
        if kw in query_lower:
            return QueryType.WEB_TASK

    for kw in _WEB_NAVIGATE_KEYWORDS:
        if kw in query_lower:
            return QueryType.WEB_TASK

    for kw in _WEB_FORM_KEYWORDS:
        if kw in query_lower:
            return QueryType.WEB_TASK

    for kw in _WEB_ACTION_KEYWORDS:
        if kw in query_lower:
            return QueryType.WEB_TASK

    return QueryType.CONVERSATION
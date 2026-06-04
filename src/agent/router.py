"""任务路由器 — 原生实现：LLM 分类 → 日常对话 / 网页操作。

替代 LangGraph，使用原生 async 函数实现路由逻辑。
LLM 判断查询类型后，路由到 conversation（直接回复）或 web_task（浏览器 Agent）。
"""

from __future__ import annotations

from src.agent.factory import create_browser_agent
from src.agent.prompts import CONVERSATION_SYSTEM_PROMPT, ROUTER_CLASSIFICATION_PROMPT, get_current_time_str
from src.browser.manager import BrowserManager
from src.exceptions import LLMError, RateLimitError, is_rate_limit_error
from src.llm.client import LLMClient


def _parse_classification(raw: str) -> str:
    """从 LLM 回复中提取分类结果，默认 conversation。"""
    text = raw.strip().lower()
    if "web_task" in text:
        return "web_task"
    return "conversation"


async def classify_query(client: LLMClient, query: str) -> str:
    """使用 LLM 分类查询类型。"""
    try:
        response = await client.chat(
            messages=[
                {"role": "system", "content": ROUTER_CLASSIFICATION_PROMPT},
                {"role": "user", "content": query},
            ],
            temperature=0.0,
        )
        return _parse_classification(response.content)
    except Exception as exc:
        if is_rate_limit_error(exc):
            raise RateLimitError() from exc
        return "conversation"


async def handle_conversation(client: LLMClient, query: str) -> str:
    """处理日常对话。"""
    try:
        system_msg = CONVERSATION_SYSTEM_PROMPT.format(current_time=get_current_time_str())
        response = await client.chat(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": query},
            ],
        )
        return response.content
    except Exception as exc:
        if is_rate_limit_error(exc):
            raise RateLimitError() from exc
        raise LLMError(str(exc)) from exc


async def handle_web_task(browser: BrowserManager, query: str) -> str:
    """处理网页操作任务。"""
    try:
        agent = create_browser_agent(browser)
        agent.task = query
        result = await agent.run()
        return result or ""
    except Exception as exc:
        if is_rate_limit_error(exc):
            raise RateLimitError() from exc
        raise LLMError(str(exc)) from exc


async def route_query(browser: BrowserManager, query: str) -> str:
    """路由查询：分类 → 对话/网页操作。"""
    client = LLMClient()
    query_type = await classify_query(client, query)

    if query_type == "web_task":
        return await handle_web_task(browser, query)
    else:
        return await handle_conversation(client, query)

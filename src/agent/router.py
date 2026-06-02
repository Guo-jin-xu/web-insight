"""任务路由器 — LangGraph 图：LLM 分类 → 日常对话 / 网页操作。

替代原先的关键词匹配，由 LLM 自主判断查询类型，
再路由到 conversation 节点（直接 LLM 回复）或 web_task 节点（浏览器 Agent）。
"""

from __future__ import annotations

from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.errors import NodeInterrupt
from langgraph.graph import END, START, StateGraph

from src.agent.loop import run_task
from src.agent.prompts import CONVERSATION_SYSTEM_PROMPT, ROUTER_CLASSIFICATION_PROMPT, get_current_time_str
from src.browser.manager import BrowserManager
from src.exceptions import LLMError, RateLimitError, is_rate_limit_error
from src.llm.factory import get_llm


class RouterState(TypedDict):
    query: str
    query_type: str
    response: str


def _parse_classification(raw: str) -> str:
    """从 LLM 回复中提取分类结果，默认 conversation。"""
    text = raw.strip().lower()
    if "web_task" in text:
        return "web_task"
    return "conversation"


def create_router_graph(browser: BrowserManager):
    """创建路由图：classify → conversation / web_task。

    Args:
        browser: 已连接的 BrowserManager，供 web_task 节点使用。

    Returns:
        Compiled LangGraph graph。
    """

    async def classify(state: RouterState) -> dict:
        llm = get_llm()
        try:
            result = await llm.ainvoke([
                SystemMessage(content=ROUTER_CLASSIFICATION_PROMPT),
                HumanMessage(content=state["query"]),
            ])
            query_type = _parse_classification(result.content)
        except Exception as exc:
            if is_rate_limit_error(exc):
                raise RateLimitError() from exc
            query_type = "conversation"
        return {"query_type": query_type}

    async def conversation(state: RouterState) -> dict:
        llm = get_llm()
        try:
            system_msg = CONVERSATION_SYSTEM_PROMPT.format(current_time=get_current_time_str())
            result = await llm.ainvoke([
                SystemMessage(content=system_msg),
                HumanMessage(content=state["query"]),
            ])
            return {"response": result.content if hasattr(result, "content") else str(result)}
        except Exception as exc:
            if is_rate_limit_error(exc):
                raise RateLimitError() from exc
            raise LLMError(str(exc)) from exc

    async def web_task(state: RouterState) -> dict:
        try:
            final = await run_task(browser, state["query"])
            return {"response": final or ""}
        except NodeInterrupt:
            from pathlib import Path
            result_file = Path("data") / "task_result.md"
            final = result_file.read_text(encoding="utf-8") if result_file.exists() else ""
            return {"response": final}
        except Exception as exc:
            if is_rate_limit_error(exc):
                raise RateLimitError() from exc
            raise LLMError(str(exc)) from exc

    def route_decision(state: RouterState) -> str:
        return state["query_type"]

    graph = StateGraph(RouterState)
    graph.add_node("classify", classify)
    graph.add_node("conversation", conversation)
    graph.add_node("web_task", web_task)

    graph.add_edge(START, "classify")
    graph.add_conditional_edges("classify", route_decision, {
        "conversation": "conversation",
        "web_task": "web_task",
    })
    graph.add_edge("conversation", END)
    graph.add_edge("web_task", END)

    return graph.compile()

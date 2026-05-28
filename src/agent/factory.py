"""Agent 工厂 — 组合 langgraph 组件创建浏览器操作 Agent。"""

from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from src.browser.manager import BrowserManager
from src.config.settings import settings
from src.llm.factory import get_llm
from src.memory.history import memory_manager
from src.tools import create_all_tools

SYSTEM_PROMPT = """你是浏览器自动化助手，操作 Chrome 完成网页任务。

## 重要规则
调用 done 工具结束每个任务 — 只有 done 才能终止。不调用 done 会导致任务永远循环。

## 完成任务的标准流程
1. search(query) 或 navigate(url) 打开目标页面
2. extract_article_content() 提取内容
3. done(summary) — 总结内容并立即结束

## 其他工具（辅助）
get_page_links, get_dom_snapshot, click_element, type_text, press_key, wait, scroll, extract_content, write_file, read_file, visual_analyze

## 禁止
- 重新搜索已经搜索过的内容
- 内容已提取后继续操作

## 站点经验
{site_experience}
"""


def create_browser_agent(browser: BrowserManager, task_domain: str = "", verbose: bool = False):
    """创建浏览器操作 Agent。

    使用 langgraph create_react_agent，自动处理 tool-calling 循环。

    Args:
        browser: 已连接的 BrowserManager
        task_domain: 任务目标域名，用于检索站点经验

    Returns:
        Runnable agent (langgraph CompiledStateGraph)
    """
    llm = get_llm()
    tools = create_all_tools(browser)

    # 检索站点经验
    site_experience = ""
    if task_domain:
        site_experience = memory_manager.search_experience(task_domain)
    if not site_experience:
        site_experience = "（无历史经验，首次访问此站点）"

    system_msg = SYSTEM_PROMPT.format(site_experience=site_experience)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_msg),
            MessagesPlaceholder(variable_name="messages", optional=True),
        ]
    )

    return create_react_agent(
        model=llm.bind_tools(tools),
        tools=tools,
        prompt=prompt,
        debug=verbose,
        version="v2",
    )


def create_custom_agent(
    browser: BrowserManager,
    task: str,
    task_domain: str = "",
    **kwargs,
):
    """创建自定义 Agent 实例（Phase 2 新增，替代 LangGraph create_react_agent）。

    使用手写的 step/run 循环，支持 judge、loop detection 等中间件。
    与 create_browser_agent 并存，不破坏现有 LangGraph 流程。

    Args:
        browser: 已连接的 BrowserManager
        task: 任务描述
        task_domain: 任务目标域名，用于检索站点经验

    Returns:
        Agent 实例
    """
    from src.agent.service import Agent

    llm = get_llm()
    tools = create_all_tools(browser)

    site_experience = ""
    if task_domain:
        site_experience = memory_manager.search_experience(task_domain)

    return Agent(
        task=task,
        llm=llm,
        browser_session=browser,
        tools=tools,
        site_experience=site_experience,
        **kwargs,
    )

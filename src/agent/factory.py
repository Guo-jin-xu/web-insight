"""Agent 工厂 — 组合 langgraph 组件创建浏览器操作 Agent。"""

from src.agent.prompts import BROWSER_AGENT_SYSTEM_PROMPT, get_current_time_str
from src.browser.manager import BrowserManager
from src.config.settings import settings
from src.llm.factory import get_llm
from src.memory.history import memory_manager
from src.tools import create_all_tools


def create_browser_agent(browser: BrowserManager, task_domain: str = "", verbose: bool = False):
    """创建浏览器操作 Agent。

    使用 langgraph create_react_agent，自动处理 tool-calling 循环。

    Args:
        browser: 已连接的 BrowserManager
        task_domain: 任务目标域名，用于检索站点经验
        verbose: 是否开启调试模式

    Returns:
        Runnable agent (langgraph CompiledStateGraph)
    """
    from langgraph.prebuilt import create_react_agent
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    llm = get_llm()
    tools = create_all_tools(browser)

    site_experience = ""
    if task_domain:
        site_experience = memory_manager.search_experience(task_domain)
    if not site_experience:
        site_experience = "（无历史经验，首次访问此站点）"

    system_msg = BROWSER_AGENT_SYSTEM_PROMPT.format(
        current_time=get_current_time_str(),
        site_experience=site_experience,
    )

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

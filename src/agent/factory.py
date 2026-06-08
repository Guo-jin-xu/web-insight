"""Agent 工厂 — 使用原生 Agent Loop。"""

from src.agent.loop import AgentLoop
from src.agent.prompts import BROWSER_AGENT_SYSTEM_PROMPT, get_current_time_str
from src.browser.manager import BrowserManager
from src.llm.client import LLMClient
from src.memory.history import memory_manager
from src.tools.browser_actions import create_browser_registry


def create_browser_agent(
    browser: BrowserManager,
    task_domain: str = "",
    verbose: bool = False,
) -> AgentLoop:
    """创建浏览器操作 Agent（使用原生 Loop）。

    Args:
        browser: 已连接的 BrowserManager
        task_domain: 任务目标域名，用于检索站点经验
        verbose: 是否开启调试模式

    Returns:
        AgentLoop 实例
    """
    client = LLMClient()
    registry = create_browser_registry(browser)

    site_experience = ""
    if task_domain:
        site_experience = memory_manager.search_experience(task_domain)
    if not site_experience:
        site_experience = "（无历史经验，首次访问此站点）"

    system_prompt = BROWSER_AGENT_SYSTEM_PROMPT.format(
        current_time=get_current_time_str(),
        site_experience=site_experience,
    )

    return AgentLoop(
        task="",
        llm_client=client,
        registry=registry,
        system_prompt=system_prompt,
        get_current_url=lambda: browser.page.url if browser._page else "",
        browser=browser,
    )

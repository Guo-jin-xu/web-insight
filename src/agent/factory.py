"""Agent 工厂 — 使用原生 Agent Loop。"""

from src.agent.loop import AgentLoop
from src.agent.prompts import BROWSER_AGENT_SYSTEM_PROMPT, get_current_time_str
from src.browser.manager import BrowserManager
from src.config.settings import settings
from src.llm.client import LLMClient
from src.tools.browser_actions import create_browser_registry


def create_browser_agent(
    browser: BrowserManager,
    verbose: bool = False,
) -> AgentLoop:
    """创建浏览器操作 Agent（使用原生 Loop）。

    Args:
        browser: 已连接的 BrowserManager
        verbose: 是否开启调试模式

    Returns:
        AgentLoop 实例
    """
    client = LLMClient()
    registry = create_browser_registry(browser)

    system_prompt = BROWSER_AGENT_SYSTEM_PROMPT.format(
        current_time=get_current_time_str(),
    )

    return AgentLoop(
        task="",
        llm_client=client,
        registry=registry,
        max_steps=settings.agent_recursion_limit,
        system_prompt=system_prompt,
        get_current_url=lambda: browser.page.url if browser._page else "",
        browser=browser,
    )

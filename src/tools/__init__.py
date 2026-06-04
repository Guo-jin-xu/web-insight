"""工具层 — 统一入口。"""

from src.browser.manager import BrowserManager
from src.tools.browser_actions import create_browser_registry
from src.tools.registry import Registry


def create_all_tools(browser: BrowserManager) -> Registry:
    """创建 Agent 可用的全部工具注册中心。

    9个核心工具：navigate, click_element, input_text, scroll,
    go_back, send_keys, extract_content, get_dom_snapshot, done
    """
    return create_browser_registry(browser)

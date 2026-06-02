"""工具层 — 统一入口。"""

from src.browser.manager import BrowserManager
from src.tools.browser_tools import create_browser_tools
from src.tools.dom_tools import create_dom_tools
from src.tools.vision_tool import create_vision_tool
from src.tools.file_tools import create_file_tools
from src.tools.time_tool import get_current_time


def create_all_tools(browser: BrowserManager) -> list:
    """创建 Agent 可用的全部工具。

    按优先级排列: DOM 工具在前（首选），浏览器操作次之，VLM 兜底。
    done 工具位于最后，作为唯一终止方式。
    write_file/read_file 不包含在默认工具中，
    因为会导致 LLM 用 write_file 代替 done 来终止任务。
    """
    tools: list = []
    tools.extend(create_dom_tools(browser))
    tools.extend(create_browser_tools(browser))
    tools.extend(create_vision_tool(browser))
    tools.append(get_current_time)
    return tools


def create_all_tools_with_files(browser: BrowserManager) -> list:
    """包含文件工具的完整工具集。"""
    tools = create_all_tools(browser)
    tools.extend(create_file_tools())
    return tools

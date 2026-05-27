"""VLM 视觉分析工具 — 按需调用。

仅在 DOM 工具连续失败时使用（正常流程中 Agent 优先使用 DOM 工具）。
"""

from langchain_core.tools import tool

from src.browser.manager import BrowserManager
from src.perception.vision import analyze_screenshot


def create_vision_tool(browser: BrowserManager) -> list:
    """创建 VLM 视觉分析工具。"""

    @tool
    async def visual_analyze() -> str:
        """使用视觉大模型（VLM）分析当前页面截图，返回页面理解和交互元素坐标。

        **何时使用**: 仅在 DOM 工具（get_dom_snapshot / extract_content / get_page_links）
        连续多次返回空结果或无法定位目标元素时使用。

        分析结果包括:
        1. 页面整体描述（类型、内容、功能）
        2. 关键交互元素（按钮、输入框、链接等）及像素坐标
        3. 操作建议
        """
        try:
            b64 = await browser.screenshot_to_b64()
            analysis = await analyze_screenshot(b64)
            return analysis.format_for_agent()
        except Exception as e:
            return f"VLM 分析失败: {e}"

    return [visual_analyze]

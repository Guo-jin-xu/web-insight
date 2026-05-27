"""浏览器操作工具 — navigate / click / type / scroll / go_back / press_key / screenshot.

参考 Playwright MCP 的接口命名和参数设计。
"""

from pathlib import Path
from typing import Annotated

from langchain_core.tools import tool
from langgraph.errors import NodeInterrupt
from playwright.async_api import Page

from src.browser.manager import BrowserManager


def create_browser_tools(browser: BrowserManager) -> list:
    """创建所有浏览器操作工具。"""

    @tool
    async def navigate(url: Annotated[str, "完整 URL，含 https://"]) -> str:
        """导航到指定 URL。打开新网页或跳转到搜索结果页时使用。"""
        try:
            await browser.page.goto(url, wait_until="domcontentloaded", timeout=15000)
            title = await browser.page.title()
            return f"已导航到: {url}\n页面标题: {title}"
        except Exception as e:
            return f"导航失败: {e}"

    @tool
    async def search(
        query: Annotated[str, "搜索关键词"],
        engine: Annotated[str, "搜索引擎: bing 或 google"] = "bing",
    ) -> str:
        """直接搜索。自动构建搜索 URL 并导航到搜索结果页。比手动 navigate → type → press_key 更可靠。"""
        import urllib.parse
        q = urllib.parse.quote_plus(query)
        urls = {
            "bing": f"https://www.bing.com/search?q={q}",
            "google": f"https://www.google.com/search?q={q}",
        }
        url = urls.get(engine.lower(), urls["bing"])
        try:
            await browser.page.goto(url, wait_until="domcontentloaded", timeout=15000)
            title = await browser.page.title()
            return f"已搜索 {engine}: {query}\n页面标题: {title}\nURL: {url}\n请用 get_page_links 查看搜索结果。"
        except Exception as e:
            return f"搜索失败: {e}"

    @tool
    async def click_element(index: Annotated[int, "可交互元素的索引号，来自 get_dom_snapshot 的结果"]) -> str:
        """点击指定索引的可交互元素（按钮、链接等）。index 必须来自 get_dom_snapshot 返回的元素列表。"""
        result = await browser.click_by_index(index)
        if result["success"]:
            el = result.get("element", {})
            return f"已点击 [{index}] <{el.get('tag', '?')}> {el.get('text', '')}"
        return f"点击失败: {result.get('error', 'unknown')}"

    @tool
    async def type_text(
        index: Annotated[int, "输入框元素索引号"],
        text: Annotated[str, "要输入的文本"],
        clear: Annotated[bool, "是否先清空已有内容"] = True,
    ) -> str:
        """向输入框键入文本。先点击输入框（通过 index），再输入内容。"""
        result = await browser.type_by_index(index, text, clear)
        if result["success"]:
            return f"已输入 '{text}' 到元素 [{index}]"
        return f"输入失败: {result.get('error', 'unknown')}"

    @tool
    async def scroll(
        down: Annotated[bool, "True=向下滚动，False=向上滚动"] = True,
        pages: Annotated[float, "滚动页数，1.0=一屏"] = 1.0,
    ) -> str:
        """滚动页面。向下滚动查看更多内容，向上滚动回到页面顶部。"""
        await browser.scroll(down=down, pages=pages)
        direction = "向下" if down else "向上"
        return f"已{direction}滚动 {pages} 页"

    @tool
    async def go_back() -> str:
        """浏览器后退到上一页。导航到错误页面时使用。"""
        try:
            await browser.go_back()
            return f"已后退，当前: {browser.page.url}"
        except Exception as e:
            return f"后退失败: {e}"

    @tool
    async def press_key(key: Annotated[str, "按键名，如 Enter / Escape / Tab / ArrowDown"]) -> str:
        """按下键盘按键。常用: Enter 提交搜索/表单，Escape 关闭弹窗。"""
        await browser.press_key(key)
        return f"已按下 {key}"

    @tool
    async def take_screenshot() -> str:
        """截取当前页面视口截图，返回 base64 编码图片。可用于 visual_analyze 分析。"""
        b64 = await browser.screenshot_to_b64()
        return f"截图完成 ({len(b64)} chars base64)"

    @tool
    async def wait(seconds: Annotated[float, "等待秒数"] = 2.0) -> str:
        """等待指定秒数。用于页面加载、搜索结果显示等需要时间的场景。"""
        import asyncio
        await asyncio.sleep(min(seconds, 10.0))
        return f"已等待 {seconds} 秒"

    @tool
    async def done(
        summary: Annotated[str, "任务的最终结果总结"],
    ) -> str:
        """标记任务完成并返回最终结果。调用后终止执行。

        所有提取、总结工作必须在调用 done 之前完成。
        """
        p = Path("data") / "task_result.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(summary, encoding="utf-8")
        raise NodeInterrupt(f"任务完成，结果已保存")

    return [navigate, search, click_element, type_text, scroll, go_back, press_key, take_screenshot, wait, done]

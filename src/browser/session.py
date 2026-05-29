"""浏览器 Session 管理 — Tab 切换、弹窗处理、下载监控。

Phase 3.3: 教学简化版 BrowserSession。
"""

import logging
from pathlib import Path

logger = logging.getLogger("web_insight.session")


class BrowserSession:
    """浏览器 Session 管理。"""

    def __init__(self, browser_manager):
        self.bm = browser_manager
        self.current_page = getattr(browser_manager, "_page", None)

    async def get_tabs(self) -> list[dict]:
        pages = self.bm.context.pages
        tabs = []
        for i, p in enumerate(pages):
            try:
                title = await p.title()
            except Exception:
                title = "unknown"
            tabs.append({
                "id": str(i),
                "url": p.url,
                "title": title,
            })
        return tabs

    async def switch_tab(self, index: int):
        pages = self.bm.context.pages
        if index < 0 or index >= len(pages):
            raise ValueError(f"Tab index {index} out of range (0-{len(pages) - 1})")
        page = pages[index]
        await page.bring_to_front()
        self.bm._page = page
        self.current_page = page
        self._setup_dialog_handler()
        return page

    async def new_tab(self, url: str = "about:blank"):
        page = await self.bm.context.new_page()
        if url != "about:blank":
            await page.goto(url)
        self.bm._page = page
        self.current_page = page
        self._setup_dialog_handler()
        return page

    async def _handle_dialog(self, dialog) -> None:
        logger.info(f"自动处理弹窗: {dialog.type} - {dialog.message}")
        await dialog.accept()

    def _setup_dialog_handler(self) -> None:
        if self.current_page is None:
            return
        self.current_page.on("dialog", self._handle_dialog)
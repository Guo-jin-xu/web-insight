"""浏览器管理层 — Playwright CDP 连接 + 页面操作.

合并原有 utils/browser_launcher.py 和 tools/browser.py，
提供统一的 BrowserManager。
"""

import base64
import os
import subprocess
import time
import urllib.request
from typing import Any

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from src.config.settings import settings


def ensure_chrome_running() -> bool:
    """确保 Chrome 以 CDP 模式运行。

    默认端口 9222，如果未运行则尝试启动。
    """
    port = 9222
    try:
        urllib.request.urlopen(f"http://localhost:{port}/json/version", timeout=2)
        return True
    except Exception:
        pass

    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    chrome_path = None
    for p in chrome_paths:
        if os.path.exists(p):
            chrome_path = p
            break

    if chrome_path is None:
        return False

    user_data_dir = r"C:\chrome-debug-profile"
    try:
        subprocess.Popen(
            [chrome_path, f"--remote-debugging-port={port}", f"--user-data-dir={user_data_dir}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(3.0)
        return True
    except Exception:
        return False


class BrowserManager:
    """Playwright CDP 浏览器管理器。

    连接已运行的 Chrome 实例，提供 page 对象和常用操作。
    """

    def __init__(self, cdp_endpoint: str = "http://localhost:9222"):
        self.cdp_endpoint = cdp_endpoint
        self._playwright: Any = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("Browser not connected. Call connect() first.")
        return self._page

    @property
    def context(self) -> BrowserContext:
        if self._context is None:
            raise RuntimeError("Browser not connected. Call connect() first.")
        return self._context

    async def connect(self) -> Page:
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.connect_over_cdp(self.cdp_endpoint)

        contexts = self._browser.contexts
        if contexts:
            self._context = contexts[0]
        else:
            self._context = await self._browser.new_context(
                viewport={"width": 1280, "height": 720}
            )

        pages = self._context.pages
        if pages:
            self._page = pages[0]
        else:
            self._page = await self._context.new_page()

        return self._page

    async def disconnect(self) -> None:
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        self._context = None
        self._page = None

    async def get_page_html(self) -> str:
        return await self.page.content()

    async def screenshot_bytes(self) -> bytes:
        return await self.page.screenshot(type="png", full_page=False)

    async def screenshot_to_b64(self) -> str:
        raw = await self.screenshot_bytes()
        return base64.b64encode(raw).decode("utf-8")

    async def get_indexed_elements(self) -> list[dict]:
        """用 JS 提取页面可交互元素列表。

        返回 [{index, tag, text, bbox, attributes}]，
        类似 browser-use 的 selector_map 文本表示。
        """
        js = """
        (() => {
            const interactive = 'a,button,input,select,textarea,[role="button"],[role="link"],[role="textbox"],'
                + '[role="combobox"],[role="listbox"],[role="checkbox"],[role="radio"],[contenteditable="true"],'
                + '[onclick],[tabindex]:not([tabindex="-1"])';
            const all = document.querySelectorAll(interactive);
            const results = [];
            all.forEach((el, i) => {
                if (i >= 20) return;
                const rect = el.getBoundingClientRect();
                if (rect.width === 0 && rect.height === 0) return;
                let text = (el.textContent || '').trim().slice(0, 80);
                let tag = el.tagName.toLowerCase();
                let attrs = {};
                for (const attr of ['id', 'name', 'type', 'placeholder', 'aria-label', 'href', 'role', 'class']) {
                    const v = el.getAttribute(attr);
                    if (v) attrs[attr] = v.slice(0, 100);
                }
                results.push({
                    index: i,
                    tag: tag,
                    text: text,
                    visible: rect.width > 0,
                    bbox: {x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height)},
                    attributes: attrs
                });
            });
            return results;
        })()
        """
        return await self.page.evaluate(js)

    async def click_by_index(self, index: int) -> dict:
        """按可交互元素索引点击。"""
        elements = await self.get_indexed_elements()
        target = next((e for e in elements if e["index"] == index), None)
        if target is None:
            return {"success": False, "error": f"Element {index} not found"}
        bbox = target["bbox"]
        x = bbox["x"] + bbox["w"] / 2
        y = bbox["y"] + bbox["h"] / 2
        await self.page.mouse.click(x, y)
        return {"success": True, "element": target}

    async def type_by_index(self, index: int, text: str, clear: bool = True) -> dict:
        """按可交互元素索引输入文本。"""
        result = await self.click_by_index(index)
        if not result["success"]:
            return result
        if clear:
            await self.page.keyboard.press("Control+a")
        await self.page.keyboard.type(text)
        return {"success": True, "text": text}

    async def scroll(self, down: bool = True, pages: float = 1.0) -> dict:
        """滚动页面。"""
        direction = 1 if down else -1
        px = int(pages * 700)
        await self.page.evaluate(f"window.scrollBy(0, {direction * px})")
        return {"success": True}

    async def go_back(self) -> dict:
        await self.page.go_back()
        return {"success": True, "url": self.page.url}

    async def press_key(self, key: str) -> dict:
        await self.page.keyboard.press(key)
        return {"success": True, "key": key}

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()

"""浏览器管理层 — Playwright CDP 连接 + 页面操作.

合并原有 utils/browser_launcher.py 和 tools/browser.py，
提供统一的 BrowserManager。
"""

import asyncio
import base64
import logging
import os
import subprocess
import time
import urllib.request
from typing import Any

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from src.browser.stealth import inject_permission_handling, inject_stealth
from src.browser.watchdogs import PopupHandler
from src.config.settings import settings

logger = logging.getLogger(__name__)


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
        # 新页面检测
        self._new_page: Page | None = None
        self._new_page_event: asyncio.Event | None = None
        # 弹窗处理
        self._popup_handler: PopupHandler | None = None

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

    @property
    def popup_handler(self) -> PopupHandler | None:
        return self._popup_handler

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

        # 注册弹窗自动处理
        self._popup_handler = PopupHandler(self._page)
        await self._popup_handler.register()

        # Task 8: 注入防检测脚本
        await inject_permission_handling(self._context)
        await inject_stealth(self._page)

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

    # ── 标签页管理（Task 7）───────────────────────────────

    async def new_tab(self, url: str = "about:blank") -> dict:
        """打开新标签页。"""
        new_page = await self.context.new_page()
        if url and url != "about:blank":
            await new_page.goto(url, wait_until="domcontentloaded", timeout=15000)
        return {"success": True, "url": new_page.url}

    async def close_tab(self, index: int = -1) -> dict:
        """关闭指定标签页（-1 = 当前页）。"""
        pages = self.context.pages
        if len(pages) <= 1:
            return {"success": False, "error": "Cannot close the last tab"}
        if index == -1:
            target = self._page
        elif 0 <= index < len(pages):
            target = pages[index]
        else:
            return {"success": False, "error": f"Tab {index} not found"}
        await target.close()
        self._page = self.context.pages[0]
        return {"success": True, "current_url": self._page.url}

    async def list_tabs(self) -> list[dict]:
        """列出所有标签页。"""
        tabs = []
        for i, page in enumerate(self.context.pages):
            try:
                title = await page.title()
            except Exception:
                title = "(unknown)"
            tabs.append({
                "index": i,
                "url": page.url,
                "title": title,
                "is_current": page == self._page,
            })
        return tabs

    async def select_dropdown(self, index: int, value: str) -> dict:
        """选择下拉菜单选项。"""
        elements = await self.get_indexed_elements()
        target = next((e for e in elements if e["index"] == index), None)
        if target is None:
            return {"success": False, "error": f"Element {index} not found"}
        try:
            el_handle = await self.page.query_selector(f'[data-index="{index}"]')
            if el_handle is None:
                # fallback: 通过标签名定位
                el_handle = await self.page.query_selector("select")
            if el_handle:
                await el_handle.select_option(label=value)
                return {"success": True, "selected": value}
        except Exception as e:
            return {"success": False, "error": str(e)}
        return {"success": False, "error": "Could not select option"}

    async def upload_file(self, index: int, file_path: str) -> dict:
        """上传文件到 input[type=file]。"""
        elements = await self.get_indexed_elements()
        target = next((e for e in elements if e["index"] == index), None)
        if target is None:
            return {"success": False, "error": f"Element {index} not found"}
        try:
            # 先尝试通过 data-index 定位
            handle = await self.page.query_selector(f'[data-index="{index}"]')
            if handle is None:
                handle = await self.page.query_selector("input[type='file']")
            if handle:
                await handle.set_input_files(file_path)
                return {"success": True, "file": file_path}
        except Exception as e:
            return {"success": False, "error": str(e)}
        return {"success": False, "error": "Could not upload file"}

    async def get_page_html(self) -> str:
        return await self.page.content()

    async def screenshot_bytes(self) -> bytes:
        return await self.page.screenshot(type="png", full_page=False)

    async def screenshot_to_b64(self) -> str:
        raw = await self.screenshot_bytes()
        return base64.b64encode(raw).decode("utf-8")

    async def get_indexed_elements(self, max_elements: int = 200) -> list[dict]:
        """用 JS 提取页面可交互元素列表（与 DomService 使用相同 JS 脚本保证索引一致）。

        返回 [{index, tag, text, bbox, attributes, is_in_viewport}]，
        类似 browser-use 的 selector_map 文本表示。
        """
        # 与 DomService.INTERACTIVE_ELEMENTS_JS 保持一致
        js = """
        (() => {
            const INTERACTIVE_SELECTOR = [
                'a[href]', 'button', 'input:not([type="hidden"])', 'select', 'textarea',
                '[role="button"]', '[role="link"]', '[role="textbox"]', '[role="combobox"]',
                '[role="listbox"]', '[role="checkbox"]', '[role="radio"]',
                '[contenteditable="true"]', '[tabindex]:not([tabindex="-1"])',
                '[onclick]', 'summary', 'details',
            ].join(',');

            const viewportHeight = window.innerHeight;
            const viewportWidth = window.innerWidth;

            const allElements = document.querySelectorAll(INTERACTIVE_SELECTOR);
            const results = [];

            allElements.forEach((el, i) => {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);

                if (style.display === 'none' || style.visibility === 'hidden') return;
                if (rect.width === 0 && rect.height === 0) return;

                const isInViewport = (
                    rect.top >= -100 &&
                    rect.left >= -100 &&
                    rect.bottom <= viewportHeight + 100 &&
                    rect.right <= viewportWidth + 100
                );

                let text = (el.textContent || '').trim().slice(0, 80);
                const tag = el.tagName.toLowerCase();
                if (tag === 'input') {
                    text = el.value || el.placeholder || el.getAttribute('aria-label') || text;
                }
                if (tag === 'textarea') {
                    text = el.value || el.placeholder || text;
                }

                const attrs = {};
                for (const attr of ['id', 'name', 'type', 'placeholder', 'aria-label', 'href', 'role', 'title', 'alt']) {
                    const v = el.getAttribute(attr);
                    if (v) attrs[attr] = v.slice(0, 100);
                }

                results.push({
                    index: i,
                    tag: tag,
                    text: text,
                    is_in_viewport: isInViewport,
                    bbox: {x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height)},
                    attributes: attrs,
                });
            });

            return results;
        })()
        """
        raw = await self.page.evaluate(js)
        return raw[:max_elements]

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

    async def click_by_coordinate(self, x: int, y: int) -> dict:
        """按坐标点击页面。"""
        await self.page.mouse.click(x, y)
        return {"success": True, "x": x, "y": y}

    # ── 标签页管理 ────────────────────────────────────────

    async def get_tabs_info(self) -> dict:
        """获取所有打开的标签页信息。

        参考 browser-use 的 BrowserState.tabs 设计，
        返回每个标签页的索引、URL、标题和是否激活。
        """
        tabs = []
        for i, page in enumerate(self.context.pages):
            try:
                url = page.url
                title = await page.title()
            except Exception:
                url = "(unknown)"
                title = "(unknown)"
            tabs.append({
                "index": i,
                "url": url,
                "title": title,
                "is_active": page == self._page,
            })
        return {
            "total": len(tabs),
            "active_index": next((i for i, t in enumerate(tabs) if t["is_active"]), -1),
            "tabs": tabs,
        }

    async def switch_to_tab(self, tab_index: int) -> dict:
        """切换到指定标签页。

        参考 browser-use 的 switch_tab 动作。
        """
        pages = self.context.pages
        if tab_index < 0 or tab_index >= len(pages):
            return {
                "success": False,
                "error": f"标签页索引 {tab_index} 超出范围 (0-{len(pages)-1})",
            }
        old_url = self._page.url if self._page else "none"
        self._page = pages[tab_index]
        try:
            await self._page.bring_to_front()
            await self._page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass
        logger.info(f"已切换标签页: {old_url} → {self._page.url}")
        return {
            "success": True,
            "old_url": old_url,
            "new_url": self._page.url,
            "tab_index": tab_index,
        }

    # ── 新页面/新标签页检测 ──────────────────────────────

    def _on_new_page(self, page: Page):
        """Playwright context.on('page') 回调。"""
        logger.info(f"检测到新页面: {page.url}")
        self._new_page = page
        if self._new_page_event:
            self._new_page_event.set()

    def start_new_page_listener(self):
        """开始监听新页面（在触发可能打开新标签页的操作前调用）。"""
        self._new_page = None
        self._new_page_event = asyncio.Event()
        try:
            self.context.on("page", self._on_new_page)
        except Exception as e:
            logger.debug(f"注册新页面监听失败: {e}")

    async def check_for_new_page(self, timeout: float = 3.0) -> dict:
        """检查是否有新页面打开，如果有则切换到新页面。

        在 click 或 send_keys 后调用，检测是否打开了新标签页。
        """
        if self._new_page_event is None:
            return {"switched": False, "reason": "listener not started"}

        try:
            # 等待一小段时间看是否有新页面事件
            await asyncio.wait_for(self._new_page_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            # 没有新页面，正常
            pass

        # 清理监听器
        try:
            self.context.remove_listener("page", self._on_new_page)
        except Exception:
            pass

        if self._new_page is not None and self._new_page != self._page:
            old_url = self._page.url if self._page else "none"
            try:
                await self._new_page.wait_for_load_state("domcontentloaded", timeout=10000)
            except Exception:
                pass
            self._page = self._new_page
            logger.info(f"已切换到新页面: {old_url} → {self._page.url}")
            return {"switched": True, "old_url": old_url, "new_url": self._page.url}

        return {"switched": False, "url": self._page.url if self._page else "none"}

    # ── 导航等待 ──────────────────────────────────────────

    async def wait_for_navigation(self, timeout: float = 10.0) -> dict:
        """等待页面导航完成。

        同时检测是否有新页面打开（target="_blank" 等场景）。
        如果有新页面，自动切换到新页面。
        """
        # 先检查是否有新页面
        new_page_result = await self.check_for_new_page(timeout=min(timeout, 3.0))
        if new_page_result.get("switched"):
            return new_page_result

        # 等待当前页面导航
        try:
            await self.page.wait_for_load_state("domcontentloaded", timeout=timeout * 1000)
            return {"success": True, "url": self.page.url}
        except Exception as e:
            return {"success": False, "error": str(e), "url": self.page.url}

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()

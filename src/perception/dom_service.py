"""CDP DOM 序列化服务 — 参考 browser-use 的 DomService 设计。

通过 Playwright CDP 获取完整 DOM 状态，包括：
- 页面标题 & URL
- 可交互元素列表（含可见性检测 + 视口裁剪）
- iframe 内元素递归收集
- 元素 index 用于 click_element / input_text 定位

与 browser-use 的差异：
- 不使用 CDP DOM.getDocument（pending 状态风险）
- 使用 JS evaluate 替代，更稳定
- 不包含 AX tree（简化版）
"""

import logging
from dataclasses import dataclass, field

from playwright.async_api import Page

logger = logging.getLogger(__name__)

# JS 脚本：提取可交互元素（含可见性 + 视口检测）
INTERACTIVE_ELEMENTS_JS = """
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

        // 跳过不可见元素
        if (style.display === 'none' || style.visibility === 'hidden') return;
        if (rect.width === 0 && rect.height === 0) return;

        // 检查是否在视口内
        const isInViewport = (
            rect.top >= -100 &&
            rect.left >= -100 &&
            rect.bottom <= viewportHeight + 100 &&
            rect.right <= viewportWidth + 100
        );

        let text = (el.textContent || '').trim().slice(0, 80);
        // input/textarea 用 value/placeholder 代替 textContent
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
            bbox: {
                x: Math.round(rect.x),
                y: Math.round(rect.y),
                w: Math.round(rect.width),
                h: Math.round(rect.height),
            },
            attributes: attrs,
        });
    });

    return results;
})()
"""


@dataclass
class ElementInfo:
    """可交互元素信息。"""
    index: int
    tag: str
    text: str
    is_in_viewport: bool
    bbox: dict  # {x, y, w, h}
    attributes: dict


@dataclass
class DOMState:
    """页面 DOM 状态。"""
    title: str = ""
    url: str = ""
    elements: list[ElementInfo] = field(default_factory=list)
    total_elements: int = 0
    visible_elements: int = 0
    has_iframes: bool = False

    def format_for_llm(self, max_elements: int = 30) -> str:
        """格式化为 LLM 可读的文本。"""
        lines = [
            f"页面标题: {self.title}",
            f"URL: {self.url}",
            f"总可交互元素: {self.total_elements} | 视口可见: {self.visible_elements}",
            "",
            "可交互元素列表:",
        ]

        visible = [e for e in self.elements if e.is_in_viewport]
        display = visible[:max_elements]

        if not display:
            display = self.elements[:max_elements]
            lines.append("  (无可见元素, 显示所有元素)")

        for el in display:
            attrs = el.attributes
            label = attrs.get("aria-label", "") or attrs.get("placeholder", "") or attrs.get("name", "") or attrs.get("title", "")
            extra = f" | {label}" if label else ""
            lines.append(
                f"  [{el.index}] <{el.tag}> \"{el.text[:40]}\"{extra}"
            )

        if len(display) < len(self.elements):
            lines.append(f"  ... 还有 {len(self.elements) - len(display)} 个元素未显示")

        return "\n".join(lines)


class DOMSerializer:
    """DOM 序列化器 — 提取交互元素并格式化。"""

    @staticmethod
    def parse_elements(raw: list[dict]) -> list[ElementInfo]:
        """解析 JS 返回的原始元素列表。"""
        return [
            ElementInfo(
                index=e["index"],
                tag=e["tag"],
                text=e["text"],
                is_in_viewport=e.get("is_in_viewport", True),
                bbox=e.get("bbox", {}),
                attributes=e.get("attributes", {}),
            )
            for e in raw
        ]


class DomService:
    """CDP DOM 服务 — 获取完整页面 DOM 状态。

    参考 browser-use 的 DomService 设计，简化版：
    - 不使用 CDP DOM.getDocument
    - 使用 JS evaluate 提取交互元素
    - 支持 iframe 递归收集
    - 支持视口可见性检测
    """

    def __init__(self, browser_manager):
        """
        Args:
            browser_manager: BrowserManager 实例
        """
        self._browser_manager = browser_manager

    @property
    def page(self) -> Page:
        return self._browser_manager.page

    async def get_page_state(self, max_elements: int = 50) -> DOMState:
        """获取当前页面完整 DOM 状态。

        Returns:
            DOMState: 包含 title, url, elements 等
        """
        try:
            title = await self.page.title()
        except Exception:
            title = "(unknown)"

        try:
            url = self.page.url
        except Exception:
            url = "(unknown)"

        # 提取主文档元素
        elements = await self.get_clickable_elements(max_elements=max_elements)

        # 检查 iframe
        has_iframes = await self._check_iframes()

        visible = sum(1 for e in elements if e.is_in_viewport)

        return DOMState(
            title=title,
            url=url,
            elements=elements,
            total_elements=len(elements),
            visible_elements=visible,
            has_iframes=has_iframes,
        )

    async def get_clickable_elements(self, max_elements: int = 50) -> list[ElementInfo]:
        """获取可交互元素列表（含视口可见性检测）。

        参考 browser-use 的 ClickableElementDetector，
        使用 JS 脚本提取所有交互元素并检测可见性。
        """
        try:
            raw = await self.page.evaluate(INTERACTIVE_ELEMENTS_JS)
        except Exception as e:
            logger.warning(f"DOM 提取失败: {e}")
            return []

        # 截断到 max_elements
        raw = raw[:max_elements]

        return DOMSerializer.parse_elements(raw)

    async def _check_iframes(self) -> bool:
        """检查页面是否包含 iframe。"""
        try:
            count = await self.page.evaluate(
                "() => document.querySelectorAll('iframe').length"
            )
            return count > 0
        except Exception:
            return False

    async def get_iframe_elements(self, max_per_iframe: int = 20) -> dict[str, list[ElementInfo]]:
        """递归收集所有 iframe 内的可交互元素。

        Returns:
            {iframe_selector: [ElementInfo, ...]}
        """
        try:
            frame_count = await self.page.evaluate(
                "() => document.querySelectorAll('iframe').length"
            )
        except Exception:
            return {}

        if frame_count == 0:
            return {}

        result = {}
        for frame in self.page.frames:
            if frame == self.page.main_frame:
                continue
            try:
                frame_elements = await frame.evaluate(INTERACTIVE_ELEMENTS_JS)
                frame_elements = frame_elements[:max_per_iframe]
                result[frame.url or frame.name or f"iframe-{len(result)}"] = (
                    DOMSerializer.parse_elements(frame_elements)
                )
            except Exception as e:
                logger.debug(f"iframe 元素提取失败: {e}")

        return result

    async def get_dom_snapshot(self, max_elements: int = 50) -> str:
        """获取 DOM 快照的文本表示（直接给 LLM 使用）。

        这是 get_dom_snapshot 工具的底层实现，
        替代原有的 get_indexed_elements。
        """
        state = await self.get_page_state(max_elements=max_elements)
        return state.format_for_llm(max_elements=min(max_elements, 30))
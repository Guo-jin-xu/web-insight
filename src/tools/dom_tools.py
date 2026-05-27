"""DOM 感知工具 — get_dom_snapshot / get_page_links / extract_content / extract_article_content.

DOM 优先：这些是 Agent 的首选感知工具，比 VLM 更快更精确。
"""

from typing import Annotated

from langchain_core.tools import tool

from src.browser.manager import BrowserManager
from src.perception.dom import extract_article, extract_links, extract_page_text


def create_dom_tools(browser: BrowserManager) -> list:
    """创建所有 DOM 感知工具。"""

    @tool
    async def get_dom_snapshot() -> str:
        """获取当前页面可交互元素列表（index/tag/text/bbox）。

        这是 Agent 感知页面的首选工具。返回每个可交互元素的索引号，
        click_element 和 type_text 通过此索引号定位元素。

        **重要**: 先调用 get_dom_snapshot 获取元素索引，再调用 click_element(index) 操作。
        """
        elements = await browser.get_indexed_elements()
        if not elements:
            return "未找到可交互元素。页面可能尚未加载，请等待或刷新。"

        lines = [f"可交互元素 (top {len(elements)}):"]
        for el in elements:
            bbox = el["bbox"]
            attrs = el.get("attributes", {})
            label = attrs.get("aria-label", "") or attrs.get("placeholder", "") or attrs.get("name", "")
            extra = f" | {label}" if label else ""
            lines.append(
                f"  [{el['index']}] <{el['tag']}> {el['text'][:40]}{extra}"
            )
        return "\n".join(lines)

    @tool
    async def get_page_links(max_count: Annotated[int, "最大返回链接数"] = 10) -> str:
        """提取当前页面的链接（文本 + URL），过滤导航类链接。

        适用场景: 搜索结果页获取链接、导航页获取目录、决定下一步跳转目标。
        最多返回 10 个链接，自动过滤站内导航链接。
        """
        html = await browser.get_page_html()
        links = extract_links(html, max_count=max_count)
        if not links:
            return "页面中未找到链接"

        lines = [f"共 {len(links)} 个有效链接:"]
        for link in links:
            lines.append(f"  [{link['index']}] {link['text'][:60]}")
            lines.append(f"       → {link['href'][:100]}")
        return "\n".join(lines)

    @tool
    async def extract_content(max_length: Annotated[int, "最大输出字符数"] = 3000) -> str:
        """提取当前页面的可见文本内容。

        适用场景: 快速了解页面内容、判断页面类型、提取关键信息。
        返回纯文本，不含坐标。需要操作元素请用 get_dom_snapshot。
        """
        html = await browser.get_page_html()
        text = extract_page_text(html, max_length=max_length)
        return f"页面文本 ({len(text)} 字符):\n{text}"

    @tool
    async def extract_article_content() -> str:
        """从当前页面提取文章正文（标题 + 主体内容）。

        适用场景: 进入文章详情页后提取核心内容用于阅读或总结。
        自动识别正文容器（article/content/post/main）。
        """
        html = await browser.get_page_html()
        article = extract_article(html)
        if not article["content"]:
            return "未提取到文章内容，当前页面可能不是文章页"
        return f"标题: {article['title']}\n\n正文 ({article['length']} 字符):\n{article['content']}"

    return [get_dom_snapshot, get_page_links, extract_content, extract_article_content]

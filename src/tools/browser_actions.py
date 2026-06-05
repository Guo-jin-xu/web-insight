"""浏览器操作工具 — 合并精简版。

参考 browser-use 的工具设计，将 browser_tools + dom_tools 合并为9个核心工具：
navigate, click_element, input_text, scroll, go_back, send_keys,
extract_content, get_dom_snapshot, done

移除的工具：
- search → 合并到 navigate（自动检测 URL vs 搜索词）
- take_screenshot → 内部调用，不暴露给 LLM
- get_page_links → 合并到 get_dom_snapshot
- extract_article_content → 合并到 extract_content
- wait → 内部自动等待
- get_current_time → 注入 system prompt
"""

import urllib.parse
from pathlib import Path

from src.browser.manager import BrowserManager
from src.perception.dom import extract_article, extract_page_text
from src.perception.dom_service import DomService
from src.tools.models import (
    ClickElementAction,
    DoneAction,
    ExtractContentAction,
    GetDomSnapshotAction,
    InputTextAction,
    NavigateAction,
    NoParamsAction,
    ScrollAction,
    SendKeysAction,
)
from src.tools.registry import Registry


def _is_url(text: str) -> bool:
    """判断文本是否为 URL。"""
    return text.startswith(("http://", "https://", "www."))


def _build_search_url(query: str, engine: str = "bing") -> str:
    """构建搜索 URL。"""
    q = urllib.parse.quote_plus(query)
    urls = {
        "bing": f"https://www.bing.com/search?q={q}",
        "google": f"https://www.google.com/search?q={q}",
    }
    return urls.get(engine, urls["bing"])


def create_browser_registry(browser: BrowserManager) -> Registry:
    """创建浏览器操作工具注册中心。"""

    reg = Registry()

    @reg.action(
        "导航到指定 URL 或搜索关键词。如果输入是完整 URL 则直接导航，如果是普通文本则自动搜索。",
        param_model=NavigateAction,
    )
    async def navigate(params: NavigateAction):
        url = params.url
        if not _is_url(url):
            url = _build_search_url(url)

        try:
            await browser.page.goto(url, wait_until="domcontentloaded", timeout=15000)
            title = await browser.page.title()
            return f"已导航到: {url}\n页面标题: {title}"
        except Exception as e:
            return f"导航失败: {e}"

    @reg.action(
        "点击页面元素。index 必须来自 get_dom_snapshot 返回的元素索引。",
        param_model=ClickElementAction,
    )
    async def click_element(params: ClickElementAction):
        result = await browser.click_by_index(params.index)
        if result["success"]:
            el = result.get("element", {})
            return f"已点击 [{params.index}] <{el.get('tag', '?')}> {el.get('text', '')}"
        return f"点击失败: {result.get('error', 'unknown')}"

    @reg.action(
        "向输入框键入文本。先点击输入框（通过 index），再输入内容。",
        param_model=InputTextAction,
    )
    async def input_text(params: InputTextAction):
        result = await browser.type_by_index(params.index, params.text, params.clear)
        if result["success"]:
            return f"已输入 '{params.text}' 到元素 [{params.index}]"
        return f"输入失败: {result.get('error', 'unknown')}"

    @reg.action(
        "滚动页面。向下滚动查看更多内容，向上滚动回到页面顶部。",
        param_model=ScrollAction,
    )
    async def scroll(params: ScrollAction):
        await browser.scroll(down=params.down, pages=params.pages)
        direction = "向下" if params.down else "向上"
        return f"已{direction}滚动 {params.pages} 页"

    @reg.action(
        "浏览器后退到上一页。导航到错误页面时使用。",
        param_model=NoParamsAction,
    )
    async def go_back(params: NoParamsAction):
        try:
            await browser.go_back()
            return f"已后退，当前: {browser.page.url}"
        except Exception as e:
            return f"后退失败: {e}"

    @reg.action(
        "按下键盘按键。常用: Enter 提交搜索/表单，Escape 关闭弹窗，Control+a 全选。",
        param_model=SendKeysAction,
    )
    async def send_keys(params: SendKeysAction):
        await browser.press_key(params.keys)
        return f"已按下 {params.keys}"

    @reg.action(
        "提取当前页面内容。自动检测页面类型（文章/列表/搜索结果）并提取核心内容。",
        param_model=ExtractContentAction,
    )
    async def extract_content(params: ExtractContentAction):
        html = await browser.get_page_html()
        # 先尝试提取文章内容
        article = extract_article(html, max_len=params.max_length)
        if article["content"] and len(article["content"]) > 200:
            return f"标题: {article['title']}\n\n正文 ({article['length']} 字符):\n{article['content']}"

        # 非文章页，提取纯文本
        text = extract_page_text(html, max_length=params.max_length)
        return f"页面文本 ({len(text)} 字符):\n{text}"

    @reg.action(
        "获取当前页面可交互元素列表（index/tag/text/bbox）。这是感知页面的首选工具，click_element 和 input_text 通过此索引定位元素。",
        param_model=GetDomSnapshotAction,
    )
    async def get_dom_snapshot(params: GetDomSnapshotAction):
        dom_service = DomService(browser)
        snapshot = await dom_service.get_dom_snapshot(max_elements=params.max_elements)
        if not snapshot or "可交互元素" not in snapshot:
            return "未找到可交互元素。页面可能尚未加载，请等待或刷新。"
        return snapshot

    @reg.action(
        "标记任务完成并返回最终结果。调用后终止执行。所有提取、总结工作必须在调用 done 之前完成。",
        param_model=DoneAction,
    )
    async def done(params: DoneAction):
        p = Path("data") / "task_result.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(params.text, encoding="utf-8")
        return params.text

    return reg

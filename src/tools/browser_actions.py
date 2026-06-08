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
from src.perception.vision import analyze_screenshot
from src.tools.models import (
    ClickCoordinateAction,
    ClickElementAction,
    CloseTabAction,
    DoneAction,
    ExtractContentAction,
    GetDomSnapshotAction,
    GetTabsInfoAction,
    InputTextAction,
    ListTabsAction,
    NavigateAction,
    NewTabAction,
    NoParamsAction,
    ScrollAction,
    SelectDropdownAction,
    SendKeysAction,
    SwitchTabAction,
    UploadFileAction,
    VisualAnalyzeAction,
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
        "点击页面元素。index 来自 get_dom_snapshot 返回的元素索引。"
        " 点击后自动检测是否有新标签页打开，如有则切换到新标签页。"
        " 如果点击后页面跳转了（URL 变化），也会自动检测。",
        param_model=ClickElementAction,
    )
    async def click_element(params: ClickElementAction):
        # 先开始监听新页面（在点击前注册监听器）
        browser.start_new_page_listener()

        result = await browser.click_by_index(params.index)
        if result["success"]:
            el = result.get("element", {})

            # 检查是否有新页面打开（点击链接可能打开新标签页）
            new_page_result = await browser.check_for_new_page(timeout=2.0)
            if new_page_result.get("switched"):
                return (
                    f"已点击 [{params.index}] <{el.get('tag', '?')}> {el.get('text', '')}，"
                    f"检测到新标签页并已切换: {new_page_result['old_url']} → {new_page_result['new_url']}"
                )

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
        "按下键盘按键。常用: Enter 提交搜索/表单，Escape 关闭弹窗，Control+a 全选。"
        " Enter 提交搜索后建议设置 wait_for_navigation=true 等待页面跳转。"
        " 如果搜索打开了新标签页，会自动切换到新标签页。",
        param_model=SendKeysAction,
    )
    async def send_keys(params: SendKeysAction):
        if params.wait_for_navigation:
            # 先开始监听新页面（在触发操作前注册监听器）
            browser.start_new_page_listener()

        await browser.press_key(params.keys)

        if params.wait_for_navigation:
            nav_result = await browser.wait_for_navigation()
            if nav_result.get("switched"):
                return f"已按下 {params.keys}，检测到新标签页并已切换: {nav_result['old_url']} → {nav_result['new_url']}"
            if nav_result.get("success"):
                return f"已按下 {params.keys}，页面已跳转到: {nav_result['url']}"
            return f"已按下 {params.keys}，等待导航超时: {nav_result.get('error', '')}"
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
        "获取当前页面可交互元素列表（index/tag/text/bbox）。这是感知页面的首选工具，click_element 和 input_text 通过此索引定位元素。"
        " 最多返回视口内所有可见元素。如果返回空或无法识别目标元素，请使用 visual_analyze 视觉分析降级。"
        " 如果怀疑当前页面不是目标页面（如搜索后打开了新标签页），请使用 get_tabs_info 查看所有标签页，再用 switch_tab 切换。",
        param_model=GetDomSnapshotAction,
    )
    async def get_dom_snapshot(params: GetDomSnapshotAction):
        dom_service = DomService(browser)
        snapshot = await dom_service.get_dom_snapshot(max_elements=params.max_elements)
        if not snapshot or "可交互元素" not in snapshot:
            return (
                "未找到可交互元素。页面可能尚未加载，请等待或刷新。"
                " 如果多次获取仍为空，请使用 visual_analyze 工具通过截图分析页面。"
            )
        return snapshot

    @reg.action(
        "点击页面指定坐标 (x, y)。配合 visual_analyze 使用：先用视觉分析定位元素，再用此工具点击坐标。"
        " 点击后自动检测是否有新标签页打开（如点击视频链接跳转到新页面），如有则切换到新标签页。",
        param_model=ClickCoordinateAction,
    )
    async def click_coordinate(params: ClickCoordinateAction):
        browser.start_new_page_listener()
        result = await browser.click_by_coordinate(params.x, params.y)

        if result["success"]:
            # 检查是否有新页面打开（点击坐标链接可能打开新标签页）
            new_page_result = await browser.check_for_new_page(timeout=2.0)
            if new_page_result.get("switched"):
                return (
                    f"已点击坐标 ({params.x}, {params.y})，"
                    f"检测到新标签页并已切换: {new_page_result['old_url']} → {new_page_result['new_url']}"
                )
            return f"已点击坐标 ({params.x}, {params.y})"
        return f"坐标点击失败: {result.get('error', 'unknown')}"

    @reg.action(
        "使用视觉模型分析当前页面截图，根据自然语言描述定位元素并返回坐标。"
        " 当 DOM 无法识别元素时（如视频、图片、Canvas 内容），使用此工具降级处理。"
        " 使用流程: visual_analyze(query='找到第一个视频') → 获取坐标 → click_coordinate(x, y) 点击。",
        param_model=VisualAnalyzeAction,
    )
    async def visual_analyze(params: VisualAnalyzeAction):
        from src.schemas.vision import PageAnalysis
        import logging

        _logger = logging.getLogger(__name__)

        try:
            screenshot_b64 = await browser.screenshot_to_b64()
            _logger.info(f"截图成功，大小: {len(screenshot_b64)} 字符")
            analysis: PageAnalysis = await analyze_screenshot(screenshot_b64)
            _logger.info(f"VLM 分析成功：发现 {len(analysis.elements)} 个元素")
        except Exception as e:
            _logger.error(f"视觉分析失败: {e}")
            return f"视觉分析失败: {e}\n\n请检查: 1) VLM 模型名称是否正确 2) API Key 是否有效 3) 网络是否可达"

        # 过滤相关元素
        query_lower = params.query.lower()
        relevant = []
        for el in analysis.elements:
            if query_lower in el.name.lower() or query_lower in el.description.lower():
                relevant.append(el)

        if not relevant:
            # 返回所有元素
            relevant = analysis.elements[:params.max_elements]

        result_lines = [
            f"## 页面描述\n{analysis.page_description}",
            f"\n## 匹配 '{params.query}' 的元素 (共 {len(relevant)} 个)",
        ]
        for i, el in enumerate(relevant[:params.max_elements]):
            result_lines.append(
                f"  [{i}] {el.name}: type={el.type}, 坐标=({el.x},{el.y}), {el.description}"
            )

        if analysis.suggestions:
            result_lines.append(f"\n## 操作建议\n{analysis.suggestions}")

        return "\n".join(result_lines)

    @reg.action(
        "获取所有打开的标签页信息（索引、URL、标题、是否激活）。"
        " 当搜索或点击操作打开了新标签页但 agent 未自动切换时，使用此工具查看所有标签页，"
        " 然后用 switch_tab 切换到正确的标签页。",
        param_model=GetTabsInfoAction,
    )
    async def get_tabs_info(params: GetTabsInfoAction):
        info = await browser.get_tabs_info()
        lines = [f"共 {info['total']} 个标签页，当前激活: 索引 {info['active_index']}"]
        for t in info["tabs"]:
            marker = " ← 当前" if t["is_active"] else ""
            lines.append(f"  [{t['index']}] {t['title'][:60]} | {t['url'][:80]}{marker}")
        return "\n".join(lines)

    @reg.action(
        "切换到指定标签页。使用 get_tabs_info 查看所有标签页后，切换到目标标签页。"
        " 切换后所有后续操作（get_dom_snapshot、click_element 等）都会在新标签页上执行。",
        param_model=SwitchTabAction,
    )
    async def switch_tab(params: SwitchTabAction):
        result = await browser.switch_to_tab(params.tab_index)
        if result["success"]:
            return f"已切换到标签页 [{params.tab_index}]: {result['new_url']}"
        return f"切换失败: {result.get('error', 'unknown')}"

    @reg.action(
        "在新标签页打开 URL。用于同时查看多个页面或对比信息。",
        param_model=NewTabAction,
    )
    async def new_tab(params: NewTabAction):
        result = await browser.new_tab(params.url)
        if result["success"]:
            return f"已在新标签页打开: {result['url']}"
        return f"打开失败: {result.get('error', '')}"

    @reg.action(
        "关闭指定标签页。index=-1 关闭当前页。",
        param_model=CloseTabAction,
    )
    async def close_tab(params: CloseTabAction):
        result = await browser.close_tab(params.index)
        if result["success"]:
            return f"已关闭标签页，当前: {result['current_url']}"
        return f"关闭失败: {result.get('error', '')}"

    @reg.action(
        "列出所有打开的标签页。",
        param_model=ListTabsAction,
    )
    async def list_tabs(params: ListTabsAction):
        tabs = await browser.list_tabs()
        lines = [f"共 {len(tabs)} 个标签页:"]
        for t in tabs:
            marker = " ← 当前" if t["is_current"] else ""
            lines.append(f"  [{t['index']}] {t['title'][:40]}{marker}")
            lines.append(f"       {t['url'][:80]}")
        return "\n".join(lines)

    @reg.action(
        "选择下拉菜单选项。index 来自 get_dom_snapshot，value 为选项文本。",
        param_model=SelectDropdownAction,
    )
    async def select_dropdown(params: SelectDropdownAction):
        result = await browser.select_dropdown(params.index, params.value)
        if result["success"]:
            return f"已选择 '{params.value}'"
        return f"选择失败: {result.get('error', '')}"

    @reg.action(
        "上传文件到文件选择框。index 来自 get_dom_snapshot，file_path 为本地文件绝对路径。",
        param_model=UploadFileAction,
    )
    async def upload_file(params: UploadFileAction):
        result = await browser.upload_file(params.index, params.file_path)
        if result["success"]:
            return f"已上传文件: {params.file_path}"
        return f"上传失败: {result.get('error', '')}"

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

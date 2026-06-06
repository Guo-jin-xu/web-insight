"""工具优先级权重 — 方案C: 根据页面 URL 动态过滤工具列表。

参考 browser-use 的 `_update_action_models_for_page()` 方法，
根据页面类型（搜索结果/文章详情/未知）动态调整可用工具列表，
引导 LLM 选择正确的工具，减少冗余调用。

页面类型检测规则：
- SEARCH_RESULTS: URL 包含搜索关键词 (search, q=, s?, wd=, query)
- ARTICLE: 普通页面（非搜索）
- UNKNOWN: 无法判断（如 about:blank）
"""

import logging
import re
from enum import Enum, auto

logger = logging.getLogger(__name__)


class PageType(Enum):
    SEARCH_RESULTS = auto()  # 搜索结果页
    ARTICLE = auto()         # 文章/详情页
    UNKNOWN = auto()         # 未知页面


# 核心工具：始终保留（不依赖页面类型）
CORE_TOOLS = {"navigate", "get_dom_snapshot", "done", "scroll", "go_back", "send_keys", "wait"}

# 搜索页隐藏的工具
SEARCH_HIDDEN = {"extract_content"}

# 文章页隐藏的工具 — 空集（复杂任务如 B站 需要点击元素）
# 文章页的冗余由方案B (action_merger) 处理
ARTICLE_HIDDEN: set[str] = set()


# 搜索 URL 检测正则
SEARCH_PATTERNS = [
    r"(?:search|query|find|suche)[/]?[\?&]",
    r"[?&]q=",
    r"[?&]s=",
    r"[?&]wd=",
    r"[?&]query=",
    r"[?&]keyword=",
    r"[?&]text=",
    r"/search[/?]",
    r"search\?",
    r"google\.[a-z]+/search",
    r"bing\.[a-z]+/search",
    r"baidu\.[a-z]+/s",
    r"duckduckgo\.[a-z]+/",
    r"sogou\.[a-z]+/web",
    r"yahoo\.[a-z]+/search",
]


def detect_page_type(url: str) -> PageType:
    """根据 URL 检测页面类型。

    Args:
        url: 当前页面 URL

    Returns:
        PageType: SEARCH_RESULTS, ARTICLE, 或 UNKNOWN
    """
    if not url or url.startswith("about:") or url.startswith("chrome://"):
        return PageType.UNKNOWN

    url_lower = url.lower()

    for pattern in SEARCH_PATTERNS:
        if re.search(pattern, url_lower):
            logger.debug(f"检测到搜索结果页: {url}")
            return PageType.SEARCH_RESULTS

    return PageType.ARTICLE


def prioritize_tools(
    tool_schemas: list[dict],
    page_type: PageType,
) -> list[dict]:
    """根据页面类型过滤工具列表。

    Args:
        tool_schemas: 原始工具 schema 列表
        page_type: 当前页面类型

    Returns:
        过滤后的工具 schema 列表
    """
    if page_type == PageType.SEARCH_RESULTS:
        hidden = SEARCH_HIDDEN
    elif page_type == PageType.ARTICLE:
        hidden = ARTICLE_HIDDEN
    else:
        hidden = set()

    filtered = []
    for schema in tool_schemas:
        name = schema["function"]["name"]
        # 核心工具始终保留
        if name in CORE_TOOLS:
            filtered.append(schema)
            continue
        # 隐藏特定工具
        if name in hidden:
            logger.debug(f"方案C: 隐藏工具 {name} (页面类型: {page_type})")
            continue
        filtered.append(schema)

    if hidden:
        hidden_names = [s["function"]["name"] for s in tool_schemas if s["function"]["name"] in hidden]
        logger.info(f"方案C: 页面类型={page_type.name}, 隐藏工具={hidden_names}")

    return filtered


def get_priority_tools(
    tool_schemas: list[dict],
    url: str,
) -> list[dict]:
    """便捷方法：根据 URL 获取优先级过滤后的工具列表。

    Args:
        tool_schemas: 原始工具 schema 列表
        url: 当前页面 URL

    Returns:
        过滤后的工具 schema 列表
    """
    page_type = detect_page_type(url)
    return prioritize_tools(tool_schemas, page_type)
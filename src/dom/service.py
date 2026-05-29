"""DomService — 从页面构建 EnhancedDOMTreeNode 树。

Phase 3.3: 教学简化版，使用 JS 遍历 DOM 构建树结构，
替代当前 flat list 的 get_indexed_elements()。
"""

from src.dom.views import EnhancedDOMTreeNode, NodeType, SerializedDOMState
from src.dom.serializer import DOMTreeSerializer, INTERACTIVE_TAGS, SCROLL_CSS_KEYWORDS


_DOM_TREE_JS = """
(() => {
    const INTERACTIVE_SELECTOR = 'a,button,input,select,textarea,[role="button"],[role="link"],[role="textbox"],'
        + '[role="combobox"],[role="listbox"],[role="checkbox"],[role="radio"],[contenteditable="true"],'
        + '[onclick],[tabindex]:not([tabindex="-1"])';
    const INTERACTIVE_SET = new Set(document.querySelectorAll(INTERACTIVE_SELECTOR));

    const SCROLLABLE_CSS = ['overflow', 'overflow-y', 'overflow-x'];
    const SCROLL_VALUES = new Set(['auto', 'scroll']);

    let highlightCounter = 0;
    let nodeIdCounter = 0;

    function isScrollable(el) {
        const style = window.getComputedStyle(el);
        for (const prop of SCROLLABLE_CSS) {
            if (SCROLL_VALUES.has(style[prop])) return true;
        }
        return false;
    }

    function walk(el) {
        if (!el) return null;
        const id = ++nodeIdCounter;
        const rect = el.getBoundingClientRect();
        const visible = rect.width > 0 && rect.height > 0;
        const interactive = INTERACTIVE_SET.has(el);

        const node = {
            nodeId: id,
            tagName: (el.tagName || '').toLowerCase(),
            nodeType: el.nodeType || 1,
            attributes: {},
            text: '',
            children: [],
            rect: { x: Math.round(rect.x), y: Math.round(rect.y), width: Math.round(rect.width), height: Math.round(rect.height) },
            isVisible: visible,
            isInteractive: interactive,
            scrollable: isScrollable(el),
            highlightIndex: null,
        };

        if (interactive && visible) {
            node.highlightIndex = ++highlightCounter;
        }

        for (const attr of ['id', 'name', 'type', 'placeholder', 'aria-label', 'href', 'role', 'class', 'title', 'value']) {
            const v = el.getAttribute(attr);
            if (v) {
                node.attributes[attr] = v.length > 100 ? v.slice(0, 100) : v;
            }
        }

        for (const child of el.childNodes) {
            if (child.nodeType === 1) {
                const childNode = walk(child);
                if (childNode) node.children.push(childNode);
            } else if (child.nodeType === 3) {
                const text = child.nodeValue ? child.nodeValue.trim() : '';
                if (text) {
                    node.text = (node.text + ' ' + text).trim().slice(0, 200);
                }
            }
        }

        return node;
    }

    return walk(document.body);
})()
"""


def _js_node_to_enhanced(
    js_node: dict,
    depth: int,
    max_depth: int,
    counter: list[int] | None = None,
) -> EnhancedDOMTreeNode | None:
    """递归将 JS 节点转为 EnhancedDOMTreeNode。"""
    if counter is None:
        counter = [0]
    if js_node is None:
        return None

    if depth > max_depth:
        return EnhancedDOMTreeNode(
            node_type=NodeType.ELEMENT_NODE,
            node_name=js_node.get("tagName", "?"),
            node_value=js_node.get("text", ""),
        )

    highlight_index = js_node.get("highlightIndex")
    is_interactive = js_node.get("isInteractive", False)
    is_visible = js_node.get("isVisible", True)

    tag_name = js_node.get("tagName", "")
    if not is_interactive and tag_name in INTERACTIVE_TAGS:
        is_interactive = True

    is_scrollable = js_node.get("scrollable", False)
    if not is_scrollable:
        attrs_preview = js_node.get("attributes", {})
        class_val = attrs_preview.get("class", "")
        style_val = attrs_preview.get("style", "")
        combined = f"{class_val} {style_val}".lower()
        if any(kw in combined for kw in SCROLL_CSS_KEYWORDS):
            is_scrollable = True

    if highlight_index is None and is_interactive and is_visible:
        counter[0] += 1
        highlight_index = counter[0]

    node = EnhancedDOMTreeNode(
        node_id=js_node.get("nodeId", 0),
        node_type=NodeType.ELEMENT_NODE if js_node.get("nodeType") == 1 else NodeType.TEXT_NODE,
        node_name=js_node.get("tagName", ""),
        node_value=js_node.get("text", ""),
        attributes=js_node.get("attributes", {}),
        is_visible=is_visible,
        x=js_node.get("rect", {}).get("x", 0),
        y=js_node.get("rect", {}).get("y", 0),
        width=js_node.get("rect", {}).get("width", 0),
        height=js_node.get("rect", {}).get("height", 0),
        is_interactive=is_interactive,
        is_scrollable=js_node.get("scrollable", False),
        highlight_index=highlight_index,
    )

    for child_js in js_node.get("children", []):
        child = _js_node_to_enhanced(child_js, depth + 1, max_depth, counter)
        if child is not None:
            child.parent_node = node
            node.children.append(child)

    return node


class DomService:
    """DOM 服务：从页面构建增强 DOM 树。"""

    def __init__(self, browser, max_depth: int = 8):
        self.browser = browser
        self.max_depth = max_depth

    async def get_dom_tree(self) -> EnhancedDOMTreeNode:
        js_result = await self.browser.page.evaluate(_DOM_TREE_JS)
        if js_result is None:
            url = self.browser.page.url
            return EnhancedDOMTreeNode(
                node_name="body",
                node_value=f"DOM unavailable (URL: {url})",
            )
        tree = _js_node_to_enhanced(js_result, depth=0, max_depth=self.max_depth)
        if tree is None:
            tree = EnhancedDOMTreeNode(node_name="body", node_value="(empty)")
        return tree

    async def get_serialized_dom(self) -> SerializedDOMState:
        tree = await self.get_dom_tree()
        return DOMTreeSerializer.serialize(tree)

    async def get_clickable_elements(self) -> list[EnhancedDOMTreeNode]:
        state = await self.get_serialized_dom()
        return list(state.selector_map.values())
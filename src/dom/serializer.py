"""DOM 树序列化器 — 将 EnhancedDOMTreeNode 转为 LLM 可读文本。

Phase 3.3: 替代当前 flat list，提供树形缩进 + highlight_index 标记。
"""

from src.dom.views import EnhancedDOMTreeNode, SerializedDOMState

INDENT = "  "

# 即使 JS 端选择器未覆盖，也能在 Python 端兜底检测
INTERACTIVE_TAGS = frozenset({"a", "button", "input", "select", "textarea", "option"})
SCROLL_CSS_KEYWORDS = ("overflow", "overflow-y", "overflow-x")


class DOMTreeSerializer:
    """将 EnhancedDOMTreeNode 树序列化为 LLM 可读文本。"""

    @staticmethod
    def serialize(root: EnhancedDOMTreeNode) -> SerializedDOMState:
        lines: list[str] = []
        selector_map: dict[int, EnhancedDOMTreeNode] = {}

        def _walk(node: EnhancedDOMTreeNode, depth: int) -> None:
            indent = INDENT * depth

            if node.node_type.value == 3:
                text = node.node_value.strip()
                if text:
                    lines.append(f"{indent}{text}")
                return

            tag = node.node_name or "?"
            attrs = node.attributes or {}

            interactive_marker = ""
            if node.is_interactive and node.highlight_index is not None:
                interactive_marker = f"[{node.highlight_index}]"
                selector_map[node.highlight_index] = node

            scroll_marker = ""
            if node.is_scrollable:
                scroll_marker = " |SCROLL|"

            focus_marker = ""
            if node.is_focused:
                focus_marker = " *FOCUSED*"

            label = ""
            if attrs.get("id"):
                label += f" #{attrs['id']}"
            if attrs.get("class"):
                cls = attrs["class"]
                label += f" .{cls[:30]}" if len(cls) <= 30 else f" .{cls[:27]}..."

            line = f"{indent}<{tag}{label}> {interactive_marker}{scroll_marker}{focus_marker}"
            line = line.rstrip()
            lines.append(line)

            if node.node_value:
                text = node.node_value.strip()
                if text:
                    lines.append(f"{indent}{INDENT}{text}")

            for child in node.children:
                _walk(child, depth + 1)

            if node.children:
                lines.append(f"{indent}</{tag}>")

        _walk(root, 0)
        return SerializedDOMState(
            text="\n".join(lines),
            selector_map=selector_map,
        )
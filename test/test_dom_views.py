"""DOM 增强测试 — TDD Phase 3.3

测试 EnhancedDOMTreeNode、SerializedDOMState 和 DOMTreeSerializer。
"""

import json

import pytest

from src.dom.views import EnhancedDOMTreeNode, NodeType, SerializedDOMState


class TestNodeType:
    """NodeType 枚举测试。"""

    def test_element_node_value(self):
        assert NodeType.ELEMENT_NODE == 1

    def test_text_node_value(self):
        assert NodeType.TEXT_NODE == 3

    def test_node_type_str_representation(self):
        assert str(NodeType.ELEMENT_NODE) == "NodeType.ELEMENT_NODE"
        assert str(NodeType.TEXT_NODE) == "NodeType.TEXT_NODE"


class TestEnhancedDOMTreeNodeElement:
    """EnhancedDOMTreeNode 基本操作。"""

    def test_create_element_node(self):
        node = EnhancedDOMTreeNode(
            node_name="div",
            node_type=NodeType.ELEMENT_NODE,
            attributes={"class": "container"},
            is_visible=True,
            is_interactive=False,
        )
        assert node.node_name == "div"
        assert node.node_type == NodeType.ELEMENT_NODE
        assert node.attributes["class"] == "container"
        assert node.is_visible is True
        assert node.is_interactive is False
        assert node.children == []

    def test_create_text_node(self):
        node = EnhancedDOMTreeNode(
            node_name="#text",
            node_type=NodeType.TEXT_NODE,
            node_value="hello world",
        )
        assert node.node_name == "#text"
        assert node.node_type == NodeType.TEXT_NODE
        assert node.node_value == "hello world"
        assert not node.is_interactive

    def test_default_values(self):
        node = EnhancedDOMTreeNode(node_name="span")
        assert node.node_id == 0
        assert node.node_type == NodeType.ELEMENT_NODE
        assert node.is_visible is True
        assert node.is_interactive is False
        assert node.highlight_index is None
        assert node.parent_node is None
        assert node.children == []

    def test_parent_child_relationship(self):
        parent = EnhancedDOMTreeNode(node_name="div")
        child = EnhancedDOMTreeNode(node_name="span")
        child.parent_node = parent
        parent.children.append(child)

        assert len(parent.children) == 1
        assert parent.children[0] is child
        assert child.parent_node is parent


class TestEnhancedDOMTreeNodeInteractive:
    """可交互元素标记测试。"""

    def test_interactive_element_has_highlight_index(self):
        node = EnhancedDOMTreeNode(
            node_name="button",
            is_interactive=True,
            highlight_index=5,
        )
        assert node.is_interactive is True
        assert node.highlight_index == 5

    def test_scrollable_element_marked(self):
        node = EnhancedDOMTreeNode(
            node_name="div",
            attributes={"overflow": "scroll"},
            is_scrollable=True,
        )
        assert node.is_scrollable is True

    def test_ax_info_populated(self):
        node = EnhancedDOMTreeNode(
            node_name="input",
            ax_name="Search box",
            ax_role="textbox",
            is_focused=True,
        )
        assert node.ax_name == "Search box"
        assert node.ax_role == "textbox"
        assert node.is_focused is True


class TestSerializedDOMState:
    """SerializedDOMState 序列化输出测试。"""

    def test_create_empty_state(self):
        state = SerializedDOMState(text="", selector_map={})
        assert state.text == ""
        assert state.selector_map == {}

    def test_create_with_content(self):
        root = EnhancedDOMTreeNode(node_name="body", highlight_index=0)
        btn = EnhancedDOMTreeNode(node_name="button", highlight_index=1)
        state = SerializedDOMState(
            text="  <body> [0]\n    <button> [1]\n",
            selector_map={0: root, 1: btn},
        )
        assert "[0]" in state.text
        assert "[1]" in state.text
        assert state.selector_map[0] is root
        assert state.selector_map[1] is btn

    def test_selector_map_indices_are_ints(self):
        node = EnhancedDOMTreeNode(node_name="a", highlight_index=42)
        state = SerializedDOMState(text="<a> [42]", selector_map={42: node})
        k = next(iter(state.selector_map))
        assert isinstance(k, int)
        assert k == 42

    def test_serialized_dom_json(self):
        """验证 SerializedDOMState 可以序列化为 JSON（给 LLM 用）。"""
        root = EnhancedDOMTreeNode(node_name="html", highlight_index=0)
        state = SerializedDOMState(
            text="<html> [0]",
            selector_map={0: root},
        )
        d = state.model_dump()
        assert "text" in d
        assert "selector_map" in d
        json_str = json.dumps(d, default=str)
        assert len(json_str) > 10
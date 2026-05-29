"""DOM 序列化器测试 — TDD Phase 3.3"""

import pytest

from src.dom.views import EnhancedDOMTreeNode, NodeType, SerializedDOMState
from src.dom.serializer import DOMTreeSerializer


def _make_leaf(index: int, name: str, text: str = "") -> EnhancedDOMTreeNode:
    return EnhancedDOMTreeNode(
        node_name=name,
        node_value=text,
        is_interactive=True,
        highlight_index=index,
    )


def _make_container(name: str, children: list) -> EnhancedDOMTreeNode:
    node = EnhancedDOMTreeNode(node_name=name)
    node.children = children
    for c in children:
        c.parent_node = node
    return node


class TestDOMTreeSerializerBasic:
    """基础序列化测试。"""

    def test_serialize_empty_tree(self):
        root = EnhancedDOMTreeNode(node_name="body")
        state = DOMTreeSerializer.serialize(root)
        assert isinstance(state, SerializedDOMState)
        assert "body" in state.text

    def test_serialize_simple_tree(self):
        leaf = _make_leaf(0, "span", "hello")
        root = _make_container("div", [leaf])

        state = DOMTreeSerializer.serialize(root)
        assert isinstance(state, SerializedDOMState)
        assert "<div>" in state.text
        assert "<span>" in state.text
        assert "hello" in state.text

    def test_serialize_tree_with_interactive_elements(self):
        btn = _make_leaf(1, "button", "Click Me")
        link = _make_leaf(2, "a", "Go Here")
        root = _make_container("div", [btn, link])

        state = DOMTreeSerializer.serialize(root)
        assert "[1]" in state.text
        assert "[2]" in state.text

    def test_serialize_nested_tree(self):
        span = _make_leaf(3, "span", "nested")
        inner = _make_container("div", [span])
        root = _make_container("body", [inner])

        state = DOMTreeSerializer.serialize(root)
        lines = state.text.split("\n")
        depths = [len(line) - len(line.lstrip()) for line in lines if line.strip()]
        assert len(depths) > 1
        assert depths[1] > depths[0]

    def test_serialize_scrollable_container(self):
        div = EnhancedDOMTreeNode(
            node_name="div",
            is_scrollable=True,
            is_interactive=True,
            highlight_index=4,
        )
        root = _make_container("body", [div])

        state = DOMTreeSerializer.serialize(root)
        assert "|SCROLL|" in state.text

    def test_serialize_focused_element(self):
        inp = EnhancedDOMTreeNode(
            node_name="input",
            is_focused=True,
            is_interactive=True,
            highlight_index=5,
            attributes={"placeholder": "enter..."},
        )
        root = _make_container("form", [inp])

        state = DOMTreeSerializer.serialize(root)
        assert "[5]" in state.text
        assert "input" in state.text


class TestDOMTreeSerializerSelectorMap:
    """selector_map 索引正确性测试。"""

    def test_selector_map_contains_interactive_elements(self):
        btn = _make_leaf(10, "button", "Submit")
        txt = _make_leaf(11, "span", "Label")
        root = _make_container("div", [btn, txt])

        state = DOMTreeSerializer.serialize(root)
        assert len(state.selector_map) == 2
        assert 10 in state.selector_map
        assert 11 in state.selector_map
        assert state.selector_map[10].node_name == "button"
        assert state.selector_map[11].node_name == "span"

    def test_selector_map_indices_unique(self):
        nodes = [
            _make_leaf(i, "a", str(i))
            for i in range(5)
        ]
        root = _make_container("body", nodes)

        state = DOMTreeSerializer.serialize(root)
        indices = list(state.selector_map.keys())
        assert len(indices) == len(set(indices))
        assert len(indices) == 5

    def test_non_interactive_not_in_selector_map(self):
        leaf = EnhancedDOMTreeNode(
            node_name="div",
            node_value="plain text",
            is_interactive=False,
        )
        root = _make_container("body", [leaf])

        state = DOMTreeSerializer.serialize(root)
        assert len(state.selector_map) == 0


class TestDOMTreeSerializerIntegrationReady:
    """验证序列化器接口可被 DomService 使用。"""

    def test_serialize_accepts_root_node(self):
        root = EnhancedDOMTreeNode(node_name="html")
        state = DOMTreeSerializer.serialize(root)
        assert state.text != ""

    def test_serialized_state_is_serializable(self):
        btn = _make_leaf(1, "button", "Click")
        root = _make_container("body", [btn])
        state = DOMTreeSerializer.serialize(root)
        d = state.model_dump()
        assert isinstance(d, dict)
        assert "text" in d
        assert "selector_map" in d
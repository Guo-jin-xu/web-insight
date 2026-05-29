"""DomService 测试 — TDD Phase 3.3"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.dom.service import DomService


@pytest.fixture
def mock_browser():
    browser = MagicMock()
    browser.page = MagicMock()
    browser.page.url = "https://test.com"
    browser.page.title = AsyncMock(return_value="Test Page")
    browser.page.evaluate = AsyncMock(return_value={
        "nodeId": 0,
        "tagName": "body",
        "nodeType": 1,
        "attributes": {},
        "children": [
            {
                "nodeId": 1,
                "tagName": "button",
                "nodeType": 1,
                "attributes": {"aria-label": "Search"},
                "text": "Search",
                "children": [],
                "rect": {"x": 10, "y": 20, "width": 80, "height": 30},
                "isInteractive": True,
                "highlightIndex": 1,
                "scrollable": False,
            },
        ],
        "rect": {"x": 0, "y": 0, "width": 1280, "height": 720},
        "isInteractive": False,
        "scrollable": False,
    })
    return browser


class TestDomServiceBasic:
    """DomService 初始化测试。"""

    def test_init_stores_browser(self, mock_browser):
        service = DomService(mock_browser)
        assert service.browser is mock_browser

    def test_init_default_max_depth(self):
        service = DomService(MagicMock())
        assert service.max_depth == 8

    def test_init_custom_max_depth(self):
        service = DomService(MagicMock(), max_depth=3)
        assert service.max_depth == 3


class TestDomServiceTree:
    """DOM 树构建测试。"""

    @pytest.mark.asyncio
    async def test_get_dom_tree_returns_tree(self, mock_browser):
        service = DomService(mock_browser)
        tree = await service.get_dom_tree()
        assert tree.node_name == "body"
        assert len(tree.children) == 1

    @pytest.mark.asyncio
    async def test_get_dom_tree_preserves_child_tag(self, mock_browser):
        service = DomService(mock_browser)
        tree = await service.get_dom_tree()
        child = tree.children[0]
        assert child.node_name == "button"
        assert child.is_interactive is True

    @pytest.mark.asyncio
    async def test_get_dom_tree_preserves_attributes(self, mock_browser):
        service = DomService(mock_browser)
        tree = await service.get_dom_tree()
        child = tree.children[0]
        assert child.attributes.get("aria-label") == "Search"

    @pytest.mark.asyncio
    async def test_get_serialized_dom_returns_state(self, mock_browser):
        service = DomService(mock_browser)
        state = await service.get_serialized_dom()
        assert state.text != ""
        assert "body" in state.text
        assert "button" in state.text

    @pytest.mark.asyncio
    async def test_get_serialized_dom_builds_selector_map(self, mock_browser):
        service = DomService(mock_browser)
        state = await service.get_serialized_dom()
        assert len(state.selector_map) > 0

    @pytest.mark.asyncio
    async def test_get_clickable_elements_returns_interactive(self, mock_browser):
        service = DomService(mock_browser)
        elements = await service.get_clickable_elements()
        assert len(elements) == 1
        assert elements[0].node_name == "button"

    @pytest.mark.asyncio
    async def test_nested_tree_structure(self):
        browser = MagicMock()
        browser.page = MagicMock()
        browser.page.url = "https://test.com"
        browser.page.evaluate = AsyncMock(return_value={
            "nodeId": 0,
            "tagName": "div",
            "nodeType": 1,
            "attributes": {},
            "children": [
                {
                    "nodeId": 1,
                    "tagName": "ul",
                    "nodeType": 1,
                    "attributes": {},
                    "children": [
                        {
                            "nodeId": 2,
                            "tagName": "li",
                            "nodeType": 1,
                            "attributes": {},
                            "text": "item 1",
                            "children": [],
                            "rect": {"x": 0, "y": 0, "width": 100, "height": 20},
                            "isInteractive": True,
                            "highlightIndex": 1,
                            "scrollable": False,
                        },
                    ],
                    "rect": {"x": 0, "y": 0, "width": 200, "height": 40},
                    "isInteractive": False,
                    "scrollable": False,
                },
            ],
            "rect": {"x": 0, "y": 0, "width": 300, "height": 100},
            "isInteractive": False,
            "scrollable": False,
        })
        service = DomService(browser)
        tree = await service.get_dom_tree()
        assert tree.node_name == "div"
        ul = tree.children[0]
        assert ul.node_name == "ul"
        li = ul.children[0]
        assert li.node_name == "li"
        assert li.is_interactive is True


class TestDomServiceIntegrationReady:
    """验证接口可被 Agent 调用。"""

    def test_has_get_dom_tree(self):
        service = DomService(MagicMock())
        assert hasattr(service, "get_dom_tree")
        assert callable(service.get_dom_tree)

    def test_has_get_serialized_dom(self):
        service = DomService(MagicMock())
        assert hasattr(service, "get_serialized_dom")
        assert callable(service.get_serialized_dom)

    def test_has_get_clickable_elements(self):
        service = DomService(MagicMock())
        assert hasattr(service, "get_clickable_elements")
        assert callable(service.get_clickable_elements)
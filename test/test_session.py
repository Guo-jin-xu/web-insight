"""BrowserSession 单元测试 — TDD Phase 3.3"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.browser.session import BrowserSession


class MockPage:
    """模拟 Playwright Page 对象。"""

    def __init__(self, url="about:blank", title="Mock Page"):
        self.url = url
        self._title = title
        self._event_handlers: dict[str, list] = {}

    async def title(self):
        return self._title

    async def goto(self, url, **kwargs):
        self.url = url

    async def bring_to_front(self):
        pass

    def on(self, event, handler):
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)

    def emit(self, event, *args):
        for handler in self._event_handlers.get(event, []):
            handler(*args)


class MockContext:
    """模拟 Playwright BrowserContext。"""

    def __init__(self, pages=None):
        self.pages: list[MockPage] = pages or []

    async def new_page(self):
        page = MockPage()
        self.pages.append(page)
        return page


class MockBrowserManager:
    """模拟 BrowserManager。"""

    def __init__(self, pages=None):
        self._page = pages[0] if pages else MockPage()
        self.context = MockContext(pages=pages)


class TestBrowserSessionBasic:
    """基础功能测试。"""

    def test_init_stores_browser_manager(self):
        bm = MockBrowserManager()
        session = BrowserSession(bm)
        assert session.bm is bm

    def test_init_records_initial_page(self):
        page = MockPage(url="https://test.com", title="Test Page")
        bm = MockBrowserManager(pages=[page])
        session = BrowserSession(bm)
        assert session.current_page is page


class TestBrowserSessionTabs:
    """Tab 管理测试。"""

    @pytest.mark.asyncio
    async def test_get_tabs_returns_list(self):
        page = MockPage(url="https://test.com", title="Test")
        bm = MockBrowserManager(pages=[page])
        session = BrowserSession(bm)

        tabs = await session.get_tabs()
        assert isinstance(tabs, list)
        assert len(tabs) == 1
        assert tabs[0]["url"] == "https://test.com"

    @pytest.mark.asyncio
    async def test_switch_tab_valid_index(self):
        p1 = MockPage(url="https://page1.com", title="Page 1")
        p2 = MockPage(url="https://page2.com", title="Page 2")
        bm = MockBrowserManager(pages=[p1, p2])
        session = BrowserSession(bm)

        result = await session.switch_tab(1)
        assert result is p2
        assert session.bm._page is p2

    @pytest.mark.asyncio
    async def test_switch_tab_invalid_index(self):
        p1 = MockPage(url="https://page1.com", title="Page 1")
        bm = MockBrowserManager(pages=[p1])
        session = BrowserSession(bm)

        with pytest.raises(ValueError, match="Tab index"):
            await session.switch_tab(5)

    @pytest.mark.asyncio
    async def test_switch_tab_negative_index(self):
        p1 = MockPage(url="https://page1.com", title="Page 1")
        p2 = MockPage(url="https://page2.com", title="Page 2")
        bm = MockBrowserManager(pages=[p1, p2])
        session = BrowserSession(bm)

        with pytest.raises(ValueError, match="Tab index"):
            await session.switch_tab(-1)

    @pytest.mark.asyncio
    async def test_new_tab_default_url(self):
        bm = MockBrowserManager(pages=[MockPage()])
        session = BrowserSession(bm)

        page = await session.new_tab()
        assert page is not None
        assert page.url == "about:blank"

    @pytest.mark.asyncio
    async def test_new_tab_with_url(self):
        bm = MockBrowserManager(pages=[MockPage()])
        session = BrowserSession(bm)

        page = await session.new_tab("https://example.com")
        assert page.url == "https://example.com"


class TestBrowserSessionDialog:
    """弹窗处理测试。"""

    @pytest.mark.asyncio
    async def test_dialog_handler_accepts_alert(self):
        page = MockPage()
        bm = MockBrowserManager(pages=[page])
        session = BrowserSession(bm)
        session._setup_dialog_handler()

        dialog = MagicMock()
        dialog.accept = AsyncMock()
        dialog.type = "alert"
        dialog.message = "test alert"

        handler = page._event_handlers.get("dialog", [])[0]
        await handler(dialog)

        dialog.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_dialog_handler_accepts_confirm(self):
        page = MockPage()
        bm = MockBrowserManager(pages=[page])
        session = BrowserSession(bm)
        session._setup_dialog_handler()

        dialog = MagicMock()
        dialog.accept = AsyncMock()
        dialog.type = "confirm"
        dialog.message = "confirm?"

        handler = page._event_handlers.get("dialog", [])[0]
        await handler(dialog)

        dialog.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_dialog_handler_accepts_prompt(self):
        page = MockPage()
        bm = MockBrowserManager(pages=[page])
        session = BrowserSession(bm)
        session._setup_dialog_handler()

        dialog = MagicMock()
        dialog.accept = AsyncMock()
        dialog.type = "prompt"
        dialog.message = "enter value"

        handler = page._event_handlers.get("dialog", [])[0]
        await handler(dialog)

        dialog.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_dialog_handler_before_setup(self):
        page = MockPage()
        bm = MockBrowserManager(pages=[page])
        session = BrowserSession(bm)

        assert "dialog" not in page._event_handlers


class TestBrowserSessionIntegrationReady:
    """验证与 Agent 集成的接口。"""

    def test_get_tabs_signature(self):
        bm = MockBrowserManager()
        session = BrowserSession(bm)
        assert hasattr(session, "get_tabs")
        assert callable(session.get_tabs)

    def test_switch_tab_signature(self):
        bm = MockBrowserManager()
        session = BrowserSession(bm)
        assert hasattr(session, "switch_tab")
        assert callable(session.switch_tab)

    def test_new_tab_signature(self):
        bm = MockBrowserManager()
        session = BrowserSession(bm)
        assert hasattr(session, "new_tab")
        assert callable(session.new_tab)
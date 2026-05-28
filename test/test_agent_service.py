"""TDD: Agent 类测试。"""

import pytest


def _make_mock_llm():
    """创建一个 mock LLM，返回固定的 AgentOutput。"""
    from unittest.mock import AsyncMock, MagicMock

    from src.agent.views import AgentOutput

    mock = MagicMock()
    mock.ainvoke = AsyncMock(return_value=AgentOutput(
        thinking="mock thinking",
        evaluation_previous_goal="Success",
        memory="",
        next_goal="test goal",
        action=[],
    ))
    mock.model_name = "mock-model"
    return mock


def _make_mock_browser():
    """创建一个 mock BrowserManager。"""
    from unittest.mock import AsyncMock, MagicMock

    mock = MagicMock()
    mock.connect = AsyncMock()
    mock.disconnect = AsyncMock()
    mock.page = MagicMock()
    mock.page.url = "about:blank"
    mock.page.title = AsyncMock(return_value="Test Page")
    mock.get_page_html = AsyncMock(return_value="<html><body>Test</body></html>")
    mock.get_indexed_elements = AsyncMock(return_value=[
        {"index": 0, "tag": "a", "text": "Link 1", "bbox": {"x": 0, "y": 0, "w": 100, "h": 20}, "attributes": {}},
    ])
    return mock


def _make_mock_tool():
    """创建一个 mock tool。"""
    from unittest.mock import MagicMock

    tool = MagicMock()
    tool.name = "mock_tool"
    tool.description = "A mock tool"
    tool.ainvoke = MagicMock()
    return tool


class TestAgentConstruction:
    """Agent 类构造函数测试。"""

    def test_create_agent_minimal(self):
        from src.agent.service import Agent

        llm = _make_mock_llm()
        browser = _make_mock_browser()
        agent = Agent(task="test task", llm=llm, browser_session=browser, tools=[])

        assert agent.task == "test task"
        assert agent.llm == llm
        assert agent.browser_session == browser
        assert agent.tools == []

    def test_agent_state_initialized(self):
        from src.agent.service import Agent

        agent = Agent(
            task="test",
            llm=_make_mock_llm(),
            browser_session=_make_mock_browser(),
            tools=[],
        )
        assert agent.state.n_steps == 0
        assert agent.state.consecutive_failures == 0
        assert agent.state.stopped is False
        assert agent.state.session_initialized is False

    def test_agent_history_initialized(self):
        from src.agent.service import Agent

        agent = Agent(
            task="test",
            llm=_make_mock_llm(),
            browser_session=_make_mock_browser(),
            tools=[],
        )
        assert agent.history.history == []
        assert agent.history.is_done() is False

    def test_agent_config_params(self):
        from src.agent.service import Agent

        agent = Agent(
            task="test",
            llm=_make_mock_llm(),
            browser_session=_make_mock_browser(),
            tools=[],
            max_failures=3,
            use_vision=False,
            use_judge=True,
        )
        assert agent.max_failures == 3
        assert agent.use_vision is False
        assert agent.use_judge is True

    def test_agent_message_manager_initialized(self):
        from src.agent.service import Agent

        agent = Agent(
            task="test",
            llm=_make_mock_llm(),
            browser_session=_make_mock_browser(),
            tools=[],
        )
        assert agent.message_manager is not None
        assert len(agent.message_manager.messages) > 0


class TestAgentMultiAct:
    """multi_act 方法测试。"""

    @pytest.mark.asyncio
    async def test_multi_act_empty(self):
        from src.agent.service import Agent

        agent = Agent(
            task="test",
            llm=_make_mock_llm(),
            browser_session=_make_mock_browser(),
            tools=[],
        )
        results = await agent.multi_act([])
        assert results == []


class TestAgentRun:
    """run 方法测试。"""

    @pytest.mark.asyncio
    async def test_run_stops_on_max_steps(self):
        from unittest.mock import AsyncMock

        from src.agent.service import Agent
        from src.agent.views import AgentOutput

        llm = MagicMock()
        llm.ainvoke = AsyncMock(return_value=AgentOutput(
            thinking="step",
            evaluation_previous_goal="",
            memory="",
            next_goal="continue",
            action=[],
        ))

        agent = Agent(
            task="test",
            llm=llm,
            browser_session=_make_mock_browser(),
            tools=[],
        )
        history = await agent.run(max_steps=2)
        assert len(history.history) == 2
        assert agent.state.n_steps == 2

    @pytest.mark.asyncio
    async def test_run_stops_on_consecutive_failures(self):
        from unittest.mock import AsyncMock

        from src.agent.service import Agent
        from src.agent.views import AgentOutput

        llm = MagicMock()
        llm.ainvoke = AsyncMock(return_value=AgentOutput(
            thinking="will fail",
            evaluation_previous_goal="",
            memory="",
            next_goal="",
            action=[],
        ))

        agent = Agent(
            task="test",
            llm=llm,
            browser_session=_make_mock_browser(),
            tools=[],
            max_failures=1,
        )
        agent.state.consecutive_failures = 2
        history = await agent.run(max_steps=10)
        assert len(history.history) == 0
        assert agent.state.stopped is False

    @pytest.mark.asyncio
    async def test_run_stops_when_done(self):
        from unittest.mock import AsyncMock

        from src.agent.service import Agent
        from src.agent.views import ActionModel, AgentOutput

        llm = MagicMock()
        llm.ainvoke = AsyncMock(return_value=AgentOutput(
            thinking="done",
            evaluation_previous_goal="",
            memory="",
            next_goal="",
            action=[ActionModel(tool_name="done", tool_args={"summary": "任务完成"})],
        ))

        agent = Agent(
            task="test",
            llm=llm,
            browser_session=_make_mock_browser(),
            tools=[],
        )
        history = await agent.run(max_steps=5)
        assert history.is_done() is True


def _magic_mock():
    from unittest.mock import MagicMock
    return MagicMock()
MagicMock = _magic_mock


@pytest.mark.asyncio
async def test_run_stops_on_max_steps():
    from unittest.mock import AsyncMock

    from src.agent.service import Agent
    from src.agent.views import AgentOutput

    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=AgentOutput(
        thinking="step",
        evaluation_previous_goal="",
        memory="",
        next_goal="continue",
        action=[],
    ))

    agent = Agent(
        task="test",
        llm=llm,
        browser_session=_make_mock_browser(),
        tools=[],
    )
    history = await agent.run(max_steps=2)
    assert len(history.history) == 2
    assert agent.state.n_steps == 2
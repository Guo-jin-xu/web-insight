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


class TestAgentStepIntegration:
    """step() 方法 MessageManager 集成测试 — Task 4.0 修复验证。"""

    @pytest.mark.asyncio
    async def test_step_records_assistant_message(self):
        """step() 应将 LLM 输出写入 message_manager。"""
        from unittest.mock import AsyncMock

        from src.agent.service import Agent
        from src.agent.views import ActionModel, AgentOutput

        llm = MagicMock()
        llm.ainvoke = AsyncMock(return_value=AgentOutput(
            thinking="搜索天气信息",
            evaluation_previous_goal="",
            memory="",
            next_goal="获取惠州天气",
            action=[ActionModel(tool_name="done", tool_args={"summary": "天气结果"})],
        ))

        agent = Agent(
            task="test",
            llm=llm,
            browser_session=_make_mock_browser(),
            tools=[],
        )
        msg_count_before = len(agent.message_manager.messages)

        await agent.step()

        msg_count_after = len(agent.message_manager.messages)
        assert msg_count_after > msg_count_before, (
            f"step() 应将 LLM 输出和工具结果写入消息历史，"
            f"但消息数未增加 (before={msg_count_before}, after={msg_count_after})"
        )

    @pytest.mark.asyncio
    async def test_step_messages_contain_agent_output_and_tool_results(self):
        """step() 生成的消息应包含 <agent_output> 和 <tool_results> 标记。"""
        from unittest.mock import AsyncMock

        from src.agent.service import Agent
        from src.agent.views import ActionModel, AgentOutput

        llm = MagicMock()
        llm.ainvoke = AsyncMock(return_value=AgentOutput(
            thinking="搜索",
            evaluation_previous_goal="",
            memory="",
            next_goal="搜索",
            action=[ActionModel(tool_name="done", tool_args={"summary": "done"})],
        ))

        agent = Agent(
            task="test",
            llm=llm,
            browser_session=_make_mock_browser(),
            tools=[],
        )

        await agent.step()

        all_content = " ".join(
            m.content if hasattr(m, "content") else ""
            for m in agent.message_manager.messages
        )
        assert "<agent_output>" in all_content, (
            "step() 应将 LLM 输出以 <agent_output> 标记写入消息历史"
        )
        assert "<tool_results>" in all_content, (
            "step() 应将工具结果以 <tool_results> 标记写入消息历史"
        )

    @pytest.mark.asyncio
    async def test_step_triggers_maybe_compact(self):
        """step() 应在每步结束时尝试压缩消息。"""
        from unittest.mock import AsyncMock

        from src.agent.service import Agent
        from src.agent.views import ActionModel, AgentOutput

        llm = MagicMock()
        llm.ainvoke = AsyncMock(return_value=AgentOutput(
            thinking="step",
            evaluation_previous_goal="",
            memory="",
            next_goal="",
            action=[ActionModel(tool_name="done", tool_args={"summary": "done"})],
        ))

        agent = Agent(
            task="test",
            llm=llm,
            browser_session=_make_mock_browser(),
            tools=[],
        )

        original_maybe_compact = agent.message_manager.maybe_compact
        call_count = [0]

        def tracking_maybe_compact(llm_param):
            call_count[0] += 1
            return original_maybe_compact(llm_param)

        agent.message_manager.maybe_compact = tracking_maybe_compact

        await agent.step()

        assert call_count[0] > 0, (
            "step() 应在每步结束时调用 maybe_compact 防止上下文溢出"
        )

    @pytest.mark.asyncio
    async def test_multi_step_message_growth(self):
        """多步执行时，消息历史应持续增长（说明 Agent 记住了历史）。"""
        from unittest.mock import AsyncMock

        from src.agent.service import Agent
        from src.agent.views import ActionModel, AgentOutput

        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=[
            AgentOutput(
                thinking="step 1",
                evaluation_previous_goal="",
                memory="",
                next_goal="step 1",
                action=[],
            ),
            AgentOutput(
                thinking="step 2",
                evaluation_previous_goal="",
                memory="",
                next_goal="step 2",
                action=[],
            ),
            AgentOutput(
                thinking="done",
                evaluation_previous_goal="",
                memory="",
                next_goal="done",
                action=[ActionModel(tool_name="done", tool_args={"summary": "done"})],
            ),
        ])

        agent = Agent(
            task="test multi-step",
            llm=llm,
            browser_session=_make_mock_browser(),
            tools=[],
        )

        history = await agent.run(max_steps=3)

        assert len(history.history) == 3, f"应执行 3 步，实际 {len(history.history)}"
        assert agent.state.n_steps == 3

        msg_count = len(agent.message_manager.messages)
        assert msg_count >= 4, (
            f"多步执行后消息历史应包含多个步骤的记录，"
            f"当前仅 {msg_count} 条消息（初始=2，每步至少+2=assistant+tool_results）"
        )


class TestAgentPlannerIntegration:
    """TaskPlanner 进度追踪集成测试 — Task 4.5 修复验证。

    所有测试使用 run(max_steps=1) 而非 step()，因为 add_plan() 在 run() 中调用。
    """

    @pytest.mark.asyncio
    async def test_run_initializes_plan(self):
        """run() 应初始化任务计划器创建计划步骤。"""
        from unittest.mock import AsyncMock

        from src.agent.service import Agent
        from src.agent.views import ActionModel, AgentOutput

        llm = MagicMock()
        llm.ainvoke = AsyncMock(return_value=AgentOutput(
            thinking="searching",
            evaluation_previous_goal="",
            memory="",
            next_goal="search",
            action=[ActionModel(tool_name="done", tool_args={"summary": "done"})],
        ))

        agent = Agent(
            task="搜索天气预报",
            llm=llm,
            browser_session=_make_mock_browser(),
            tools=[],
        )

        await agent.run(max_steps=1)

        assert len(agent.task_planner.state.plan) > 0, (
            "run() 应通过 add_plan() 初始化计划步骤"
        )

    @pytest.mark.asyncio
    async def test_planner_step_marked_complete_after_success(self):
        """全成功步骤执行后，第一个计划步骤应被标记为 COMPLETED。"""
        from unittest.mock import AsyncMock

        from src.agent.planning import PlanStatus
        from src.agent.service import Agent
        from src.agent.views import ActionModel, AgentOutput

        llm = MagicMock()
        llm.ainvoke = AsyncMock(return_value=AgentOutput(
            thinking="done",
            evaluation_previous_goal="",
            memory="",
            next_goal="done",
            action=[ActionModel(tool_name="done", tool_args={"summary": "done"})],
        ))

        agent = Agent(
            task="搜索天气预报",
            llm=llm,
            browser_session=_make_mock_browser(),
            tools=[],
        )

        await agent.run(max_steps=1)

        first_step = agent.task_planner.state.plan[0]
        assert first_step.status == PlanStatus.COMPLETED, (
            f"成功执行后，第一个计划步骤应为 COMPLETED，"
            f"但当前状态为 {first_step.status}: {first_step.description}"
        )

    @pytest.mark.asyncio
    async def test_planner_advances_on_successful_step(self):
        """全成功步骤执行后任务计划器应推进到下一步。"""
        from unittest.mock import AsyncMock

        from src.agent.planning import PlanStatus
        from src.agent.service import Agent
        from src.agent.views import ActionModel, AgentOutput

        llm = MagicMock()
        llm.ainvoke = AsyncMock(return_value=AgentOutput(
            thinking="step 1 done",
            evaluation_previous_goal="",
            memory="",
            next_goal="next step",
            action=[ActionModel(tool_name="done", tool_args={"summary": "step done"})],
        ))

        agent = Agent(
            task="搜索天气预报",
            llm=llm,
            browser_session=_make_mock_browser(),
            tools=[],
        )
        assert agent.task_planner.state.current_step == 0, "初始步骤应为 0"

        await agent.run(max_steps=1)

        completed_or_advanced = (
            agent.task_planner.state.current_step > 0
            or agent.task_planner.state.plan[0].status == PlanStatus.COMPLETED
        )
        assert completed_or_advanced, (
            f"成功步骤后，计划应标记当前步骤为完成或推进到下一步，"
            f"但当前步骤仍为 {agent.task_planner.state.current_step}，"
            f"计划状态: {agent.task_planner.summary()}"
        )
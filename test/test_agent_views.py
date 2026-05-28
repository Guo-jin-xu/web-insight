"""TDD: AgentOutput / ActionModel / AgentHistory / AgentState 模型测试。"""

import pytest
from pydantic import ValidationError


class TestActionModel:
    """ActionModel: 单步工具调用模型。"""

    def test_create_action_model(self):
        from src.agent.views import ActionModel

        action = ActionModel(tool_name="search", tool_args={"query": "test"})
        assert action.tool_name == "search"
        assert action.tool_args == {"query": "test"}

    def test_action_model_default_args(self):
        from src.agent.views import ActionModel

        action = ActionModel(tool_name="navigate")
        assert action.tool_args == {}

    def test_action_model_requires_tool_name(self):
        from src.agent.views import ActionModel

        with pytest.raises(ValidationError):
            ActionModel()


class TestAgentOutput:
    """AgentOutput: 每步结构化输出。"""

    def test_create_agent_output_full(self):
        from src.agent.views import ActionModel, AgentOutput

        output = AgentOutput(
            thinking="页面是搜索结果",
            evaluation_previous_goal="Success: 搜索成功",
            memory="搜索结果为 10 条",
            next_goal="点击第一个结果",
            action=[ActionModel(tool_name="click_element", tool_args={"index": 0})],
        )
        assert output.thinking == "页面是搜索结果"
        assert output.evaluation_previous_goal == "Success: 搜索成功"
        assert output.memory == "搜索结果为 10 条"
        assert output.next_goal == "点击第一个结果"
        assert len(output.action) == 1
        assert output.action[0].tool_name == "click_element"

    def test_create_agent_output_minimal(self):
        from src.agent.views import AgentOutput

        output = AgentOutput(
            thinking="test",
            evaluation_previous_goal="",
            memory="",
            next_goal="",
            action=[],
        )
        assert output.thinking == "test"
        assert output.action == []

    def test_agent_output_defaults(self):
        from src.agent.views import AgentOutput

        output = AgentOutput()
        assert output.thinking == ""
        assert output.evaluation_previous_goal == ""
        assert output.memory == ""
        assert output.next_goal == ""
        assert output.action == []

    def test_agent_output_is_done_detection(self):
        from src.agent.views import ActionModel, AgentOutput

        output_with_done = AgentOutput(
            thinking="任务完成",
            evaluation_previous_goal="",
            memory="",
            next_goal="",
            action=[ActionModel(tool_name="done", tool_args={"summary": "done"})],
        )
        output_without_done = AgentOutput(
            thinking="继续",
            evaluation_previous_goal="",
            memory="",
            next_goal="",
            action=[ActionModel(tool_name="click_element", tool_args={"index": 0})],
        )
        assert output_with_done.is_done is True
        assert output_without_done.is_done is False


class TestAgentState:
    """AgentState: Agent 运行时状态。"""

    def test_agent_state_defaults(self):
        from src.agent.views import AgentState

        state = AgentState()
        assert state.n_steps == 0
        assert state.consecutive_failures == 0
        assert state.last_model_output is None
        assert state.last_result is None
        assert state.paused is False
        assert state.stopped is False
        assert state.session_initialized is False

    def test_agent_state_mutable(self):
        from src.agent.views import AgentState

        state = AgentState()
        state.n_steps = 5
        state.consecutive_failures = 2
        state.paused = True
        assert state.n_steps == 5
        assert state.consecutive_failures == 2
        assert state.paused is True


class TestAgentHistory:
    """AgentHistory / AgentHistoryList: 历史记录模型。"""

    def test_agent_history_list_empty(self):
        from src.agent.views import AgentHistoryList

        hist = AgentHistoryList()
        assert hist.history == []

    def test_agent_history_list_final_result_none(self):
        from src.agent.views import AgentHistoryList

        hist = AgentHistoryList()
        assert hist.final_result() is None

    def test_agent_history_list_final_result_returns_last(self):
        from src.agent.views import ActionModel, AgentHistory, AgentHistoryList, AgentOutput

        h1 = AgentHistory(
            model_output=AgentOutput(thinking="step 1",
                                     evaluation_previous_goal="",
                                     memory="",
                                     next_goal="",
                                     action=[ActionModel(tool_name="navigate", tool_args={})]),
            result=[],
            state=None,
        )
        h2 = AgentHistory(
            model_output=AgentOutput(thinking="done",
                                     evaluation_previous_goal="",
                                     memory="",
                                     next_goal="",
                                     action=[ActionModel(tool_name="done", tool_args={"summary": "最终结果内容"})]),
            result=[],
            state=None,
        )
        hist = AgentHistoryList(history=[h1, h2])
        result = hist.final_result()
        assert result is not None
        assert "最终结果内容" in result

    def test_agent_history_list_is_done(self):
        from src.agent.views import ActionModel, AgentHistory, AgentHistoryList, AgentOutput

        h1 = AgentHistory(
            model_output=AgentOutput(thinking="done",
                                     evaluation_previous_goal="",
                                     memory="",
                                     next_goal="",
                                     action=[ActionModel(tool_name="done", tool_args={"summary": "ok"})]),
            result=[],
            state=None,
        )
        hist = AgentHistoryList(history=[h1])
        assert hist.is_done() is True
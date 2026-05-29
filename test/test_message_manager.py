"""MessageManager 单元测试 — TDD Phase 3.2"""

import pytest
from unittest.mock import MagicMock

from langchain_core.messages import HumanMessage, SystemMessage

from src.agent.message_manager import MessageManager


class TestMessageManagerBasic:
    """基础功能测试。"""

    def test_init_creates_system_and_user_messages(self):
        mgr = MessageManager(task="test task", system_prompt="you are a helper")
        messages = mgr.get_messages()
        assert len(messages) == 2
        assert isinstance(messages[0], SystemMessage)
        assert messages[0].content == "you are a helper"
        assert isinstance(messages[1], HumanMessage)
        assert "test task" in messages[1].content

    def test_add_state_message_appends(self):
        mgr = MessageManager(task="test", system_prompt="prompt")
        mgr.add_state_message("URL: https://example.com")
        messages = mgr.get_messages()
        assert len(messages) == 3
        assert "URL: https://example.com" in messages[2].content

    def test_estimate_tokens_returns_positive(self):
        mgr = MessageManager(task="test task", system_prompt="you are a helper")
        tokens = mgr.estimate_tokens()
        assert tokens > 0

    def test_estimate_tokens_grows_with_messages(self):
        mgr = MessageManager(task="short", system_prompt="short")
        base = mgr.estimate_tokens()
        for _ in range(5):
            mgr.add_state_message("long message " * 20)
        larger = mgr.estimate_tokens()
        assert larger > base

    def test_compact_triggered_when_over_threshold(self):
        mgr = MessageManager(task="test", system_prompt="prompt", max_tokens=50, keep_recent=1)
        mgr.add_state_message("x" * 200)
        mgr.add_state_message("y" * 200)

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "compressed summary"
        mock_llm.invoke.return_value = mock_response

        assert mgr.estimate_tokens() > 50
        result = mgr.maybe_compact(mock_llm)
        assert result is True
        mock_llm.invoke.assert_called_once()

        messages = mgr.get_messages()
        assert "compressed summary" in messages[2].content

    def test_compact_skips_when_under_threshold(self):
        mgr = MessageManager(task="test", system_prompt="prompt", max_tokens=100000)

        mock_llm = MagicMock()
        result = mgr.maybe_compact(mock_llm)
        assert result is False
        mock_llm.invoke.assert_not_called()


class TestMessageManagerCompaction:
    """压缩行为测试。"""

    def test_compacted_messages_keep_recent_steps(self):
        mgr = MessageManager(task="test", system_prompt="prompt", max_tokens=30, keep_recent=1)

        mgr.add_state_message("step 1 state")
        mgr.add_assistant_message("step 1 output")
        mgr.add_tool_results("step 1 result")
        mgr.add_state_message("step 2 state")
        mgr.add_assistant_message("step 2 output")
        mgr.add_tool_results("step 2 result")

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "summary"
        mock_llm.invoke.return_value = mock_response

        result = mgr.maybe_compact(mock_llm)
        assert result is True

        messages = mgr.get_messages()
        messages_text = " ".join(
            m.content if hasattr(m, "content") else "" for m in messages
        )
        assert "summary" in messages_text
        assert "step 2 state" in messages_text
        assert "step 2 output" in messages_text
        assert "step 2 result" in messages_text

    def test_compacted_removes_old_steps(self):
        mgr = MessageManager(task="test", system_prompt="prompt", max_tokens=30, keep_recent=1)

        mgr.add_state_message("old step 1 state")
        mgr.add_assistant_message("old step 1 output")
        mgr.add_tool_results("old step 1 result")
        mgr.add_state_message("old step 2 state")
        mgr.add_assistant_message("old step 2 output")
        mgr.add_tool_results("old step 2 result")
        mgr.add_state_message("recent step state")
        mgr.add_assistant_message("recent step output")
        mgr.add_tool_results("recent step result")

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "compacted_summary"
        mock_llm.invoke.return_value = mock_response

        result = mgr.maybe_compact(mock_llm)
        assert result is True

        messages = mgr.get_messages()
        messages_text = " ".join(
            m.content if hasattr(m, "content") else "" for m in messages
        )
        assert "compacted_summary" in messages_text
        assert "old step 1" not in messages_text
        assert "old step 2" not in messages_text
        assert "recent step" in messages_text

    def test_compacted_summary_position(self):
        mgr = MessageManager(task="test", system_prompt="prompt", max_tokens=30, keep_recent=0)

        mgr.add_state_message("old step")
        mgr.add_assistant_message("old output")
        mgr.add_tool_results("old results")

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "my summary"
        mock_llm.invoke.return_value = mock_response

        mgr.maybe_compact(mock_llm)

        messages = mgr.get_messages()
        assert messages[0].content == "prompt"
        assert "my summary" in messages[2].content


class TestMessageManagerHistory:
    """历史消息管理测试。"""

    def test_add_state_message_with_step_info(self):
        mgr = MessageManager(task="test", system_prompt="prompt")
        assert len(mgr._step_boundaries) == 0
        mgr.add_state_message("browser state")
        assert len(mgr._step_boundaries) == 1

    def test_add_assistant_store_in_history(self):
        mgr = MessageManager(task="test", system_prompt="prompt")
        mgr.add_assistant_message("model output text")
        messages = mgr.get_messages()
        assert any("model output text" in str(m) for m in messages)

    def test_add_tool_results_store_in_history(self):
        mgr = MessageManager(task="test", system_prompt="prompt")
        mgr.add_tool_results("tool result text")
        messages = mgr.get_messages()
        assert any("tool result text" in str(m) for m in messages)

    def test_keep_recent_zero_keeps_no_history(self):
        mgr = MessageManager(task="test", system_prompt="prompt", max_tokens=20, keep_recent=0)

        mgr.add_state_message("old step")
        mgr.add_assistant_message("old output")
        mgr.add_tool_results("old result")

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "summary"
        mock_llm.invoke.return_value = mock_response

        mgr.maybe_compact(mock_llm)

        messages = mgr.get_messages()
        messages_text = " ".join(
            m.content if hasattr(m, "content") else "" for m in messages
        )
        assert "old step" not in messages_text
"""LoopDetector 单元测试 — TDD Phase 3.1"""

import pytest

from src.agent.loop_detector import LoopDetector


class TestLoopDetectorBasic:
    """基础功能测试。"""

    def test_init_with_default_window(self):
        detector = LoopDetector()
        assert detector.window_size == 10
        assert detector.recent_action_keys == []

    def test_init_with_custom_window(self):
        detector = LoopDetector(window_size=5)
        assert detector.window_size == 5

    def test_record_single_action_no_effect(self):
        detector = LoopDetector()
        detector.record("click", {"index": 1}, "https://example.com")
        nudge = detector.get_nudge()
        assert nudge is None


class TestLoopDetectorActionRepetition:
    """重复 action 检测。"""

    def test_detect_repeated_same_action(self):
        detector = LoopDetector()
        for _ in range(4):
            detector.record("click", {"index": 1}, "https://example.com")
        nudge = detector.get_nudge()
        assert nudge is not None
        assert "重复" in nudge

    def test_no_detection_when_actions_vary(self):
        detector = LoopDetector()
        detector.record("click", {"index": 1}, "https://example.com")
        detector.record("click", {"index": 2}, "https://example.com")
        detector.record("type", {"index": 3, "text": "hello"}, "https://example.com")
        detector.record("navigate", {"url": "https://other.com"}, "https://other.com")
        nudge = detector.get_nudge()
        assert nudge is None

    def test_escalating_nudge_levels(self):
        detector = LoopDetector(window_size=20)

        for _ in range(3):
            detector.record("click", {"index": 1}, "https://example.com")
        nudge_low = detector.get_nudge()
        assert nudge_low is not None
        assert "建议" in nudge_low

        for _ in range(3):
            detector.record("click", {"index": 1}, "https://example.com")
        nudge_med = detector.get_nudge()
        assert nudge_med is not None
        assert "警告" in nudge_med

        for _ in range(4):
            detector.record("click", {"index": 1}, "https://example.com")
        nudge_high = detector.get_nudge()
        assert nudge_high is not None
        assert "严重" in nudge_high

    def test_nudge_resets_after_different_action(self):
        detector = LoopDetector(window_size=10)
        for _ in range(4):
            detector.record("click", {"index": 1}, "https://example.com")
        assert detector.get_nudge() is not None

        detector.record("navigate", {"url": "https://new.com"}, "https://new.com")
        assert detector.get_nudge() is None

    def test_normalized_search_actions(self):
        detector = LoopDetector()
        detector.record("search", {"query": "hello world"}, "https://google.com")
        detector.record("search", {"query": "hello world"}, "https://google.com")
        detector.record("search", {"query": "hello world"}, "https://google.com")
        nudge = detector.get_nudge()
        assert nudge is not None


class TestLoopDetectorPageStagnation:
    """页面停滞检测。"""

    def test_detect_page_stagnation(self):
        detector = LoopDetector()
        for _ in range(5):
            detector.record("click", {"index": 1}, "https://example.com")
        nudge = detector.get_nudge()
        assert nudge is not None
        assert "停滞" in nudge or "页面" in nudge

    def test_stagnation_resets_on_url_change(self):
        detector = LoopDetector()
        for _ in range(3):
            detector.record("click", {"index": 1}, "https://example.com")
        detector.record("navigate", {"url": "https://new.com"}, "https://new.com")
        nudge = detector.get_nudge()
        assert nudge is None

    def test_stagnation_combined_with_action_repetition(self):
        detector = LoopDetector()
        for _ in range(6):
            detector.record("click", {"index": 5}, "https://stuck.com")
        nudge = detector.get_nudge()
        assert nudge is not None
        assert len(nudge) > 50


class TestLoopDetectorWindow:
    """滑动窗口边界测试。"""

    def test_window_slides_out_old_actions(self):
        detector = LoopDetector(window_size=5)

        for i in range(6):
            detector.record("click", {"index": i}, f"https://example.com/page{i}")

        nudge = detector.get_nudge()
        assert nudge is None

    def test_window_keeps_recent_only(self):
        detector = LoopDetector(window_size=10)

        for _ in range(4):
            detector.record("click", {"index": 1}, "https://example.com")
        for _ in range(7):
            detector.record("click", {"index": 2}, "https://example.com")

        nudge = detector.get_nudge()
        assert nudge is not None
        assert "7" in nudge or "6" in nudge or "5" in nudge

    def test_edge_case_zero_actions(self):
        detector = LoopDetector()
        assert detector.get_nudge() is None
        assert detector.consecutive_same_action == 0
        assert detector.consecutive_same_url == 0

    def test_edge_case_single_action(self):
        detector = LoopDetector()
        detector.record("click", {"index": 1}, "https://example.com")
        nudge = detector.get_nudge()
        assert nudge is None


class TestLoopDetectorIntegrationReady:
    """验证与 Agent 集成所需的接口。"""

    def test_record_signature_matches_agent_needs(self):
        detector = LoopDetector()
        detector.record("click", {"index": 1}, "https://example.com")
        assert len(detector.recent_action_keys) == 1

    def test_get_nudge_returns_string_or_none(self):
        detector = LoopDetector()
        result = detector.get_nudge()
        assert result is None or isinstance(result, str)
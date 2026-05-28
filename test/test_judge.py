"""TDD: Agent Judge 机制测试。"""

import pytest


class TestJudgementResult:
    """JudgementResult: Judge 验证结果模型。"""

    def test_create_judgement_pass(self):
        from src.agent.judge import JudgementResult

        result = JudgementResult(
            verdict=True,
            reason="页面包含目标内容",
            evidence="找到 LangChain 教程标题",
        )
        assert result.verdict is True
        assert "目标内容" in result.reason
        assert "LangChain" in result.evidence

    def test_create_judgement_fail(self):
        from src.agent.judge import JudgementResult

        result = JudgementResult(
            verdict=False,
            reason="页面 404 错误",
            evidence="当前页面显示 Not Found",
        )
        assert result.verdict is False
        assert "404" in result.reason

    def test_judgement_result_defaults(self):
        from src.agent.judge import JudgementResult

        result = JudgementResult()
        assert result.verdict is False
        assert result.reason == ""
        assert result.evidence == ""


class TestJudgeStepFunction:
    """judge_step: 评估单步执行结果。"""

    def test_judge_step_with_no_results(self):
        from src.agent.judge import judge_step

        result = judge_step(step_results=[])
        assert result.verdict is True
        assert result.reason == "No actions to evaluate"

    def test_judge_step_all_success(self):
        from src.agent.judge import judge_step
        from src.schemas.tool_result import ActionResult

        results = [
            ActionResult(success=True, extracted_content="已导航"),
            ActionResult(success=True, extracted_content="已点击"),
        ]
        result = judge_step(step_results=results)
        assert result.verdict is True

    def test_judge_step_has_failure(self):
        from src.agent.judge import judge_step
        from src.schemas.tool_result import ActionResult

        results = [
            ActionResult(success=True, extracted_content="已导航"),
            ActionResult(success=False, error="元素未找到"),
        ]
        result = judge_step(step_results=results)
        assert result.verdict is False
        assert "失败" in result.reason

    def test_judge_step_has_done(self):
        from src.agent.judge import judge_step
        from src.schemas.tool_result import ActionResult

        results = [
            ActionResult(success=True, extracted_content="已提取内容"),
            ActionResult(is_done=True, success=True, extracted_content="任务完成"),
        ]
        result = judge_step(step_results=results)
        assert result.verdict is True
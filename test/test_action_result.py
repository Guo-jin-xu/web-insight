"""TDD: ActionResult 模型测试。"""


class TestActionResult:
    """ActionResult: 工具执行结果模型。"""

    def test_create_action_result_success(self):
        from src.schemas.tool_result import ActionResult

        result = ActionResult(
            success=True,
            extracted_content="页面标题: 百度",
        )
        assert result.success is True
        assert result.is_done is False
        assert result.error is None
        assert result.extracted_content == "页面标题: 百度"

    def test_create_action_result_failure(self):
        from src.schemas.tool_result import ActionResult

        result = ActionResult(
            success=False,
            error="连接超时",
        )
        assert result.success is False
        assert result.error == "连接超时"

    def test_create_action_result_done(self):
        from src.schemas.tool_result import ActionResult

        result = ActionResult(
            is_done=True,
            success=True,
            extracted_content="任务完成总结",
        )
        assert result.is_done is True
        assert result.extracted_content == "任务完成总结"

    def test_action_result_defaults(self):
        from src.schemas.tool_result import ActionResult

        result = ActionResult()
        assert result.is_done is False
        assert result.success is True
        assert result.extracted_content == ""
        assert result.error is None
        assert result.long_term_memory == ""
        assert result.include_in_memory is False
        assert result.screenshot is None

    def test_action_result_to_text_success(self):
        from src.schemas.tool_result import ActionResult

        result = ActionResult(
            success=True,
            extracted_content="已导航到: https://example.com",
        )
        text = result.to_text()
        assert "已导航到" in text

    def test_action_result_to_text_error(self):
        from src.schemas.tool_result import ActionResult

        result = ActionResult(
            success=False,
            error="Timeout connecting to page",
        )
        text = result.to_text()
        assert "Timeout" in text

    def test_action_result_include_in_memory(self):
        from src.schemas.tool_result import ActionResult

        result = ActionResult(
            success=True,
            extracted_content="重要信息",
            include_in_memory=True,
            long_term_memory="记住这个页面结构",
        )
        assert result.include_in_memory is True
        assert result.long_term_memory == "记住这个页面结构"

    def test_action_result_screenshot(self):
        from src.schemas.tool_result import ActionResult

        result = ActionResult(
            success=True,
            screenshot="data/screenshots/step_1.png",
        )
        assert result.screenshot == "data/screenshots/step_1.png"
"""TDD: get_current_time 工具测试。"""

from datetime import datetime


class TestGetCurrentTimeTool:
    def test_tool_exists_and_is_callable(self):
        from src.tools.time_tool import get_current_time

        result = get_current_time.invoke({})
        assert isinstance(result, str)
        assert len(result) > 0

    def test_result_contains_current_year(self):
        from src.tools.time_tool import get_current_time

        result = get_current_time.invoke({})
        current_year = str(datetime.now().year)
        assert current_year in result, f"Expected result to contain year '{current_year}'"

    def test_result_contains_month_and_day(self):
        from src.tools.time_tool import get_current_time

        result = get_current_time.invoke({})
        now = datetime.now()
        assert str(now.month) in result
        assert str(now.day) in result

    def test_result_contains_weekday(self):
        from src.tools.time_tool import get_current_time

        result = get_current_time.invoke({})
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        assert any(wd in result for wd in weekdays), f"Expected weekday in '{result}'"

    def test_result_contains_time_of_day(self):
        from src.tools.time_tool import get_current_time

        result = get_current_time.invoke({})
        assert ":" in result, f"Expected ':' in result: '{result}'"

    def test_result_format_is_consistent(self):
        from src.tools.time_tool import get_current_time

        result = get_current_time.invoke({})
        assert "年" in result
        assert "月" in result
        assert "日" in result
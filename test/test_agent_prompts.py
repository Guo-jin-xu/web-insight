"""TDD: 增强 System Prompt 测试。"""


class TestSystemPrompt:
    """get_system_prompt: 生成 Agent 系统提示。"""

    def test_returns_non_empty_string(self):
        from src.agent.prompts import get_system_prompt

        prompt = get_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 100

    def test_contains_agent_role(self):
        from src.agent.prompts import get_system_prompt

        prompt = get_system_prompt()
        assert "浏览器" in prompt
        assert "自动化" in prompt

    def test_contains_output_format(self):
        from src.agent.prompts import get_system_prompt

        prompt = get_system_prompt()
        assert "thinking" in prompt
        assert "evaluation_previous_goal" in prompt
        assert "next_goal" in prompt
        assert "action" in prompt

    def test_contains_browser_rules(self):
        from src.agent.prompts import get_system_prompt

        prompt = get_system_prompt()
        assert "index" in prompt.lower()

    def test_contains_tool_usage_strategy(self):
        from src.agent.prompts import get_system_prompt

        prompt = get_system_prompt()
        assert "done" in prompt.lower()
        assert "DOM" in prompt or "dom" in prompt

    def test_custom_site_experience(self):
        from src.agent.prompts import get_system_prompt

        prompt = get_system_prompt(site_experience="bing.com 在搜索结果页用 get_page_links")
        assert "bing.com" in prompt

    def test_override_system_message(self):
        from src.agent.prompts import get_system_prompt

        prompt = get_system_prompt(override_system_message="CUSTOM OVERRIDE")
        assert prompt == "CUSTOM OVERRIDE"

    def test_extend_system_message(self):
        from src.agent.prompts import get_system_prompt

        prompt = get_system_prompt(extend_system_message="EXTRA RULE: always use visual_analyze")
        assert "EXTRA RULE" in prompt
        assert "浏览器" in prompt


class TestCurrentTimeInjection:
    def test_prompt_contains_current_time_section(self):
        from src.agent.prompts import get_system_prompt

        prompt = get_system_prompt()
        assert "当前时间" in prompt

    def test_prompt_contains_current_year(self):
        from datetime import datetime
        from src.agent.prompts import get_system_prompt

        prompt = get_system_prompt()
        current_year = str(datetime.now().year)
        assert current_year in prompt, f"Expected prompt to contain year '{current_year}'"

    def test_prompt_contains_month_and_day(self):
        from datetime import datetime
        from src.agent.prompts import get_system_prompt

        prompt = get_system_prompt()
        now = datetime.now()
        assert str(now.month) in prompt
        assert str(now.day) in prompt

    def test_prompt_contains_weekday(self):
        from src.agent.prompts import get_system_prompt

        prompt = get_system_prompt()
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        assert any(wd in prompt for wd in weekdays), "Expected prompt to contain weekday"

    def test_prompt_still_works_with_override(self):
        from src.agent.prompts import get_system_prompt

        prompt = get_system_prompt(override_system_message="CUSTOM")
        assert prompt == "CUSTOM"


class TestConversationSystemPrompt:
    def test_conversation_prompt_contains_current_time(self):
        from datetime import datetime
        from src.agent.prompts import get_conversation_system_prompt

        prompt = get_conversation_system_prompt()
        assert "当前时间" in prompt

        current_year = str(datetime.now().year)
        assert current_year in prompt, f"Expected conversation prompt to contain year '{current_year}'"

    def test_conversation_prompt_contains_weekday(self):
        from src.agent.prompts import get_conversation_system_prompt

        prompt = get_conversation_system_prompt()
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        assert any(wd in prompt for wd in weekdays)

    def test_conversation_prompt_contains_role_description(self):
        from src.agent.prompts import get_conversation_system_prompt

        prompt = get_conversation_system_prompt()
        assert "AI 助手" in prompt or "有帮助" in prompt
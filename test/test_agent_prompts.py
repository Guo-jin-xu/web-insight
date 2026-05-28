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
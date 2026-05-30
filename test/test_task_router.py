"""任务路由测试 — TDD: 区分"网页操作任务"和"日常对话"。"""

import pytest

from src.agent.router import classify_query, QueryType


class TestQueryType:
    def test_query_type_values(self):
        assert QueryType.WEB_TASK == "web_task"
        assert QueryType.CONVERSATION == "conversation"

    def test_query_type_comparison(self):
        assert QueryType.WEB_TASK != QueryType.CONVERSATION


class TestClassifyQuery:
    """classify_query 核心分类逻辑。"""

    # ── 网页操作任务 ──

    @pytest.mark.parametrize("query", [
        "搜索惠州最近几天的天气如何",
        "在百度搜索Python教程",
        "搜索最新新闻",
        "帮我查一下今天的股价",
        "查找资料",
    ])
    def test_search_queries_are_web_tasks(self, query: str):
        assert classify_query(query) == QueryType.WEB_TASK

    @pytest.mark.parametrize("query", [
        "打开百度首页",
        "打开https://www.example.com",
        "访问GitHub",
        "导航到淘宝",
        "浏览知乎热榜",
    ])
    def test_navigate_queries_are_web_tasks(self, query: str):
        assert classify_query(query) == QueryType.WEB_TASK

    @pytest.mark.parametrize("query", [
        "填写这个表单",
        "帮我注册一个账号",
        "登录这个网站",
        "提交订单",
    ])
    def test_form_queries_are_web_tasks(self, query: str):
        assert classify_query(query) == QueryType.WEB_TASK

    @pytest.mark.parametrize("query", [
        "点击页面上的登录按钮",
        "帮我点击提交",
        "输入用户名和密码",
        "滚动到页面底部",
        "提取这篇文章的内容",
    ])
    def test_action_queries_are_web_tasks(self, query: str):
        assert classify_query(query) == QueryType.WEB_TASK

    def test_url_in_query_is_web_task(self):
        assert classify_query("帮我看看 https://example.com 这个网站") == QueryType.WEB_TASK

    # ── 日常对话 ──

    @pytest.mark.parametrize("query", [
        "你是哪个模型",
        "你好",
        "今天星期几",
        "你能做什么",
        "介绍一下你自己",
        "1+1等于几",
        "什么是人工智能",
        "讲个笑话",
        "天气真好啊",
    ])
    def test_conversational_queries_are_conversation(self, query: str):
        assert classify_query(query) == QueryType.CONVERSATION

    def test_empty_query_is_conversation(self):
        assert classify_query("") == QueryType.CONVERSATION

    def test_greeting_is_conversation(self):
        assert classify_query("hello world") == QueryType.CONVERSATION

    def test_model_question_is_conversation(self):
        assert classify_query("你用的是哪个大模型") == QueryType.CONVERSATION

    def test_code_question_is_conversation(self):
        assert classify_query("帮我写一个Python排序函数") == QueryType.CONVERSATION
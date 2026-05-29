"""任务规划测试 — TDD Phase 3.5"""

import pytest

from src.agent.planning import PlanItem, PlanStatus, PlanningState, TaskPlanner


class TestPlanItem:
    """PlanItem 模型测试。"""

    def test_create_plan_item(self):
        item = PlanItem(step=1, description="打开浏览器")
        assert item.step == 1
        assert item.description == "打开浏览器"
        assert item.status == PlanStatus.PENDING

    def test_plan_item_default_status(self):
        item = PlanItem(step=2, description="搜索关键词")
        assert item.status == PlanStatus.PENDING

    def test_plan_item_optional_goal(self):
        item = PlanItem(step=3, description="提交", expected_result="页面跳转成功")
        assert item.expected_result == "页面跳转成功"

    def test_plan_item_str_representation(self):
        item = PlanItem(step=1, description="打开浏览器", status=PlanStatus.COMPLETED)
        s = str(item)
        assert "打开浏览器" in s
        assert "completed" in s


class TestPlanStatus:
    """PlanStatus 枚举测试。"""

    def test_status_values(self):
        assert PlanStatus.PENDING == "pending"
        assert PlanStatus.IN_PROGRESS == "in_progress"
        assert PlanStatus.COMPLETED == "completed"
        assert PlanStatus.FAILED == "failed"

    def test_status_comparison(self):
        assert PlanStatus.PENDING != PlanStatus.COMPLETED


class TestPlanningState:
    """PlanningState 模型测试。"""

    def test_create_empty_plan(self):
        state = PlanningState()
        assert state.plan == []
        assert state.current_step == 0

    def test_create_plan_with_items(self):
        items = [
            PlanItem(step=1, description="step one"),
            PlanItem(step=2, description="step two"),
        ]
        state = PlanningState(plan=items, current_step=0)
        assert len(state.plan) == 2
        assert state.current_step == 0

    def test_replan_on_stall_default(self):
        state = PlanningState()
        assert state.replan_on_stall is True

    def test_replan_on_stall_custom(self):
        state = PlanningState(replan_on_stall=False)
        assert state.replan_on_stall is False


class TestTaskPlanner:
    """TaskPlanner 核心逻辑测试。"""

    def test_add_plan(self):
        planner = TaskPlanner()
        planner.add_plan("搜索天气预报")
        assert len(planner.state.plan) > 0

    def test_builtin_plan_structure(self):
        """验证内置计划模板包含合适步骤。"""
        planner = TaskPlanner()
        planner.add_plan("在百度搜索Python教程")
        assert len(planner.state.plan) >= 2
        descriptions = [item.description for item in planner.state.plan]
        assert any("导航" in d for d in descriptions)

    def test_current_step_none_for_empty_plan(self):
        planner = TaskPlanner()
        assert planner.current_step() is None

    def test_current_step_returns_pending(self):
        planner = TaskPlanner()
        planner.state.plan = [
            PlanItem(step=1, description="打开页面", status=PlanStatus.COMPLETED),
            PlanItem(step=2, description="搜索", status=PlanStatus.PENDING),
        ]
        planner.state.current_step = 1
        step = planner.current_step()
        assert step is not None
        assert step.description == "搜索"

    def test_mark_complete(self):
        planner = TaskPlanner()
        planner.state.plan = [
            PlanItem(step=1, description="打开"),
            PlanItem(step=2, description="搜索"),
        ]
        planner.mark_complete(0)
        assert planner.state.plan[0].status == PlanStatus.COMPLETED
        assert planner.state.plan[1].status == PlanStatus.PENDING

    def test_mark_failed(self):
        planner = TaskPlanner()
        planner.state.plan = [PlanItem(step=1, description="打开")]
        planner.mark_failed(0, "网络错误")
        assert planner.state.plan[0].status == PlanStatus.FAILED
        assert "网络错误" in planner.state.plan[0].failure_reason

    def test_advance_to_next(self):
        planner = TaskPlanner()
        planner.state.plan = [
            PlanItem(step=1, description="step 1"),
            PlanItem(step=2, description="step 2"),
        ]
        planner.state.current_step = 0
        planner.mark_complete(0)
        result = planner.advance()
        assert result is True
        assert planner.state.current_step == 1

    def test_advance_at_end_returns_false(self):
        planner = TaskPlanner()
        planner.state.plan = [PlanItem(step=1, description="step 1")]
        planner.state.current_step = 0
        planner.mark_complete(0)
        result = planner.advance()
        assert result is False
        assert planner.state.current_step == 0

    def test_should_replan_when_enabled(self):
        planner = TaskPlanner()
        planner.state.replan_on_stall = True
        planner.ticks_since_progress = 5
        assert planner.should_replan() is True

    def test_should_not_replan_when_disabled(self):
        planner = TaskPlanner()
        planner.state.replan_on_stall = False
        planner.ticks_since_progress = 10
        assert planner.should_replan() is False

    def test_should_not_replan_below_threshold(self):
        planner = TaskPlanner()
        planner.state.replan_on_stall = True
        planner.ticks_since_progress = 2
        assert planner.should_replan() is False

    def test_tick_increments_counter(self):
        planner = TaskPlanner()
        assert planner.ticks_since_progress == 0
        planner.tick()
        assert planner.ticks_since_progress == 1
        planner.tick()
        assert planner.ticks_since_progress == 2

    def test_reset_ticks(self):
        planner = TaskPlanner()
        planner.ticks_since_progress = 5
        planner.reset_ticks()
        assert planner.ticks_since_progress == 0

    def test_is_complete_all_done(self):
        planner = TaskPlanner()
        planner.state.plan = [
            PlanItem(step=1, description="done", status=PlanStatus.COMPLETED),
        ]
        assert planner.is_complete() is True

    def test_is_not_complete_with_pending(self):
        planner = TaskPlanner()
        planner.state.plan = [
            PlanItem(step=1, description="done", status=PlanStatus.COMPLETED),
            PlanItem(step=2, description="pending", status=PlanStatus.PENDING),
        ]
        assert planner.is_complete() is False

    def test_plan_summary(self):
        planner = TaskPlanner()
        planner.state.plan = [
            PlanItem(step=1, description="打开", status=PlanStatus.COMPLETED),
            PlanItem(step=2, description="搜索", status=PlanStatus.IN_PROGRESS),
            PlanItem(step=3, description="提交", status=PlanStatus.PENDING),
        ]
        summary = planner.summary()
        assert "completed" in summary
        assert "in_progress" in summary
        assert "pending" in summary
        assert "打开" in summary
        assert "搜索" in summary
        assert "提交" in summary


class TestTaskPlannerIntegrationReady:
    """验证接口可被 Agent 调用。"""

    def test_add_plan_accepts_string(self):
        planner = TaskPlanner()
        planner.add_plan("test task")
        assert len(planner.state.plan) > 0

    def test_planner_stateless_api(self):
        """TaskPlanner 可在 Agent step 循环中调用。"""
        planner = TaskPlanner()
        planner.add_plan("搜索")
        assert planner.current_step() is not None
        step = planner.current_step()
        planner.mark_complete(planner.state.current_step)
        planner.advance()
        planner.tick()
        assert planner.ticks_since_progress > 0
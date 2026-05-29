"""任务规划器 — 将复杂任务拆解为子步骤，跟踪进度。

Phase 3.5: 教学简化版，使用内置模板 + 规则生成计划步骤。
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class PlanStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class PlanItem(BaseModel):
    step: int
    description: str
    expected_result: str = ""
    failure_reason: str = ""
    status: PlanStatus = PlanStatus.PENDING

    def __str__(self) -> str:
        return f"[{self.status.value}] Step {self.step}: {self.description}"


class PlanningState(BaseModel):
    plan: list[PlanItem] = Field(default_factory=list)
    current_step: int = 0
    replan_on_stall: bool = True


_STEP_TEMPLATES: dict[str, list[str]] = {
    "search_default": [
        "导航到搜索引擎首页",
        "在搜索框中输入关键词并提交",
        "等待搜索结果加载完成",
        "浏览搜索结果并提取关键信息",
        "汇报搜索结果",
    ],
    "navigate": [
        "打开目标网站",
        "等待页面加载完成",
        "浏览页面主要内容",
        "执行目标操作",
        "确认操作结果",
    ],
    "form": [
        "打开表单页面",
        "定位表单字段",
        "填写表单信息",
        "提交表单",
        "确认提交结果",
    ],
    "info_extract": [
        "打开目标页面",
        "等待内容加载",
        "提取关键信息",
        "整理和汇总信息",
    ],
}

_SEARCH_KEYWORDS = ("搜索", "查找", "找到", "查找", "百度", "Google", "bing", "search")
_NAVIGATE_KEYWORDS = ("打开", "访问", "导航", "打开网站", "浏览")
_FORM_KEYWORDS = ("填写", "表单", "提交", "注册", "登录")


def _classify_task(task: str) -> list[str]:
    task_lower = task.lower()
    for kw in _SEARCH_KEYWORDS:
        if kw in task_lower:
            return _STEP_TEMPLATES["search_default"]
    for kw in _FORM_KEYWORDS:
        if kw in task_lower:
            return _STEP_TEMPLATES["form"]
    for kw in _NAVIGATE_KEYWORDS:
        if kw in task_lower:
            return _STEP_TEMPLATES["navigate"]
    return _STEP_TEMPLATES["info_extract"]


class TaskPlanner:
    REBUILD_THRESHOLD: int = 5

    def __init__(self):
        self.state = PlanningState()
        self.ticks_since_progress: int = 0

    def add_plan(self, task: str) -> None:
        steps = _classify_task(task)
        self.state.plan = [
            PlanItem(step=i + 1, description=desc)
            for i, desc in enumerate(steps)
        ]
        self.state.current_step = 0
        if self.state.plan:
            self.state.plan[0].status = PlanStatus.IN_PROGRESS

    def current_step(self) -> PlanItem | None:
        if not self.state.plan:
            return None
        idx = self.state.current_step
        if idx < len(self.state.plan):
            return self.state.plan[idx]
        return None

    def mark_complete(self, step_index: int) -> None:
        if 0 <= step_index < len(self.state.plan):
            self.state.plan[step_index].status = PlanStatus.COMPLETED

    def mark_failed(self, step_index: int, reason: str) -> None:
        if 0 <= step_index < len(self.state.plan):
            self.state.plan[step_index].status = PlanStatus.FAILED
            self.state.plan[step_index].failure_reason = reason

    def advance(self) -> bool:
        next_idx = self.state.current_step + 1
        if next_idx < len(self.state.plan):
            self.state.current_step = next_idx
            self.state.plan[next_idx].status = PlanStatus.IN_PROGRESS
            return True
        return False

    def should_replan(self) -> bool:
        return self.state.replan_on_stall and self.ticks_since_progress >= self.REBUILD_THRESHOLD

    def tick(self) -> None:
        self.ticks_since_progress += 1

    def reset_ticks(self) -> None:
        self.ticks_since_progress = 0

    def is_complete(self) -> bool:
        if not self.state.plan:
            return True
        return all(item.status == PlanStatus.COMPLETED for item in self.state.plan)

    def summary(self) -> str:
        lines = []
        for item in self.state.plan:
            marker = ""
            if item.status == PlanStatus.COMPLETED:
                marker = "[completed]"
            elif item.status == PlanStatus.IN_PROGRESS:
                marker = "[in_progress]"
            elif item.status == PlanStatus.FAILED:
                marker = f"[failed: {item.failure_reason}]"
            else:
                marker = "[pending]"
            lines.append(f"  {marker} Step {item.step}: {item.description}")
        return "\n".join(lines)
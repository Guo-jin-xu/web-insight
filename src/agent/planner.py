"""Planning 规划系统 — 任务分解为步骤计划。

功能：
- 将用户任务分解为 PlanItem 列表
- 跟踪每步执行状态
- 停滞检测时自动重规划
"""

import logging

from pydantic import BaseModel, ConfigDict, field_validator

logger = logging.getLogger(__name__)

VALID_STATUSES = {"pending", "in_progress", "done", "failed"}


class PlanItem(BaseModel):
    """规划步骤。"""

    model_config = ConfigDict(validate_assignment=True)

    step: int
    description: str
    expected_outcome: str
    status: str = "pending"

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"status 必须是 {VALID_STATUSES} 之一，收到: {v}")
        return v


class Plan(BaseModel):
    """执行计划。"""

    task: str = ""
    items: list[PlanItem] = []

    @property
    def pending_items(self) -> list[PlanItem]:
        return [i for i in self.items if i.status == "pending"]

    @property
    def pending_count(self) -> int:
        return len(self.pending_items)

    @property
    def is_completed(self) -> bool:
        return self.pending_count == 0 and len(self.items) > 0


class Planner:
    """任务规划器 — 将用户任务分解为步骤计划。

    当前为规则版（不依赖 LLM），后续可扩展为 LLM-based。
    """

    def generate_plan(self, task: str) -> dict:
        """根据任务生成执行计划。

        Args:
            task: 用户任务描述

        Returns:
            {"task": str, "items": [{"step": 1, "description": "...", "expected_outcome": "...", "status": "pending"}, ...]}
        """
        # 规则版：根据任务关键词生成通用步骤
        task_lower = task.lower()

        if any(kw in task_lower for kw in ["搜索", "天气", "查询", "查"]):
            items = [
                {"step": 1, "description": "导航到搜索引擎或目标网站", "expected_outcome": "页面加载完成", "status": "pending"},
                {"step": 2, "description": "输入搜索关键词", "expected_outcome": "搜索词已输入", "status": "pending"},
                {"step": 3, "description": "提交搜索并等待结果", "expected_outcome": "搜索结果页面加载", "status": "pending"},
                {"step": 4, "description": "提取搜索结果内容", "expected_outcome": "获取目标信息", "status": "pending"},
                {"step": 5, "description": "总结结果并结束任务", "expected_outcome": "任务完成", "status": "pending"},
            ]
        elif any(kw in task_lower for kw in ["登录", "登陆", "login", "sign"]):
            items = [
                {"step": 1, "description": "导航到登录页面", "expected_outcome": "登录页加载完成", "status": "pending"},
                {"step": 2, "description": "填写用户名", "expected_outcome": "用户名已输入", "status": "pending"},
                {"step": 3, "description": "填写密码", "expected_outcome": "密码已输入", "status": "pending"},
                {"step": 4, "description": "点击登录按钮", "expected_outcome": "登录成功", "status": "pending"},
            ]
        elif any(kw in task_lower for kw in ["视频", "b站", "bilibili", "播放"]):
            items = [
                {"step": 1, "description": "导航到目标网站", "expected_outcome": "首页加载完成", "status": "pending"},
                {"step": 2, "description": "搜索目标内容", "expected_outcome": "搜索结果展示", "status": "pending"},
                {"step": 3, "description": "点击目标内容进入详情页", "expected_outcome": "详情页加载完成", "status": "pending"},
                {"step": 4, "description": "执行目标操作（播放/下载等）", "expected_outcome": "操作完成", "status": "pending"},
                {"step": 5, "description": "总结完成并结束任务", "expected_outcome": "任务完成", "status": "pending"},
            ]
        else:
            # 通用步骤
            items = [
                {"step": 1, "description": "分析任务目标，导航到目标页面", "expected_outcome": "页面加载完成", "status": "pending"},
                {"step": 2, "description": "执行页面交互操作", "expected_outcome": "交互完成", "status": "pending"},
                {"step": 3, "description": "提取或验证结果", "expected_outcome": "获取目标信息", "status": "pending"},
                {"step": 4, "description": "总结并结束任务", "expected_outcome": "任务完成", "status": "pending"},
            ]

        return {"task": task, "items": items}

    def replan(
        self,
        task: str,
        current_plan: list[dict],
        stalled_step: int,
        reason: str,
    ) -> dict:
        """当某步骤停滞时重新规划。

        Args:
            task: 原始任务
            current_plan: 当前计划
            stalled_step: 停滞的步骤号
            reason: 停滞原因

        Returns:
            新的执行计划
        """
        logger.info(f"步骤 {stalled_step} 停滞: {reason}，重新规划...")

        # 简单策略：从停滞步骤开始生成新计划
        new_plan = self.generate_plan(task)
        remaining = current_plan[stalled_step - 1:] if stalled_step <= len(current_plan) else current_plan

        # 标记停滞步骤为 failed
        for item in remaining:
            item_copy = dict(item)
            if item_copy["step"] == stalled_step:
                item_copy["status"] = "failed"
            new_plan["items"].insert(0, item_copy)

        # 重新编号
        for i, item in enumerate(new_plan["items"], 1):
            item["step"] = i

        return new_plan

    def format_for_prompt(self, plan_items: list[dict]) -> str:
        """格式化计划为 system prompt 可注入的文本。

        Args:
            plan_items: 计划步骤列表

        Returns:
            格式化的文本
        """
        if not plan_items:
            return "（无计划）"

        lines = ["## 执行计划"]
        for item in plan_items:
            step = item["step"]
            desc = item["description"]
            expected = item.get("expected_outcome", "")
            status = item.get("status", "pending")
            status_icon = {
                "pending": "[未完成]",
                "in_progress": "[执行中]",
                "done": "[已完成]",
                "failed": "[失败]",
            }.get(status, "")

            lines.append(f"  Step {step} {status_icon} {desc} → {expected}")

        return "\n".join(lines)
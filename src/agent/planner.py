"""Planning 规划系统 — 基于 LLM 的任务分解为步骤计划。

功能：
- 使用 LLM 将用户任务分解为 PlanItem 列表
- 跟踪每步执行状态
"""

import logging

from pydantic import BaseModel, ConfigDict, field_validator

from src.llm.client import LLMClient

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
    """任务规划器 — 基于 LLM 的任务分解。

    使用 LLM 根据任务描述生成执行计划。
    若 LLM 不可用，回退到通用步骤模板。
    """

    def __init__(self, llm_client: LLMClient | None = None):
        """
        Args:
            llm_client: LLM 客户端，用于生成计划
        """
        self.llm_client = llm_client

    async def generate_plan(self, task: str) -> dict:
        """根据任务生成执行计划。

        Args:
            task: 用户任务描述

        Returns:
            {"task": str, "items": [{"step": 1, "description": "...", "expected_outcome": "...", "status": "pending"}, ...]}
        """
        if self.llm_client is None:
            return self._fallback_plan(task)

        messages = self._build_plan_messages(task)

        try:
            response = await self.llm_client.chat(messages, temperature=0.3)
            content = response.content.strip()
            return self._parse_plan_response(task, content)
        except Exception as e:
            logger.warning(f"Planner LLM 生成计划失败，回退到通用模板: {e}")
            return self._fallback_plan(task)

    def _build_plan_messages(self, task: str) -> list[dict]:
        """构建计划生成的 LLM 消息。"""
        system_prompt = (
            "你是一个任务规划助手。你的职责是将用户的任务分解为清晰的执行步骤。\n\n"
            "要求：\n"
            "1. 每个步骤应包含：step(序号), description(操作描述), expected_outcome(预期结果)\n"
            "2. 步骤应具体、可执行，避免过于笼统\n"
            "3. 对于网页操作任务，典型步骤包括：导航→搜索/交互→提取信息→总结\n"
            "4. 步骤数量适中（通常 3-7 步）\n\n"
            "你必须以 JSON 格式返回计划，不要添加任何其他文字：\n"
            '{"items": [{"step": 1, "description": "...", "expected_outcome": "..."}, ...]}'
        )

        user_prompt = f"请为以下任务制定执行计划：\n\n{task}"

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _parse_plan_response(self, task: str, content: str) -> dict:
        """解析 LLM 返回的计划。"""
        import json

        # 尝试从 markdown 代码块提取
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        # 尝试提取 JSON 对象
        try:
            data = json.loads(content)
            items = data.get("items", [])
            if items:
                # 确保每个 item 有 status 字段
                for item in items:
                    item.setdefault("status", "pending")
                return {"task": task, "items": items}
        except (json.JSONDecodeError, ValueError):
            pass

        # 尝试从文本中提取 JSON 对象
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(content[start:end + 1])
                items = data.get("items", [])
                if items:
                    for item in items:
                        item.setdefault("status", "pending")
                    return {"task": task, "items": items}
            except (json.JSONDecodeError, ValueError):
                pass

        logger.warning(f"Planner 无法解析 LLM 响应，回退到通用模板: {content[:100]}...")
        return self._fallback_plan(task)

    def _fallback_plan(self, task: str) -> dict:
        """通用步骤模板（LLM 不可用时的回退）。"""
        items = [
            {"step": 1, "description": "导航到目标网站或搜索引擎", "expected_outcome": "页面加载完成", "status": "pending"},
            {"step": 2, "description": "执行页面交互（搜索/点击/输入等）", "expected_outcome": "交互完成，获取目标内容", "status": "pending"},
            {"step": 3, "description": "提取或验证所需信息", "expected_outcome": "获取目标信息", "status": "pending"},
            {"step": 4, "description": "总结结果并结束任务", "expected_outcome": "任务完成", "status": "pending"},
        ]
        return {"task": task, "items": items}

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

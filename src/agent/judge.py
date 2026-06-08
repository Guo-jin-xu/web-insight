"""Self-Judge 自我评估系统 — 每步执行后评估动作质量。

评估维度：
- 动作是否合理（符合任务目标）
- 进度是否符合预期
- 是否需要调整策略

反馈注入：评估结果注入下一步上下文消息，引导 LLM 自我纠错。
"""

import json
import logging

from pydantic import BaseModel, field_validator

logger = logging.getLogger(__name__)

VALID_EVALUATIONS = {"success", "failure", "partial"}


class JudgeResult(BaseModel):
    """Judge 评估结果。"""

    evaluation: str  # success / failure / partial
    reasoning: str = ""
    suggestion: str = ""

    @field_validator("evaluation")
    @classmethod
    def validate_evaluation(cls, v: str) -> str:
        if v not in VALID_EVALUATIONS:
            raise ValueError(f"evaluation 必须是 {VALID_EVALUATIONS} 之一，收到: {v}")
        return v

    @property
    def is_success(self) -> bool:
        return self.evaluation == "success"


class Judge:
    """自我评估器 — 评估每步动作质量。

    不依赖 LLM（简化版），基于规则评估：
    - 动作执行成功 → success
    - 动作失败但有替代方案 → partial
    - 动作完全失败 → failure

    可扩展为 LLM-based 评估。
    """

    # 不需要 LLM 即可工作的评估规则（简化版）
    # 后续可扩展为 LLM-based

    def construct_messages(
        self,
        task: str,
        last_action: dict,
        result: str,
        step_count: int = 0,
    ) -> list[dict]:
        """构建评估上下文消息（用于后续 LLM-based Judge 扩展）。

        Args:
            task: 原始任务描述
            last_action: 最近执行的动作 {"tool": "...", "args": {...}}
            result: 动作执行结果
            step_count: 当前步数

        Returns:
            评估上下文消息列表
        """
        prompt = (
            f"## 任务\n{task}\n\n"
            f"## 第 {step_count} 步动作\n"
            f"工具: {last_action.get('tool', 'unknown')}\n"
            f"参数: {json.dumps(last_action.get('args', {}), ensure_ascii=False)}\n"
            f"结果: {result[:500]}\n\n"
            f"## 评估\n"
            f"请评估该动作：{{'evaluation': 'success'|'failure'|'partial', "
            f"'reasoning': '...', 'suggestion': '...'}}"
        )
        return [{"role": "user", "content": prompt}]

    def evaluate(
        self,
        task: str,
        last_action: dict,
        result: str,
        step_count: int = 0,
    ) -> JudgeResult:
        """评估单步动作（简化规则版）。

        规则：
        - 结果以 "工具执行失败" 开头 → failure
        - done 动作结果不为空 → success
        - 结果非空 → success
        - 结果为空 → partial

        Args:
            task: 原始任务描述
            last_action: 最近执行的动作
            result: 动作执行结果
            step_count: 当前步数

        Returns:
            JudgeResult 评估结果
        """
        tool_name = last_action.get("tool", "")
        result_str = str(result) if result else ""

        if result_str.startswith("工具执行失败"):
            return JudgeResult(
                evaluation="failure",
                reasoning=f"{tool_name} 执行失败: {result_str[:100]}",
                suggestion=f"尝试不同的方式完成 {tool_name}，或跳过此步骤",
            )

        if tool_name == "done":
            return JudgeResult(
                evaluation="success",
                reasoning="任务完成",
                suggestion="",
            )

        if result_str.strip():
            return JudgeResult(
                evaluation="success",
                reasoning=f"{tool_name} 执行成功",
                suggestion="",
            )
        else:
            return JudgeResult(
                evaluation="partial",
                reasoning=f"{tool_name} 返回空结果",
                suggestion="检查是否需要调整参数或换一种方式",
            )

    def parse_result(self, llm_response: str) -> JudgeResult:
        """解析 LLM 返回的评估结果（用于 LLM-based Judge 扩展）。

        Args:
            llm_response: LLM 返回的 JSON 字符串

        Returns:
            JudgeResult
        """
        try:
            data = json.loads(llm_response)
            return JudgeResult(**data)
        except (json.JSONDecodeError, ValueError) as e:
            logger.debug(f"Judge 解析 LLM 响应失败: {e}")
            return JudgeResult(
                evaluation="success",
                reasoning=f"无法解析 Judge 结果，默认继续 ({str(e)[:50]})",
                suggestion="",
            )
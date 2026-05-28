from pydantic import BaseModel, Field

from src.schemas.tool_result import ActionResult


class JudgementResult(BaseModel):
    verdict: bool = Field(default=False, description="是否通过验证")
    reason: str = Field(default="", description="判断原因")
    evidence: str = Field(default="", description="证据")


def judge_step(step_results: list[ActionResult]) -> JudgementResult:
    """评估单步执行结果。

    基于 ActionResult 列表判断当前步骤是否成功。
    - 无 action: verdict=True（没有失败就是成功）
    - 所有 action 成功: verdict=True
    - 任一 action 失败: verdict=False
    - 任一 action is_done: verdict=True（任务完成标记）
    """
    if not step_results:
        return JudgementResult(verdict=True, reason="No actions to evaluate")

    failures = [r for r in step_results if not r.success]
    done_actions = [r for r in step_results if r.is_done]

    if failures:
        reasons = [f"{f.error or '未知错误'}" for f in failures]
        return JudgementResult(
            verdict=False,
            reason=f"操作失败: {'; '.join(reasons)}",
        )

    if done_actions:
        return JudgementResult(
            verdict=True,
            reason="任务完成标记已触发",
            evidence=done_actions[0].extracted_content,
        )

    return JudgementResult(
        verdict=True,
        reason="全部操作成功",
    )
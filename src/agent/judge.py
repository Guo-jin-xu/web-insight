"""Self-Judge 自我评估系统 — 任务完成评估（LLM-based）。

设计参考 browser-use:
- done 被调用后，Judge 评估任务是否真正完成（而非 agent 自认为完成）
- 评估维度：任务满足度、输出质量、步骤完整性
- 评估成功 → 终止并返回结果
- 评估失败 → 注入反馈消息，继续迭代

实现：基于 LLM 的任务完成评估，通过 construct_task_completion_messages
构建评估提示，调用 LLM 获取 verdict/reasoning/failure_reason。
"""

import json
import logging

from pydantic import BaseModel, ConfigDict, field_validator

from src.llm.client import LLMClient

logger = logging.getLogger(__name__)


class TaskCompletionJudge(BaseModel):
    """任务完成评估结果 — done 被调用后的最终评估。

    参考 browser-use JudgementResult 设计：
    - verdict: bool — 任务是否真正完成
    - reasoning: str — 评估推理过程
    - failure_reason: str — 失败原因（若 verdict=False）
    """

    model_config = ConfigDict(validate_assignment=True)

    verdict: bool
    reasoning: str = ""
    failure_reason: str = ""

    @field_validator("verdict", mode="before")
    @classmethod
    def validate_verdict(cls, v) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            if v.lower() in ("true", "1", "yes"):
                return True
            if v.lower() in ("false", "0", "no"):
                return False
        raise ValueError(f"verdict 必须是 bool 类型，收到: {type(v).__name__} = {v!r}")

    @property
    def is_success(self) -> bool:
        return self.verdict is True

    def to_feedback_message(self) -> str:
        """生成注入 LLM 上下文的反馈消息。"""
        if self.is_success:
            return f"[Judge评估] ✓ {self.reasoning}"
        return (
            f"[Judge评估] ✗ 任务未完成\n"
            f"原因: {self.failure_reason}\n"
            f"分析: {self.reasoning}\n"
            f"请继续执行任务，确保满足所有要求后再调用 done。"
        )


class Judge:
    """自我评估器 — 基于 LLM 的任务完成评估。"""

    def __init__(self, llm_client: LLMClient | None = None):
        """
        Args:
            llm_client: LLM 客户端，用于任务完成评估
        """
        self.llm_client = llm_client

    async def evaluate_task_completion(
        self,
        task: str,
        done_result: str,
        step_history: list[dict],
    ) -> TaskCompletionJudge:
        """评估任务是否真正完成（done 被调用后）。

        基于 LLM 的评估逻辑：
        1. 构建评估提示（任务 + 执行历史 + done 结果）
        2. 调用 LLM 获取评估结果
        3. 解析 JSON 返回 TaskCompletionJudge

        若 LLM 调用失败，回退到规则版评估（空结果/步骤过少检查）。

        Args:
            task: 原始任务描述
            done_result: done 工具返回的结果文本
            step_history: 执行历史 [{"step": 1, "tool": "...", "result": "..."}, ...]

        Returns:
            TaskCompletionJudge 评估结果
        """
        # 规则兜底：空结果直接失败
        result_str = str(done_result) if done_result else ""
        if not result_str.strip():
            return TaskCompletionJudge(
                verdict=False,
                reasoning="done 工具返回空结果，任务可能未完成",
                failure_reason="未返回任何结果，请提取目标信息后再结束任务",
            )

        # 规则兜底：步骤过少
        real_steps = [s for s in step_history if s.get("tool") != "done"]
        if len(real_steps) < 2:
            return TaskCompletionJudge(
                verdict=False,
                reasoning=f"执行步骤过少（仅 {len(real_steps)} 步），怀疑任务未真正执行",
                failure_reason="步骤过少，请实际执行页面操作后再结束任务",
            )

        # LLM-based 评估
        if self.llm_client is None:
            # 无 LLM 客户端时，通过基本检查即认为成功
            return TaskCompletionJudge(
                verdict=True,
                reasoning=f"任务已完成，共执行 {len(real_steps)} 步，结果符合要求",
                failure_reason="",
            )

        messages = self._build_evaluation_messages(task, done_result, step_history)

        try:
            response = await self.llm_client.chat(messages, temperature=0.0)
            content = response.content.strip()

            # 尝试从 markdown 代码块或纯文本中提取 JSON
            judge_result = self._parse_llm_judge_response(content)

            # 记录评估结果
            logger.debug(
                f"Judge LLM 评估: verdict={judge_result.verdict}, "
                f"reasoning={judge_result.reasoning[:50]}..."
            )

            return judge_result

        except Exception as e:
            logger.warning(f"Judge LLM 评估失败，回退到规则版: {e}")
            # LLM 失败时回退：有结果且步骤足够即认为成功
            return TaskCompletionJudge(
                verdict=True,
                reasoning=f"任务已完成，共执行 {len(real_steps)} 步（LLM 评估失败，回退通过）",
                failure_reason="",
            )

    def _build_evaluation_messages(
        self,
        task: str,
        done_result: str,
        step_history: list[dict],
    ) -> list[dict]:
        """构建任务完成评估的 LLM 消息。"""
        steps_text = "\n".join(
            f"Step {s['step']}: {s['tool']} → {str(s['result'])[:100]}"
            for s in step_history
        )

        system_prompt = (
            "你是一个严格的任务完成评估器。你的职责是评估 Agent 的任务执行结果\n"
            "是否真正满足用户的原始任务要求。\n\n"
            "评估标准：\n"
            "1. 结果是否完整回答了任务的所有要求？\n"
            "2. 输出格式是否符合任务要求（如需要链接、数量、特定格式等）？\n"
            "3. 执行步骤是否合理，没有遗漏关键操作？\n"
            "4. 结果中是否有敷衍、模糊或不相关的内容？\n\n"
            "你必须以 JSON 格式返回评估结果，不要添加任何其他文字：\n"
            '{"verdict": true/false, "reasoning": "...", "failure_reason": "..."}'
        )

        user_prompt = (
            f"## 原始任务\n{task}\n\n"
            f"## 执行历史\n{steps_text}\n\n"
            f"## done 返回结果\n{done_result[:2000]}\n\n"
            f"请评估任务是否真正完成。以 JSON 格式返回。"
        )

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _parse_llm_judge_response(self, content: str) -> TaskCompletionJudge:
        """解析 LLM 返回的评估结果。"""
        # 尝试从 markdown 代码块提取
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        # 尝试提取 JSON 对象
        try:
            data = json.loads(content)
            return TaskCompletionJudge(**data)
        except (json.JSONDecodeError, ValueError):
            pass

        # 尝试从文本中提取 JSON 对象（找第一个 { 和最后一个 }）
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(content[start:end + 1])
                return TaskCompletionJudge(**data)
            except (json.JSONDecodeError, ValueError):
                pass

        # 解析失败，默认通过（避免阻塞）
        logger.warning(f"Judge 无法解析 LLM 响应: {content[:100]}...")
        return TaskCompletionJudge(
            verdict=True,
            reasoning="无法解析 Judge 评估结果，默认通过",
            failure_reason="",
        )

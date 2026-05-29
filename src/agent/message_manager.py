"""消息管理器 — 管理 Agent 对话上下文，支持 token 估算和自动压缩。

Phase 3.2: 从 src/agent/service.py 独立，新增 compaction 功能。
"""

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models import BaseChatModel


class MessageManager:
    """消息管理器。"""

    def __init__(
        self,
        task: str,
        system_prompt: str,
        max_tokens: int = 8000,
        keep_recent: int = 2,
    ):
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens
        self.keep_recent = keep_recent

        self.messages: list = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"<user_request>\n{task}\n</user_request>"),
        ]
        self._step_boundaries: list[int] = []

    def add_state_message(self, browser_state: str) -> None:
        self._step_boundaries.append(len(self.messages))
        self.messages.append(
            HumanMessage(content=f"<browser_state>\n{browser_state}\n</browser_state>")
        )

    def add_assistant_message(self, text: str) -> None:
        self.messages.append(
            HumanMessage(content=f"<agent_output>\n{text}\n</agent_output>")
        )

    def add_tool_results(self, text: str) -> None:
        self.messages.append(
            HumanMessage(content=f"<tool_results>\n{text}\n</tool_results>")
        )

    def get_messages(self) -> list:
        return self.messages

    def estimate_tokens(self) -> int:
        total_chars = sum(
            len(m.content) if hasattr(m, "content") else 0
            for m in self.messages
        )
        return max(1, total_chars // 4)

    def maybe_compact(self, llm: BaseChatModel) -> bool:
        if self.estimate_tokens() < self.max_tokens:
            return False

        if len(self._step_boundaries) <= self.keep_recent:
            return False

        if self.keep_recent <= 0:
            recent_messages: list = []
            old_step_messages = self.messages[2:]
        else:
            split_idx = len(self._step_boundaries) - self.keep_recent
            first_kept_boundary = self._step_boundaries[split_idx]
            recent_messages = self.messages[first_kept_boundary:]
            old_step_messages = self.messages[2:first_kept_boundary]

        summary_text = self._build_summary_text(old_step_messages)
        response = llm.invoke([
            SystemMessage(content=(
                "将以下浏览器操作历史压缩为简洁摘要，保留关键信息："
                "任务进展、访问过的URL、尝试过的操作及结果、"
                "获取的关键数据、失败的操作及原因。"
            )),
            HumanMessage(content=summary_text),
        ])

        self.messages = [
            self.messages[0],
            self.messages[1],
            HumanMessage(content=f"<compacted_summary>\n{response.content}\n</compacted_summary>"),
        ] + recent_messages

        self._step_boundaries = [3 + i for i in range(len(recent_messages))]

        return True

    def _build_summary_text(self, messages: list) -> str:
        parts: list[str] = []
        for m in messages:
            content = m.content if hasattr(m, "content") else str(m)
            parts.append(content)
        return "\n---\n".join(parts)
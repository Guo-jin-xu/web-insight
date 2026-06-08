"""任务记忆管理器 — 单次对话内的短期记忆管理。

管理 Agent 在单次任务执行中的关键信息：
- 关键发现（key findings）
- 已访问的 URL
- 已提取的数据
- 中间步骤结果
- 消息压缩（当消息过多时自动摘要）
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TaskMemory:
    """单次任务内的记忆存储。

    存储 Agent 在执行过程中积累的关键信息，避免重复操作。
    """

    # 关键发现
    findings: list[str] = field(default_factory=list)

    # 已访问的 URL（避免重复导航）
    visited_urls: list[str] = field(default_factory=list)

    # 已提取的数据（结构化）
    extracted_data: dict[str, str] = field(default_factory=dict)

    # 中间步骤结果
    step_results: list[dict] = field(default_factory=list)

    # 当前子任务/目标
    current_goal: str = ""

    def add_finding(self, finding: str) -> None:
        """添加关键发现。"""
        if finding not in self.findings:
            self.findings.append(finding)

    def add_visited_url(self, url: str) -> None:
        """记录已访问的 URL。"""
        if url not in self.visited_urls:
            self.visited_urls.append(url)

    def add_extracted_data(self, key: str, value: str) -> None:
        """添加提取的数据。"""
        self.extracted_data[key] = value

    def add_step_result(self, step: int, action: str, result: str) -> None:
        """记录步骤结果。"""
        self.step_results.append({
            "step": step,
            "action": action,
            "result_summary": result[:200],
        })
        # 只保留最近 10 步
        if len(self.step_results) > 10:
            self.step_results = self.step_results[-10:]

    def get_context_for_llm(self) -> str:
        """生成给 LLM 的记忆上下文。"""
        parts = []

        if self.current_goal:
            parts.append(f"## 当前目标\n{self.current_goal}")

        if self.findings:
            parts.append("## 已发现的信息")
            for f in self.findings[-5:]:  # 最近 5 条
                parts.append(f"- {f}")

        if self.visited_urls:
            parts.append(f"## 已访问的页面 ({len(self.visited_urls)} 个)")
            for u in self.visited_urls[-5:]:
                parts.append(f"- {u}")

        if self.extracted_data:
            parts.append("## 已提取的数据")
            for k, v in self.extracted_data.items():
                parts.append(f"- {k}: {v[:100]}")

        return "\n\n".join(parts) if parts else ""

    def is_url_visited(self, url: str) -> bool:
        """检查 URL 是否已访问过。"""
        return url in self.visited_urls


class MessageCompactor:
    """消息压缩器 — 当消息过多时自动摘要旧消息。

    参考 browser-use 的 MessageManager.compact_messages。
    """

    def __init__(self, max_messages: int = 30):
        self.max_messages = max_messages

    def should_compact(self, messages: list[dict]) -> bool:
        """检查是否需要压缩消息。"""
        return len(messages) > self.max_messages

    def compact(self, messages: list[dict]) -> list[dict]:
        """压缩消息列表：保留系统消息 + 最近 N 条，旧消息用摘要替代。

        注意：这只是一个简单的截断策略，完整的 compaction 需要 LLM 参与。
        这里采用保留最近消息 + 注入摘要的策略。
        """
        if not self.should_compact(messages):
            return messages

        # 保留前 2 条（通常是 system + user task）和最近 20 条
        keep_head = 2
        keep_tail = 20

        head = messages[:keep_head]
        tail = messages[-keep_tail:]

        # 中间被移除的消息，生成摘要
        removed_count = len(messages) - keep_head - keep_tail
        if removed_count > 0:
            summary = {
                "role": "user",
                "content": f"[系统通知] 为了节省上下文，已压缩 {removed_count} 条中间消息。请继续基于当前可见的消息完成任务。"
            }
            return head + [summary] + tail

        return head + tail

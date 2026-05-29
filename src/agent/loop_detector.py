"""循环检测器 — 检测 Agent 行为循环并生成渐进式提醒。

参考 browser_use `ActionLoopDetector`, 教学简化版。
"""

from collections import Counter


class LoopDetector:
    """检测 Agent 行为循环并生成渐进式提醒。"""

    def __init__(self, window_size: int = 10):
        self.window_size = window_size
        self.recent_action_keys: list[str] = []
        self.consecutive_same_action: int = 0
        self.consecutive_same_url: int = 0
        self._last_action_key: str | None = None
        self._current_url: str | None = None

    def _normalize_action(self, action_name: str, params: dict) -> str:
        if action_name == "search":
            query = str(params.get("query", ""))
            tokens = sorted(set(query.lower().split()))
            return f"search|{'|'.join(tokens)}"
        if action_name in ("click", "input", "type"):
            index = params.get("index")
            return f"{action_name}|{index}"
        if action_name == "navigate":
            url = str(params.get("url", ""))
            return f"navigate|{url}"
        if action_name == "scroll":
            direction = "down" if params.get("down", True) else "up"
            index = params.get("index")
            return f"scroll|{direction}|{index}"
        filtered = {k: v for k, v in sorted(params.items()) if v is not None}
        return f"{action_name}|{str(filtered)}"

    def record(self, action_name: str, params: dict, url: str) -> None:
        key = self._normalize_action(action_name, params)

        if key == self._last_action_key:
            self.consecutive_same_action += 1
        else:
            self.consecutive_same_action = 0
        self._last_action_key = key

        if url == self._current_url:
            self.consecutive_same_url += 1
        else:
            self.consecutive_same_url = 0
            self._current_url = url

        self.recent_action_keys.append(key)
        if len(self.recent_action_keys) > self.window_size:
            self.recent_action_keys = self.recent_action_keys[-self.window_size:]

    def _max_repetition_in_window(self) -> int:
        if not self.recent_action_keys:
            return 0
        return max(Counter(self.recent_action_keys).values())

    def get_nudge(self) -> str | None:
        max_rep = self._max_repetition_in_window()
        messages: list[str] = []

        if self.consecutive_same_action >= 8:
            messages.append(
                f"严重: 在过去 {len(self.recent_action_keys)} 步中，"
                f"你已重复相同操作 {max_rep} 次。"
                f"如果每次重复都有进展，请继续。否则，建议切换策略或使用"
                f" visual_analyze 分析页面。"
            )
        elif self.consecutive_same_action >= 5:
            messages.append(
                f"警告: 在过去 {len(self.recent_action_keys)} 步中，"
                f"你已重复相同操作 {max_rep} 次。"
                f"每次尝试是否都有进展？如果没有，建议尝试不同的方法。"
            )
        elif self.consecutive_same_action >= 2:
            messages.append(
                f"建议: 在过去 {len(self.recent_action_keys)} 步中，"
                f"你已重复相同操作 {max_rep} 次。"
                f"如果这是故意的且有进展，请继续。如果不是，建议重新考虑策略。"
            )

        if self.consecutive_same_url >= 4:
            messages.append(
                f"页面停滞: 连续 {self.consecutive_same_url + 1} 步停留在同一页面"
                f" ({self._current_url})。操作可能未达到预期效果，"
                f"建议尝试不同的元素或方法。"
            )

        if messages:
            return "\n\n".join(messages)
        return None
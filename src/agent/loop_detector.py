"""循环检测器 — 检测 Agent 行为循环和页面停滞。

参考 browser-use 的 ActionLoopDetector：
- 动作哈希追踪：检测重复执行相同操作
- 页面指纹追踪：检测页面无变化
- 分级提醒：5/8/12 次重复时发出不同级别的提醒
"""

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PageFingerprint:
    """页面指纹 — 用于检测页面是否变化。"""

    url: str
    element_count: int
    text_hash: str

    @classmethod
    def from_state(cls, url: str, text: str, element_count: int) -> "PageFingerprint":
        text_hash = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]
        return cls(url=url, element_count=element_count, text_hash=text_hash)


def _normalize_action(action_name: str, params: dict[str, Any]) -> str:
    """标准化动作参数，用于相似度哈希。"""
    if action_name == "navigate":
        url = str(params.get("url", ""))
        return f"navigate|{url}"

    if action_name in ("click_element", "input_text"):
        index = params.get("index")
        if action_name == "input_text":
            text = str(params.get("text", "")).strip().lower()
            return f"input_text|{index}|{text}"
        return f"click_element|{index}"

    if action_name == "scroll":
        direction = "down" if params.get("down", True) else "up"
        return f"scroll|{direction}"

    if action_name == "extract_content":
        return f"extract_content|{params.get('max_length', '')}"

    if action_name == "get_dom_snapshot":
        return "get_dom_snapshot"

    # 默认：动作名 + 排序后的参数
    filtered = {k: v for k, v in sorted(params.items()) if v is not None}
    return f"{action_name}|{json.dumps(filtered, sort_keys=True, default=str)}"


def compute_action_hash(action_name: str, params: dict[str, Any]) -> str:
    """计算动作哈希。"""
    normalized = _normalize_action(action_name, params)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]


class ActionLoopDetector:
    """动作循环检测器。

    追踪最近 N 步的动作哈希和页面指纹，检测重复行为和页面停滞。
    只生成提醒消息，不阻止动作执行。
    """

    def __init__(self, window_size: int = 20):
        self.window_size = window_size

        # 动作追踪
        self.recent_action_hashes: list[str] = []
        self.max_repetition_count: int = 0
        self.most_repeated_hash: str | None = None

        # 页面停滞追踪
        self.recent_page_fingerprints: list[PageFingerprint] = []
        self.consecutive_stagnant_pages: int = 0

    def record_action(self, action_name: str, params: dict[str, Any]) -> None:
        """记录一个动作。"""
        h = compute_action_hash(action_name, params)
        self.recent_action_hashes.append(h)
        if len(self.recent_action_hashes) > self.window_size:
            self.recent_action_hashes = self.recent_action_hashes[-self.window_size :]
        self._update_repetition_stats()

    def record_page_state(self, url: str, text: str, element_count: int) -> None:
        """记录当前页面状态。"""
        fp = PageFingerprint.from_state(url, text, element_count)
        if self.recent_page_fingerprints and self.recent_page_fingerprints[-1] == fp:
            self.consecutive_stagnant_pages += 1
        else:
            self.consecutive_stagnant_pages = 0
        self.recent_page_fingerprints.append(fp)
        if len(self.recent_page_fingerprints) > 5:
            self.recent_page_fingerprints = self.recent_page_fingerprints[-5:]

    def _update_repetition_stats(self) -> None:
        """重新计算重复统计。"""
        if not self.recent_action_hashes:
            self.max_repetition_count = 0
            self.most_repeated_hash = None
            return
        counts: dict[str, int] = {}
        for h in self.recent_action_hashes:
            counts[h] = counts.get(h, 0) + 1
        self.most_repeated_hash = max(counts, key=lambda k: counts[k])
        self.max_repetition_count = counts[self.most_repeated_hash]

    def get_nudge_message(self) -> str | None:
        """获取循环检测提醒消息，无循环时返回 None。

        分级提醒：
        - 5 次重复：温和提醒
        - 8 次重复：中度提醒
        - 12 次重复：强烈提醒
        """
        messages: list[str] = []

        # 动作重复提醒
        if self.max_repetition_count >= 12:
            messages.append(
                f"警告：你已经重复了相似操作 {self.max_repetition_count} 次 "
                f"（在最近 {len(self.recent_action_hashes)} 步中）。"
                "如果每次重复都有进展，请继续。否则请尝试不同的方法。"
            )
        elif self.max_repetition_count >= 8:
            messages.append(
                f"注意：你已经重复了相似操作 {self.max_repetition_count} 次 "
                f"（在最近 {len(self.recent_action_hashes)} 步中）。"
                "每次尝试是否仍有进展？如果没有，建议换个方式。"
            )
        elif self.max_repetition_count >= 5:
            messages.append(
                f"提示：你已经重复了相似操作 {self.max_repetition_count} 次。"
                "如果这是有意的探索，请继续。否则可以考虑换个思路。"
            )

        # 页面停滞提醒
        if self.consecutive_stagnant_pages >= 5:
            messages.append(
                f"页面内容在连续 {self.consecutive_stagnant_pages} 步中没有变化。"
                "你的操作可能没有生效，建议尝试不同的元素或方法。"
            )

        if messages:
            return "\n\n".join(messages)
        return None

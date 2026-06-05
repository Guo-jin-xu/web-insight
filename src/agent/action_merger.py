"""动作合并器 — 方案B: Post-processing 冗余动作检测与消除。

参考 browser-use 中 Agent step 的动作执行逻辑，
在 LLM 返回 tool_calls 后自动检测并消除冗余动作。

合并规则：
1. extract_content + get_dom_snapshot → 删除 snapshot（内容已提取）
2. click_element + get_dom_snapshot → 删除 snapshot（页面已跳转）
3. 连续多个 get_dom_snapshot → 只保留第一个
4. navigate + extract_content → 保留两者（正常流程）
5. done 始终保留（终止信号）
"""

import logging
from src.llm.client import ToolCall

logger = logging.getLogger(__name__)

# 冗余模式字典：{trigger_action: [redundant_action]}
# 如果 trigger_action 之后出现 redundant_action，则删除后者
REDUNDANT_PATTERNS: dict[str, list[str]] = {
    "extract_content": ["get_dom_snapshot"],
    "click_element": ["get_dom_snapshot"],
    "get_dom_snapshot": ["get_dom_snapshot"],  # 连续 snapshot → 去重
}

# 这些动作不应被合并/删除
PROTECTED_ACTIONS = {"done", "navigate"}


def merge_redundant_actions(
    tool_calls: list[ToolCall],
) -> tuple[list[ToolCall], list[str]]:
    """检测并消除冗余的工具调用。

    Args:
        tool_calls: LLM 返回的 tool_calls 列表

    Returns:
        (merged_tool_calls, skipped_names): 合并后的列表 + 被跳过的动作名
    """
    if len(tool_calls) <= 1:
        return tool_calls, []

    merged: list[ToolCall] = []
    skipped: list[str] = []

    for tc in tool_calls:
        if tc.name in PROTECTED_ACTIONS:
            merged.append(tc)
            continue

        should_skip = False

        # 检查是否与之前已保留的动作冗余
        for prev in reversed(merged):
            if prev.name in REDUNDANT_PATTERNS:
                redundant_list = REDUNDANT_PATTERNS[prev.name]
                if tc.name in redundant_list:
                    should_skip = True
                    reason = f"{prev.name} → {tc.name}"
                    logger.debug(f"跳过冗余动作: {reason}")
                    break

        if should_skip:
            skipped.append(tc.name)
        else:
            merged.append(tc)

    if skipped:
        logger.info(f"冗余动作合并: 跳过 {len(skipped)} 个 ({skipped})")

    return merged, skipped


def should_auto_extract_after_navigate(
    previous_tool_name: str | None,
    current_tool_calls: list[ToolCall],
) -> bool:
    """判断是否应该在 navigate 后自动插入 extract_content。

    当前不做自动插入，仅作为未来扩展点。
    """
    return False
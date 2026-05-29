"""DOM 增强数据模型 — EnhancedDOMTreeNode + SerializedDOMState。

Phase 3.3: 教学简化版 CDP DOM Tree 替代当前 flat list。
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class NodeType(int, Enum):
    ELEMENT_NODE = 1
    TEXT_NODE = 3


class EnhancedDOMTreeNode(BaseModel):
    """增强的 DOM 树节点，整合视觉和交互信息。"""

    node_id: int = 0
    backend_node_id: int | None = None
    node_type: NodeType = NodeType.ELEMENT_NODE
    node_name: str = ""
    node_value: str = ""
    attributes: dict[str, str] = Field(default_factory=dict)
    children: list[EnhancedDOMTreeNode] = Field(default_factory=list)

    is_visible: bool = True
    x: float = 0
    y: float = 0
    width: float = 0
    height: float = 0

    is_interactive: bool = False
    is_scrollable: bool = False
    highlight_index: int | None = None

    ax_name: str = ""
    ax_role: str = ""
    is_focused: bool = False

    parent_node: EnhancedDOMTreeNode | None = Field(default=None, exclude=True)


class SerializedDOMState(BaseModel):
    """序列化后的 DOM 状态，供 LLM 消费。"""

    text: str = ""
    selector_map: dict[int, EnhancedDOMTreeNode] = Field(default_factory=dict)
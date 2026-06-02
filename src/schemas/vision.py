"""视觉分析结构化输出模型。"""

from typing import Literal

from pydantic import BaseModel, Field

ElementType = Literal["button", "input", "link", "dropdown", "checkbox", "radio", "text", "image", "other"]


class PageElement(BaseModel):
    name: str = Field(description="元素名称")
    type: ElementType = Field(description="元素类型")
    x: int = Field(description="水平坐标（像素）")
    y: int = Field(description="垂直坐标（像素）")
    description: str = Field(default="", description="元素用途说明")


class PageAnalysis(BaseModel):
    page_description: str = Field(description="页面整体描述")
    elements: list[PageElement] = Field(default_factory=list, description="关键交互元素及坐标")
    suggestions: str = Field(default="", description="操作建议")

    def format_for_agent(self) -> str:
        lines = [
            f"## 页面描述\n{self.page_description}\n",
            f"## 关键交互元素（共 {len(self.elements)} 个）",
        ]
        for el in self.elements:
            lines.append(
                f"- {el.name}: type={el.type}, pos=({el.x},{el.y}), {el.description}"
            )
        lines.append(f"\n## 操作建议\n{self.suggestions}")
        return "\n".join(lines)

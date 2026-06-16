"""视觉分析结构化输出模型。"""

from typing import Literal, Any

from pydantic import BaseModel, Field, field_validator, model_validator

ElementType = Literal["button", "input", "link", "dropdown", "checkbox", "radio", "text", "image", "other"]


class PageElement(BaseModel):
    name: str = Field(description="元素名称")
    type: ElementType = Field(description="元素类型")
    x: int = Field(description="水平坐标（像素）")
    y: int = Field(description="垂直坐标（像素）")
    description: str = Field(default="", description="元素用途说明")

    @model_validator(mode="before")
    @classmethod
    def fix_coordinate_formats(cls, data: Any) -> Any:
        """松弛校验：修复 VLM 返回的各种异常坐标格式。

        常见问题：
        - x 为 [x, y] 列表，y 缺失 → 拆分列表
        - x 或 y 为字符串数字 → 转 int
        - 坐标为 float → 转 int
        """
        if not isinstance(data, dict):
            return data

        x_val = data.get("x")
        y_val = data.get("y")

        # VLM 把 [x, y] 放到了 x 字段
        if isinstance(x_val, list) and len(x_val) >= 2 and y_val is None:
            data["x"] = x_val[0]
            data["y"] = x_val[1]
        elif isinstance(x_val, list) and len(x_val) >= 1:
            data["x"] = x_val[0]

        # VLM 把 [x, y] 放到了 y 字段
        if isinstance(y_val, list) and len(y_val) >= 1:
            data["y"] = y_val[0] if not isinstance(x_val, list) else y_val[1] if len(y_val) >= 2 else y_val[0]

        # 字符串数字转 int
        if isinstance(data.get("x"), str):
            try:
                data["x"] = int(float(data["x"]))
            except (ValueError, TypeError):
                data["x"] = 0
        if isinstance(data.get("y"), str):
            try:
                data["y"] = int(float(data["y"]))
            except (ValueError, TypeError):
                data["y"] = 0

        # float 转 int
        if isinstance(data.get("x"), float):
            data["x"] = int(data["x"])
        if isinstance(data.get("y"), float):
            data["y"] = int(data["y"])

        return data


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

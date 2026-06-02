"""统一工具返回模型。"""

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    success: bool = Field(description="操作是否成功")
    tool_name: str = Field(default="", description="工具名称")
    data: dict = Field(default_factory=dict, description="结构化数据")
    summary: str = Field(default="", description="给 LLM 的简短摘要")
    error: str | None = Field(default=None, description="错误信息")
    screenshot: str | None = Field(default=None, description="截图路径")

    def to_text(self) -> str:
        if not self.success:
            return f"[{self.tool_name}] 失败: {self.error or '未知错误'}"
        parts = [f"[{self.tool_name}] {self.summary}"]
        if self.screenshot:
            parts.append(f"截图: {self.screenshot}")
        return "\n".join(parts)


class ActionResult(BaseModel):
    """工具执行结果 — browser-use 兼容格式。"""
    is_done: bool = Field(default=False, description="任务是否完成")
    success: bool = Field(default=True, description="操作是否成功")
    extracted_content: str = Field(default="", description="提取的内容")
    error: str | None = Field(default=None, description="错误信息")
    long_term_memory: str = Field(default="", description="跨步骤记忆")
    include_in_memory: bool = Field(default=False, description="是否纳入长期记忆")
    screenshot: str | None = Field(default=None, description="截图路径")

    def to_text(self) -> str:
        if self.error:
            return f"错误: {self.error}"
        if self.extracted_content:
            return self.extracted_content
        return "操作完成"

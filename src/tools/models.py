"""工具参数 Pydantic 模型 — 参考 browser-use 的 Action 定义。"""

from pydantic import BaseModel, Field


class NavigateAction(BaseModel):
    """导航到 URL 或搜索关键词。

    如果输入是完整 URL（含 http/https），直接导航；
    如果是普通文本，自动构建搜索 URL 并导航。
    """
    url: str = Field(description="完整 URL 或搜索关键词。URL 示例: https://example.com；搜索示例: Python 教程")
    new_tab: bool = Field(default=False, description="是否在新标签页打开")


class ClickElementAction(BaseModel):
    """点击页面元素。index 来自 get_dom_snapshot 返回的元素索引。"""
    index: int = Field(ge=0, description="元素索引号，来自 get_dom_snapshot 的结果")


class InputTextAction(BaseModel):
    """向输入框键入文本。先点击输入框，再输入内容。"""
    index: int = Field(ge=0, description="输入框元素索引号")
    text: str = Field(description="要输入的文本")
    clear: bool = Field(default=True, description="是否先清空已有内容")


class ScrollAction(BaseModel):
    """滚动页面。"""
    down: bool = Field(default=True, description="True=向下滚动，False=向上滚动")
    pages: float = Field(default=1.0, description="滚动页数，1.0=一屏")


class SendKeysAction(BaseModel):
    """按下键盘按键。常用: Enter 提交搜索/表单，Escape 关闭弹窗。"""
    keys: str = Field(description="按键名，如 Enter / Escape / Tab / Control+a")
    wait_for_navigation: bool = Field(
        default=False,
        description="是否等待页面导航完成（Enter 提交搜索时建议设为 true）",
    )


class ClickCoordinateAction(BaseModel):
    """点击页面指定坐标。用于 VLM 视觉分析后精确定位元素。"""
    x: int = Field(ge=0, description="水平坐标（像素）")
    y: int = Field(ge=0, description="垂直坐标（像素）")


class VisualAnalyzeAction(BaseModel):
    """使用视觉模型分析页面截图，定位指定元素并返回坐标。当 DOM 无法识别元素时使用。"""
    query: str = Field(description="要查找的元素描述，如'第一个视频的链接'、'搜索按钮'")
    max_elements: int = Field(default=10, description="最多返回的元素数量")


class ExtractContentAction(BaseModel):
    """提取当前页面内容。自动检测页面类型（文章/列表/搜索结果）并提取核心内容。"""
    max_length: int = Field(default=3000, description="最大输出字符数")


class GetDomSnapshotAction(BaseModel):
    """获取当前页面可交互元素列表。这是感知页面的首选工具。"""
    max_elements: int = Field(default=200, description="最大返回元素数")


class GetTabsInfoAction(BaseModel):
    """获取所有打开的标签页信息。"""
    pass


class SwitchTabAction(BaseModel):
    """切换到指定标签页。"""
    tab_index: int = Field(ge=0, description="标签页索引（0=第一个标签页）")


class NewTabAction(BaseModel):
    """在新标签页打开 URL。"""
    url: str = Field(default="about:blank", description="URL 或 about:blank")


class CloseTabAction(BaseModel):
    """关闭指定标签页。"""
    index: int = Field(default=-1, description="标签页索引，-1=当前页")


class ListTabsAction(BaseModel):
    """列出所有标签页。"""
    pass


class SelectDropdownAction(BaseModel):
    """选择下拉菜单选项。"""
    index: int = Field(ge=0, description="下拉菜单元素索引")
    value: str = Field(description="要选择的选项文本")


class UploadFileAction(BaseModel):
    """上传文件到 input[type=file]。"""
    index: int = Field(ge=0, description="文件上传元素索引")
    file_path: str = Field(description="本地文件绝对路径")


class DoneAction(BaseModel):
    """标记任务完成并返回最终结果。调用后终止执行。"""
    text: str = Field(description="任务的最终结果总结")
    success: bool = Field(default=True, description="任务是否成功完成")


class NoParamsAction(BaseModel):
    """无参数操作（如 go_back、get_tabs_info）。"""
    pass

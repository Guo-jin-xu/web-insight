"""VLM 视觉分析 — 纯函数，截图 → VLM 结构化分析。

仅在 DOM fallback 或 judge 阶段调用。
"""

from langchain_core.messages import HumanMessage

from src.llm.factory import get_vlm
from src.schemas.vision import PageAnalysis

VLM_ANALYSIS_PROMPT = """你是一个网页视觉分析专家。请分析这个网页截图，返回结构化的分析结果。

请识别：
1. 页面整体描述：这是什么类型的页面？主要内容是什么？
2. 关键交互元素：识别所有可点击/可输入的元素，每个元素提供名称、类型、坐标(x,y)和用途说明。
   - 坐标以像素为单位，从视口左上角(0,0)计算。
   - 类型包括: button, input, link, dropdown, checkbox, radio, text, image, other
3. 操作建议：基于当前页面状态，给出下一步操作的合理建议。
"""


async def analyze_screenshot(screenshot_b64: str) -> PageAnalysis:
    """截图 → VLM 结构化 PageAnalysis。

    Args:
        screenshot_b64: PNG 截图的 base64 编码字符串

    Returns:
        PageAnalysis 结构化对象
    """
    vlm = get_vlm()
    structured_vlm = vlm.with_structured_output(PageAnalysis)

    message = HumanMessage(
        content=[
            {"type": "text", "text": VLM_ANALYSIS_PROMPT},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"},
            },
        ]
    )

    response = await structured_vlm.ainvoke([message])
    return response

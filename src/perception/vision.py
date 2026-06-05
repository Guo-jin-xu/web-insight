"""VLM 视觉分析 — 纯 httpx 调用，不依赖 langchain。

仅在 DOM fallback 或 judge 阶段调用。
"""

import httpx

from src.config.settings import settings
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
    payload = {
        "model": settings.vlm_model_name,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": VLM_ANALYSIS_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"},
                    },
                ],
            }
        ],
        "temperature": settings.vlm_temperature,
    }

    if settings.vlm_max_tokens is not None:
        payload["max_tokens"] = settings.vlm_max_tokens

    headers = {
        "Authorization": f"Bearer {settings.vlm_api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=settings.vlm_timeout) as client:
        response = await client.post(
            f"{settings.vlm_base_url}/chat/completions",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

    content = data["choices"][0]["message"]["content"]
    return PageAnalysis.model_validate_json(content)
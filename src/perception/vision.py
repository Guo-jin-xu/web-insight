"""VLM 视觉分析 — 纯 httpx 调用，不依赖 langchain。

仅在 DOM fallback 或 judge 阶段调用。
"""

import json
import logging
import re

import httpx

from src.config.settings import settings
from src.schemas.vision import PageAnalysis

logger = logging.getLogger(__name__)

VLM_ANALYSIS_PROMPT = """你是一个网页视觉分析专家。请分析这个网页截图，返回结构化的 JSON 分析结果。

## 分析要求
1. 页面整体描述：这是什么类型的页面？主要内容是什么？
2. 关键交互元素：识别所有可点击/可输入的元素，每个元素提供名称、类型、坐标(x,y)和用途说明。
   - 坐标以像素为单位，从视口左上角(0,0)计算。
   - 类型包括: button, input, link, dropdown, checkbox, radio, text, image, other
3. 操作建议：基于当前页面状态，给出下一步操作的合理建议。

## 输出格式（必须严格按以下 JSON 格式输出，不要添加任何额外文字）
```json
{
    "page_description": "页面整体描述",
    "elements": [
        {"name": "元素名称", "type": "link", "x": 300, "y": 200, "description": "元素用途"}
    ],
    "suggestions": "操作建议"
}
```

## 重要
- 只输出 JSON，不要输出任何其他文字
- 坐标必须是整数，从视口左上角(0,0)开始计算
- 视频通常以链接(link)或图片(image)形式出现，标题文字在下方或右侧
"""


def extract_json_from_text(text: str) -> str:
    """从文本中提取 JSON 内容。

    处理 VLM 可能返回的各种格式：
    - 纯 JSON: {"key": "value"}
    - Markdown 代码块: ```json ... ```
    - 前后有解释文字: 这是结果 {...} 希望有帮助

    Args:
        text: VLM 返回的原始文本

    Returns:
        提取的 JSON 字符串
    """
    text = text.strip()

    # 尝试匹配 markdown 代码块 ```json ... ``` 或 ``` ... ```
    code_block_pattern = r"```(?:json)?\s*\n?(.*?)\n?```"
    match = re.search(code_block_pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # 尝试匹配 JSON 对象 { ... }
    json_pattern = r"\{[\s\S]*\}"
    match = re.search(json_pattern, text)
    if match:
        return match.group(0).strip()

    # 如果都匹配不到，返回原始文本
    return text


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
        if response.status_code != 200:
            raise ValueError(
                f"VLM API 请求失败 (HTTP {response.status_code}): {response.text[:500]}"
            )
        data = response.json()

    content = data["choices"][0]["message"]["content"]
    logger.debug(f"VLM 原始响应: {content[:500]}")

    # 提取 JSON 内容
    json_str = extract_json_from_text(content)

    try:
        return PageAnalysis.model_validate_json(json_str)
    except Exception as e:
        logger.warning(f"JSON 解析失败，原始内容: {content[:300]}")
        raise ValueError(f"VLM 返回内容无法解析为 JSON: {e}\n原始内容前300字符: {content[:300]}")
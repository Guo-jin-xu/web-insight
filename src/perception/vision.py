"""VLM 视觉分析 — 纯 httpx 调用，不依赖 langchain。

仅在 DOM fallback 阶段调用。
"""

import base64
import json
import logging
import re
from datetime import datetime
from pathlib import Path

import httpx

from src.config.settings import settings
from src.schemas.vision import PageAnalysis

logger = logging.getLogger(__name__)

# 截图保存目录
SCREENSHOT_DIR = settings.project_root / "data" / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

VLM_ANALYSIS_PROMPT_TEMPLATE = """你是一个网页视觉分析专家。请分析这个网页截图，返回简洁的 JSON 分析结果。

## 图片尺寸信息（极其重要）
- 图片宽度: {width} 像素
- 图片高度: {height} 像素
- 坐标系: 左上角为 (0, 0)，右下角为 ({width}, {height})
- **严格约束**: x 必须在 [0, {width}] 范围内，y 必须在 [0, {height}] 范围内
- **禁止**: 返回超出图片范围的坐标（如 y > {height}）

## 分析要求
1. 页面描述：一句话概括页面类型和主要内容（不超过50字）
2. 关键元素：只识别与用户任务最相关的 3-5 个可点击元素，每个提供：
   - name: 元素名称（简短）
   - type: 类型（button/link/input/other）
   - x, y: 坐标（整数，**必须严格在图片范围内**）
   - description: 一句话说明用途
3. 建议：下一步操作建议（不超过30字）
   - **重要**：如果对下一步操作不确定，建议中必须包含"使用 visual_analyze 进行视觉分析"

## 输出格式（严格 JSON，不要其他文字）
```json
{{
    "page_description": "页面描述",
    "elements": [
        {{"name": "元素名", "type": "link", "x": 300, "y": 200, "description": "用途"}}
    ],
    "suggestions": "操作建议，不确定时建议 visual_analyze"
}}
```

## 重要规则
- 只输出 JSON，不要解释
- 元素数量限制 3-5 个，只返回最关键的
- **坐标必须严格在 [0, {width}] x [0, {height}] 范围内**
- 如果目标元素不在当前视口内，请在 suggestions 中说明"目标元素不在当前视口，需要滚动"
- 视频通常以链接或图片形式出现
- **遇到不确定的操作时，必须在 suggestions 中建议调用 visual_analyze 工具**
"""


def save_screenshot(screenshot_b64: str, prefix: str = "screenshot") -> Path:
    """保存截图到 data/screenshots 目录。

    Args:
        screenshot_b64: base64 编码的截图
        prefix: 文件名前缀

    Returns:
        保存的文件路径
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.png"
    filepath = SCREENSHOT_DIR / filename

    try:
        image_data = base64.b64decode(screenshot_b64)
        filepath.write_bytes(image_data)
        logger.info(f"截图已保存: {filepath}")
        return filepath
    except Exception as e:
        logger.warning(f"保存截图失败: {e}")
        return None


def extract_json_from_text(text: str) -> str:
    """从文本中提取 JSON 内容。

    处理 VLM 可能返回的各种格式：
    - 纯 JSON: {"key": "value"}
    - Markdown 代码块: ```json ... ``` （含未闭合情况）
    - 前后有解释文字: 这是结果 {...} 希望有帮助
    - 截断的 JSON: 尝试修复

    Args:
        text: VLM 返回的原始文本

    Returns:
        提取的 JSON 字符串
    """
    text = text.strip()

    # 1. 尝试匹配闭合的 markdown 代码块 ```json ... ``` 或 ``` ... ```
    code_block_pattern = r"```(?:json)?\s*\n?(.*?)\n?```"
    match = re.search(code_block_pattern, text, re.DOTALL)
    if match:
        extracted = match.group(1).strip()
        return try_fix_truncated_json(extracted)

    # 2. 尝试匹配未闭合的 markdown 代码块（响应被截断时常见）
    #    匹配 ```json 或 ``` 开头，后面跟任意内容直到文本结束
    unclosed_block_pattern = r"```(?:json)?\s*\n?([\s\S]+)$"
    match = re.search(unclosed_block_pattern, text)
    if match:
        extracted = match.group(1).strip()
        # 尝试提取 JSON 部分
        return try_fix_truncated_json(extracted)

    # 3. 尝试匹配 JSON 对象 { ... }（贪婪匹配到最后一个 }）
    json_pattern = r"\{[\s\S]*\}"
    match = re.search(json_pattern, text)
    if match:
        json_str = match.group(0).strip()
        return try_fix_truncated_json(json_str)

    # 4. 如果文本以 { 开头但没有闭合 }，说明被截断了
    if text.startswith("{"):
        return try_fix_truncated_json(text)

    # 如果都匹配不到，返回原始文本
    return text


def try_fix_truncated_json(text: str) -> str:
    """尝试修复被截断的 JSON。

    策略：
    1. 如果已经是合法 JSON，直接返回
    2. 用栈追踪括号嵌套，找到最后一个完整元素位置
    3. 移除不完整的 key-value 对（如截断在 key 中间的情况）
    4. 按 LIFO 逆序补全未闭合的括号

    Args:
        text: 可能截断的 JSON 字符串

    Returns:
        修复后的 JSON 字符串
    """
    text = text.strip()

    # 如果已经是合法 JSON，直接返回
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # 用栈追踪括号嵌套，找到最后一个完整元素的位置
    stack = []          # 未闭合的括号: '{', '['
    in_string = False
    escape_next = False
    last_complete_pos = -1
    stack_at_complete = []   # 在最后一个完整元素处的栈快照

    for i, c in enumerate(text):
        if escape_next:
            escape_next = False
            continue
        if c == '\\' and in_string:
            escape_next = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        # 不在字符串内
        if c in ('{', '['):
            stack.append(c)
        elif c == '}' and stack and stack[-1] == '{':
            stack.pop()
        elif c == ']' and stack and stack[-1] == '[':
            stack.pop()
        elif c == ',':
            # 逗号标志一个完整元素的结束
            last_complete_pos = i
            stack_at_complete = list(stack)

    # 策略1：从最后一个完整元素处截断，按 LIFO 逆序补全括号
    if last_complete_pos > 0:
        candidate = text[:last_complete_pos].rstrip()
        # 删除末尾逗号
        candidate = re.sub(r',\s*$', '', candidate)
        # 按 LIFO 逆序补全括号（先开的后关）
        for bracket in reversed(stack_at_complete):
            candidate += '}' if bracket == '{' else ']'
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

    # 策略2：检测并移除不完整的 key-value 对
    # 这种情况常见于截断在 key 中间，如 `"typ` 而非 `"type"`
    candidate = _remove_incomplete_keyvalue(text)
    if candidate != text:
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

    # 策略3：逐步从末尾回退，尝试补全
    for end_pos in range(len(text), max(len(text) - 500, 0), -1):
        candidate = text[:end_pos]

        # 找到最后一个安全截断点
        safe_pos = -1
        for p in range(len(candidate) - 1, max(len(candidate) - 100, 0), -1):
            if candidate[p] in (',', '}', ']'):
                safe_pos = p + 1
                break

        if safe_pos > 0:
            candidate = candidate[:safe_pos]

        # 删除末尾多余的逗号
        candidate = re.sub(r',\s*$', '', candidate)

        # 补全未闭合的字符串引号
        if candidate.count('"') % 2 == 1:
            candidate += '"'

        # 用栈追踪括号，按 LIFO 逆序补全
        bracket_stack = []
        in_str = False
        esc = False
        for ch in candidate:
            if esc:
                esc = False
                continue
            if ch == '\\' and in_str:
                esc = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch in ('{', '['):
                bracket_stack.append(ch)
            elif ch == '}' and bracket_stack and bracket_stack[-1] == '{':
                bracket_stack.pop()
            elif ch == ']' and bracket_stack and bracket_stack[-1] == '[':
                bracket_stack.pop()

        for bracket in reversed(bracket_stack):
            candidate += '}' if bracket == '{' else ']'

        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            continue

    # 最终兜底：返回原文（让上层报错）
    return text


def _remove_incomplete_keyvalue(text: str) -> str:
    """移除 JSON 中不完整的 key-value 对。

    处理截断在 key 中间的情况，如 `"typ` 而非 `"type": "video"`。
    策略：找到最后一个完整的 key-value 对或数组元素，截断后面的内容。

    Args:
        text: 可能包含不完整 key-value 对的 JSON 字符串

    Returns:
        移除不完整部分并补全括号后的 JSON 字符串
    """
    text = text.strip()

    # 用栈追踪括号嵌套，记录每个完整元素的位置
    stack = []          # 未闭合的括号: '{', '['
    in_string = False
    escape_next = False
    last_complete_pos = -1
    stack_at_complete = []   # 在最后一个完整元素处的栈快照

    # 追踪 key-value 对的状态
    # 在对象中，我们期望的模式是: "key": value, "key": value, ...
    # 如果截断发生在 key 中间，我们会看到未闭合的引号后没有冒号

    for i, c in enumerate(text):
        if escape_next:
            escape_next = False
            continue
        if c == '\\' and in_string:
            escape_next = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        # 不在字符串内
        if c in ('{', '['):
            stack.append(c)
        elif c == '}' and stack and stack[-1] == '{':
            stack.pop()
            # 对象闭合，记录位置
            last_complete_pos = i + 1
            stack_at_complete = list(stack)
        elif c == ']' and stack and stack[-1] == '[':
            stack.pop()
            # 数组闭合，记录位置
            last_complete_pos = i + 1
            stack_at_complete = list(stack)
        elif c == ',':
            # 逗号标志一个完整元素的结束
            last_complete_pos = i
            stack_at_complete = list(stack)

    # 如果找到了完整元素的位置，从那里截断
    if last_complete_pos > 0:
        candidate = text[:last_complete_pos].rstrip()
        # 删除末尾逗号
        candidate = re.sub(r',\s*$', '', candidate)
        # 按 LIFO 逆序补全括号（先开的后关）
        for bracket in reversed(stack_at_complete):
            candidate += '}' if bracket == '{' else ']'
        return candidate

    # 如果没有找到完整元素，尝试更激进的策略：
    # 找到最后一个冒号（key-value 分隔符），检查后面是否有完整 value
    last_colon_pos = text.rfind(':')
    if last_colon_pos > 0:
        # 检查冒号后面是否有完整的 value
        after_colon = text[last_colon_pos + 1:].strip()
        # 如果冒号后面是空的或者只有不完整的字符串，截断到冒号前的 key
        if not after_colon or (after_colon.startswith('"') and after_colon.count('"') % 2 == 1):
            # 找到这个 key 的开始位置
            # 向前找到最后一个逗号或左括号
            key_start = text.rfind(',', 0, last_colon_pos)
            bracket_start = text.rfind('{', 0, last_colon_pos)
            key_start = max(key_start, bracket_start)
            if key_start > 0:
                candidate = text[:key_start].rstrip()
                # 删除末尾逗号
                candidate = re.sub(r',\s*$', '', candidate)
                # 补全括号
                bracket_stack = []
                in_str = False
                esc = False
                for ch in candidate:
                    if esc:
                        esc = False
                        continue
                    if ch == '\\' and in_str:
                        esc = True
                        continue
                    if ch == '"':
                        in_str = not in_str
                        continue
                    if in_str:
                        continue
                    if ch in ('{', '['):
                        bracket_stack.append(ch)
                    elif ch == '}' and bracket_stack and bracket_stack[-1] == '{':
                        bracket_stack.pop()
                    elif ch == ']' and bracket_stack and bracket_stack[-1] == '[':
                        bracket_stack.pop()
                for bracket in reversed(bracket_stack):
                    candidate += '}' if bracket == '{' else ']'
                return candidate

    return text


async def analyze_screenshot(screenshot_b64: str) -> PageAnalysis:
    """截图 → VLM 结构化 PageAnalysis。

    Args:
        screenshot_b64: PNG 截图的 base64 编码字符串

    Returns:
        PageAnalysis 结构化对象
    """
    from PIL import Image
    import io

    # 解析图片尺寸
    img_data = base64.b64decode(screenshot_b64)
    img = Image.open(io.BytesIO(img_data))
    img_width, img_height = img.size
    logger.info(f"截图图片尺寸: {img_width}x{img_height}")

    # 保存截图到 data/screenshots 目录
    save_screenshot(screenshot_b64, prefix="analyze")

    # 根据图片尺寸动态生成提示词
    prompt = VLM_ANALYSIS_PROMPT_TEMPLATE.format(width=img_width, height=img_height)

    payload = {
        "model": settings.vlm_model_name,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"},
                    },
                ],
            }
        ],
        "temperature": settings.vlm_temperature,
    }

    # 设置 max_tokens 防止截断,VLM 分析需要足够输出空间
    # MiMo API 使用 max_completion_tokens,其他 API 使用 max_tokens
    if "xiaomimimo" in settings.vlm_base_url:
        payload["max_completion_tokens"] = settings.vlm_max_tokens or 4096
    else:
        payload["max_tokens"] = settings.vlm_max_tokens or 4096

    # 小米 MiMo API 需要禁用 thinking
    if "xiaomimimo" in settings.vlm_base_url:
        payload["thinking"] = {"type": "disabled"}

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
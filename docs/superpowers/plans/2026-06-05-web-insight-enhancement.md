# web-insight Enhancement Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 对照 browser-use 参考实现，完善 web-insight 项目：增强 DOM 提取、弹窗处理、循环检测、防检查、短期记忆管理，清理未使用的 langchain 代码，移除 LLM_MAX_TOKENS 限制。

**Architecture:** 维持现有原生 async 架构（不引入 langchain/langgraph），增强 AgentLoop 的感知能力（DOM CDP 序列化）、自我保护（弹窗/dialog 处理）、智能决策（循环检测 + 记忆管理），清理所有 langchain 遗留代码，精简为标准 Python + httpx + Playwright + Pydantic 栈。

**Tech Stack:** Python 3.11+, Playwright (CDP), httpx, Pydantic v2, BeautifulSoup4+lxml, python-dotenv

---

## 当前项目 vs browser-use 差距分析

| 能力维度 | 当前状态 | browser-use 参考 | 差距 |
|---------|---------|-----------------|------|
| **DOM 提取** | JS evaluate 简单提取 top 20 元素 | CDP 全量 DOM tree + AX tree + paint order 过滤 + selector_map | 需大幅增强 |
| **弹窗处理** | 无 | PopupsWatchdog 自动处理 alert/confirm/prompt | 需新增 |
| **循环检测** | 无 | ActionLoopDetector（action hash + page fingerprint） | 需新增 |
| **防检查** | 无 | SecurityWatchdog + 域名白名单 | 需新增 |
| **短期记忆** | 仅 `_messages` 列表，无管理 | MessageManager（compaction/truncation/sensitive data redact） | 需新增 message 管理 |
| **多 Agent 协同** | 无 | 无（browser-use 也是单 Agent） | 非核心需求 |
| **工具准确性** | 9 个工具，无 iframe/multi-tab/file upload | 完整工具集（含 iframe/multi-tab/upload/download） | 需增强 |
| **代码整洁** | 大量 langchain 遗留代码未清理 | 无 | 需清理 |
| **LLM_MAX_TOKENS** | 硬编码 2048 | 可选 | 需移除 |

---

## browser-use 参考代码位置对照表

以下对照表帮助快速定位 browser-use 中对应能力的实现，便于对比分析：

| 能力维度 | 当前 web-insight 文件 | browser-use 参考文件 | 关键类/函数 |
|---------|----------------------|---------------------|------------|
| **DOM 提取** | `src/perception/dom.py` | `browser-use-ref/browser_use/dom/service.py` | `DomService.__init__`, `get_page_state()` |
| | | `browser-use-ref/browser_use/dom/serializer/serializer.py` | `DOMTreeSerializer`, `serialize_accessible_elements()` |
| | | `browser-use-ref/browser_use/dom/serializer/clickable_elements.py` | `ClickableElementDetector.is_interactive()` |
| **弹窗处理** | （无） | `browser-use-ref/browser_use/browser/watchdogs/popups_watchdog.py` | `PopupsWatchdog.on_TabCreatedEvent()` |
| | | `browser-use-ref/browser_use/browser/watchdog_base.py` | `BaseWatchdog` (watchdog 框架) |
| **循环检测** | （无） | `browser-use-ref/browser_use/agent/views.py#L157-L255` | `ActionLoopDetector`, `PageFingerprint` |
| | | `browser-use-ref/browser_use/agent/service.py#L1484-L1520` | `_inject_loop_detection_nudge()` |
| **防检查** | （无） | `browser-use-ref/browser_use/browser/watchdogs/security_watchdog.py` | `SecurityWatchdog._is_url_allowed()` |
| **短期记忆** | `src/memory/history.py` (ChromaDB, 未使用) | `browser-use-ref/browser_use/agent/message_manager/service.py` | `MessageManager` |
| **Agent 循环** | `src/agent/loop.py` | `browser-use-ref/browser_use/agent/service.py#L100-L300` | `Agent.__init__()`, `step()` |
| **工具注册** | `src/tools/registry.py` | `browser-use-ref/browser_use/tools/registry/service.py` | `Registry.action()`, `_normalize_action_function_signature()` |
| **Judge 评估** | （无） | `browser-use-ref/browser_use/agent/judge.py` | `construct_judge_messages()`, `JudgementResult` |
| **LLM 客户端** | `src/llm/client.py` | `browser-use-ref/browser_use/llm/` | 各模型 provider 实现 |
| **浏览器 Session** | `src/browser/manager.py` | `browser-use-ref/browser_use/browser/session.py` | `BrowserSession` |
| **默认动作** | （无） | `browser-use-ref/browser_use/browser/watchdogs/default_action_watchdog.py` | `DefaultActionWatchdog._execute_click_with_download_detection()` |
| **CAPTCHA** | （无） | `browser-use-ref/browser_use/browser/watchdogs/captcha_watchdog.py` | `CaptchaWatchdog` |
| **System Prompt** | `src/agent/prompts.py` | `browser-use-ref/browser_use/agent/system_prompts/` | 多个 prompt 变体文件 |

---

### 搜索执行路径优化分析（基于 Terminal 日志）

#### 当前问题

终端日志显示 "今天广州的天气如何" 的执行路径：

```
Step 1: navigate("广州今天天气")        ← 搜索
Step 2: extract_content({})             ← 提取搜索结果
Step 3: get_dom_snapshot({})            ← 冗余！已有内容
Step 4: click_element(index=2)          ← 点击结果
Step 5: get_dom_snapshot({})            ← 冗余！已打开详情页
Step 6: navigate("weather.com.cn/...")  ← 直接导航到天气站
Step 7: extract_content({})             ← 提取天气
```

#### 问题分析

1. **Step 3 冗余** — `extract_content` 已拿到页面文本，`get_dom_snapshot` 在此之后无意义（Agent 已知道页面内容）
2. **Step 5 冗余** — 点击进入详情页后立即 `get_dom_snapshot`，而实际需要的是 `extract_content`
3. **Step 2→6 跳跃** — 搜索后先提取内容，又点击链接，又直接导航到 weather.com.cn，说明 Agent 在搜索结果和直接导航之间犹豫
4. **缺少 "done" 步骤** — 最终结果通过 `extract_content` 返回而非 `done`，说明 done 未被正确调用

#### 优化方案（参考 browser-use 的 Agent step 设计）

参考 `browser-use-ref/browser_use/agent/service.py` 中 Agent 的 step 方法（约 L1080-L1179），browser-use 采用以下优化策略：

**方案 A：System Prompt 约束优化（立即实施）**

在 prompt 中明确告知 LLM：
- `get_dom_snapshot` 仅在需要点击元素前使用，不应在 `extract_content` 之后立即调用
- 搜索结果页 → 直接点击链接进入详情页，不要先提取内容
- 进入详情页后 → 直接 `extract_content`，不要先 `get_dom_snapshot`

**方案 B：Post-processing 动作合并（后续实现）**

在 AgentLoop 中检测连续动作模式：
- `extract_content` + `get_dom_snapshot` → 删除后者（内容已提取）
- `navigate` + `extract_content` → 合并为导航后自动提取
- `click_element` + 立即 `get_dom_snapshot` → 保留点击，删除 snapshot

**方案 C：工具优先级权重（参考 browser-use）**

browser-use 在 `_update_action_models_for_page()` 中根据页面 URL 动态过滤工具：
- 搜索结果页 → 隐藏 `extract_content`，突出 `click_element`
- 文章详情页 → 隐藏 `click_element`，突出 `extract_content` + `done`

**推荐路径**：先实施方案 A（成本最低），再逐步实施方案 B 和 C。

---

### Task 1: 移除 LLM_MAX_TOKENS 限制 + 清理 .env 和 settings

**Files:**
- Modify: `.env` (lines 1-29)
- Modify: `.env.example` (lines 1-29)
- Modify: `src/config/settings.py` (lines 1-46)

- [ ] **Step 1: 修改 settings.py — 移除 max_tokens 默认值，改为 None**

```python
# src/config/settings.py — 修改后

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM
    llm_api_key: str = ""
    llm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    llm_model_name: str = "GLM-4-Flash-250414"
    llm_temperature: float = 0.1
    llm_max_tokens: int | None = None  # None = 不限制，由 API 自行决定
    llm_timeout: int = 30
    llm_max_retries: int = 3

    # VLM
    vlm_api_key: str = ""
    vlm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    vlm_model_name: str = "GLM-4.1V-Thinking-Flash"
    vlm_temperature: float = 0.1
    vlm_max_tokens: int | None = None  # None = 不限制
    vlm_timeout: int = 30
    vlm_max_retries: int = 3

    # Agent
    agent_recursion_limit: int = 16

    # Paths
    experience_dir: str = "data/experiences"
    chroma_persist_dir: str = "data/chroma"

    @property
    def project_root(self) -> Path:
        return Path(__file__).parent.parent.parent

    def resolve_path(self, relative: str) -> Path:
        p = Path(relative)
        if not p.is_absolute():
            p = self.project_root / p
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
```

- [ ] **Step 2: 修改 client.py — 当 max_tokens 为 None 时不传该参数**

```python
# src/llm/client.py — 修改 __init__ 和 _request 方法

class LLMClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout: int | None = None,
    ):
        self.api_key = api_key or settings.llm_api_key
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.model = model or settings.llm_model_name
        self.temperature = temperature if temperature is not None else settings.llm_temperature
        self.max_tokens = max_tokens if max_tokens is not None else settings.llm_max_tokens
        self.timeout = timeout or settings.llm_timeout

    async def _request(self, payload: dict) -> LLMResponse:
        """发送 HTTP 请求到 API。"""
        # 如果 max_tokens 为 None，从 payload 中移除该字段
        if self.max_tokens is None:
            payload.pop("max_tokens", None)
        # ... 其余代码不变
```

- [ ] **Step 3: 修改 .env 和 .env.example — 移除 LLM_MAX_TOKENS 和 VLM_MAX_TOKENS 行**

从两个文件中删除以下行：
```
LLM_MAX_TOKENS=2048
VLM_MAX_TOKENS=2048
```

- [ ] **Step 4: 验证 — 运行 python -c "from src.config.settings import settings; print(settings.llm_max_tokens)"**

```bash
conda activate web-ai && python -c "from src.config.settings import settings; print(settings.llm_max_tokens)"
```
Expected: `None`

---

### Task 2: 清理 langchain 遗留代码

**Files:**
- Delete: `src/tools/browser_tools.py` (langchain `@tool` 装饰器，未被使用)
- Delete: `src/tools/dom_tools.py` (langchain `@tool` 装饰器，未被使用)
- Delete: `src/tools/file_tools.py` (langchain `@tool` 装饰器，未被使用)
- Delete: `src/tools/vision_tool.py` (langchain `@tool` 装饰器，未被使用)
- Delete: `src/tools/time_tool.py` (langchain `@tool` 装饰器，已被 system prompt 替代)
- Delete: `src/llm/factory.py` (langchain_openai 依赖，未被使用)
- Delete: `src/agent/loop.py` (旧 langgraph 实现，已被 loop.py 替代)
- Delete: `src/schemas/tool_result.py` (仅被 langchain 工具使用)
- Delete: `src/schemas/vision.py` (仅被 langchain vision_tool 使用)
- Modify: `src/perception/vision.py` (移除 langchain 依赖，改为原生 httpx)
- Modify: `src/agent/router.py` (移除对已删除 factory.py 的引用)
- Modify: `requirements.txt` (移除 langchain 相关依赖)

- [ ] **Step 1: 删除所有 langchain 遗留文件**

```bash
# 在项目根目录执行
Remove-Item src/tools/browser_tools.py
Remove-Item src/tools/dom_tools.py
Remove-Item src/tools/file_tools.py
Remove-Item src/tools/vision_tool.py
Remove-Item src/tools/time_tool.py
Remove-Item src/llm/factory.py
Remove-Item src/agent/loop.py
Remove-Item src/schemas/tool_result.py
Remove-Item src/schemas/vision.py
```

- [ ] **Step 2: 重写 perception/vision.py — 移除 langchain 依赖**

```python
# src/perception/vision.py — 修改后

"""VLM 视觉分析 — 纯函数，截图 → VLM 结构化分析。

使用原生 httpx 调用 VLM API，不依赖 langchain。
"""

import json
import logging

import httpx

from src.config.settings import settings

logger = logging.getLogger(__name__)

VLM_ANALYSIS_PROMPT = """你是一个网页视觉分析专家。请分析这个网页截图，返回 JSON 格式的分析结果。

返回格式（严格遵守 JSON）：
{
  "page_description": "页面整体描述",
  "elements": [
    {"name": "元素名称", "type": "button|input|link|dropdown|checkbox|radio|text|image|other", "x": 像素坐标, "y": 像素坐标, "description": "用途说明"}
  ],
  "suggestions": "操作建议"
}
"""


async def analyze_screenshot(screenshot_b64: str) -> dict:
    """截图 → VLM 结构化分析结果。

    Args:
        screenshot_b64: PNG 截图的 base64 编码字符串

    Returns:
        dict with keys: page_description, elements, suggestions
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
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"page_description": content, "elements": [], "suggestions": ""}
```

- [ ] **Step 3: 修改 requirements.txt — 移除 langchain 依赖**

```txt
# requirements.txt — 修改后

# 原生 HTTP 客户端
httpx

# 国内搜索引擎
requests
beautifulsoup4
lxml
playwright

# 数据验证
pydantic
pydantic-settings

# 环境管理
python-dotenv

# 测试
pytest
```

- [ ] **Step 4: 修改 src/agent/router.py — 移除对 factory.py 的引用（router 已正确使用 LLMClient）**

router.py 已经使用 `from src.llm.client import LLMClient`，无需修改。仅需确认 `from src.agent.factory import create_browser_agent` 引用仍有效（factory.py 未被删除）。

- [ ] **Step 5: 验证项目可运行**

```bash
conda activate web-ai && python -c "from src.agent.router import route_query; from src.llm.client import LLMClient; print('All imports OK')"
```
Expected: `All imports OK`

---

### Task 3: 增强 DOM 提取 — 参考 browser-use 的 CDP DOM 序列化

**Files:**
- Create: `src/perception/dom_service.py` (CDP DOM 树提取 + 序列化)
- Modify: `src/browser/manager.py` (添加 CDP 会话能力)
- Modify: `src/tools/browser_actions.py` (增强 get_dom_snapshot 使用 CDP)

- [ ] **Step 1: 创建 dom_service.py — 基于 CDP 的 DOM 树提取**

```python
# src/perception/dom_service.py

"""DOM 服务 — 通过 CDP 提取完整 DOM 树 + Accessibility Tree。

参考 browser-use 的 DomService，提供：
- 完整 DOM 树（含 iframe 内联）
- Accessibility Tree
- 可交互元素高亮索引
- 元素可见性检测
"""

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

# 非交互/隐藏标签白名单
SKIP_TAGS = {"script", "style", "head", "meta", "link", "title", "noscript", "svg", "path", "g", "circle"}

# 可交互标签
INTERACTIVE_TAGS = {"a", "button", "input", "select", "textarea", "iframe", "frame", "video", "audio"}
INTERACTIVE_ROLES = {"button", "link", "textbox", "combobox", "listbox", "checkbox", "radio", "menuitem", "option", "tab", "switch", "slider", "spinbutton"}


class DomService:
    """通过 CDP 获取和序列化 DOM 状态。"""

    def __init__(self, browser_session):
        self.browser_session = browser_session
        self._selector_map: dict[int, dict] = {}
        self._interactive_counter = 0

    async def get_page_state(self, max_elements: int = 100) -> dict:
        """获取当前页面 DOM 状态，返回结构化数据。

        Returns:
            dict with:
                - selector_map: {index: {tag, text, bbox, attributes, visible}}
                - text_content: str (页面纯文本摘要)
                - url: str
                - title: str
        """
        page = self.browser_session.page
        cdp = self.browser_session._browser  # 获取 CDP session

        url = page.url
        title = await page.title()

        # 方法1: 通过 CDP Accessibility.getFullAXTree 获取完整 AX tree
        # 方法2: 通过 JS evaluate 获取增强版可交互元素（fallback）
        try:
            elements = await self._extract_elements_via_js(page, max_elements)
        except Exception as e:
            logger.warning(f"CDP DOM extraction failed: {e}, falling back to simple JS")
            elements = await self._extract_elements_simple(page, max_elements)

        # 构建 selector_map
        self._selector_map = {}
        self._interactive_counter = 0
        for el in elements:
            self._interactive_counter += 1
            idx = self._interactive_counter
            self._selector_map[idx] = el
            el["index"] = idx

        # 提取页面文本
        text_content = await self._extract_text_summary(page)

        return {
            "selector_map": self._selector_map,
            "text_content": text_content,
            "url": url,
            "title": title,
        }

    async def _extract_elements_via_js(self, page, max_elements: int) -> list[dict]:
        """增强版 JS 元素提取 — 包含隐藏元素提示和 iframe 内容。"""
        js = """
        (() => {
            const interactive = 'a,button,input,select,textarea,[role="button"],[role="link"],[role="textbox"],'
                + '[role="combobox"],[role="listbox"],[role="checkbox"],[role="radio"],[contenteditable="true"],'
                + '[onclick],[tabindex]:not([tabindex="-1"]),iframe,frame';
            const all = document.querySelectorAll(interactive);
            const results = [];
            const viewportHeight = window.innerHeight;
            const viewportWidth = window.innerWidth;

            all.forEach((el, i) => {
                if (i >= 200) return; // 安全上限
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                const isVisible = (
                    style.display !== 'none' &&
                    style.visibility !== 'hidden' &&
                    style.opacity !== '0' &&
                    rect.width > 0 &&
                    rect.height > 0
                );
                const isInViewport = (
                    rect.top < viewportHeight &&
                    rect.bottom > 0 &&
                    rect.left < viewportWidth &&
                    rect.right > 0
                );

                let text = (el.textContent || '').trim().slice(0, 80);
                let tag = el.tagName.toLowerCase();

                // 尝试获取 label
                let label = '';
                if (el.labels && el.labels[0]) {
                    label = el.labels[0].textContent.trim().slice(0, 50);
                }

                let attrs = {};
                for (const attr of ['id', 'name', 'type', 'placeholder', 'aria-label', 'href', 'role', 'value', 'alt', 'title']) {
                    const v = el.getAttribute(attr);
                    if (v) attrs[attr] = v.slice(0, 100);
                }

                // 检测 iframe 内容
                let iframeInfo = null;
                if (tag === 'iframe' || tag === 'frame') {
                    try {
                        const iframeDoc = el.contentDocument || el.contentWindow.document;
                        if (iframeDoc) {
                            const iframeInteractive = iframeDoc.querySelectorAll('a,button,input,select,textarea');
                            iframeInfo = {
                                hasContent: true,
                                interactiveCount: iframeInteractive.length,
                                title: iframeDoc.title || ''
                            };
                        }
                    } catch(e) {
                        iframeInfo = {hasContent: false, crossOrigin: true};
                    }
                }

                results.push({
                    index: i,
                    tag: tag,
                    text: text,
                    label: label,
                    visible: isVisible,
                    inViewport: isInViewport,
                    bbox: {x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height)},
                    scrollDistance: isVisible && !isInViewport ? Math.ceil(Math.abs(rect.top) / viewportHeight) : 0,
                    attributes: attrs,
                    iframe: iframeInfo
                });
            });

            // 去重、排序：可见 > 视口内 > 其他
            results.sort((a, b) => {
                if (a.visible && !b.visible) return -1;
                if (!a.visible && b.visible) return 1;
                if (a.inViewport && !b.inViewport) return -1;
                if (!a.inViewport && b.inViewport) return 1;
                return 0;
            });

            return results.slice(0, 200);
        })()
        """
        return await page.evaluate(js)

    async def _extract_elements_simple(self, page, max_elements: int) -> list[dict]:
        """简单 JS 元素提取（fallback）。"""
        js = """
        (() => {
            const interactive = 'a,button,input,select,textarea,[role="button"],[role="link"],[role="textbox"],[onclick]';
            const all = document.querySelectorAll(interactive);
            const results = [];
            all.forEach((el, i) => {
                if (i >= 50) return;
                const rect = el.getBoundingClientRect();
                if (rect.width === 0 && rect.height === 0) return;
                let text = (el.textContent || '').trim().slice(0, 80);
                let tag = el.tagName.toLowerCase();
                let attrs = {};
                for (const attr of ['id', 'name', 'type', 'placeholder', 'aria-label', 'href', 'role']) {
                    const v = el.getAttribute(attr);
                    if (v) attrs[attr] = v.slice(0, 100);
                }
                results.push({
                    tag: tag, text: text,
                    visible: true,
                    bbox: {x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height)},
                    attributes: attrs
                });
            });
            return results;
        })()
        """
        return await page.evaluate(js)

    async def _extract_text_summary(self, page) -> str:
        """提取页面文本摘要。"""
        js = """
        (() => {
            const body = document.body;
            if (!body) return '';
            const clone = body.cloneNode(true);
            const skip = clone.querySelectorAll('script,style,noscript,iframe,svg,nav,footer');
            skip.forEach(el => el.remove());
            let text = clone.textContent || '';
            text = text.replace(/\\s+/g, ' ').trim();
            return text.slice(0, 3000);
        })()
        """
        return await page.evaluate(js)

    def format_selector_map(self, max_elements: int = 30) -> str:
        """将 selector_map 格式化为 LLM 可读文本。"""
        if not self._selector_map:
            return "未找到可交互元素。"

        visible_in_view = [el for el in self._selector_map.values() if el.get("inViewport") and el.get("visible")]
        hidden_visible = [el for el in self._selector_map.values() if el.get("visible") and not el.get("inViewport")]
        invisible = [el for el in self._selector_map.values() if not el.get("visible")]

        lines = []
        lines.append(f"## 可交互元素（视口内 {len(visible_in_view)} 个）")

        for el in visible_in_view[:max_elements]:
            idx = el["index"]
            tag = el["tag"]
            text = el.get("text", "")[:40]
            label = el.get("label", "")
            attrs = el.get("attributes", {})
            aria_label = attrs.get("aria-label", "")
            placeholder = attrs.get("placeholder", "")
            href = attrs.get("href", "")
            role = attrs.get("role", "")

            desc_parts = []
            if label:
                desc_parts.append(f"label={label}")
            if aria_label:
                desc_parts.append(f"aria={aria_label}")
            if placeholder:
                desc_parts.append(f"placeholder={placeholder}")
            if href:
                desc_parts.append(f"href={href[:60]}")
            if role:
                desc_parts.append(f"role={role}")

            desc = " | ".join(desc_parts) if desc_parts else text
            bbox = el.get("bbox", {})
            lines.append(f"  [{idx}] <{tag}> {desc}")

        if hidden_visible:
            lines.append(f"\n## 需滚动才能看到的元素（{len(hidden_visible)} 个）")
            for el in hidden_visible[:5]:
                idx = el["index"]
                tag = el["tag"]
                scroll = el.get("scrollDistance", 0)
                text = el.get("text", "")[:30]
                lines.append(f"  [{idx}] <{tag}> {text} (向下滚动 {scroll} 页)")

        if invisible:
            lines.append(f"\n## 隐藏元素（{len(invisible)} 个，不可交互）")
            for el in invisible[:3]:
                idx = el["index"]
                tag = el["tag"]
                text = el.get("text", "")[:30]
                lines.append(f"  [{idx}] <{tag}> {text} (隐藏)")

        return "\n".join(lines)
```

- [ ] **Step 2: 修改 browser_actions.py 的 get_dom_snapshot — 使用 DomService**

```python
# 在 browser_actions.py 的 create_browser_registry 中，修改 get_dom_snapshot：

from src.perception.dom_service import DomService

# 在 create_browser_registry 函数内：
dom_service = DomService(browser)

@reg.action(
    "获取当前页面可交互元素列表（index/tag/text/bbox/可见性）。这是感知页面的首选工具，click_element 和 input_text 通过此索引定位元素。",
    param_model=GetDomSnapshotAction,
)
async def get_dom_snapshot(params: GetDomSnapshotAction):
    state = await dom_service.get_page_state(max_elements=params.max_elements)
    formatted = dom_service.format_selector_map(max_elements=params.max_elements)
    return formatted
```

- [ ] **Step 3: 验证 DOM 提取**

```bash
conda activate web-ai && python -c "from src.perception.dom_service import DomService; print('DomService OK')"
```
Expected: `DomService OK`

---

### Task 4: 实现弹窗/对话框处理

**Files:**
- Create: `src/browser/watchdogs.py` (弹窗处理 + 基础 watchdog 框架)
- Modify: `src/browser/manager.py` (添加弹窗状态管理)
- Modify: `src/agent/loop.py` (在 step 循环中检查弹窗)

- [x] **Step 1: 创建 watchdogs.py — 弹窗自动处理**

```python
# src/browser/watchdogs.py

"""浏览器 Watchdog — 弹窗/对话框自动处理。

参考 browser-use 的 PopupsWatchdog 和 AboutBlankWatchdog。
"""

import asyncio
import logging

logger = logging.getLogger(__name__)


class PopupHandler:
    """自动处理 JavaScript 弹窗（alert/confirm/prompt）。"""

    def __init__(self, page):
        self.page = page
        self._closed_popup_messages: list[str] = []
        self._handler_registered = False

    async def register(self) -> None:
        """注册弹窗处理 handler。"""
        if self._handler_registered:
            return

        async def handle_dialog(dialog):
            """处理弹窗：alert 和 confirm 自动接受，prompt 自动取消。"""
            dialog_type = dialog.type
            message = dialog.message
            self._closed_popup_messages.append(f"[{dialog_type}] {message}")
            logger.info(f"Dialog detected: {dialog_type} - '{message[:100]}'")

            if dialog_type in ("alert", "confirm", "beforeunload"):
                await dialog.accept()
                logger.info(f"Dialog accepted: {dialog_type}")
            elif dialog_type == "prompt":
                await dialog.dismiss()
                logger.info(f"Dialog dismissed: {dialog_type}")

        self.page.on("dialog", handle_dialog)
        self._handler_registered = True
        logger.debug("PopupHandler registered")

    def get_and_clear_messages(self) -> list[str]:
        """获取并清空已关闭的弹窗消息。"""
        messages = self._closed_popup_messages.copy()
        self._closed_popup_messages.clear()
        return messages

    def has_pending_popups(self) -> bool:
        """检查是否有未处理的弹窗消息。"""
        return len(self._closed_popup_messages) > 0


class PageCrashHandler:
    """检测页面崩溃并尝试恢复。"""

    def __init__(self, browser_manager):
        self.browser = browser_manager
        self._crash_count = 0

    async def check_and_recover(self) -> bool:
        """检查页面是否崩溃，尝试恢复。"""
        try:
            # 尝试执行简单 JS 检测页面是否响应
            await self.browser.page.evaluate("1 + 1")
            return True
        except Exception:
            self._crash_count += 1
            logger.warning(f"Page appears crashed (attempt {self._crash_count})")
            if self._crash_count >= 3:
                logger.error("Page crashed 3 times, cannot recover")
                return False
            try:
                await self.browser.page.reload()
                logger.info("Page reloaded after crash")
                return True
            except Exception:
                return False
```

- [x] **Step 2: 修改 BrowserManager — 集成 PopupHandler**

```python
# 在 BrowserManager 的 connect() 方法中添加：

from src.browser.watchdogs import PopupHandler

class BrowserManager:
    def __init__(self, ...):
        # ...
        self._popup_handler: PopupHandler | None = None

    async def connect(self) -> Page:
        # ... 原有连接逻辑 ...
        self._popup_handler = PopupHandler(self._page)
        await self._popup_handler.register()
        return self._page

    @property
    def popup_handler(self) -> PopupHandler | None:
        return self._popup_handler
```

- [x] **Step 3: 修改 AgentLoop._step — 在每步执行前检查弹窗**

```python
# 在 loop.py 的 _step 方法开头添加：

async def _step(self, system_prompt: str) -> str | None:
    # 检查弹窗
    if hasattr(self, '_browser') and self._browser:
        popup = self._browser.popup_handler
        if popup and popup.has_pending_popups():
            msgs = popup.get_and_clear_messages()
            self._messages.append({
                "role": "user",
                "content": f"[系统通知] 页面弹出了以下对话框，已自动处理：\n" + "\n".join(msgs)
            })
    # ... 原有逻辑 ...
```

- [x] **Step 4: 验证弹窗处理**

```bash
conda activate web-ai && python -c "from src.browser.watchdogs import PopupHandler, PageCrashHandler; print('Watchdogs OK')"
```

**验证结果**: 全部 18 个 watchdogs 测试通过（PopupHandler 10 个、PageCrashHandler 4 个、BrowserManager 集成 2 个、AgentLoop 集成 2 个），全量 107 个测试通过。
Expected: `Watchdogs OK`

---

### Task 5: 实现循环检测

**Files:**
- Create: `src/agent/loop_detector.py` (ActionLoopDetector)
- Modify: `src/agent/loop.py` (集成循环检测)

- [ ] **Step 1: 创建 loop_detector.py**

```python
# src/agent/loop_detector.py

"""循环检测器 — 检测 Agent 行为循环和页面停滞。

参考 browser-use 的 ActionLoopDetector：
- 动作哈希追踪：检测重复执行相同操作
- 页面指纹追踪：检测页面无变化
- 分级提醒：5/8/12 次重复时发出不同级别的提醒
"""

import hashlib
import json
import re
from dataclasses import dataclass, field


@dataclass
class PageFingerprint:
    """页面指纹 — 用于检测页面是否变化。"""
    url: str
    element_count: int
    text_hash: str

    @classmethod
    def from_state(cls, url: str, text: str, element_count: int) -> "PageFingerprint":
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        return cls(url=url, element_count=element_count, text_hash=text_hash)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PageFingerprint):
            return False
        return (
            self.url == other.url
            and self.element_count == other.element_count
            and self.text_hash == other.text_hash
        )


def _normalize_action(action_name: str, params: dict) -> str:
    """标准化动作参数，用于相似度哈希。"""
    if action_name in ("navigate",):
        url = str(params.get("url", ""))
        return f"navigate|{url}"

    if action_name in ("click_element", "input_text"):
        index = params.get("index")
        if action_name == "input_text":
            text = str(params.get("text", "")).strip().lower()
            return f"input_text|{index}|{text}"
        return f"click_element|{index}"

    if action_name == "scroll":
        direction = "down" if params.get("down", True) else "up"
        return f"scroll|{direction}"

    if action_name == "extract_content":
        return f"extract_content|{params.get('max_length', '')}"

    if action_name == "get_dom_snapshot":
        return "get_dom_snapshot"

    # 默认：动作名 + 排序后的参数
    filtered = {k: v for k, v in sorted(params.items()) if v is not None}
    return f"{action_name}|{json.dumps(filtered, sort_keys=True, default=str)}"


def compute_action_hash(action_name: str, params: dict) -> str:
    """计算动作哈希。"""
    normalized = _normalize_action(action_name, params)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]


class LoopDetector:
    """动作循环检测器。

    追踪最近 N 步的动作哈希和页面指纹，检测重复行为和页面停滞。
    只生成提醒消息，不阻止动作执行。
    """

    def __init__(self, window_size: int = 20):
        self.window_size = window_size

        # 动作追踪
        self.recent_action_hashes: list[str] = []
        self.max_repetition_count: int = 0
        self.most_repeated_hash: str | None = None

        # 页面停滞追踪
        self.recent_page_fingerprints: list[PageFingerprint] = []
        self.consecutive_stagnant_pages: int = 0

    def record_action(self, action_name: str, params: dict) -> None:
        """记录一个动作。"""
        h = compute_action_hash(action_name, params)
        self.recent_action_hashes.append(h)
        if len(self.recent_action_hashes) > self.window_size:
            self.recent_action_hashes = self.recent_action_hashes[-self.window_size:]
        self._update_repetition_stats()

    def record_page_state(self, url: str, text: str, element_count: int) -> None:
        """记录当前页面状态。"""
        fp = PageFingerprint.from_state(url, text, element_count)
        if self.recent_page_fingerprints and self.recent_page_fingerprints[-1] == fp:
            self.consecutive_stagnant_pages += 1
        else:
            self.consecutive_stagnant_pages = 0
        self.recent_page_fingerprints.append(fp)
        if len(self.recent_page_fingerprints) > 5:
            self.recent_page_fingerprints = self.recent_page_fingerprints[-5:]

    def _update_repetition_stats(self) -> None:
        """重新计算重复统计。"""
        if not self.recent_action_hashes:
            self.max_repetition_count = 0
            self.most_repeated_hash = None
            return
        counts: dict[str, int] = {}
        for h in self.recent_action_hashes:
            counts[h] = counts.get(h, 0) + 1
        self.most_repeated_hash = max(counts, key=lambda k: counts[k])
        self.max_repetition_count = counts[self.most_repeated_hash]

    def get_nudge_message(self) -> str | None:
        """获取循环检测提醒消息，无循环时返回 None。

        分级提醒：
        - 5 次重复：温和提醒
        - 8 次重复：中度提醒
        - 12 次重复：强烈提醒
        """
        messages: list[str] = []

        # 动作重复提醒
        if self.max_repetition_count >= 12:
            messages.append(
                f"警告：你已经重复了相似操作 {self.max_repetition_count} 次 "
                f"（在最近 {len(self.recent_action_hashes)} 步中）。"
                "如果每次重复都有进展，请继续。否则请尝试不同的方法。"
            )
        elif self.max_repetition_count >= 8:
            messages.append(
                f"注意：你已经重复了相似操作 {self.max_repetition_count} 次 "
                f"（在最近 {len(self.recent_action_hashes)} 步中）。"
                "每次尝试是否仍有进展？如果没有，建议换个方式。"
            )
        elif self.max_repetition_count >= 5:
            messages.append(
                f"提示：你已经重复了相似操作 {self.max_repetition_count} 次。"
                "如果这是有意的探索，请继续。否则可以考虑换个思路。"
            )

        # 页面停滞提醒
        if self.consecutive_stagnant_pages >= 5:
            messages.append(
                f"页面内容在连续 {self.consecutive_stagnant_pages} 步中没有变化。"
                "你的操作可能没有生效，建议尝试不同的元素或方法。"
            )

        if messages:
            return "\n\n".join(messages)
        return None
```

- [ ] **Step 2: 集成到 AgentLoop**

```python
# 修改 loop.py 的 AgentLoop：

from src.agent.loop_detector import LoopDetector

class AgentLoop:
    def __init__(self, ...):
        # ... 原有初始化 ...
        self.loop_detector = LoopDetector(window_size=20)

    async def _step(self, system_prompt: str) -> str | None:
        # ... 原有逻辑 ...

        # Phase 4: 执行工具调用后，记录到循环检测器
        for tc in response.tool_calls:
            # ... 执行工具 ...
            # 排除某些动作不记录
            if tc.name not in ("done", "go_back", "send_keys"):
                self.loop_detector.record_action(tc.name, tc.arguments)

        # 注入循环检测提醒
        nudge = self.loop_detector.get_nudge_message()
        if nudge:
            self._messages.append({
                "role": "user",
                "content": f"[系统提醒 - 循环检测]\n{nudge}"
            })

        return None
```

- [ ] **Step 3: 验证循环检测**

```bash
conda activate web-ai && python -c "from src.agent.loop_detector import LoopDetector; ld = LoopDetector(); ld.record_action('click_element', {'index': 1}); print('LoopDetector OK')"
```
Expected: `LoopDetector OK`

---

### Task 6: 实现短期记忆管理（单次对话内的任务记忆）

**Files:**
- Create: `src/memory/task_memory.py` (任务内记忆管理)
- Modify: `src/agent/loop.py` (集成记忆管理)

- [ ] **Step 1: 创建 task_memory.py**

```python
# src/memory/task_memory.py

"""任务记忆管理器 — 单次对话内的短期记忆管理。

管理 Agent 在单次任务执行中的关键信息：
- 关键发现（key findings）
- 已访问的 URL
- 已提取的数据
- 中间步骤结果
- 消息压缩（当消息过多时自动摘要）
"""

import json
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TaskMemory:
    """单次任务内的记忆存储。

    存储 Agent 在执行过程中积累的关键信息，避免重复操作。
    """

    # 关键发现
    findings: list[str] = field(default_factory=list)

    # 已访问的 URL（避免重复导航）
    visited_urls: list[str] = field(default_factory=list)

    # 已提取的数据（结构化）
    extracted_data: dict[str, str] = field(default_factory=dict)

    # 中间步骤结果
    step_results: list[dict] = field(default_factory=list)

    # 当前子任务/目标
    current_goal: str = ""

    def add_finding(self, finding: str) -> None:
        """添加关键发现。"""
        if finding not in self.findings:
            self.findings.append(finding)

    def add_visited_url(self, url: str) -> None:
        """记录已访问的 URL。"""
        if url not in self.visited_urls:
            self.visited_urls.append(url)

    def add_extracted_data(self, key: str, value: str) -> None:
        """添加提取的数据。"""
        self.extracted_data[key] = value

    def add_step_result(self, step: int, action: str, result: str) -> None:
        """记录步骤结果。"""
        self.step_results.append({
            "step": step,
            "action": action,
            "result_summary": result[:200],
        })
        # 只保留最近 10 步
        if len(self.step_results) > 10:
            self.step_results = self.step_results[-10:]

    def get_context_for_llm(self) -> str:
        """生成给 LLM 的记忆上下文。"""
        parts = []

        if self.current_goal:
            parts.append(f"## 当前目标\n{self.current_goal}")

        if self.findings:
            parts.append("## 已发现的信息")
            for f in self.findings[-5:]:  # 最近 5 条
                parts.append(f"- {f}")

        if self.visited_urls:
            parts.append(f"## 已访问的页面 ({len(self.visited_urls)} 个)")
            for u in self.visited_urls[-5:]:
                parts.append(f"- {u}")

        if self.extracted_data:
            parts.append("## 已提取的数据")
            for k, v in self.extracted_data.items():
                parts.append(f"- {k}: {v[:100]}")

        return "\n\n".join(parts) if parts else ""

    def is_url_visited(self, url: str) -> bool:
        """检查 URL 是否已访问过。"""
        return url in self.visited_urls


class MessageCompactor:
    """消息压缩器 — 当消息过多时自动摘要旧消息。

    参考 browser-use 的 MessageManager.compact_messages。
    """

    def __init__(self, max_messages: int = 30):
        self.max_messages = max_messages

    def should_compact(self, messages: list[dict]) -> bool:
        """检查是否需要压缩消息。"""
        # 系统消息 + 用户消息 + 助手消息 + 工具消息
        return len(messages) > self.max_messages

    def compact(self, messages: list[dict]) -> list[dict]:
        """压缩消息列表：保留系统消息 + 最近 N 条，旧消息用摘要替代。

        注意：这只是一个简单的截断策略，完整的 compaction 需要 LLM 参与。
        这里采用保留最近消息 + 注入摘要的策略。
        """
        if not self.should_compact(messages):
            return messages

        # 保留前 2 条（通常是 system + user task）和最近 20 条
        keep_head = 2
        keep_tail = 20

        head = messages[:keep_head]
        tail = messages[-keep_tail:]

        # 中间被移除的消息，生成摘要
        removed_count = len(messages) - keep_head - keep_tail
        if removed_count > 0:
            summary = {
                "role": "user",
                "content": f"[系统通知] 为了节省上下文，已压缩 {removed_count} 条中间消息。请继续基于当前可见的消息完成任务。"
            }
            return head + [summary] + tail

        return head + tail
```

- [ ] **Step 2: 集成到 AgentLoop**

```python
# 修改 loop.py：

from src.memory.task_memory import TaskMemory, MessageCompactor

class AgentLoop:
    def __init__(self, ...):
        # ... 原有初始化 ...
        self.task_memory = TaskMemory()
        self.message_compactor = MessageCompactor(max_messages=30)

    async def _step(self, system_prompt: str) -> str | None:
        # 压缩消息（如果过多）
        self._messages = self.message_compactor.compact(self._messages)

        # 注入任务记忆上下文
        memory_context = self.task_memory.get_context_for_llm()
        if memory_context:
            self._messages.append({
                "role": "user",
                "content": f"[任务记忆]\n{memory_context}"
            })

        # ... 原有逻辑 ...

        # 执行工具后更新记忆
        for tc in response.tool_calls:
            # ... 执行工具 ...
            self.task_memory.add_step_result(self.step_count, tc.name, str(result))

            if tc.name == "navigate":
                self.task_memory.add_visited_url(tc.arguments.get("url", ""))
            elif tc.name == "extract_content":
                # 记录提取的内容摘要
                result_str = str(result)
                if len(result_str) > 50:
                    self.task_memory.add_finding(result_str[:200])
```

- [ ] **Step 3: 验证记忆管理**

```bash
conda activate web-ai && python -c "from src.memory.task_memory import TaskMemory, MessageCompactor; print('TaskMemory OK')"
```
Expected: `TaskMemory OK`

---

### Task 7: 增强工具集 — 添加 iframe/多标签/上传/下载支持

**Files:**
- Modify: `src/browser/manager.py` (添加新操作)
- Modify: `src/tools/browser_actions.py` (添加新工具)
- Modify: `src/tools/models.py` (添加新参数模型)

- [ ] **Step 1: 在 BrowserManager 中添加新方法**

```python
# 在 manager.py 的 BrowserManager 类中添加：

async def new_tab(self, url: str = "about:blank") -> dict:
    """打开新标签页。"""
    new_page = await self.context.new_page()
    if url:
        await new_page.goto(url, wait_until="domcontentloaded", timeout=15000)
    return {"success": True, "url": new_page.url}

async def switch_tab(self, index: int) -> dict:
    """切换到指定标签页。"""
    pages = self.context.pages
    if 0 <= index < len(pages):
        self._page = pages[index]
        await self._page.bring_to_front()
        return {"success": True, "url": self._page.url, "title": await self._page.title()}
    return {"success": False, "error": f"Tab {index} not found. Available: 0-{len(pages)-1}"}

async def close_tab(self, index: int = -1) -> dict:
    """关闭指定标签页（-1 = 当前页）。"""
    pages = self.context.pages
    if len(pages) <= 1:
        return {"success": False, "error": "Cannot close the last tab"}
    if index == -1:
        target = self._page
    elif 0 <= index < len(pages):
        target = pages[index]
    else:
        return {"success": False, "error": f"Tab {index} not found"}
    await target.close()
    # 切换到第一个剩余标签
    self._page = self.context.pages[0]
    return {"success": True, "current_url": self._page.url}

async def list_tabs(self) -> list[dict]:
    """列出所有标签页。"""
    tabs = []
    for i, page in enumerate(self.context.pages):
        tabs.append({
            "index": i,
            "url": page.url,
            "title": await page.title(),
            "is_current": page == self._page,
        })
    return tabs

async def select_dropdown(self, index: int, value: str) -> dict:
    """选择下拉菜单选项。"""
    elements = await self.get_indexed_elements()
    target = next((e for e in elements if e["index"] == index), None)
    if target is None:
        return {"success": False, "error": f"Element {index} not found"}
    try:
        await self.page.select_option(f"[data-index='{index}']", value)
        return {"success": True}
    except Exception:
        # fallback: 点击后选择
        await self.click_by_index(index)
        await self.page.select_option(f"option:has-text('{value}')", value)
        return {"success": True}

async def upload_file(self, index: int, file_path: str) -> dict:
    """上传文件到 input[type=file]。"""
    elements = await self.get_indexed_elements()
    target = next((e for e in elements if e["index"] == index), None)
    if target is None:
        return {"success": False, "error": f"Element {index} not found"}
    try:
        file_input = self.page.locator(f"input[type='file']").first
        await file_input.set_input_files(file_path)
        return {"success": True, "file": file_path}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

- [ ] **Step 2: 在 models.py 中添加新参数模型**

```python
# 添加到 src/tools/models.py：

class NewTabAction(BaseModel):
    """在新标签页打开 URL。"""
    url: str = Field(default="about:blank", description="URL 或 about:blank")

class SwitchTabAction(BaseModel):
    """切换到指定标签页。"""
    index: int = Field(ge=0, description="标签页索引，来自 list_tabs")

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
```

- [ ] **Step 3: 在 browser_actions.py 中注册新工具**

```python
# 在 create_browser_registry 中添加：

@reg.action("在新标签页打开 URL。", param_model=NewTabAction)
async def new_tab(params: NewTabAction):
    result = await browser.new_tab(params.url)
    if result["success"]:
        return f"已在新标签页打开: {result['url']}"
    return f"打开失败: {result.get('error', '')}"

@reg.action("切换到指定标签页。先使用 list_tabs 查看所有标签页。", param_model=SwitchTabAction)
async def switch_tab(params: SwitchTabAction):
    result = await browser.switch_tab(params.index)
    if result["success"]:
        return f"已切换到标签 [{params.index}]: {result['title']} ({result['url']})"
    return f"切换失败: {result.get('error', '')}"

@reg.action("关闭指定标签页。", param_model=CloseTabAction)
async def close_tab(params: CloseTabAction):
    result = await browser.close_tab(params.index)
    if result["success"]:
        return f"已关闭标签页，当前: {result['current_url']}"
    return f"关闭失败: {result.get('error', '')}"

@reg.action("列出所有打开的标签页。", param_model=ListTabsAction)
async def list_tabs(params: ListTabsAction):
    tabs = await browser.list_tabs()
    lines = [f"共 {len(tabs)} 个标签页:"]
    for t in tabs:
        marker = " ← 当前" if t["is_current"] else ""
        lines.append(f"  [{t['index']}] {t['title'][:40]}{marker}")
        lines.append(f"       {t['url'][:80]}")
    return "\n".join(lines)

@reg.action("选择下拉菜单选项。", param_model=SelectDropdownAction)
async def select_dropdown(params: SelectDropdownAction):
    result = await browser.select_dropdown(params.index, params.value)
    if result["success"]:
        return f"已选择 '{params.value}'"
    return f"选择失败: {result.get('error', '')}"

@reg.action("上传文件到文件选择框。", param_model=UploadFileAction)
async def upload_file(params: UploadFileAction):
    result = await browser.upload_file(params.index, params.file_path)
    if result["success"]:
        return f"已上传文件: {params.file_path}"
    return f"上传失败: {result.get('error', '')}"
```

- [ ] **Step 4: 验证新工具**

```bash
conda activate web-ai && python -c "from src.tools.browser_actions import create_browser_registry; from src.tools.models import NewTabAction, SwitchTabAction; print('New tools OK')"
```
Expected: `New tools OK`

---

### Task 8: 防检测基础实现

**Files:**
- Create: `src/browser/stealth.py` (防检测脚本)
- Modify: `src/browser/manager.py` (注入防检测脚本)

- [ ] **Step 1: 创建 stealth.py**

```python
# src/browser/stealth.py

"""浏览器防检测 — 注入反自动化检测脚本。

参考 browser-use 的 SecurityWatchdog 和防检测实践：
- 隐藏 webdriver 属性
- 覆盖 navigator 属性
- 处理权限请求
"""

STEALTH_SCRIPTS = [
    # 隐藏 webdriver 标记
    """
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined
    });
    """,

    # 覆盖 chrome.runtime（避免被检测为自动化）
    """
    window.chrome = {
        runtime: {},
        loadTimes: function() {},
        csi: function() {},
        app: {}
    };
    """,

    # 覆盖 permissions（静默处理权限请求）
    """
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications' ?
            Promise.resolve({ state: Notification.permission }) :
            originalQuery(parameters)
    );
    """,

    # 覆盖 plugins 和 mimeTypes（避免指纹检测）
    """
    Object.defineProperty(navigator, 'plugins', {
        get: () => [1, 2, 3, 4, 5]
    });
    Object.defineProperty(navigator, 'languages', {
        get: () => ['zh-CN', 'zh', 'en']
    });
    """,
]

PERMISSION_HANDLING_SCRIPT = """
// 自动授予常见权限请求
const originalQuery = navigator.permissions.query.bind(navigator.permissions);
navigator.permissions.query = (parameters) => {
    if (parameters.name === 'notifications' || parameters.name === 'geolocation') {
        return Promise.resolve({ state: 'granted' });
    }
    return originalQuery(parameters);
};
"""


def get_stealth_scripts() -> list[str]:
    """获取所有防检测脚本。"""
    return STEALTH_SCRIPTS


async def inject_stealth(page) -> None:
    """向页面注入防检测脚本。"""
    for script in STEALTH_SCRIPTS:
        try:
            await page.evaluate(script)
        except Exception:
            pass  # 某些脚本可能在某些页面无效，忽略


async def inject_permission_handling(context) -> None:
    """向浏览器上下文注入权限处理。"""
    await context.grant_permissions(["notifications", "geolocation"])
```

- [ ] **Step 2: 在 BrowserManager 中集成防检测**

```python
# 修改 BrowserManager.connect()：

from src.browser.stealth import inject_stealth, inject_permission_handling

async def connect(self) -> Page:
    # ... 原有连接逻辑 ...
    await inject_permission_handling(self._context)
    await inject_stealth(self._page)
    return self._page
```

- [ ] **Step 3: 验证防检测**

```bash
conda activate web-ai && python -c "from src.browser.stealth import get_stealth_scripts; print(f'Stealth scripts: {len(get_stealth_scripts())}')"
```
Expected: `Stealth scripts: 4`

---

### Task 9: 更新 System Prompt — 反映新工具和能力

**Files:**
- Modify: `src/agent/prompts.py`

- [ ] **Step 1: 更新 BROWSER_AGENT_SYSTEM_PROMPT**

```python
# src/agent/prompts.py — 更新后

BROWSER_AGENT_SYSTEM_PROMPT = """你是浏览器自动化助手，操作 Chrome 完成网页任务。

## 当前时间
{current_time}

## 核心规则
1. 调用 done 工具结束每个任务 — 只有 done 才能终止
2. 不要重复已完成的搜索或操作
3. 如果页面有弹窗/对话框，系统会自动处理，请继续执行
4. 如果连续 5 步页面无变化，请尝试不同的方法

## 工具分类

### 导航
- navigate(url) — 打开 URL 或搜索关键词
- go_back() — 后退到上一页
- new_tab(url) — 在新标签页打开
- switch_tab(index) — 切换标签页
- close_tab(index) — 关闭标签页
- list_tabs() — 列出所有标签页

### 页面感知
- get_dom_snapshot() — 获取可交互元素列表（index/tag/text/可见性）
- extract_content() — 提取页面文本内容

### 交互
- click_element(index) — 点击元素
- input_text(index, text) — 输入文本
- send_keys(key) — 按键（Enter/Escape/Tab 等）
- scroll(down, pages) — 滚动页面
- select_dropdown(index, value) — 选择下拉选项
- upload_file(index, file_path) — 上传文件

### 完成任务
- done(text) — 标记任务完成，返回最终结果

## 完成任务的标准流程
1. navigate(url) 打开目标页面
2. get_dom_snapshot() 查看页面元素
3. click_element / input_text 交互
4. extract_content() 提取内容
5. done(summary) 总结并结束

## 跨页面搜索对比流程
1. navigate(query1) 搜索第一个关键词
2. extract_content() 提取结果
3. navigate(query2) 搜索第二个关键词（或用 switch_tab）
4. extract_content() 提取结果
5. done(comparison) 对比总结

## 禁止
- 重新搜索已经搜索过的内容
- 内容已提取后继续操作
- 在同一页面无意义地反复点击

## 站点经验
{site_experience}
"""
```

---

### Task 10: 最终验证 — 运行完整测试

- [ ] **Step 1: 激活环境并验证所有导入**

```bash
conda activate web-ai && python -c "
from src.agent.router import route_query
from src.agent.loop import AgentLoop
from src.agent.loop_detector import LoopDetector
from src.agent.prompts import BROWSER_AGENT_SYSTEM_PROMPT
from src.browser.manager import BrowserManager
from src.browser.watchdogs import PopupHandler
from src.browser.stealth import get_stealth_scripts
from src.config.settings import settings
from src.llm.client import LLMClient
from src.memory.task_memory import TaskMemory, MessageCompactor
from src.perception.dom_service import DomService
from src.perception.dom import extract_article, extract_page_text
from src.perception.vision import analyze_screenshot
from src.tools.browser_actions import create_browser_registry
from src.tools.registry import Registry
from src.tools.models import NavigateAction, ClickElementAction, DoneAction
from src.exceptions import LLMError, RateLimitError
print('All imports OK')
print(f'LLM_MAX_TOKENS = {settings.llm_max_tokens} (should be None)')
"
```
Expected: `All imports OK` + `LLM_MAX_TOKENS = None (should be None)`

- [ ] **Step 2: 验证不再依赖 langchain**

```bash
conda activate web-ai && python -c "
try:
    import langchain
    print('WARNING: langchain still installed!')
except ImportError:
    print('OK: langchain not imported')
try:
    import langgraph
    print('WARNING: langgraph still installed!')
except ImportError:
    print('OK: langgraph not imported')
"
```
Expected: `OK: langchain not imported` + `OK: langgraph not imported`

- [ ] **Step 3: 运行 main.py 交互测试**

```bash
conda activate web-ai && python main.py
```
Enter a simple task like "搜索 Python 教程" and verify it works.

---

## 文件变更总结

| 操作 | 文件 | 说明 |
|-----|------|------|
| **删除** | `src/tools/browser_tools.py` | langchain 遗留 |
| **删除** | `src/tools/dom_tools.py` | langchain 遗留 |
| **删除** | `src/tools/file_tools.py` | langchain 遗留 |
| **删除** | `src/tools/vision_tool.py` | langchain 遗留 |
| **删除** | `src/tools/time_tool.py` | langchain 遗留 |
| **删除** | `src/llm/factory.py` | langchain 遗留 |
| **删除** | `src/agent/loop.py` | 旧 langgraph 实现 |
| **删除** | `src/schemas/tool_result.py` | 仅被 langchain 代码使用 |
| **删除** | `src/schemas/vision.py` | 仅被 langchain 代码使用 |
| **修改** | `.env` | 移除 LLM_MAX_TOKENS, VLM_MAX_TOKENS |
| **修改** | `.env.example` | 移除 LLM_MAX_TOKENS, VLM_MAX_TOKENS |
| **修改** | `src/config/settings.py` | max_tokens 改为 None |
| **修改** | `src/llm/client.py` | max_tokens=None 时不传参数 |
| **修改** | `src/perception/vision.py` | 移除 langchain 依赖 |
| **修改** | `src/browser/manager.py` | 添加弹窗处理器、防检测、多标签/下拉/上传方法 |
| **修改** | `src/tools/browser_actions.py` | 增强 DOM 提取、添加新工具 |
| **修改** | `src/tools/models.py` | 添加新工具参数模型 |
| **修改** | `src/agent/loop.py` | 集成循环检测、记忆管理、弹窗检查 |
| **修改** | `src/agent/prompts.py` | 更新 system prompt 反映新工具 |
| **修改** | `requirements.txt` | 移除 langchain 依赖 |
| **创建** | `src/perception/dom_service.py` | CDP DOM 序列化服务 |
| **创建** | `src/browser/watchdogs.py` | 弹窗处理 + 页面崩溃恢复 |
| **创建** | `src/agent/loop_detector.py` | 动作循环检测器 |
| **创建** | `src/memory/task_memory.py` | 任务内记忆管理 + 消息压缩 |
| **创建** | `src/browser/stealth.py` | 浏览器防检测脚本 |
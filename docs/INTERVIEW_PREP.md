# Agent 开发岗位面试准备文档

> 基于 web-insight 项目实战经验，覆盖浏览器自动化 Agent 核心知识点。

---

## 一、项目概述 (30 秒自我介绍)

**web-insight** 是一个简化教学版的 browser-use 实现，使用原生 Python + Playwright + httpx 构建浏览器自动化 Agent，不依赖 langchain/langgraph。

**核心能力：**
- CDP 连接控制 Chrome 浏览器
- LLM (OpenAI-compatible API) 决策工具调用
- 18+ 浏览器操作工具（导航、点击、输入、上传、标签页管理等）
- 循环检测、短期记忆、弹窗处理、防检测
- 三层执行路径优化（Prompt + 后处理 + 工具过滤）

---

## 二、核心知识点详解

### 2.1 浏览器自动化架构

**Q: 为什么选择 Playwright CDP 而不是 Selenium？**

| 维度 | Playwright CDP | Selenium WebDriver |
|------|---------------|-------------------|
| 协议 | Chrome DevTools Protocol | JSON Wire Protocol / W3C |
| 连接方式 | connect_over_cdp 连接已有 Chrome | 启动新 WebDriver 进程 |
| 速度 | 快（直接复用用户浏览器） | 慢（需启动独立进程） |
| 防检测 | 容易（用户真实浏览器） | 难（webdriver 标记明显） |
| 多标签页 | 原生支持 | 需额外处理 |
| 弹窗处理 | page.on('dialog') | Alert API |

**关键代码：**
```python
# src/browser/manager.py
self._browser = await playwright.chromium.connect_over_cdp(
    "http://localhost:9222"
)
```

---

### 2.2 Agent Loop 设计

**Q: 描述 Agent 的决策循环？**

```
while not done and steps < max_steps:
    1. 构建上下文 (system_prompt + history + memory)
    2. 工具优先级过滤 (根据页面类型隐藏冗余工具)
    3. 调用 LLM 获取 tool_calls
    4. 冗余动作合并 (post-processing)
    5. 顺序执行工具
    6. 更新记忆和循环检测器
    7. 检查终止条件
```

**关键设计决策：**
- **顺序执行** 而非并行：浏览器操作有状态依赖（如必须先 navigate 再 click）
- **工具调用日志**：记录到 `data/tool_calls.log` 便于调试
- **失败重试**：连续失败 5 次自动终止，防止无限循环

---

### 2.3 工具注册与调用

**Q: 如何实现工具的动态注册和 LLM 调用？**

**Registry 模式：**
```python
# src/tools/registry.py
class Registry:
    def action(self, description: str, param_model: type[BaseModel]):
        def decorator(func):
            self._actions[name] = Action(func, description, param_model)
        return decorator

    def get_tool_schemas(self) -> list[dict]:
        # 生成 OpenAI function calling schema
        return [{"type": "function", "function": {...}}]
```

**使用 Pydantic 模型定义参数：**
```python
class ClickElementAction(BaseModel):
    index: int = Field(ge=0, description="元素索引")
```

**优势：**
- 类型安全：LLM 返回的参数自动验证
- 自文档：schema 自动生成，无需手动维护 JSON

---

### 2.4 循环检测 (Task 5)

**Q: 如何检测 Agent 陷入循环？**

**两层检测：**

| 层级 | 检测方式 | 阈值 | 响应 |
|------|---------|------|------|
| 动作层 | 动作哈希 (name + sorted_args) | 连续 3 次相同 | 提醒 "请尝试不同方法" |
| 页面层 | 页面指纹 (URL + 文本前 200 字 + 元素数) | 连续 5 次相同 | 提醒 "页面可能卡住" |

**代码实现：**
```python
# src/agent/loop_detector.py
class ActionLoopDetector:
    def record_action(self, name: str, args: dict):
        action_hash = f"{name}:{json.dumps(args, sort_keys=True)}"
        self._action_hashes.append(action_hash)

    def record_page_state(self, url: str, text: str, elements: int):
        fingerprint = f"{url}:{text[:200]}:{elements}"
        self._page_fingerprints.append(fingerprint)
```

---

### 2.5 短期记忆管理 (Task 6)

**Q: 如何管理长对话的上下文窗口？**

**三层记忆：**

| 类型 | 存储内容 | 实现 |
|------|---------|------|
| 消息历史 | LLM 对话消息 | `_messages` 列表 |
| 任务记忆 | URL、关键发现、步骤结果 | `TaskMemory` 类 |
| 消息压缩 | 早期消息摘要 | `MessageCompactor` |

**压缩策略：**
```python
class MessageCompactor:
    def compact(self, messages: list[dict]) -> list[dict]:
        if len(messages) > self.max_messages:
            # 保留 system + 最近消息，早期消息压缩为摘要
            early = messages[2:-self.keep_recent]
            summary = self._summarize(early)
            return [messages[0], summary] + messages[-self.keep_recent:]
```

---

### 2.6 防检测 (Task 8)

**Q: 如何防止被网站检测为自动化工具？**

**检测点与对策：**

| 检测点 | 正常浏览器 | 自动化工具 | 对策 |
|--------|-----------|-----------|------|
| navigator.webdriver | undefined | true | Object.defineProperty 覆盖 |
| chrome.runtime | 存在 | 不存在 | 注入伪装对象 |
| navigator.plugins | 有内容 (Flash/PDF) | 空数组 | 注入假插件列表 |
| navigator.languages | ["zh-CN", "zh", "en"] | ["en-US"] | 覆盖为中文环境 |
| Permissions API | 正常查询 | 特殊行为 | 覆盖 query 方法 |

**注入时机：**
```python
# src/browser/manager.py
async def connect(self) -> Page:
    # ... 连接逻辑 ...
    await inject_permission_handling(self._context)
    await inject_stealth(self._page)
```

---

### 2.7 执行路径优化 (三层防护)

**Q: 如何减少冗余工具调用？**

**问题：** LLM 经常在 `extract_content` 后调用 `get_dom_snapshot`，或在点击后重复获取 DOM。

**方案 A — Prompt 约束：**
```
禁止:
- extract_content 后立即 get_dom_snapshot
- 搜索结果页先提取内容再点击
```

**方案 B — 后处理合并：**
```python
def merge_redundant_actions(tool_calls):
    # extract_content + get_dom_snapshot → 删除后者
    if names == ["extract_content", "get_dom_snapshot"]:
        return [tool_calls[0]], ["get_dom_snapshot"]
```

**方案 C — 工具过滤：**
```python
def get_priority_tools(schemas, url):
    if is_search_page(url):
        # 隐藏 extract_content，突出 click_element
        return [s for s in schemas if s["function"]["name"] != "extract_content"]
```

---

### 2.8 新标签页检测

**Q: 如何处理点击后在新标签页打开的场景？**

**问题：** B站搜索后按 Enter，结果在新标签页打开，但 Agent 仍操作原页面。

**解决方案：**
```python
async def send_keys(self, keys: str, wait_for_navigation: bool = False):
    if wait_for_navigation:
        # 1. 预注册监听器
        self.start_new_page_listener()

        # 2. 执行操作
        await self.page.keyboard.press(keys)

        # 3. 检查新页面
        new_page = await self.check_for_new_page(timeout=3000)
        if new_page:
            self._page = new_page
            return "已切换到新标签页"
```

---

## 三、常见面试问题

### Q1: 如何处理 LLM 的幻觉问题？

**A:**
1. **工具参数验证**：Pydantic 模型强制类型检查，无效参数会报错并反馈给 LLM
2. **循环检测**：连续相同动作触发提醒，引导 LLM 改变策略
3. **工具过滤**：根据页面类型限制可用工具，减少错误选择
4. **弹窗处理**：自动处理意外弹窗，避免 LLM 因弹窗困惑

### Q2: 如果页面有 iframe 怎么处理？

**A:**
1. **CDP DOM 提取**：`DomService` 通过 JS 递归获取 iframe 内可交互元素数量
2. **iframe 信息注入**：在 `get_dom_snapshot` 结果中标注 iframe 及其内部元素数
3. **切换 frame**：未来可扩展 `switch_frame` 工具（当前通过 `new_tab` 打开 iframe URL  workaround）

### Q3: 如何确保 Agent 不会无限运行？

**A:**
1. **最大步数限制**：`max_steps=16`
2. **连续失败限制**：`max_failures=5`
3. **循环检测**：连续 10 次相同动作强制终止
4. **超时控制**：每个工具调用有独立 timeout

### Q4: 如何扩展新的浏览器工具？

**A:**
1. 在 `src/tools/models.py` 定义 Pydantic 参数模型
2. 在 `src/browser/manager.py` 实现底层浏览器操作
3. 在 `src/tools/browser_actions.py` 使用 `@reg.action()` 注册工具
4. 在 `src/agent/prompts.py` 更新 system prompt 说明新工具
5. 编写单元测试验证工具参数和执行逻辑

---

## 四、技术栈与工具

| 层级 | 技术 | 用途 |
|------|------|------|
| 浏览器控制 | Playwright (CDP) | 连接 Chrome，执行操作 |
| HTTP 客户端 | httpx | 调用 LLM API |
| 数据验证 | Pydantic v2 | 工具参数模型、settings |
| 测试 | pytest + pytest-asyncio | 单元测试和端到端测试 |
| 环境管理 | python-dotenv + pydantic-settings | 配置管理 |

---

## 五、项目亮点 (面试加分项)

1. **零 langchain 依赖**：完全原生实现，理解底层原理而非依赖框架黑盒
2. **三层优化防护**：Prompt + 后处理 + 工具过滤，系统解决冗余调用问题
3. **完整的测试覆盖**：186+ 测试，包括单元测试、集成测试、端到端测试
4. **生产级细节**：弹窗处理、防检测、新标签页检测、循环检测等 edge case 处理
5. **可扩展架构**：Registry 模式工具注册，新增工具只需 3 个文件修改

---

## 六、手写代码练习

**练习 1：实现一个简单的工具注册器**
```python
from pydantic import BaseModel

class Registry:
    def __init__(self):
        self._tools = {}

    def action(self, description: str, param_model: type[BaseModel]):
        def decorator(func):
            self._tools[func.__name__] = {
                "func": func,
                "description": description,
                "schema": param_model.model_json_schema(),
            }
            return func
        return decorator

    def get_schemas(self):
        return [
            {"type": "function", "function": {
                "name": name,
                "description": info["description"],
                "parameters": info["schema"],
            }}
            for name, info in self._tools.items()
        ]
```

**练习 2：实现循环检测器**
```python
from collections import deque

class LoopDetector:
    def __init__(self, window_size=10):
        self.hashes = deque(maxlen=window_size)

    def record(self, action: str, args: dict):
        h = f"{action}:{sorted(args.items())}"
        self.hashes.append(h)

    def is_looping(self, threshold=3):
        if len(self.hashes) < threshold:
            return False
        return len(set(list(self.hashes)[-threshold:])) == 1
```

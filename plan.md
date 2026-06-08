# web-insight 实施计划与进度跟踪

> 最后更新: 2026-06-05
> 详细计划文档: [docs/superpowers/plans/2026-06-05-web-insight-enhancement.md](docs/superpowers/plans/2026-06-05-web-insight-enhancement.md)

---

## 任务总览

| # | 任务 | 状态 | 计划文档位置 |
|---|------|------|-------------|
| 1 | 移除 LLM_MAX_TOKENS 限制 | ✅ | [Task 1](docs/superpowers/plans/2026-06-05-web-insight-enhancement.md#L106) |
| 2 | 清理 langchain 遗留代码 | ✅ | [Task 2](docs/superpowers/plans/2026-06-05-web-insight-enhancement.md#L213) |
| 3 | 增强 DOM 提取 (CDP) | ✅ | [Task 3](docs/superpowers/plans/2026-06-05-web-insight-enhancement.md#L361) |
| 4 | 弹窗/对话框处理 | ✅ | [Task 4](docs/superpowers/plans/2026-06-05-web-insight-enhancement.md#L672) |
| 5 | 循环检测 | ⬜ | [Task 5](docs/superpowers/plans/2026-06-05-web-insight-enhancement.md#L814) |
| 6 | 短期记忆管理 | ⬜ | [Task 6](docs/superpowers/plans/2026-06-05-web-insight-enhancement.md#L1028) |
| 7 | 增强工具集 (iframe/标签/上传) | ⬜ | [Task 7](docs/superpowers/plans/2026-06-05-web-insight-enhancement.md#L1224) |
| 8 | 防检测基础实现 | ⬜ | [Task 8](docs/superpowers/plans/2026-06-05-web-insight-enhancement.md#L1401) |
| 9 | 更新 System Prompt | ✅ | [Task 9](docs/superpowers/plans/2026-06-05-web-insight-enhancement.md#L1513) |
| 10 | 最终验证 | ⬜ | [Task 10](docs/superpowers/plans/2026-06-05-web-insight-enhancement.md#L1585) |

---

## 搜索执行路径优化 (方案 A/B/C) — 已完成

| 方案 | 说明 | 状态 | 核心文件 |
|------|------|------|---------|
| **A: Prompt 优化** | System prompt 明确禁止冗余工具调用 | ✅ | [src/agent/prompts.py](src/agent/prompts.py) |
| **B: 动作合并** | Post-processing 检测并删除冗余 tool_calls | ✅ | [src/agent/action_merger.py](src/agent/action_merger.py) |
| **C: 工具优先级** | 根据页面 URL 动态过滤工具列表 | ✅ | [src/agent/tool_prioritizer.py](src/agent/tool_prioritizer.py) |

### 架构: 三层防护

```
用户输入 → Phase 1: 方案C (工具过滤) → Phase 2: 方案A (LLM Prompt) → Phase 3: 方案B (合并器)
```

- **方案C** 在调用 LLM 前根据页面类型过滤工具（搜索结果页隐藏 `extract_content`）
- **方案A** 通过 system prompt 引导 LLM 选择正确的工具调用序列
- **方案B** 在 LLM 返回后检测冗余（如 `extract_content` + `get_dom_snapshot` → 删除后者）

### 实现位置

| 文件 | 作用 |
|------|------|
| [src/agent/tool_prioritizer.py](src/agent/tool_prioritizer.py) | 页面类型检测 + 工具过滤 (方案C) |
| [src/agent/action_merger.py](src/agent/action_merger.py) | 冗余动作合并 (方案B) |
| [src/agent/prompts.py](src/agent/prompts.py) | 优化后的 System Prompt (方案A) |
| [src/agent/loop.py](src/agent/loop.py) | AgentLoop 集成方案B和C |
| [src/agent/factory.py](src/agent/factory.py) | 传递 `get_current_url` 给 AgentLoop |

### 方案C 修复记录 (2026-06-05)

**问题**: ARTICLE 页面隐藏 `click_element` 导致复杂任务（如 B站搜索场景）无法点击元素。

**修复**: `ARTICLE_HIDDEN` 从 `{"click_element"}` 改为空集 `set()`。文章页的冗余由方案B处理。

**验证**: [tests/test_bilibili_e2e.py](tests/test_bilibili_e2e.py) — B站搜索场景端到端测试通过。

---

## 新标签页检测与自动切换 (2026-06-05) — 已完成

### 问题描述

B站搜索在**新标签页**打开结果，但 Agent 的 `send_keys("Enter", wait_for_navigation=true)` 只等待**当前页面**的 `domcontentloaded`，未检测新标签页。导致后续所有操作（`get_dom_snapshot`、`click_element`、`extract_content`）都在原页面执行，操作的是搜索建议而非视频搜索结果。

**日志证据** ([data/tool_calls.log](data/tool_calls.log)):
```
Step 4 send_keys({"keys": "Enter", "wait_for_navigation": true})
  -> 已按下 Enter，页面已跳转到: https://www.bilibili.com/   ← 仍停留在首页！
Step 5 get_dom_snapshot
  -> [11] <div> "aiagent是什么"  ← 搜索建议，不是视频
  -> [13] <div> "agent是什么"     ← 搜索建议，不是视频
Step 6 click_element({"index": 13})  ← 点击了搜索建议，不是视频！
```

### 根因分析

| 层级 | 问题 |
|------|------|
| **BrowserManager** | `wait_for_navigation` 仅等待当前 page 的 `domcontentloaded`，未监听新页面事件 |
| **send_keys** | 没有在按键前注册 `context.on('page', ...)` 监听器 |
| **click_element** | 同样没有新页面检测 |

### 修复方案 (参考 Playwright 官方文档)

Playwright 标准模式：在触发操作前使用 `context.on('page', handler)` 预注册监听器，操作后检查是否有新页面产生。

| 修复 | 说明 | 核心文件 |
|------|------|---------|
| **start_new_page_listener** | 在触发操作前注册 `context.on('page', ...)` 回调 | [src/browser/manager.py](src/browser/manager.py) |
| **check_for_new_page** | 操作后等待新页面事件，自动切换到新页面 | [src/browser/manager.py](src/browser/manager.py) |
| **send_keys 集成** | `wait_for_navigation=true` 时启动监听器，检测新标签页并切换 | [src/tools/browser_actions.py](src/tools/browser_actions.py) |
| **click_element 集成** | 点击前启动监听器，点击后自动检测新标签页 | [src/tools/browser_actions.py](src/tools/browser_actions.py) |

### 新标签页检测流程

```
send_keys(keys="Enter", wait_for_navigation=true)
    ↓
start_new_page_listener()  ← 注册 context.on('page', handler)
    ↓
press_key("Enter")  ← 触发新标签页打开
    ↓
check_for_new_page(timeout=3s)
    ↓
检测到新页面 → 切换到新页面 → 返回新 URL
    ↓
后续操作（get_dom_snapshot, click_element）在新页面执行 ✓
```

### 预期日志变化

```
修复前:
  Step 4 send_keys → 已按下 Enter，页面已跳转到: https://www.bilibili.com/

修复后:
  Step 4 send_keys → 已按下 Enter，检测到新标签页并已切换:
    https://www.bilibili.com → https://search.bilibili.com/search?keyword=agent是什么
```

### 测试覆盖 (新增)

| 测试文件 | 测试数 | 说明 |
|---------|--------|------|
| [tests/test_new_tab_switch.py](tests/test_new_tab_switch.py) | 12 | 新页面监听器 + send_keys/click_element 新标签检测 + B站场景 |

---

## VLM JSON 解析修复 + 工具调用日志 (2026-06-05) — 已完成

### 问题描述

`visual_analyze` 工具调用失败，VLM 视觉分析无法定位第一个视频：

```
Step 7  visual_analyze({"query": "第一个视频"})
[Agent] 回复: 视觉分析失败，无法定位第一个视频
```

### 根因分析

1. **JSON 解析失败**: VLM (GLM-4.1V-Thinking-Flash) 返回的 JSON 包裹在 markdown 代码块中（`\`\`\`json ... \`\`\``），原代码直接调用 `PageAnalysis.model_validate_json(content)` 无法解析
2. **提示词未强制 JSON**: 原提示词只说"返回结构化的分析结果"，VLM 可能返回带解释文字的 JSON
3. **无工具调用日志**: 无法查看实际 VLM 返回内容，难以诊断问题

### 修复方案

| 修复 | 说明 | 核心文件 |
|------|------|---------|
| **extract_json_from_text** | 新增 JSON 提取函数，处理 markdown 代码块、前后文字的 JSON | [src/perception/vision.py](src/perception/vision.py) |
| **强化 VLM 提示词** | 明确要求仅输出 JSON、提供 JSON schema 示例、强调坐标要求 | [src/perception/vision.py](src/perception/vision.py) |
| **HTTP 错误处理** | 检查 HTTP 状态码，非 200 返回详细错误信息 | [src/perception/vision.py](src/perception/vision.py) |
| **增强错误信息** | 视觉分析失败时提供排查建议（模型名、API Key、网络） | [src/tools/browser_actions.py](src/tools/browser_actions.py) |
| **工具调用日志** | 每次工具调用写入 `data/tool_calls.log`，包含时间戳、参数、结果 | [src/agent/loop.py](src/agent/loop.py) |

### 日志文件格式

```
[2026-06-05 14:30:01] Step 1 navigate({"url": "https://www.bilibili.com"})
  -> 已导航至 https://www.bilibili.com
[2026-06-05 14:30:05] Step 7 visual_analyze({"query": "第一个视频"})
  -> VLM 分析成功：发现 5 个元素
```

### 测试覆盖 (新增)

| 测试文件 | 测试数 | 说明 |
|---------|--------|------|
| [tests/test_vlm_json_parse.py](tests/test_vlm_json_parse.py) | 8 | JSON 提取 + 提示词格式 + 工具日志 + VLM 流程 |

---

## VLM 视觉降级 + 页面聚焦修复 (2026-06-05) — 已完成

### 问题描述

1. **页面聚焦问题 (Terminal#703-720)**: `send_keys("Enter")` 后页面跳转，但 `get_dom_snapshot` 可能获取旧页面元素，导致 `click_element` 点击错误元素。
2. **VLM 降级问题 (Terminal#549-561)**: `get_dom_snapshot` 无法识别视频等元素时，Agent 直接放弃任务。

### 修复方案

| 修复 | 说明 | 核心文件 |
|------|------|---------|
| **send_keys 导航等待** | `send_keys` 新增 `wait_for_navigation=true` 参数，Enter 提交搜索后等待页面跳转完成 | [src/tools/models.py](src/tools/models.py), [src/tools/browser_actions.py](src/tools/browser_actions.py) |
| **click_coordinate 工具** | 新增按坐标点击工具，配合 VLM 视觉分析定位后精确点击 | [src/tools/models.py](src/tools/models.py), [src/tools/browser_actions.py](src/tools/browser_actions.py) |
| **visual_analyze 工具** | 截图 → VLM 分析 → 返回元素坐标，DOM 无法识别时降级使用 | [src/tools/models.py](src/tools/models.py), [src/tools/browser_actions.py](src/tools/browser_actions.py) |
| **System Prompt 更新** | 新增搜索跳转规范 + VLM 视觉降级流程说明 | [src/agent/prompts.py](src/agent/prompts.py) |
| **BrowserManager 扩展** | 新增 `click_by_coordinate(x, y)` 和 `wait_for_navigation()` 方法 | [src/browser/manager.py](src/browser/manager.py) |

### VLM 降级流程

```
get_dom_snapshot 无结果
    ↓
visual_analyze(query="找到第一个视频")  ← VLM 截图分析
    ↓
获取元素坐标 (x, y)
    ↓
click_coordinate(x, y)  ← 精确点击
```

### 搜索跳转修复

```
send_keys(keys="Enter", wait_for_navigation=true)  ← 等待页面跳转
    ↓
页面加载完成 (domcontentloaded)
    ↓
get_dom_snapshot  ← 获取新页面元素
```

### 测试覆盖 (新增)

| 测试文件 | 测试数 | 说明 |
|---------|--------|------|
| [tests/test_vlm_fallback_fix.py](tests/test_vlm_fallback_fix.py) | 8 | 导航等待 + 坐标点击 + 视觉分析 + VLM 降级 |
| [tests/test_vlm_json_parse.py](tests/test_vlm_json_parse.py) | 8 | JSON 提取 + 提示词格式 + 日志 + VLM 流程 |

---

## 测试覆盖 (汇总)

| 测试文件 | 测试数 | 说明 |
|---------|--------|------|
| [tests/test_task1_max_tokens.py](tests/test_task1_max_tokens.py) | 4 | Task 1: max_tokens 验证 |
| [tests/test_task2_langchain_cleanup.py](tests/test_task2_langchain_cleanup.py) | 4 | Task 2: langchain 清理 |
| [tests/test_task3_dom_service.py](tests/test_task3_dom_service.py) | 5 | Task 3: DOM 服务 |
| [tests/test_plan_a_prompt.py](tests/test_plan_a_prompt.py) | 2 | 方案A: prompt 单元测试 |
| [tests/test_plan_a_e2e.py](tests/test_plan_a_e2e.py) | 2 | 方案A: LLM E2E |
| [tests/test_plan_b_merger.py](tests/test_plan_b_merger.py) | 6 | 方案B: 合并器单元测试 |
| [tests/test_plan_b_e2e.py](tests/test_plan_b_e2e.py) | 2 | 方案B: LLM E2E |
| [tests/test_plan_c_prioritizer.py](tests/test_plan_c_prioritizer.py) | 12 | 方案C: 页面检测 + 过滤 |
| [tests/test_plan_c_e2e.py](tests/test_plan_c_e2e.py) | 2 | 方案C: LLM E2E |
| [tests/test_ultimate_abc.py](tests/test_ultimate_abc.py) | 3 | A+B+C 联合验证 |
| [tests/test_bilibili_e2e.py](tests/test_bilibili_e2e.py) | 1 | 方案C修复: B站复杂场景 |
| [tests/test_vlm_fallback_fix.py](tests/test_vlm_fallback_fix.py) | 8 | VLM 降级 + 页面聚焦 |
| [tests/test_vlm_json_parse.py](tests/test_vlm_json_parse.py) | 8 | JSON 提取 + 日志 + VLM 修复 |
| [tests/test_new_tab_switch.py](tests/test_new_tab_switch.py) | 26 | 详见下方 |
| [tests/test_e2e_api.py](tests/test_e2e_api.py) | 5 | 通用 API 连通性 |
| **总计** | **89** | |

---

## 元素数量 & 标签页管理修复 (2026-06-06) — 已完成

### 问题

B站搜索后，`get_dom_snapshot` 只返回 20 个元素，LLM 尝试点击 `click_element(index=39)` 失败（`Element 39 not found`）。同时，`click_coordinate` 点击后没有检测新页面，导致后续 `visual_analyze` 仍在旧页面截图。

### 根因

1. **元素数量硬编码 20**：`get_indexed_elements` 的 JS 中有 `if (i >= 20) return;`，`GetDomSnapshotAction.max_elements` 默认 20，`DomService` 也二次截断到 30
2. **索引不一致**：`get_indexed_elements`（click_element 使用）和 `INTERACTIVE_ELEMENTS_JS`（DomService 使用）使用不同的选择器和过滤逻辑，导致 get_dom_snapshot 返回的 index 与 click_element 的 index 不匹配
3. **click_coordinate 无新页面检测**：点击坐标后没有 `start_new_page_listener` + `check_for_new_page`，导致页面跳转后 agent 仍操作旧页面
4. **缺少标签页管理工具**：没有 `get_tabs_info` / `switch_tab` 工具，agent 无法手动查看和切换标签页

### 修复

参考 browser-use 的 multi-tab 设计（`BrowserState.tabs` + `switch_tab` action）：

**1. 统一元素提取逻辑**
- `get_indexed_elements` 改用与 `DomService.INTERACTIVE_ELEMENTS_JS` 完全相同的 JS 脚本
- 移除硬编码 `if (i >= 20) return;`，改为 `raw[:max_elements]` 截断
- 默认 `max_elements` 从 20 提升到 200

**2. 新增标签页管理工具**
- `get_tabs_info`：列出所有标签页（索引、URL、标题、是否激活）
- `switch_tab`：按索引切换标签页，调用 `bring_to_front()` 确保页面激活

**3. click_coordinate 集成新页面检测**
- 点击前 `start_new_page_listener()`，点击后 `check_for_new_page(timeout=2.0)`

**4. 索引一致性**
- `get_indexed_elements` 和 `DomService.get_clickable_elements` 使用完全相同的 JS 选择器和过滤逻辑，保证 `get_dom_snapshot` 返回的 index 与 `click_element` 的 index 一致

### 修改文件

| 文件 | 修改 |
|------|------|
| [src/browser/manager.py](src/browser/manager.py) | 统一 JS 脚本、新增 `get_tabs_info()` / `switch_to_tab()` |
| [src/tools/browser_actions.py](src/tools/browser_actions.py) | 新增 `get_tabs_info` / `switch_tab` 工具、`click_coordinate` 集成新页面检测 |
| [src/tools/models.py](src/tools/models.py) | 新增 `GetTabsInfoAction` / `SwitchTabAction`、`max_elements` 默认 200 |
| [src/perception/dom_service.py](src/perception/dom_service.py) | 默认 `max_elements` 从 50 → 200，移除二次截断 |

### 新增测试

| 测试类 | 测试数 | 说明 |
|--------|--------|------|
| `TestElementCountAndIndexing` | 5 | 默认 200 元素、无硬编码 20 限制、JS 一致性 |
| `TestTabManagement` | 8 | get_tabs_info / switch_tab / 注册表 / 模型 |
| `TestClickCoordinateNewTabDetection` | 2 | click_coordinate 新页面检测 |

### 浏览器标签页管理流程

```
get_tabs_info                    switch_tab(tab_index=1)
    ↓                                  ↓
[0] 哔哩哔哩 | bilibili.com     self._page = pages[1]
[1] agent是什么-搜索 | search... → bring_to_front()
                                     ↓
                              后续操作在搜索页执行 ✓
```

### 日志变化

**修复前**（Step 5-6）：
```
Step 5 get_dom_snapshot({"max_elements": 20})
  → 总可交互元素: 20 | 视口可见: 20  ← 元素太少，视频列表在 20+ 索引
Step 6 click_element({"index": 39})
  → 点击失败: Element 39 not found  ← 索引超出范围
```

**修复后**（预期）：
```
Step 5 get_dom_snapshot({"max_elements": 200})
  → 总可交互元素: 47 | 视口可见: 35  ← 包含所有视频链接
Step 6 click_element({"index": 39})
  → 已点击 [39] <a> 【Agent】什么是AI Agent？  ← 成功定位视频
```

---

## 运行测试

```bash
conda activate web-ai
python -m pytest tests/ -v
```

## 运行交互式 CLI

```bash
conda activate web-ai
python main.py
```
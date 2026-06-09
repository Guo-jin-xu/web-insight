# web-insight

AI 驱动的浏览器自动化 Agent，原生异步循环 + Playwright CDP + VLM。

**核心思路**: 让 LLM 像人一样操作浏览器 — 理解意图 → 感知页面 → 做决策 → 执行操作 → 输出结果。

## 亮点

- **原生 Agent 循环** — 自研 step 循环，不依赖 LangGraph，轻量可控
- **DOM 优先 + VLM 兜底** — 页面感知首选 DOM 解析（快），视觉分析仅兜底（准）
- **CDP 连接** — 复用用户 Chrome 实例，可见可干预，保留登录态
- **循环检测** — 动作哈希追踪 + 页面指纹对比检测循环
- **任务规划** — LLM 自动分解任务步骤
- **短期记忆管理** — 任务内记忆（已访问 URL、关键发现、提取数据）+ 消息自动压缩
- **多标签页管理** — 自动检测新标签页，支持手动查看和切换标签页
- **弹窗自动处理** — 自动接受/关闭 alert/confirm/prompt 弹窗，页面崩溃自动恢复
- **统一异常处理** — 速率限制等 API 错误友好提示，不崩溃

## 快速开始

### 环境要求

- Python >= 3.12
- Google Chrome 浏览器
- LLM API Key（OpenAI 兼容接口，如智谱 GLM）

### 1. 创建环境

```bash
conda create -n web-ai python=3.12
conda activate web-ai
```

### 2. 安装依赖

```bash
cd web-insight
pip install -r requirements.txt
```

### 3. 配置 API Key

```bash
cp .env.example .env
# 编辑 .env，填入 API Key 和 Base URL
```

### 4. 运行

```bash
python main.py
```

程序会自动检测并启动 Chrome（CDP 调试模式），无需手动启动。

## CLI 使用

```
  web-insight CLI — AI 浏览器自动化
  输入任务描述，Agent 自动操作浏览器完成
  /quit 或 Ctrl+C 退出  |  /clear 清除会话

Chrome 已连接: 新标签页

[You] 搜索今天广州的天气

[Agent] 分析中...

[Plan] 生成执行计划（4 步）：
  Step 1 导航到搜索引擎 → 页面加载完成
  Step 2 输入搜索关键词并提交 → 搜索结果页加载
  Step 3 点击天气详情链接 → 进入天气详情页
  Step 4 提取天气信息并总结 → 获取目标信息

[Agent] 开始执行任务...

  Step 1  navigate({"url": "https://www.bing.com/search?q=今天广州天气"})
  Step 2  click_element({"index": 3})
  Step 3  extract_content({})
  Step 4  done

  [Judge] ✓ 任务完成，结果包含完整的天气信息

[Agent] 结果:

广州今天的天气预报：最高气温35°C，最低气温28°C，局部多云...
```

命令: `/quit` 退出, `/clear` 清除会话, `Ctrl+C` 退出。

## 架构

```
用户输入
  │
  ▼
┌──────────────────────────────────────────────────────────────┐
│                      Router (router.py)                      │
│                                                              │
│   LLM 分类 ──► conversation ──► LLM 直接回复                 │
│       │                                                      │
│       └──► web_task ──► Browser Agent ──► done               │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                AgentLoop (src/agent/loop.py)                  │
│                                                              │
│   LLM 决策 ──► 工具选择 ──► 冗余合并 ──► 工具执行 ──► done   │
│                                              │               │
│                              ┌───────────────┘               │
│                              ▼                               │
│                    ┌── 循环检测 ──► 提醒注入                  │
│                    ├── 记忆管理 ──► 上下文注入                │
│                    └── 弹窗检查 ──► 系统通知注入              │
└──────────────────────────────────────────────────────────────┘
               │                │
    ┌──────────┘                │
    ▼                           ▼
┌──────────┐           ┌──────────────┐
│ Browser  │           │  Perception  │
│Playwright│           │ DOM (BS4)    │
│ CDP 连接 │           │ VLM (视觉)   │
└──────────┘           └──────────────┘
```

## 核心模块详解

### 1. Agent 循环 (`src/agent/loop.py`)

自研原生 async step 循环，每步执行流程：

1. **弹窗检查** — 检查并注入已自动处理的弹窗消息
2. **消息压缩** — 超过30条消息时自动压缩
3. **记忆注入** — 将 TaskMemory 上下文注入消息
4. **LLM 决策** — 调用 LLM 获取下一步动作（含工具调用）
5. **冗余合并** — Post-processing 消除冗余动作
6. **工具执行** — 执行工具并记录结果
7. **循环检测** — 记录动作哈希和页面指纹，检测循环

终止条件：LLM 调用 done / 达到最大步数(16) / 连续失败5次

### 2. 路由器 (`src/agent/router.py`)

基于 LLM 的意图分类器，将用户输入分为：
- **conversation** — 日常对话，LLM 直接回复
- **web_task** — 网页操作，启动 Browser Agent

比关键词匹配更精准，能理解"帮我搜一下最新新闻"等隐式网页操作意图。

### 3. 循环检测 (`src/agent/loop_detector.py`)

双维度检测 Agent 行为循环：

- **动作哈希追踪** — 标准化动作参数后计算 SHA-256 哈希，追踪最近20步的重复次数
  - 5次重复：温和提醒
  - 8次重复：中度提醒
  - 12次重复：强烈提醒
- **页面指纹对比** — URL + 元素数 + 文本哈希构成页面指纹，检测连续5步页面无变化

### 4. 任务规划 (`src/agent/planner.py`)

基于 LLM 的任务分解：

- **generate_plan** — 将用户任务分解为 3-7 个执行步骤（step/description/expected_outcome）
- **fallback** — LLM 不可用时回退到通用4步模板

### 5. 页面感知 (`src/perception/`)

**DOM 优先**（`dom_service.py` + `dom.py`）：
- 通过 JS evaluate 提取可交互元素（含可见性检测 + 视口裁剪）
- BeautifulSoup4 + lxml 解析 HTML，提取文章内容和链接
- 元素 index 用于 click_element / input_text 定位

**VLM 兜底**（`vision.py`）：
- 截图 → base64 → VLM API → 结构化 PageAnalysis
- 仅在 DOM 无法识别元素时降级调用（视频、图片、Canvas）
- JSON 解析容错：支持 markdown 代码块、纯 JSON、前后有解释文字

### 6. 浏览器管理 (`src/browser/manager.py`)

- **CDP 连接** — `connect_over_cdp()` 复用用户 Chrome，保留登录态
- **新页面检测** — `context.on('page')` 事件 + `asyncio.Event` 异步等待
- **标签页管理** — new_tab / close_tab / list_tabs / switch_to_tab
- **元素操作** — click_by_index / type_by_index / scroll / go_back
- **弹窗处理** — PopupHandler 自动接受/关闭对话框
- **防检测** — 注入 stealth 脚本隐藏 webdriver 属性

### 7. 工具注册中心 (`src/tools/registry.py`)

装饰器模式的工具注册：
- `@reg.action(description, param_model)` 注册工具
- 自动生成 OpenAI function calling schema
- Pydantic 模型验证参数类型
- 统一执行入口 `execute_action()`

## 项目结构

```
web-insight/
├── main.py                         # CLI 交互入口
├── src/
│   ├── agent/
│   │   ├── factory.py              # Agent 工厂（创建 AgentLoop 实例）
│   │   ├── router.py               # 任务路由器（LLM 分类 → conversation/web_task）
│   │   ├── loop.py                 # Agent 循环（step 循环 + 工具调用 + 循环检测 + 记忆管理）
│   │   ├── prompts.py              # 提示词集中管理
│   │   ├── action_merger.py        # 冗余动作合并（Post-processing）
│   │   ├── loop_detector.py        # 动作循环检测 + 页面停滞检测
│   │   ├── planner.py              # 任务规划系统（步骤分解）
│   ├── browser/
│   │   ├── manager.py              # Playwright CDP 连接 + 标签页管理 + 元素索引
│   │   ├── stealth.py              # 浏览器防检测脚本注入
│   │   └── watchdogs.py            # 弹窗自动处理 + 页面崩溃恢复
│   ├── config/
│   │   └── settings.py             # Pydantic Settings（.env 配置）
│   ├── exceptions.py               # 异常体系（RateLimitError / LLMError）
│   ├── llm/
│   │   └── client.py               # LLM/VLM 客户端（OpenAI 兼容，纯 httpx）
│   ├── memory/
│   │   └── task_memory.py          # 短期记忆管理 + 消息压缩
│   ├── perception/
│   │   ├── dom.py                  # DOM 解析（BS4+lxml，纯函数）
│   │   ├── dom_service.py          # DOM 服务（元素提取 + 格式化 + iframe 支持）
│   │   └── vision.py               # VLM 截图分析（结构化输出）
│   ├── schemas/
│   │   └── vision.py               # 视觉分析模型（PageAnalysis / PageElement）
│   └── tools/
│       ├── registry.py             # 工具注册中心（装饰器模式）
│       ├── browser_actions.py      # 浏览器操作工具（19 个）
│       └── models.py               # 工具参数 Pydantic 模型
├── .env.example                    # 环境变量模板
├── pyproject.toml
└── requirements.txt
```

## 可用工具

| 工具 | 说明 |
|------|------|
| `navigate` | 导航到指定 URL 或搜索关键词（自动检测） |
| `click_element` | 按索引点击可交互元素（自动检测新标签页） |
| `click_coordinate` | 按坐标点击（配合 visual_analyze） |
| `input_text` | 在输入框中输入文本 |
| `send_keys` | 发送按键（Enter/Escape 等），支持等待导航 |
| `scroll` | 滚动页面 |
| `go_back` | 返回上一页 |
| `extract_content` | 提取页面正文内容（自动检测文章/列表页） |
| `get_dom_snapshot` | 获取当前页面可交互元素列表 |
| `visual_analyze` | VLM 视觉分析截图（DOM 失效时降级） |
| `get_tabs_info` | 查看所有标签页信息 |
| `switch_tab` | 切换到指定标签页 |
| `new_tab` | 在新标签页打开 URL |
| `close_tab` | 关闭指定标签页 |
| `list_tabs` | 列出所有标签页 |
| `select_dropdown` | 选择下拉菜单选项 |
| `upload_file` | 上传文件到文件选择框 |
| `done` | 标记任务完成并返回结果（Judge 二次验证） |

## 技术选型

| 组件 | 技术 | 选型理由 |
|------|------|----------|
| Agent 循环 | 原生 async 循环 | 轻量可控，不依赖重型框架 |
| 路由器 | LLM 文本分类 | 比关键词匹配更精确，理解隐式意图 |
| LLM | OpenAI 兼容接口（智谱 GLM） | 可切换任意模型，成本低 |
| VLM | 视觉模型（GLM-4.1V） | 截图分析 + 结构化输出，DOM 兜底 |
| 浏览器驱动 | Playwright CDP | 复用用户 Chrome，保留登录态 |
| DOM 解析 | BeautifulSoup4 + lxml | 快速、轻量、纯函数 |
| HTTP 客户端 | httpx | 原生异步，不依赖 langchain |
| 配置 | Pydantic Settings | 类型安全 + .env 支持 |
| 数据验证 | Pydantic BaseModel | 工具参数校验 + JSON Schema 生成 |

## 设计原则

- **DOM 优先**: 页面感知首选 DOM 解析，快速低成本；VLM 仅兜底
- **CDP 连接**: 复用用户 Chrome，可见可干预，保留登录态
- **提示词集中管理**: 所有 Prompt 在 `prompts.py` 统一管理
- **统一异常处理**: RateLimitError / LLMError 友好提示，不崩溃
- **参考 browser-use**: 架构设计参考 browser-use 的成熟模式，简化实现

## 参考项目

- [browser-use](https://github.com/browser-use/browser-use) — 架构设计参考
- [Playwright](https://playwright.dev/) — 浏览器自动化

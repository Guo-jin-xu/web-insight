# web-insight

AI 驱动的浏览器自动化 Agent，基于 LangGraph + Playwright + 智谱 GLM。

**核心思路**: 让 LLM 像人一样操作浏览器 — 理解意图 → 感知页面 → 做决策 → 执行操作 → 输出结果。

> **当前实现**: 详细文档见 [docs/](docs/)

## 亮点

- **LangGraph 路由图** — LLM 自主判断日常对话/网页操作，精确分流
- **ReAct Agent** — 基于 `create_react_agent` 的工具调用循环，16 个 StructuredTool
- **DOM 优先 + VLM 兜底** — 页面感知首选 DOM 解析（快），视觉分析仅兜底（准）
- **CDP 连接** — 复用用户 Chrome 实例，可见可干预，保留登录态
- **站点经验记忆** — ChromaDB 存储操作经验，跨任务复用
- **统一异常处理** — 速率限制等 API 错误友好提示，不崩溃

## 快速开始

### 环境要求

- Python >= 3.12
- Google Chrome 浏览器
- 智谱 API Key（[免费注册](https://open.bigmodel.cn/)）

### 1. 创建环境

```bash
conda create -n web-ai python=3.12.13
conda activate web-ai
```

### 2. 安装依赖

```bash
cd web-insight
pip install -r requirements.txt
pip install -e .
```

### 3. 配置 API Key

```bash
cp .env.example .env
# 编辑 .env，填入你的智谱 API Key:
#   LLM_API_KEY=你的key
#   VLM_API_KEY=你的key
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

[You] 你好，介绍一下你自己

[Agent] 分析中...

[Agent] 回复:

你好！我是一个 AI 助手，可以帮你操作浏览器完成各种网页任务...

[You] 搜索今天广州的天气

[Agent] 分析中...

[Agent] 开始执行任务...

  Step 1  search: {'query': '今天广州天气'}...
  Step 2  get_page_links: {}...
  Step 3  extract_article_content: {}...
  Step 4  done

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
│                  Router (LangGraph StateGraph)               │
│                                                              │
│   classify ──► conversation ──► LLM 直接回复 ──► END        │
│       │                                                      │
│       └──► web_task ──► Browser Agent ──► END               │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│           Browser Agent (create_react_agent)                 │
│                                                              │
│   System Prompt (时间+站点经验)                               │
│        │                                                     │
│        ▼                                                     │
│   LLM 决策 ──► 工具选择 ──► 工具执行 ──► 结果返回 ──► 循环   │
│                                              │               │
│                                         done 工具            │
│                                              │               │
│                                        NodeInterrupt         │
│                                         终止循环             │
└──────────────────────────────────────────────────────────────┘
               │                │                │
    ┌──────────┘                │                └──────────┐
    ▼                           ▼                           ▼
┌──────────┐           ┌──────────────┐           ┌──────────┐
│ Browser  │           │  Perception  │           │  Memory  │
│Playwright│           │ DOM (BS4)    │           │ ChromaDB │
│ CDP 连接 │           │ VLM (GLM-4V) │           │ 站点经验 │
└──────────┘           └──────────────┘           └──────────┘
```

## 项目结构

```
web-insight/
├── main.py                         # CLI 交互入口
├── src/
│   ├── agent/
│   │   ├── factory.py              # Agent 工厂 (create_react_agent)
│   │   ├── router.py               # LangGraph 路由图 (classify → conversation/web_task)
│   │   ├── loop.py                 # 任务执行循环 (run_task + 步骤打印)
│   │   └── prompts.py              # 提示词集中管理 (3 个 Prompt + 时间注入)
│   ├── browser/
│   │   └── manager.py              # Playwright CDP 连接 + 元素索引系统
│   ├── config/settings.py          # Pydantic Settings (.env 配置)
│   ├── exceptions.py               # 异常体系 (RateLimitError / LLMError)
│   ├── llm/factory.py              # LLM/VLM 工厂 (OpenAI 兼容)
│   ├── memory/history.py           # ChromaDB 站点经验管理
│   ├── perception/
│   │   ├── dom.py                  # DOM 解析 (BS4+lxml, 纯函数)
│   │   └── vision.py               # VLM 截图分析 (结构化输出)
│   ├── schemas/                    # Pydantic 数据模型
│   │   ├── tool_result.py          # 工具返回模型
│   │   └── vision.py               # 视觉分析模型 (PageAnalysis)
│   └── tools/
│       ├── __init__.py             # 工具统一入口 (create_all_tools)
│       ├── browser_tools.py        # 浏览器操作 (10 个, 含 done)
│       ├── dom_tools.py            # DOM 感知 (4 个)
│       ├── vision_tool.py          # VLM 分析 (1 个)
│       ├── file_tools.py           # 文件读写 (2 个, 非默认)
│       └── time_tool.py            # 时间工具 (1 个)
├── docs/                           # 详细技术文档
│   ├── architecture.md             # 架构设计
│   ├── router.md                   # 路由器设计
│   ├── agent.md                    # Agent 设计
│   ├── tools.md                    # 工具系统
│   ├── browser.md                  # 浏览器层
│   ├── perception.md               # 感知层
│   ├── memory.md                   # 记忆系统
│   └── exceptions.md               # 异常处理
├── test/                           # pytest 测试
├── .env.example                    # 环境变量模板
├── pyproject.toml
└── requirements.txt
```

## 技术选型

| 组件 | 技术 | 选型理由 |
|------|------|----------|
| Agent 框架 | LangGraph `create_react_agent` | 自动处理 tool-calling 循环，稳定可靠 |
| 路由器 | LangGraph `StateGraph` | LLM 自主分类，比关键词匹配更精确 |
| LLM | 智谱 GLM-4-Flash (OpenAI 兼容) | 国产模型，免费额度，中文能力强 |
| VLM | 智谱 GLM-4.1V-Thinking-Flash | 视觉理解 + 结构化输出 |
| 浏览器驱动 | Playwright `connect_over_cdp` | 用户可见，复用登录态 |
| DOM 解析 | BeautifulSoup4 + lxml | 快速、轻量、纯函数 |
| 向量存储 | ChromaDB | 嵌入式向量库，零运维 |
| 配置 | Pydantic Settings | 类型安全 + .env 支持 |
| 测试 | pytest + pytest-asyncio | 异步测试支持 |

## 设计原则

- **DOM 优先**: 页面感知首选 DOM 解析，快速低成本；VLM 仅兜底
- **CDP 连接**: 复用用户 Chrome，可见可干预，保留登录态
- **提示词集中管理**: 所有 Prompt 在 `prompts.py` 统一管理，时间注入在 LangGraph 执行前
- **统一异常处理**: RateLimitError / LLMError 友好提示，不崩溃
- **参考 browser-use**: 架构设计参考 browser-use 的成熟模式，以教学简化版落地

## 详细文档

| 文档 | 内容 |
|------|------|
| [架构设计](docs/architecture.md) | 整体架构、核心设计决策、模块职责 |
| [路由器设计](docs/router.md) | LangGraph 路由图、分类逻辑、异常处理 |
| [Agent 设计](docs/agent.md) | ReAct Agent、终止机制、结果提取 |
| [工具系统](docs/tools.md) | 16 个工具详解、注册机制、参数注解 |
| [浏览器层](docs/browser.md) | CDP 连接、元素索引、坐标点击 |
| [感知层](docs/perception.md) | DOM 解析、VLM 视觉分析、DOM 优先策略 |
| [记忆系统](docs/memory.md) | ChromaDB 站点经验、双重存储 |
| [异常处理](docs/exceptions.md) | 异常层级、传播链、友好提示 |

## 参考项目

- [browser-use](https://github.com/browser-use/browser-use) — 架构设计参考
- [Playwright MCP](https://github.com/microsoft/playwright-mcp) — 工具接口设计参考

# web-insight

AI 驱动的浏览器自动化 Agent，原生异步循环 + Playwright + VLM。

**核心思路**: 让 LLM 像人一样操作浏览器 — 理解意图 → 感知页面 → 做决策 → 执行操作 → 输出结果。

## 亮点

- **原生 Agent 循环** — 自研 step 循环，不依赖 LangGraph，轻量可控
- **DOM 优先 + VLM 兜底** — 页面感知首选 DOM 解析（快），视觉分析仅兜底（准）
- **CDP 连接** — 复用用户 Chrome 实例，可见可干预，保留登录态
- **多标签页管理** — 自动检测新标签页，支持手动查看和切换标签页
- **弹窗自动处理** — 自动接受/关闭 alert/confirm/prompt 弹窗，页面崩溃自动恢复
- **循环检测** — 检测 Agent 重复动作和页面停滞，自动提醒 LLM 调整策略
- **短期记忆管理** — 任务内记忆（已访问 URL、关键发现、提取数据）+ 消息自动压缩
- **统一异常处理** — 速率限制等 API 错误友好提示，不崩溃

## 快速开始

### 环境要求

- Python >= 3.12
- Google Chrome 浏览器
- LLM API Key（OpenAI 兼容接口）

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

[Agent] 开始执行任务...

  Step 1  navigate({"url": "https://www.baidu.com"})
  Step 2  send_keys({"keys": "今天广州天气", "wait_for_navigation": true})
  Step 3  get_dom_snapshot({})
  Step 4  click_element({"index": 3})
  Step 5  extract_content({})
  Step 6  done

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
│   classify ──► conversation ──► LLM 直接回复                 │
│       │                                                      │
│       └──► web_task ──► Browser Agent ──► done               │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                AgentLoop (src/agent/loop.py)                  │
│                                                              │
│|   System Prompt (时间)                                       |│
│        │                                                     │
│        ▼                                                     │
│   LLM 决策 ──► 工具选择 ──► 工具执行 ──► 结果返回 ──► 循环   │
│                                              │               │
│                                         done 工具            │
│                                              │               │
│                                         终止循环             │
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

## 项目结构

```
web-insight/
├── main.py                         # CLI 交互入口
├── src/
│   ├── agent/
│   │   ├── factory.py              # Agent 工厂
│   │   ├── router.py               # 任务路由器 (classify → conversation/web_task)
│   │   ├── loop.py                 # Agent 循环 (step 循环 + 工具调用日志 + 循环检测 + 记忆管理)
│   │   ├── prompts.py              # 提示词集中管理
│   │   ├── action_merger.py        # 方案B: 冗余动作合并
│   │   ├── loop_detector.py        # Task 5: 动作循环检测 + 页面停滞检测
│   │   ├── judge.py                # 自我评估系统：每步动作质量评估
│   │   └── planner.py              # 任务规划系统：步骤分解 + 停滞重规划
│   ├── browser/
│   │   ├── manager.py              # Playwright CDP 连接 + 标签页管理 + 元素索引
│   │   ├── stealth.py              # Task 8: 浏览器防检测脚本注入
│   │   └── watchdogs.py            # 弹窗自动处理 + 页面崩溃恢复
│   ├── config/
│   │   └── settings.py             # Pydantic Settings (.env 配置)
│   ├── exceptions.py               # 异常体系 (RateLimitError / LLMError)
│   ├── llm/
│   │   └── client.py               # LLM/VLM 客户端 (OpenAI 兼容)
│   ├── memory/
│   │   └── task_memory.py          # Task 6: 短期记忆管理 + 消息压缩
│   ├── perception/
│   │   ├── dom.py                  # DOM 解析 (BS4+lxml, 纯函数)
│   │   ├── dom_service.py          # DOM 服务 (全量元素提取 + 格式化)
│   │   └── vision.py               # VLM 截图分析 (结构化输出)
│   ├── schemas/
│   │   └── vision.py               # 视觉分析模型 (PageAnalysis)
│   └── tools/
│       ├── registry.py             # 工具注册中心
│       ├── browser_actions.py      # 浏览器操作工具 (12 个)
│       └── models.py               # 工具参数模型
├── tests/                          # pytest 测试 (182 个)
│   ├── test_task5_loop_detector.py # Task 5: 循环检测单元测试
│   ├── test_task6_task_memory.py   # Task 6: 短期记忆管理单元测试
│   ├── test_task7_enhanced_tools.py # Task 7: 增强工具集单元测试
│   ├── test_task8_stealth.py       # Task 8: 防检测基础单元测试
│   ├── test_watchdogs.py           # 弹窗处理 + 页面崩溃恢复测试
├── .env.example                    # 环境变量模板
├── pyproject.toml
└── requirements.txt
```

## 可用工具

| 工具 | 说明 |
|------|------|
| `navigate` | 导航到指定 URL |
| `click_element` | 按索引点击可交互元素 |
| `click_coordinate` | 按坐标点击（配合 visual_analyze） |
| `input_text` | 在输入框中输入文本 |
| `send_keys` | 发送按键（Enter/Escape 等） |
| `scroll` | 滚动页面 |
| `go_back` | 返回上一页 |
| `wait` | 等待指定时间 |
| `extract_content` | 提取页面正文内容 |
| `get_dom_snapshot` | 获取当前页面可交互元素列表 |
| `visual_analyze` | VLM 视觉分析截图 |
| `get_tabs_info` | 查看所有标签页信息 |
| `switch_tab` | 切换到指定标签页 |
| `new_tab` | 在新标签页打开 URL |
| `close_tab` | 关闭指定标签页 |
| `list_tabs` | 列出所有标签页 |
| `select_dropdown` | 选择下拉菜单选项 |
| `upload_file` | 上传文件到文件选择框 |
| `done` | 标记任务完成并返回结果 |

## 技术选型

| 组件 | 技术 | 选型理由 |
|------|------|----------|
| Agent 循环 | 原生 async 循环 | 轻量可控，不依赖重型框架 |
| 路由器 | LLM 文本分类 | 比关键词匹配更精确 |
| LLM | OpenAI 兼容接口 | 可切换任意模型 |
| VLM | 视觉模型 | 截图分析 + 结构化输出 |
| 浏览器驱动 | Playwright CDP | 复用用户 Chrome，保留登录态 |
| DOM 解析 | BeautifulSoup4 + lxml | 快速、轻量、纯函数 |
| 配置 | Pydantic Settings | 类型安全 + .env 支持 |
| 测试 | pytest + pytest-asyncio | 异步测试支持 |

## 设计原则

- **DOM 优先**: 页面感知首选 DOM 解析，快速低成本；VLM 仅兜底
- **CDP 连接**: 复用用户 Chrome，可见可干预，保留登录态
- **提示词集中管理**: 所有 Prompt 在 `prompts.py` 统一管理
- **统一异常处理**: RateLimitError / LLMError 友好提示，不崩溃
- **参考 browser-use**: 架构设计参考 browser-use 的成熟模式

## 参考项目

- [browser-use](https://github.com/browser-use/browser-use) — 架构设计参考
- [Playwright](https://playwright.dev/) — 浏览器自动化
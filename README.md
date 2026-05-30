# web-insight

AI 驱动的浏览器自动化 Agent，基于 LangChain + Playwright + 智谱 GLM-4.7。

**核心思路**: 让 LLM 像人一样操作浏览器 — 看页面 → 做决策 → 执行操作 → 输出结果。

> **当前阶段**: Phase 4 完成 (2026-05-30) | 测试: 205 passed | 下一阶段: Phase 5

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

### 4. 启动 Chrome（CDP 调试模式）

```bash
# Windows
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222

# macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222

# Linux
google-chrome --remote-debugging-port=9222
```

### 5. 运行

```bash
# CLI 交互模式
python main.py

# 运行全部测试
python -m pytest test/ -v
```

## CLI 使用

```
[You] 搜索 langchain菜鸟教程，找到 runoob 教程，提取内容并总结核心要点

[Agent] 开始执行任务...
  Step 1  search: {'query': 'langchain菜鸟教程'}...
  Step 2  search: 已搜索 bing: langchain菜鸟教程 页面标题: langch...
  Step 3  get_page_links: {}...
  Step 4  get_page_links: 共 10 个有效链接...
  Step 5  navigate: {'url': 'https://www.runoob.com/ai-agent/...
  Step 6  navigate: 已导航到: https://www.runoob.com/ai-agent...
  Step 7  extract_article_content: {}...
  Step 8  extract_article_content: 标题: LangChain 制作智能体...
  Step 9  done
  
  [Agent] 结果:
  ## LangChain 菜鸟教程核心要点总结
  ...
```

命令: `/quit` 退出, `/clear` 清除会话, `Ctrl+C` 退出。

## 架构

```
用户输入
  │
  ├── 日常对话? → handle_conversation() → LLM 直接回复
  │
  ▼ (网页操作任务)
┌─────────────────────────────────────────────────────────┐
│  Agent.run() — 自定义 step/run 循环                     │
│  ┌───────────────────────────────────────────────────┐ │
│  │  step() 循环                                      │ │
│  │  1. DOM Snapshot (CDP DOM Tree)                   │ │
│  │  2. LLM 决策 (System Prompt 含当前时间 + 站点经验)   │ │
│  │  3. Tool 执行 → 结果写入 MessageManager              │ │
│  │  4. Post-process: Judge + Planner 进度 + Loop 检测  │ │
│  │  5. MessageManager.maybe_compact() 自动压缩         │ │
│  └───────────────────────────────────────────────────┘ │
│  中间件: LoopDetector | MessageManager | TaskPlanner    │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│  16 个 StructuredTool                                   │
│  ┌─ 浏览器 (10) ──────┐  ┌─ DOM 感知 (4) ───────────┐ │
│  │ navigate search     │  │ get_dom_snapshot (CDP树) │ │
│  │ click type scroll   │  │ get_page_links           │ │
│  │ press_key wait done │  │ extract_content          │ │
│  │ go_back new_tab     │  │ extract_article_content  │ │
│  └─────────────────────┘  └──────────────────────────┘ │
│  ┌─ VLM (1) ──────────┐  ┌─ 文件 (2) ───────────────┐ │
│  │ visual_analyze      │  │ write_file read_file     │ │
│  └─────────────────────┘  └──────────────────────────┘ │
└──────────┬──────────────────────────────────────────────┘
           │
    ┌──────┴──────┐
    ▼             ▼
┌────────┐  ┌──────────┐
│Browser │  │Perception│
│Playwright│ │DOM (BS4) │
│CDP 连接│  │VLM (GLM) │
└────────┘  └──────────┘
    │             │
    └──────┬──────┘
           ▼
  ┌──────────────┐
  │ Memory       │
  │ ChromaDB     │
  └──────────────┘
```

## 项目结构

```
web-insight/
├── main.py                         # CLI 交互入口（路由 + 流式输出）
├── src/
│   ├── agent/
│   │   ├── service.py              # 自定义 Agent 类（step/run 循环）
│   │   ├── factory.py              # Agent 工厂 + LangGraph 兼容
│   │   ├── planning.py             # 任务规划器
│   │   ├── loop_detector.py        # 循环检测器
│   │   ├── message_manager.py      # 消息管理器（含自动压缩）
│   │   ├── router.py               # 查询分类路由
│   │   ├── judge.py                # 步骤裁判
│   │   ├── prompts.py              # System Prompt 模板（含时间注入）
│   │   └── views.py                # 数据模型 (AgentOutput, AgentState 等)
│   ├── browser/
│   │   ├── manager.py              # Playwright CDP 连接 + 元素索引
│   │   └── session.py              # Session 管理 (Tab/弹窗)
│   ├── dom/
│   │   ├── service.py              # DOM 服务 (CDP DOM Tree)
│   │   ├── serializer.py           # DOM 序列化器
│   │   └── views.py                # DOM 数据模型
│   ├── config/settings.py          # Pydantic Settings
│   ├── llm/factory.py              # LLM/VLM 工厂
│   ├── memory/history.py           # ChromaDB 站点经验管理
│   ├── perception/
│   │   ├── dom.py                  # DOM 解析 (BS4+lxml)
│   │   └── vision.py               # VLM 截图分析
│   ├── schemas/                    # Pydantic 数据模型
│   └── tools/
│       ├── browser_tools.py        # 浏览器操作工具
│       ├── dom_tools.py            # DOM 感知工具
│       ├── vision_tool.py          # VLM 分析工具
│       └── file_tools.py           # 文件读写工具
├── test/                           # TDD 测试 (205 tests)
├── docs/
│   └── phase3-completion-and-phase4-plan.md  # 阶段文档
├── .env.example
├── pyproject.toml
└── requirements.txt
```

## 技术选型

| 组件 | 技术 |
|------|------|
| Agent 框架 | 自定义 step/run 循环 + LangGraph `create_react_agent` (兼容) |
| LLM | 智谱 GLM-4.7 (OpenAI 兼容) |
| VLM | 智谱 GLM-4.1V-Thinking-Flash |
| 浏览器驱动 | Playwright (connect_over_cdp) |
| DOM 解析 | BeautifulSoup4 + lxml + CDP DOM Snapshot |
| 向量存储 | ChromaDB |
| 配置 | Pydantic Settings |
| 测试 | pytest + pytest-asyncio |

## 设计原则

- **DOM 优先**: 页面感知首选 DOM 解析，快速低成本
- **VLM 兜底**: 视觉分析仅在 DOM 操作连续失败时调用
- **渐进增强**: LoopDetector 渐进式提醒（建议 → 警告 → 严重）
- **自动压缩**: MessageManager 自动压缩长对话，防止超出上下文窗口
- **TDD 先行**: 所有新功能先写测试，再写实现 (205 tests, 0 failures)
- **参考 browser-use**: 架构设计参考 browser-use 的成熟模式，以教学简化版落地

## 项目路线图

```
Phase 1 (MVP)     → 基础工具 + LangGraph Agent + CLI                    ✅
Phase 2           → 自定义 Agent 类 + Judge + 结构化输出                 ✅
Phase 3           → 循环检测 + 消息压缩 + DOM增强 + Session + 任务规划    ✅
Phase 4 (集成修复) → MessageManager + 查询路由 + Planner追踪 + 时间注入  ✅ (当前)
Phase 5-A (紧急)  → 流式输出 + DB管理 + DB质量守卫 + 暂停恢复            📋
Phase 5-B (增强)  → Profile持久化 + 错误恢复 + Memory增强 + 多Tab       📋
Phase 6 (未来)    → 多Agent协作 + 沙箱执行 + 代码执行 + 自改进           🔮
```

## 参考项目

- [browser-use](https://github.com/browser-use/browser-use) — 架构设计参考
- [Playwright MCP](https://github.com/microsoft/playwright-mcp) — 工具接口设计参考

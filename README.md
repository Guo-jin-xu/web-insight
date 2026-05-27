# web-insight

AI 驱动的浏览器自动化 Agent，基于 LangGraph + Playwright + 智谱 GLM-4.7。

**核心思路**: 让 LLM 像人一样操作浏览器 — 看页面 → 做决策 → 执行操作 → 输出结果。

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

# 或运行测试
python test/test_runoob.py
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
  ▼
┌─────────────────────────┐
│  create_react_agent     │  ← LangGraph（决策 + 工具调用循环）
│  glm-4.7 (bind_tools)  │
└──────┬──────────────────┘
       │
       ▼
┌─────────────────────────┐
│  16 个 StructuredTool   │
│  ┌─ 浏览器 (10) ──────┐ │
│  │ navigate search     │ │
│  │ click type scroll   │ │
│  │ press_key wait done │ │
│  ├─ DOM 感知 (4) ─────┤ │
│  │ get_dom_snapshot    │ │
│  │ get_page_links      │ │
│  │ extract_content     │ │
│  │ extract_article     │ │
│  ├─ VLM (1) ──────────┤ │
│  │ visual_analyze      │ │
│  └─ 文件 (2) ─────────┘ │
│  │ write_file read_file│ │
│  └─────────────────────┘ │
└──────────┬──────────────┘
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
├── main.py                     # CLI 交互入口
├── src/
│   ├── agent/factory.py        # Agent 工厂 + system prompt
│   ├── browser/manager.py      # Playwright CDP + 元素索引
│   ├── config/settings.py      # Pydantic Settings
│   ├── llm/factory.py          # LLM/VLM 工厂
│   ├── memory/history.py       # ChromaDB 对话 + 站点经验
│   ├── perception/
│   │   ├── dom.py              # DOM 解析 (BS4+lxml)
│   │   └── vision.py           # VLM 截图分析
│   ├── schemas/                # Pydantic 数据模型
│   └── tools/
│       ├── browser_tools.py    # 浏览器操作 (10 tools)
│       ├── dom_tools.py        # DOM 感知 (4 tools)
│       ├── vision_tool.py      # VLM 分析 (1 tool)
│       └── file_tools.py       # 文件读写 (2 tools)
├── test/
│   └── test_runoob.py          # 基准测试
├── .env.example
├── pyproject.toml
└── requirements.txt
```

## 技术选型

| 组件 | 技术 |
|------|------|
| Agent 框架 | LangGraph `create_react_agent` |
| LLM | 智谱 GLM-4.7 (OpenAI 兼容) |
| VLM | 智谱 GLM-4.1V-Thinking-Flash |
| 浏览器驱动 | Playwright (connect_over_cdp) |
| DOM 解析 | BeautifulSoup4 + lxml |
| 向量存储 | ChromaDB |
| 配置 | Pydantic Settings |

## 设计原则

- **不重复造轮子**: Agent 循环交给 LangGraph，只写工具和感知层
- **DOM 优先**: 页面感知首选 DOM 解析，快速低成本
- **VLM 兜底**: 视觉分析仅在操作失败时调用
- **MCP 规范**: 工具设计参考 Playwright MCP / Filesystem MCP 接口

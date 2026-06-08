# web-insight 详细工作流文档

> 本文档基于项目 10 个核心任务实现，描述从用户输入到结果输出的完整工作流。

---

## 一、系统启动流程

```
用户运行: python main.py
    │
    ├─→ 检查 Chrome 是否已启动 (ensure_chrome_running)
    │   └─→ 未启动则尝试自动启动 chrome --remote-debugging-port=9222
    │
    ├─→ BrowserManager.connect()
    │   ├─→ playwright.chromium.connect_over_cdp("http://localhost:9222")
    │   ├─→ 获取 browser context 和 page
    │   ├─→ PopupHandler.register() — 注册弹窗自动处理
    │   ├─→ inject_permission_handling() — 自动授予通知/地理位置权限
    │   └─→ inject_stealth() — 注入防检测脚本
    │       ├─→ 隐藏 navigator.webdriver
    │       ├─→ 伪装 chrome.runtime
    │       ├─→ 伪装 navigator.plugins / languages
    │       └─→ 覆盖 Permissions API
    │
    └─→ 进入交互式对话循环
```

---

## 二、单次任务执行工作流

```
用户输入任务 (如: "搜索 Python 教程")
    │
    ├─→ route_query(browser, query)
    │   ├─→ LLM 分类: conversation / web_task
    │   └─→ web_task → handle_web_task(browser, query)
    │
    ├─→ create_browser_agent(browser)
    │   ├─→ 创建 LLMClient (httpx + OpenAI-compatible API)
    │   ├─→ create_browser_registry(browser) — 注册所有工具
    │   │   ├─→ 导航: navigate, go_back, new_tab, switch_tab, close_tab, list_tabs
    │   │   ├─→ 感知: get_dom_snapshot, extract_content, visual_analyze
    │   │   ├─→ 交互: click_element, input_text, send_keys, scroll, select_dropdown, upload_file
    │   │   └─→ 完成: done
    │   ├─→ 加载站点经验 (memory_manager.search_experience)
    │   └─→ 构建 system prompt (含当前时间 + 站点经验)
    │
    ├─→ agent.run() — AgentLoop 主循环
    │   │
    │   ├─→ 初始化状态
    │   │   ├─→ loop_detector = ActionLoopDetector(window_size=20)
    │   │   ├─→ task_memory = TaskMemory()
    │   │   └─→ message_compactor = MessageCompactor(max_messages=30)
    │   │
    │   ├─→ while step_count < max_steps and not is_done:
    │   │   │
    │   │   ├─→ Phase 0: 弹窗检查
    │   │   │   └─→ 如果有未处理弹窗，将消息注入上下文
    │   │   │
    │   │   ├─→ Phase 1: 消息压缩 (Task 6)
    │   │   │   └─→ 消息数 > 30 时，压缩早期消息为摘要
    │   │   │
    │   │   ├─→ Phase 2: 注入任务记忆 (Task 6)
    │   │   │   └─→ 将已访问 URL、关键发现、中间结果注入上下文
    │   │   │
    │   │   ├─→ Phase 3: 构建消息列表
    │   │   │   └─→ system_prompt + history + user_task
    │   │   │
    │   │   ├─→ Phase 4: 工具优先级过滤 (方案 C)
    │   │   │   └─→ 根据当前 URL 动态隐藏/显示工具
    │   │   │       ├─→ 搜索结果页: 隐藏 extract_content，突出 click_element
    │   │   │       └─→ 文章详情页: 突出 extract_content + done
    │   │   │
    │   │   ├─→ Phase 5: 调用 LLM (chat_with_tools)
    │   │   │   └─→ 发送 messages + tools schemas → 获取 tool_calls
    │   │   │
    │   │   ├─→ Phase 6: 冗余动作合并 (方案 B)
    │   │   │   └─→ extract_content + get_dom_snapshot → 删除后者
    │   │   │   └─→ navigate + extract_content → 合并为导航后自动提取
    │   │   │
    │   │   ├─→ Phase 7: 执行工具调用
    │   │   │   │
    │   │   │   ├─→ 每个 tool_call:
    │   │   │   │   ├─→ registry.execute_action(name, arguments)
    │   │   │   │   ├─→ 记录到 loop_detector (排除 done/go_back/send_keys)
    │   │   │   │   ├─→ 更新 task_memory (URL/发现/步骤结果)
    │   │   │   │   ├─→ 检查是否为 done → 设置 _done_result
    │   │   │   │   └─→ 记录工具调用日志 (data/tool_calls.log)
    │   │   │   │
    │   │   │   └─→ 新标签页检测 (send_keys/click_element)
    │   │   │       └─→ 操作前注册 context.on('page') 监听器
    │   │   │       └─→ 操作后检查是否有新页面，自动切换
    │   │   │
    │   │   ├─→ Phase 8: 循环检测 (Task 5)
    │   │   │   ├─→ 记录页面状态 (URL + 文本 + 元素数)
    │   │   │   └─→ 检测重复动作或页面停滞
    │   │   │       ├─→ 连续 3 次相同动作 → 提醒 "请尝试不同方法"
    │   │   │       ├─→ 连续 5 次页面无变化 → 提醒 "页面可能卡住"
    │   │   │       └─→ 连续 10 次 → 强制终止
    │   │   │
    │   │   └─→ Phase 9: 注入循环检测提醒到上下文
    │   │       └─→ 将 nudge_message 加入 messages，引导 LLM 改变策略
    │   │
    │   └─→ 返回 _done_result
    │
    └─→ 输出结果给用户
```

---

## 三、核心任务实现对照

| 任务 | 核心文件 | 关键类/函数 | 作用 |
|------|---------|------------|------|
| **Task 1** 移除 LLM_MAX_TOKENS | `src/config/settings.py` | `llm_max_tokens: int \| None = None` | 不限制 token，由 API 自行决定 |
| **Task 2** 清理 langchain | `requirements.txt` | 移除 langchain/langgraph | 精简为原生 Python + httpx + Playwright |
| **Task 3** 增强 DOM 提取 | `src/perception/dom_service.py` | `DomService.get_page_state()` | CDP DOM 树 + 可交互元素索引 |
| **Task 4** 弹窗处理 | `src/browser/watchdogs.py` | `PopupHandler` | 自动处理 alert/confirm/prompt |
| **Task 5** 循环检测 | `src/agent/loop_detector.py` | `ActionLoopDetector` | 动作哈希 + 页面指纹追踪 |
| **Task 6** 短期记忆 | `src/memory/task_memory.py` | `TaskMemory`, `MessageCompactor` | 任务内信息管理和消息压缩 |
| **Task 7** 增强工具集 | `src/tools/browser_actions.py` | `new_tab`, `upload_file`, `select_dropdown` | 多标签/文件上传/下拉选择 |
| **Task 8** 防检测 | `src/browser/stealth.py` | `inject_stealth()` | 隐藏 webdriver，伪装浏览器指纹 |
| **Task 9** System Prompt | `src/agent/prompts.py` | `BROWSER_AGENT_SYSTEM_PROMPT` | 引导正确工具调用序列 |
| **Task 10** 最终验证 | `tests/` | 全部 186+ 测试 | 端到端验证 |

---

## 四、搜索执行路径优化 (三层防护)

```
用户输入: "今天广州的天气如何"
    │
    ├─→ Phase 1: 方案 C (工具过滤)
    │   ├─→ 当前在 bilibili.com → 识别为 VIDEO 页面
    │   └─→ 隐藏 click_element (视频页不需要点击)
    │
    ├─→ Phase 2: 方案 A (Prompt 引导)
    │   └─→ System Prompt 告知:
    │       ├─→ "搜索结果页 → 直接点击链接进入详情页"
    │       ├─→ "进入详情页后 → 直接 extract_content"
    │       └─→ "禁止 extract_content 后立即 get_dom_snapshot"
    │
    └─→ Phase 3: 方案 B (冗余合并)
        ├─→ LLM 返回: [extract_content, get_dom_snapshot]
        └─→ 合并器删除 get_dom_snapshot
```

---

## 五、新标签页检测流程

```
用户任务: "在 B站搜索 AI Agent"
    │
    ├─→ Step 1: navigate("https://www.bilibili.com")
    ├─→ Step 2: input_text(index=0, text="AI Agent") — 输入搜索词
    ├─→ Step 3: send_keys(keys="Enter", wait_for_navigation=true)
    │   │
    │   ├─→ 操作前: browser.start_new_page_listener()
    │   │   └─→ context.on('page', handler) — 监听新页面事件
    │   │
    │   ├─→ 按下 Enter
    │   │
    │   ├─→ 操作后: browser.check_for_new_page(timeout=3000)
    │   │   └─→ 检测到新页面 → 自动切换到新标签页
    │   │   └─→ 新页面 URL: https://search.bilibili.com/...
    │   │
    │   └─→ 返回: "已切换到新标签页: search.bilibili.com"
    │
    ├─→ Step 4: get_dom_snapshot() — 现在在新标签页执行
    └─→ Step 5: click_element(index=2) — 点击视频结果
```

---

## 六、测试覆盖

| 测试文件 | 测试内容 | 数量 |
|---------|---------|------|
| `tests/test_e2e_all_tools.py` | 端到端工具集成验证 | 4 |
| `tests/test_stealth_detection.py` | 防检测脚本验证 | 4 |
| `tests/test_task7_enhanced_tools.py` | 增强工具集单元测试 | 10 |
| `tests/test_task8_stealth.py` | 防检测单元测试 | 5 |
| `tests/test_loop_detector.py` | 循环检测单元测试 | 8 |
| `tests/test_task_memory.py` | 短期记忆单元测试 | 6 |
| `tests/test_bilibili_e2e.py` | B站搜索端到端测试 | 1 |
| 其他现有测试 | DOM、工具注册、浏览器管理等 | ~150 |
| **总计** | | **186+** |

---

## 七、运行命令速查

```bash
# 激活环境
conda activate web-ai

# 启动 Chrome (如未启动)
chrome --remote-debugging-port=9222

# 运行主程序
python main.py

# 运行全部测试
python -m pytest tests/ -v

# 运行端到端测试
python -m pytest tests/test_e2e_all_tools.py tests/test_stealth_detection.py -v

# 验证导入
python -c "from src.config.settings import settings; print(settings.llm_max_tokens)"
```

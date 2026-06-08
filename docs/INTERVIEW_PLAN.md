# web-insight 面试计划实现文档

> 目标：将 web-insight 打造为 Agent 开发岗位面试中有竞争力的项目
> 参考：browser-use 原仓库 + nanobot 开源项目

---

## 一、当前实现状态总览

### 1.1 已实现的核心功能 ✅

| 模块 | 核心文件 | 功能说明 | 面试价值 |
|------|---------|---------|---------|
| **Agent Loop** | `src/agent/loop.py` | 自研 step 循环，替代 LangGraph | **高** — 体现 Agent 核心循环设计能力 |
| **Router** | `src/agent/router.py` | LLM 分类 → 对话/网页任务路由 | **高** — 体现任务分发架构设计 |
| **Tool Registry** | `src/tools/registry.py` | 装饰器注册 + OpenAI function calling schema 生成 | **高** — 体现工具系统设计 |
| **LLM Client** | `src/llm/client.py` | 原生 httpx + OpenAI 兼容 API | **中** — 体现代码精简意识 |
| **Browser Manager** | `src/browser/manager.py` | Playwright CDP 连接 + 多标签管理 | **高** — 体现浏览器控制能力 |
| **DOM Service** | `src/perception/dom_service.py` | CDP JS 注入提取可交互元素 | **高** — 体现 CDP 协议理解 |
| **VLM Vision** | `src/perception/vision.py` | 截图 → VLM 视觉分析降级 | **高** — 多模态感知设计 |
| **Stealth** | `src/browser/stealth.py` | 反自动化检测脚本注入 | **中** — 体现工程细节 |
| **Watchdogs** | `src/browser/watchdogs.py` | 弹窗自动处理 + 页面崩溃恢复 | **中** — 鲁棒性设计 |
| **Loop Detector** | `src/agent/loop_detector.py` | 动作哈希 + 页面指纹循环检测 | **高** — 体现 Agent 安全防护意识 |
| **Action Merger** | `src/agent/action_merger.py` | LLM 返回后冗余工具调用合并 | **中** — Post-processing 优化 |
| **Judge** | `src/agent/judge.py` | 自我评估系统：任务完成评估(done后) + 单步动作评估 + 失败反馈注入 | **极高** — Self-correcting 设计 |
| **Planner** | `src/agent/planner.py` | 任务规划系统：步骤分解 + 停滞重规划 + 进度追踪 | **极高** — Planning 设计 |
| **Task Memory** | `src/memory/task_memory.py` | 任务内短期记忆 + 消息自动压缩 | **高** — 记忆管理设计 |

### 1.2 与 browser-use 的差距分析

| browser-use 功能 | 当前状态 | 面试加分 | 实现难度 |
|-----------------|---------|---------|---------|
| Self-Judge / 自我评估 | ✅ 已实现 | **极高** | 中 |
| Planning 规划系统 | ✅ 已实现 | **极高** | 中 |
| Structured Output | ❌ 缺失 | **高** | 中 |
| Skills 技能系统 | ❌ 缺失 | **高** | 中 |
| File System 集成 | ❌ 缺失 | 中 | 低 |
| Token Cost 追踪 | ❌ 缺失 | 中 | 低 |
| GIF/Video 录制 | ❌ 缺失 | 低 | 低 |
| Demo Mode | ❌ 缺失 | 低 | 低 |
| Multi-LLM Provider | ⚠️ 仅 OpenAI 兼容 | **高** | 中 |
| MCP Server | ❌ 缺失 | **高** | 高 |
| StepInfo / 进度追踪 | ❌ 缺失 | 中 | 低 |
| Variable Detection | ❌ 缺失 | 中 | 中 |

---

## 二、面试高优先级实现计划

按面试官看重程度排序：

### P0: Self-Judge 自我评估系统 ⭐⭐⭐⭐⭐

**面试价值**：体现对 Agent 可靠性、自我纠错能力的深度思考。这是 browser-use 的核心特性之一。

**实现方案**：
```
1. 任务完成评估（done 被调用后触发）
   ├─ 评估维度: 结果是否满足任务要求、步骤是否充分、格式是否正确
   ├─ 输出格式: {verdict: true/false, reasoning: "...", failure_reason: "..."}
   ├─ 成功 → 终止任务，返回结果
   └─ 失败 → 注入反馈到上下文，继续迭代

2. 单步动作评估（动作失败时触发）
   ├─ 评估维度: 动作是否合理、进度是否符合预期
   ├─ 输出格式: {evaluation: "success"/"failure"/"partial", reasoning: "...", suggestion: "..."}
   └─ 反馈注入: 将评估结果注入下一步的上下文消息
```

**核心文件**：`src/agent/judge.py`
- `TaskCompletionJudge` — 任务完成评估 Pydantic 模型（verdict/reasoning/failure_reason）
- `evaluate_task_completion()` — 基于规则的任务完成度判断（空结果/步骤过少/模糊结果）
- `construct_task_completion_messages()` — 构建 LLM-based 评估消息（扩展用）
- `JudgeResult` / `evaluate()` — 单步动作评估（兼容旧模式）
- 在 `AgentLoop._step()` 中集成：done 后调用 `evaluate_task_completion()`，失败时继续循环

### P0: Planning 规划系统 ⭐⭐⭐⭐⭐

**面试价值**：体现 Agent 的任务分解和长期规划能力，是高级 Agent 的标志。

**实现方案**：
```
用户任务 → LLM 生成 Plan
  ├─ PlanItem: {step, description, expected_outcome}
  ├─ 每步执行前注入当前 Plan 状态
  ├─ 停滞检测: 连续 N 步无进展 → 重新规划
  └─ 探索限制: 单步最多尝试 K 次不同方法
```

**核心文件**：新增 `src/agent/planner.py`
- `PlanItem` / `Plan` Pydantic 模型
- `generate_plan()` — 任务分解
- `update_plan_status()` — 更新执行状态
- `replan_on_stall()` — 停滞重规划

### P1: Structured Output 结构化输出 ⭐⭐⭐⭐

**面试价值**：体现工程化思维，TypedDict/JSON Schema 保证输出可靠。

**实现方案**：
- 用户可定义输出 schema（Pydantic 模型）
- LLM 的 `done` 工具参数使用该 schema 约束
- 支持 `List[Dict[str, str]]` 等常见数据提取格式
- 结合 `response_format` 或 `tool_choice` 约束

**核心文件**：修改 `src/tools/models.py` 的 `DoneAction`
- `DoneAction` 支持 `output_schema: dict | None` 参数
- 在 system prompt 中注入输出格式要求

### P1: Skills 技能系统（含向量检索按需加载） ⭐⭐⭐⭐

**面试价值**：体现可扩展性 + 向量检索 + 领域知识注入的综合设计能力。
同时替代已移除的 ChromaDB 站点经验系统，实现更优的按需 skill 加载架构。

**实现方案**（参考 nanobot SKILL.md + browser-use SkillService）：
```
skills/
  ├── update_database.py    # 使用当前目录下的skills对向量数据库的更新，以便管理
  ├── bilibili/SKILL.md     # B站操作经验
  ├── github/SKILL.md       # GitHub 操作经验
  └── shopping/SKILL.md     # 购物操作经验

启动时向量化 SKILL.md → 存入 ChromaDB
Agent 执行任务时 → 用任务描述检索相关 Skill → 注入 system prompt
```

**核心文件**：新增 `src/agent/skills.py`
- `Skill` 数据模型
- `SkillService.load_all()` — 加载 + 向量化所有技能
- `SkillService.retrieve(task_description)` — 语义检索相关 skill
- `SkillService.inject_to_prompt(skills)` — 注入 system prompt
- 在 `factory.py` 中集成，ChromaDB 作为 skill 检索后端

### P1: MessageBus 消息总线 ⭐⭐⭐⭐

**面试价值**：体现事件驱动架构设计能力，为多通道扩展打基础。

**实现方案**（参考 nanobot）：
```
用户输入 → MessageBus.publish(event)
  ├─ AgentLoop 订阅 → 处理任务
  ├─ Logger 订阅 → 记录日志
  └─ Monitor 订阅 → 监控统计
```

**核心文件**：新增 `src/bus/` 模块
- `MessageBus` — 异步发布/订阅
- `Event` — 标准化事件格式
- 集成到 `main.py` 替换直接调用

### P2: ContextManager 上下文管理增强 ⭐⭐⭐

**面试价值**：体现对 LLM 上下文窗口限制的工程解决方案。

**实现方案**：
- 智能截断：优先保留 system prompt + 最近消息 + 关键记忆
- Token 计数：使用 tiktoken 精确计算 token 数
- 分级压缩：轻度(<80%)、中度(<90%)、重度(>95%)
- 图片压缩：大截图自动缩放（参考 browser-use 的 `llm_screenshot_size`）

**核心文件**：增强 `src/memory/task_memory.py` 的 `MessageCompactor`
- 添加 `tiktoken` 依赖
- 实现 token-aware 压缩策略

### P2: Subagents 子代理 ⭐⭐⭐

**面试价值**：体现并行任务处理和任务委派的设计思想。

**实现方案**（参考 nanobot）：
```
主 Agent 识别复杂任务 → 拆分子任务 → 并行创建 Subagents
  ├─ Subagent 1: 搜索产品A价格
  ├─ Subagent 2: 搜索产品B价格
  └─ 主 Agent: 汇总对比结果 → done
```

**核心文件**：新增 `src/agent/subagent.py`
- `SubagentManager` — 创建和管理子代理
- `SpawnTool` — 给 LLM 的 spawn 工具
- 在 `AgentLoop` 中集成子任务结果汇总

### P3: Cron / Heartbeat 定时唤醒 ⭐⭐

**面试价值**：体现从「被动响应」到「主动服务」的架构跃迁。

**实现方案**（参考 nanobot）：
```
CronService: 定时触发任务（每天8点报天气）
HeartbeatService: 定期主动检查（每5分钟检查新消息）
```

**核心文件**：新增 `src/services/` 模块
- `src/services/cron.py` — 定时任务管理
- `src/services/heartbeat.py` — 心跳服务

### P3: Observability 可观测性 ⭐⭐

**面试价值**：体现生产级系统的思维方式。

**实现方案**：
- 结构化日志（JSON 格式）
- Token 用量统计 + 成本估算
- 步骤执行时间追踪
- 错误率监控

**核心文件**：新增 `src/observability.py`
- `TokenCost` — 成本和用量追踪
- `StepMetrics` — 步骤性能统计

---

## 三、nanobot 关键借鉴点

从 [nanobot 源码解析](https://juejin.cn/post/7603195960254218240) 中提炼的核心可借鉴设计：

| 借鉴点 | nanobot 实现 | web-insight 适配方案 |
|--------|-------------|-------------------|
| **MessageBus** | `bus/queue.py` 异步事件总线 | 新增 `src/bus/` 模块，解耦 CLI 和 AgentLoop |
| **Skill 文档系统** | `skills/` 目录 SKILL.md | 新增 `src/agent/skills.py`，注入 system prompt |
| **Subagents** | `agent/subagent.py` 子代理管理 | 新增 `src/agent/subagent.py`，支持 spawn 工具 |
| **Cron/Heartbeat** | `cron/service.py` 定时唤醒 | 新增 `src/services/` 模块 |
| **Session 持久化** | `session/manager.py` 文件系统持久化 | 增强 `MemoryManager` 支持会话恢复 |
| **配置管理** | AGENTS.md / SOUL.md / USER.md / MEMORY.md | 新增 `data/config/` 配置模板 |
| **Multi-Channel** | Telegram + WhatsApp + CLI | 可选扩展 WebSocket/FastAPI |

---

## 四、实现路线图

```
Phase 1 (1-2天) — P0 核心差异化
  ├─ Self-Judge 自我评估系统
  └─ Planning 规划系统

Phase 2 (2-3天) — P1 架构亮点
  ├─ Structured Output 结构化输出
  ├─ Skills 技能系统（含向量检索按需加载）
  └─ MessageBus 消息总线

Phase 3 (2-3天) — P2 工程深度
  ├─ ContextManager 上下文管理增强
  └─ Subagents 子代理

Phase 4 (可选) — P3 锦上添花
  ├─ Cron/Heartbeat 定时唤醒
  └─ Observability 可观测性
```

---

## 五、面试话术准备

### 5.1 项目一句话介绍
> "web-insight 是一个从零构建的 AI 浏览器自动化 Agent，自研了完整的 agent loop、工具注册系统、DOM 感知和 VLM 视觉降级双通道感知架构，参考了 browser-use 的设计理念但不依赖 LangChain/LangGraph 等重型框架。"

### 5.2 核心技术亮点（面试表达）
1. **自研 Agent 循环**：不依赖 LangGraph，手动管理状态 + step 迭代，对 Agent 执行流有完全控制
2. **双通道感知**：DOM 优先（快）+ VLM 降级（准），体现工程权衡
3. **三层冗余防护**：工具过滤 → Prompt 引导 → Post-processing 合并
4. **模块化工具系统**：装饰器注册 + OpenAI function calling schema 自动生成
5. **CDP 协议操作**：通过 Playwright CDP 注入 JS 提取元素，理解浏览器底层
6. **循环检测 + 记忆管理**：Agent 安全防护和上下文压缩

### 5.3 常见追问准备
- **"为什么不用 LangChain/LangGraph？"** → 太重、黑盒、学习成本高；自研更灵活、可调试、代码量少
- **"和 browser-use 有什么区别？"** → 教学简化版，去除了云服务、MCP 等生产复杂度，聚焦核心 Agent 设计
- **"VLM 和 DOM 怎么选择？"** → DOM 优先（毫秒级），VLM 兜底（秒级），在 system prompt 中引导 LLM 降级策略
- **"怎么防止 Agent 死循环？"** → 动作哈希 + 页面指纹双重检测，分级提醒 + 强制终止
- **"怎么处理 token 超限？"** → 消息自动压缩 + 任务记忆注入 + 早期消息摘要

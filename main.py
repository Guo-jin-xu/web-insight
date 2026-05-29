"""web-insight CLI — AI 浏览器自动化交互式对话。

使用方法:
    conda activate web-ai
    python main.py

命令:
    /quit 或 Ctrl+C — 退出
    /clear          — 清除会话
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.agent.factory import create_browser_agent, create_custom_agent
from src.browser.manager import BrowserManager, ensure_chrome_running
from src.config.settings import settings
from src.memory.history import memory_manager

# ── colors ──────────────────────────────────────────────────────────
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"
RESET = "\033[0m"

PURPLE = "\033[38;5;99m"          # [Agent] 前缀
CYAN = "\033[1;36m"              # [You] 前缀
GRAY = "\033[38;5;240m"          # 工具调用文本
SUCCESS = "\033[32m"             # 成功状态
WARN = "\033[33m"                # 警告
ERROR = "\033[31m"               # 错误

YOU_PREFIX = f"{CYAN}[You]{RESET}"
AGENT_PREFIX = f"{BOLD}{PURPLE}[Agent]{RESET}"


# ── result extraction ────────────────────────────────────────────────

def extract_final_result(messages: list) -> str | None:
    """从 langgraph 消息列表中提取最终结果。

    优先级:
    1. data/task_result.md（done 工具写入）
    2. 最后一个无 tool_calls 的 AIMessage
    3. None
    """
    result_file = Path("data") / "task_result.md"
    if result_file.exists():
        return result_file.read_text(encoding="utf-8")

    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content and not getattr(msg, "tool_calls", []):
            return msg.content

    return None


def extract_tool_calls(messages: list) -> list[dict]:
    """从消息列表提取所有工具调用记录。"""
    tools = []
    for msg in messages:
        if isinstance(msg, ToolMessage):
            tools.append({
                "name": getattr(msg, "name", "?"),
                "content": getattr(msg, "content", ""),
            })
        elif isinstance(msg, AIMessage) and getattr(msg, "tool_calls", []):
            for tc in msg.tool_calls:
                tools.append({
                    "name": tc.get("name", "?"),
                    "content": str(tc.get("args", "")),
                })
    return tools


def extract_domain_hint(task: str) -> str:
    """从任务描述提取域名提示。"""
    keywords = ["bing", "baidu", "google", "runoob", "github", "zhihu", "csdn"]
    for word in keywords:
        if word in task.lower():
            return f"{word}.com" if "." not in word else word
    return ""


# ── main loop ────────────────────────────────────────────────────────

async def run_task(browser: BrowserManager, task: str) -> str | None:
    """执行单次任务（LangGraph 模式）并打印步骤。"""
    domain = extract_domain_hint(task)
    agent = create_browser_agent(browser, task_domain=domain, verbose=False)

    print(f"\n{AGENT_PREFIX} 开始执行任务...\n")

    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=task)]},
        config={"recursion_limit": settings.agent_recursion_limit},
    )

    messages = result.get("messages", [])
    tools = extract_tool_calls(messages)

    # ── print step-by-step tool calls ──
    step = 0
    for t in tools:
        step += 1
        name = t["name"]
        content_preview = t["content"][:50].replace("\n", " ")
        if name == "done":
            print(f"  {BOLD}Step {step}{RESET}  {SUCCESS}{name}{RESET}")
        else:
            print(f"  {DIM}Step {step}{RESET}  {GRAY}{ITALIC}{name}: {content_preview}...{RESET}")

    # ── final result ──
    final = extract_final_result(messages)
    if final:
        print(f"\n{AGENT_PREFIX} {SUCCESS}{BOLD}结果:{RESET}\n")
        print(final)
    else:
        print(f"\n{AGENT_PREFIX} {WARN}未找到最终结果{RESET}")

    # ── save experience ──
    if domain:
        try:
            memory_manager.add_experience(
                domain,
                task,
                f"任务: {task}\n最终 URL: {browser.page.url}",
            )
        except Exception:
            pass

    return final


async def run_task_custom(browser: BrowserManager, task: str) -> str | None:
    """执行单次任务（Phase 3 自定义 Agent 模式 — LoopDetector + MessageManager + BrowserSession + DomService + TaskPlanner）。"""
    domain = extract_domain_hint(task)
    agent = create_custom_agent(browser, task=task, task_domain=domain)

    print(f"\n{AGENT_PREFIX} 开始执行任务 (Custom Agent)...\n")

    plan = agent.task_planner.state.plan
    if plan:
        print(f"  {BOLD}{PURPLE}计划步骤:{RESET}")
        for item in plan:
            print(f"    {DIM}[{item.status.value}] Step {item.step}: {item.description}{RESET}")
        print()

    spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    spinner_idx = 0

    async def on_step(ag):
        nonlocal spinner_idx
        step_no = ag.state.n_steps
        output = ag.state.last_model_output
        results = ag.state.last_result or []

        if output and output.action:
            action_names = [a.tool_name for a in output.action]
            thinking_preview = output.thinking[:80].replace("\n", " ")
            thinking_icon = "💭" if output.thinking else ""

            if "done" in action_names:
                print(f"\n  {BOLD}Step {step_no}{RESET}  {SUCCESS}✓ done{RESET}")
            else:
                print(f"\n  {BOLD}Step {step_no}{RESET}  {CYAN}→ {' + '.join(action_names)}{RESET}")
                if thinking_preview:
                    print(f"  {DIM}  {thinking_icon} {thinking_preview}...{RESET}")

        for r in results:
            content_preview = str(r.content)[:100].replace("\n", " ")
            if r.success:
                print(f"  {SUCCESS}  ✓{RESET} {DIM}{content_preview}{RESET}")
            else:
                print(f"  {ERROR}  ✗{RESET} {DIM}{content_preview}{RESET}")

    print(f"  {DIM}执行中{RESET}", end="", flush=True)
    history = await agent.run(
        max_steps=settings.agent_recursion_limit,
        on_step=on_step,
    )
    print()

    final = history.final_result()
    if final:
        print(f"{AGENT_PREFIX} {SUCCESS}{BOLD}结果:{RESET}\n")
        print(final)
    else:
        print(f"\n{AGENT_PREFIX} {WARN}未找到最终结果{RESET}")

    if domain:
        try:
            memory_manager.add_experience(
                domain,
                task,
                f"任务: {task}\n最终 URL: {browser.page.url}",
            )
        except Exception:
            pass

    return final


async def interactive_loop():
    """交互式对话循环。"""
    use_custom = "--custom" in sys.argv or "-c" in sys.argv

    print(f"\n  {BOLD}web-insight CLI{RESET} — AI 浏览器自动化")
    if use_custom:
        print(f"  {PURPLE}模式: Phase 3 Custom Agent{RESET}")
    print(f"  {DIM}输入任务描述，Agent 自动操作浏览器完成")
    print(f"  /quit 或 {ITALIC}Ctrl+C{RESET}{DIM} 退出  |  /clear 清除会话{RESET}\n")

    if not ensure_chrome_running():
        print(f"{ERROR}无法启动 Chrome。请手动: chrome --remote-debugging-port=9222{RESET}")
        return

    browser = BrowserManager()
    await browser.connect()
    print(f"{SUCCESS}Chrome 已连接: {await browser.page.title()}{RESET}\n")

    try:
        while True:
            try:
                user_input = input(f"{YOU_PREFIX} ").strip()
            except (EOFError, KeyboardInterrupt):
                print(f"\n{AGENT_PREFIX} 再见!")
                break

            if not user_input:
                continue

            if user_input.lower() in ("/quit", "/exit", "/q"):
                print(f"\n{AGENT_PREFIX} 再见!")
                break

            if user_input.lower() == "/clear":
                os.system("cls" if sys.platform == "win32" else "clear")
                print(f"{AGENT_PREFIX} 会话已清除\n")
                continue

            # Execute task
            if use_custom:
                await run_task_custom(browser, user_input)
            else:
                await run_task(browser, user_input)

    finally:
        await browser.disconnect()
        print(f"\n{DIM}浏览器已断开{RESET}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(name)s] %(message)s")
    asyncio.run(interactive_loop())

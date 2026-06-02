"""任务执行循环 — run_task 及辅助函数。

从 main.py 解耦，使 CLI 入口与任务执行逻辑分离。
日常对话已移入 router.py 的 conversation 节点。
"""

from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.errors import NodeInterrupt

from src.agent.factory import create_browser_agent
from src.browser.manager import BrowserManager
from src.config.settings import settings
from src.memory.history import memory_manager

BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"
RESET = "\033[0m"

PURPLE = "\033[38;5;99m"
GRAY = "\033[38;5;240m"
SUCCESS = "\033[32m"
WARN = "\033[33m"

AGENT_PREFIX = f"{BOLD}{PURPLE}[Agent]{RESET}"


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


async def run_task(browser: BrowserManager, task: str) -> str | None:
    """执行单次任务（LangGraph 模式）并打印步骤。"""
    domain = extract_domain_hint(task)
    agent = create_browser_agent(browser, task_domain=domain, verbose=False)

    print(f"\n{AGENT_PREFIX} 开始执行任务...\n")

    all_messages: list = []
    try:
        async for chunk in agent.astream(
            {"messages": [HumanMessage(content=task)]},
            config={"recursion_limit": settings.agent_recursion_limit},
        ):
            for node_name, node_output in chunk.items():
                if isinstance(node_output, dict) and "messages" in node_output:
                    for msg in node_output["messages"]:
                        if not any(m is msg for m in all_messages):
                            all_messages.append(msg)
    except NodeInterrupt:
        pass

    tools = extract_tool_calls(all_messages)

    step = 0
    for t in tools:
        step += 1
        name = t["name"]
        content_preview = t["content"][:50].replace("\n", " ")
        if name == "done":
            print(f"  {BOLD}Step {step}{RESET}  {SUCCESS}{name}{RESET}")
        else:
            print(f"  {DIM}Step {step}{RESET}  {GRAY}{ITALIC}{name}: {content_preview}...{RESET}")

    final = extract_final_result(all_messages)
    if final:
        print(f"\n{AGENT_PREFIX} {SUCCESS}{BOLD}结果:{RESET}\n")
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

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

from src.agent.router import route_query
from src.browser.manager import BrowserManager, ensure_chrome_running
from src.exceptions import LLMError, RateLimitError

BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"
RESET = "\033[0m"

PURPLE = "\033[38;5;99m"
CYAN = "\033[1;36m"
SUCCESS = "\033[32m"
WARN = "\033[33m"
ERROR = "\033[31m"

YOU_PREFIX = f"{CYAN}[You]{RESET}"
AGENT_PREFIX = f"{BOLD}{PURPLE}[Agent]{RESET}"


async def interactive_loop():
    """交互式对话循环。"""
    print(f"\n  {BOLD}web-insight CLI{RESET} — AI 浏览器自动化")
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

            try:
                print(f"\n{AGENT_PREFIX} {DIM}分析中...{RESET}")
                response = await route_query(browser, user_input)

                if response:
                    print(f"\n{AGENT_PREFIX} {SUCCESS}{BOLD}回复:{RESET}\n")
                    print(response)
                    print()

            except RateLimitError:
                print(f"\n{AGENT_PREFIX} {WARN}当前请求过于频繁，请稍后再试~{RESET}\n")
            except LLMError as e:
                print(f"\n{AGENT_PREFIX} {ERROR}模型调用失败: {e}{RESET}\n")
            except KeyboardInterrupt:
                raise
            except Exception:
                print(f"\n{AGENT_PREFIX} {ERROR}发生未知错误，请重试{RESET}\n")

    finally:
        await browser.disconnect()
        print(f"\n{DIM}浏览器已断开{RESET}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(name)s] %(message)s")
    asyncio.run(interactive_loop())

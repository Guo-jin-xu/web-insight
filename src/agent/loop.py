"""Agent Loop — 参考 browser-use 的 step 循环。

自研循环：
1. prepare_context — 构建消息上下文
2. get_next_action — 调用 LLM 获取下一步动作
3. execute_action — 执行工具
4. post_process — 更新状态、检测循环

循环终止条件：
- LLM 调用 done 工具
- 达到最大步数
- 连续失败次数超限
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from src.agent.action_merger import merge_redundant_actions
from src.agent.loop_detector import ActionLoopDetector
from src.llm.client import LLMClient, LLMResponse
from src.memory.task_memory import MessageCompactor, TaskMemory
from src.tools.registry import Registry

logger = logging.getLogger(__name__)

# 工具调用日志文件
TOOL_LOG_PATH = Path("data") / "tool_calls.log"

BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
PURPLE = "\033[38;5;99m"
SUCCESS = "\033[32m"
WARN = "\033[33m"
ERROR = "\033[31m"

AGENT_PREFIX = f"{BOLD}{PURPLE}[Agent]{RESET}"


# 工具结果最大长度（字符），防止 DOM snapshots 撑爆上下文
MAX_TOOL_RESULT_LENGTH = 3000


def _truncate_result(result: str, max_len: int = MAX_TOOL_RESULT_LENGTH) -> str:
    """截断过长的工具结果，保留头尾。"""
    if len(result) <= max_len:
        return result
    half = max_len // 2
    return result[:half] + f"\n\n... [中间省略 {len(result) - max_len} 字符] ...\n\n" + result[-half:]


def _log_tool_call(step: int, tool_name: str, args: dict, result: str = ""):
    """记录工具调用到日志文件。"""
    try:
        TOOL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        args_preview = json.dumps(args, ensure_ascii=False)[:200]
        line = f"[{ts}] Step {step} {tool_name}({args_preview})"
        if result:
            result_preview = result[:500].replace("\n", "\\n")
            line += f"\n  -> {result_preview}"
        with open(TOOL_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as e:
        logger.debug(f"工具日志写入失败: {e}")


class AgentLoop:
    """自研 Agent 循环。"""

    def __init__(
        self,
        task: str,
        llm_client: LLMClient,
        registry: Registry,
        max_steps: int = 16,
        max_failures: int = 5,
        system_prompt: str = "",
        get_current_url: callable = None,  # 获取当前页面 URL（用于循环检测）
        browser=None,  # 可选：BrowserManager 引用，用于弹窗检查
    ):
        self.task = task
        self.llm_client = llm_client
        self.registry = registry
        self.max_steps = max_steps
        self.max_failures = max_failures
        self.system_prompt = system_prompt
        self.get_current_url = get_current_url or (lambda: "")
        self._browser = browser

        # 内部状态
        self.step_count: int = 0
        self.consecutive_failures: int = 0
        self._done_result: str | None = None
        self._messages: list[dict] = []

        # Task 5: 循环检测
        self.loop_detector = ActionLoopDetector(window_size=20)

        # Task 6: 短期记忆管理
        self.task_memory = TaskMemory()
        self.message_compactor = MessageCompactor(max_messages=30)

    @property
    def is_done(self) -> bool:
        return self._done_result is not None

    def _build_messages(
        self,
        system_prompt: str,
        history: list[dict],
    ) -> list[dict]:
        """构建消息列表。"""
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        return messages

    def _format_tool_result(
        self,
        tool_call_id: str,
        tool_name: str,
        result: str,
    ) -> dict:
        """格式化工具执行结果为 API 消息格式。"""
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": _truncate_result(str(result)),
        }

    def _format_assistant_message(self, response: LLMResponse) -> dict:
        """格式化助手消息（含工具调用）。"""
        msg: dict = {"role": "assistant", "content": response.content or ""}

        if response.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                    },
                }
                for tc in response.tool_calls
            ]

        return msg

    async def run(self) -> str | None:
        """执行 Agent 循环。"""
        from src.agent.prompts import BROWSER_AGENT_SYSTEM_PROMPT, get_current_time_str

        system_prompt = self.system_prompt or BROWSER_AGENT_SYSTEM_PROMPT.format(
            current_time=get_current_time_str(),
        )

        self._messages = [{"role": "user", "content": self.task}]

        print(f"\n{AGENT_PREFIX} 开始执行任务...\n")

        while self.step_count < self.max_steps and not self.is_done:
            self.step_count += 1
            try:
                result = await self._step(system_prompt)
                if result is not None and not self.is_done:
                    # LLM 不调用工具时直接返回文本
                    return result
            except Exception as e:
                self.consecutive_failures += 1
                logger.error(f"Step {self.step_count} failed: {type(e).__name__}: {e}")
                if self.consecutive_failures >= self.max_failures:
                    logger.error(f"连续 {self.max_failures} 次失败，终止任务")
                    break

        if self._done_result:
            print(f"\n{AGENT_PREFIX} {SUCCESS}{BOLD}结果:{RESET}\n")
            print(self._done_result)
            print()

        return self._done_result

    async def _step(self, system_prompt: str) -> str | None:
        """执行单步：LLM 调用 → 工具执行 → 状态更新。"""
        # Phase 0: 检查弹窗
        if self._browser and self._browser.popup_handler:
            popup = self._browser.popup_handler
            if popup.has_pending_popups():
                msgs = popup.get_and_clear_messages()
                self._messages.append({
                    "role": "user",
                    "content": f"[系统通知] 页面弹出了以下对话框，已自动处理：\n" + "\n".join(msgs),
                })

        # Task 6: 消息压缩（如果过多）
        self._messages = self.message_compactor.compact(self._messages)

        # Task 6: 注入任务记忆上下文
        memory_context = self.task_memory.get_context_for_llm()
        if memory_context:
            self._messages.append({
                "role": "user",
                "content": f"[任务记忆]\n{memory_context}"
            })

        # Phase 1: 准备上下文
        messages = self._build_messages(system_prompt, self._messages)
        tool_schemas = self.registry.get_tool_schemas()

        # Phase 2: 调用 LLM
        response = await self.llm_client.chat_with_tools(
            messages=messages,
            tools=tool_schemas,
        )

        # Phase 3: 处理响应
        if not response.has_tool_calls:
            # LLM 未调用工具，直接返回文本
            if response.content:
                self._messages.append({"role": "assistant", "content": response.content})
                return response.content
            # 无内容也无工具调用，视为失败
            self.consecutive_failures += 1
            return None

        # 方案B: Post-processing 冗余动作合并
        original_count = len(response.tool_calls)
        merged_calls, skipped = merge_redundant_actions(response.tool_calls)
        if len(merged_calls) < original_count:
            print(f"  {DIM}方案B: 跳过冗余动作{RESET} {skipped}")
            # 注意：跳过动作后，需要更新 tool_calls 数量
            response.tool_calls = merged_calls

        # 记录助手消息
        self._messages.append(self._format_assistant_message(response))

        # Phase 4: 执行工具调用
        for tc in response.tool_calls:
            step_label = f"Step {self.step_count}"
            args_preview = json.dumps(tc.arguments, ensure_ascii=False)[:60]
            print(f"  {DIM}{step_label}{RESET}  {tc.name}({args_preview})")

            try:
                result = await self.registry.execute_action(tc.name, tc.arguments)
                self.consecutive_failures = 0

                # 记录工具调用日志
                _log_tool_call(self.step_count, tc.name, tc.arguments, str(result))

                # Task 5: 记录动作到循环检测器（排除某些动作）
                if tc.name not in ("done", "go_back", "send_keys"):
                    self.loop_detector.record_action(tc.name, tc.arguments)

                # Task 6: 更新任务记忆
                self.task_memory.add_step_result(self.step_count, tc.name, str(result))
                if tc.name == "navigate":
                    self.task_memory.add_visited_url(tc.arguments.get("url", ""))
                elif tc.name == "extract_content":
                    result_str = str(result)
                    if len(result_str) > 50:
                        self.task_memory.add_finding(result_str[:200])

                # 检查是否调用了 done
                if tc.name == "done":
                    done_result = str(result)
                    print(f"  {BOLD}{step_label}{RESET}  {SUCCESS}done{RESET}")
                    self._done_result = done_result
                    return self._done_result

            except Exception as e:
                result = f"工具执行失败: {e}"
                self.consecutive_failures += 1
                _log_tool_call(self.step_count, tc.name, tc.arguments, str(result))

            # 记录工具结果
            self._messages.append(self._format_tool_result(tc.id, tc.name, result))

            # 动作失败时记录日志
            is_failure = str(result).startswith("工具执行失败")
            if is_failure:
                print(f"    {WARN}⚠ 动作失败:{RESET} {tc.name}")
                self._messages.append({
                    "role": "user",
                    "content": (
                        f"[动作失败反馈]\n"
                        f"工具: {tc.name}\n"
                        f"结果: {str(result)[:200]}\n"
                        f"建议: 尝试不同的方式完成该操作，或跳过此步骤继续。"
                    ),
                })

        # Task 5: 尝试记录页面状态到循环检测器
        try:
            current_url = self.get_current_url()
            if current_url and self._browser and hasattr(self._browser, "page"):
                page = self._browser.page
                # 获取页面文本和元素数量用于指纹
                text = await page.evaluate("() => document.body.innerText || ''")
                elements = await page.evaluate("() => document.querySelectorAll('*').length")
                self.loop_detector.record_page_state(current_url, text, elements)
        except Exception as e:
            logger.debug(f"循环检测页面状态记录跳过: {e}")

        # Task 5: 注入循环检测提醒
        nudge = self.loop_detector.get_nudge_message()
        if nudge:
            self._messages.append({
                "role": "user",
                "content": f"[系统提醒 - 循环检测]\n{nudge}"
            })

        return None
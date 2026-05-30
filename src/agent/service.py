import asyncio
import json
import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.language_models import BaseChatModel

from src.agent.judge import judge_step
from src.agent.loop_detector import LoopDetector
from src.agent.message_manager import MessageManager
from src.agent.planning import TaskPlanner
from src.agent.prompts import get_system_prompt
from src.agent.views import (
    ActionModel,
    AgentHistory,
    AgentHistoryList,
    AgentOutput,
    AgentState,
    BrowserStateHistory,
)
from src.browser.session import BrowserSession
from src.dom.service import DomService
from src.schemas.tool_result import ActionResult

logger = logging.getLogger("web_insight.agent")


class Agent:
    """浏览器自动化 Agent — 自定义 step/run 循环。"""

    def __init__(
        self,
        task: str,
        llm: BaseChatModel,
        browser_session: Any,
        tools: list,
        max_failures: int = 5,
        use_vision: bool = True,
        use_judge: bool = True,
        site_experience: str = "",
    ):
        self.task = task
        self.llm = llm
        self.browser_session = browser_session
        self.tools = tools
        self.max_failures = max_failures
        self.use_vision = use_vision
        self.use_judge = use_judge

        self.state = AgentState()
        self.history = AgentHistoryList()
        self.loop_detector = LoopDetector()

        self.session_wrapper = BrowserSession(browser_session)
        self.dom_service = DomService(browser_session)
        self.task_planner = TaskPlanner()

        system_prompt = get_system_prompt(site_experience=site_experience)
        self.message_manager = MessageManager(task=task, system_prompt=system_prompt)

        self._tool_map: dict[str, Any] = {}
        for t in tools:
            if hasattr(t, "name"):
                self._tool_map[t.name] = t

    async def run(
        self,
        max_steps: int = 100,
        on_step: Callable[["Agent"], Awaitable[None]] | None = None,
    ) -> AgentHistoryList:
        """执行任务直到完成或达到最大步数。

        Args:
            max_steps: 最大执行步数
            on_step: 每步完成后的异步回调（用于流式输出等场景），接收 Agent 自身
        """
        await self.browser_session.connect()
        self.state.session_initialized = True
        self.session_wrapper._setup_dialog_handler()
        self.task_planner.add_plan(self.task)

        while self.state.n_steps < max_steps:
            if self.state.stopped:
                break
            if self.state.consecutive_failures >= self.max_failures:
                logger.warning(f"超过最大连续失败次数 {self.max_failures}，终止")
                break

            is_done = await self.step()
            if on_step is not None:
                await on_step(self)
            if is_done:
                break

        return self.history

    async def step(self) -> bool:
        """执行单步: prepare → llm → execute → post_process"""
        self.state.n_steps += 1

        # Phase 1: 准备上下文
        browser_state_summary = await self._get_browser_state_summary()
        self.message_manager.add_state_message(browser_state_summary)

        # Phase 2: LLM 调用
        model_output = await self._get_next_action()
        if model_output is None:
            self.state.consecutive_failures += 1
            return False

        self.state.last_model_output = model_output
        self.message_manager.add_assistant_message(model_output.model_dump_json())

        # Phase 3: 执行 actions
        results = await self.multi_act(model_output.action)
        self.state.last_result = results
        results_text = json.dumps([r.model_dump() for r in results], ensure_ascii=False)
        self.message_manager.add_tool_results(results_text)

        # Phase 4: 后处理
        await self._post_process(model_output, results)

        # Loop detection: 记录 action 并检查是否注入 nudge
        self._record_and_check_loop(model_output)

        self.message_manager.maybe_compact(self.llm)

        return model_output.is_done

    async def _get_browser_state_summary(self) -> str:
        """获取当前浏览器状态摘要。"""
        try:
            url = self.browser_session.page.url
            title = await self.browser_session.page.title()

            lines = [f"URL: {url}", f"Title: {title}"]

            plan_summary = self.task_planner.summary()
            lines.append("")
            lines.append("--- Task Plan ---")
            lines.append(plan_summary)

            try:
                dom_state = await self.dom_service.get_serialized_dom()
                lines.append("")
                lines.append("--- Interactive Elements ---")
                lines.append(dom_state.text)
            except Exception:
                elements = await self.browser_session.get_indexed_elements()
                lines.append("")
                lines.append("--- Interactive Elements ---")
                for el in elements:
                    bbox = el["bbox"]
                    attrs = el.get("attributes", {})
                    label = attrs.get("aria-label", "") or attrs.get("placeholder", "") or ""
                    extra = f" | {label}" if label else ""
                    lines.append(
                        f"  [{el['index']}] <{el['tag']}> {el['text'][:40]}{extra}"
                    )

            return "\n".join(lines)
        except Exception as e:
            logger.error(f"获取浏览器状态失败: {e}")
            return f"浏览器状态获取失败: {e}"

    async def _get_next_action(self) -> AgentOutput | None:
        """调用 LLM 获取下一步 action。"""
        messages = self.message_manager.get_messages()

        try:
            response = await self.llm.ainvoke(messages)
            return self._parse_response(response)
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            return None

    def _parse_response(self, response: Any) -> AgentOutput | None:
        """解析 LLM 响应为 AgentOutput。"""
        if isinstance(response, AgentOutput):
            return response

        if hasattr(response, "thinking") and hasattr(response, "action"):
            return response

        if hasattr(response, "tool_calls") and response.tool_calls:
            actions = []
            for tc in response.tool_calls:
                actions.append(ActionModel(
                    tool_name=tc.get("name", ""),
                    tool_args=tc.get("args", {}),
                ))
            return AgentOutput(
                thinking=getattr(response, "content", "") or "",
                evaluation_previous_goal="",
                memory="",
                next_goal="",
                action=actions,
            )

        content = getattr(response, "content", "")
        if isinstance(content, str) and content.strip():
            try:
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    data = json.loads(json_match.group())
                    return AgentOutput(**data)
            except (json.JSONDecodeError, Exception):
                pass

            return AgentOutput(
                thinking=content[:500],
                evaluation_previous_goal="",
                memory="",
                next_goal="",
                action=[],
            )

        return None

    async def multi_act(self, actions: list[ActionModel]) -> list[ActionResult]:
        """顺序执行多个 action。"""
        results: list[ActionResult] = []
        for action in actions:
            result = await self._execute_action(action)
            results.append(result)
            if result.error:
                break
        return results

    async def _execute_action(self, action: ActionModel) -> ActionResult:
        """执行单个 action。"""
        if action.tool_name == "done":
            summary = action.tool_args.get("summary", "任务完成")
            return ActionResult(
                is_done=True,
                success=True,
                extracted_content=summary,
            )

        tool = self._tool_map.get(action.tool_name)
        if tool is None:
            return ActionResult(
                success=False,
                error=f"未知工具: {action.tool_name}",
            )

        try:
            result = await asyncio.wait_for(
                tool.ainvoke(action.tool_args),
                timeout=15.0,
            )
            return self._tool_result_to_action_result(action.tool_name, result)
        except asyncio.TimeoutError:
            return ActionResult(
                success=False,
                error=f"工具 {action.tool_name} 执行超时",
            )
        except Exception as e:
            return ActionResult(
                success=False,
                error=f"工具 {action.tool_name} 执行异常: {str(e)[:200]}",
            )

    def _tool_result_to_action_result(self, tool_name: str, result: Any) -> ActionResult:
        """将工具返回值转换为 ActionResult。"""
        if isinstance(result, ActionResult):
            return result

        if isinstance(result, str):
            is_error = result.startswith("失败") or "error" in result.lower()
            return ActionResult(
                is_done=(tool_name == "done"),
                success=not is_error,
                extracted_content=result,
                error=result if is_error else None,
            )

        return ActionResult(
            is_done=(tool_name == "done"),
            success=True,
            extracted_content=str(result),
        )

    async def _post_process(self, model_output: AgentOutput, results: list[ActionResult]) -> None:
        """后处理: 记录 history、更新状态。"""
        self.state.last_model_output = model_output
        self.state.last_result = results

        all_success = all(r.success for r in results) if results else False
        if all_success:
            self.task_planner.mark_complete(self.task_planner.state.current_step)
            self.task_planner.advance()
            self.task_planner.reset_ticks()
        else:
            self.task_planner.tick()

        if self.task_planner.should_replan():
            self.message_manager.messages.append(
                HumanMessage(
                    content="<replan_suggestion>\n"
                    "当前步骤连续失败，请考虑更换策略或调整当前计划步骤。\n"
                    "</replan_suggestion>"
                )
            )
            self.task_planner.reset_ticks()

        try:
            url = self.browser_session.page.url
            title = await self.browser_session.page.title()
        except Exception:
            url = "unknown"
            title = "unknown"

        browser_state = BrowserStateHistory(
            url=url,
            title=title,
            tabs_count=1,
        )

        history_entry = AgentHistory(
            model_output=model_output,
            result=[r.model_dump() for r in results],
            state=browser_state,
        )
        self.history.history.append(history_entry)

        if model_output.is_done:
            for result in results:
                if result.is_done:
                    self.state.stopped = True
                    return

        if self.use_judge:
            judgement = judge_step(results)
            if not judgement.verdict:
                self.state.consecutive_failures += 1
            else:
                self.state.consecutive_failures = 0

    def _record_and_check_loop(self, model_output: AgentOutput) -> None:
        """记录 action 到 LoopDetector 并注入 nudge 到消息。"""
        try:
            url = self.browser_session.page.url
        except Exception:
            url = "unknown"

        for action in model_output.action:
            self.loop_detector.record(
                action.tool_name, action.tool_args, url
            )

        nudge = self.loop_detector.get_nudge()
        if nudge:
            self.message_manager.messages.append(
                HumanMessage(
                    content=f"<loop_reminder>\n{nudge}\n</loop_reminder>"
                )
            )
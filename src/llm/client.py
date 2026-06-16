"""原生 OpenAI 兼容 API 客户端 — 替代 langchain。

直接使用 httpx 调用智谱 API，支持 function calling / 工具调用。
不依赖 langchain 或 langgraph。
"""

import json
import logging
from dataclasses import dataclass, field

import httpx

from src.config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    """工具调用。"""
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    """LLM 响应。"""
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = ""
    usage: dict = field(default_factory=dict)

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class LLMClient:
    """OpenAI 兼容 API 客户端。"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout: int | None = None,
    ):
        self.api_key = api_key or settings.llm_api_key
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.model = model or settings.llm_model_name
        self.temperature = temperature if temperature is not None else settings.llm_temperature
        self.max_tokens = max_tokens if max_tokens is not None else settings.llm_max_tokens
        self.timeout = timeout or settings.llm_timeout

    def _build_messages(
        self,
        system_prompt: str,
        user_message: str,
        history: list[dict],
    ) -> list[dict]:
        """构建消息列表。"""
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})
        return messages

    async def chat(
        self,
        messages: list[dict],
        temperature: float | None = None,
    ) -> LLMResponse:
        """发送聊天请求（无工具调用）。"""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
        }
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens

        # 小米 MiMo API 需要禁用 thinking
        if "xiaomimimo" in self.base_url:
            payload["thinking"] = {"type": "disabled"}

        return await self._request(payload)

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        temperature: float | None = None,
    ) -> LLMResponse:
        """发送带工具的聊天请求。"""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "tools": tools,
            "tool_choice": "auto",
        }
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens

        # 小米 MiMo API 需要禁用 thinking
        if "xiaomimimo" in self.base_url:
            payload["thinking"] = {"type": "disabled"}

        return await self._request(payload)

    async def _request(self, payload: dict) -> LLMResponse:
        """发送 HTTP 请求到 API。"""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        return self._parse_response(data)

    def _parse_response(self, data: dict) -> LLMResponse:
        """解析 API 响应。"""
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "") or ""
        finish_reason = choice.get("finish_reason", "")
        usage = data.get("usage", {})

        tool_calls = []
        # 处理 tool_calls 可能为 None 的情况
        raw_tool_calls = message.get("tool_calls") or []
        for tc in raw_tool_calls:
            func = tc.get("function", {})
            try:
                arguments = json.loads(func.get("arguments", "{}"))
            except json.JSONDecodeError:
                arguments = {}
            tool_calls.append(ToolCall(
                id=tc.get("id", ""),
                name=func.get("name", ""),
                arguments=arguments,
            ))

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage,
        )

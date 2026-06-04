"""工具注册中心 — 参考 browser-use 的 Registry 模式。

提供装饰器注册工具、生成 OpenAI function calling schema、执行工具。
"""

import inspect
import logging
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class RegisteredAction:
    """已注册的工具。"""

    def __init__(
        self,
        name: str,
        description: str,
        function: Callable,
        param_model: type[BaseModel],
    ):
        self.name = name
        self.description = description
        self.function = function
        self.param_model = param_model

    def to_openai_schema(self) -> dict:
        """生成 OpenAI function calling 格式的 schema。"""
        schema = self.param_model.model_json_schema()
        # 移除 Pydantic 内部字段
        properties = schema.get("properties", {})
        properties.pop("model_config", None)

        # 移除 title（不需要传给 LLM）
        for prop in properties.values():
            if isinstance(prop, dict):
                prop.pop("title", None)

        required = schema.get("required", [])

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


class Registry:
    """工具注册中心。"""

    def __init__(self):
        self._actions: dict[str, RegisteredAction] = {}

    def action(
        self,
        description: str,
        param_model: type[BaseModel] | None = None,
    ) -> Callable:
        """装饰器：注册一个工具。"""

        def decorator(func: Callable) -> Callable:
            name = func.__name__
            model = param_model or self._create_param_model(func)
            self._actions[name] = RegisteredAction(
                name=name,
                description=description,
                function=func,
                param_model=model,
            )
            return func

        return decorator

    def _create_param_model(self, func: Callable) -> type[BaseModel]:
        """从函数签名自动生成 Pydantic 模型。"""
        sig = inspect.signature(func)
        annotations = {}
        namespace = {}

        for param_name, param in sig.parameters.items():
            if param_name in ("self", "params", "browser"):
                continue
            annotation = param.annotation if param.annotation != inspect.Parameter.empty else str
            default = ... if param.default == inspect.Parameter.empty else param.default
            annotations[param_name] = annotation
            if default is not ...:
                namespace[param_name] = default

        namespace["__annotations__"] = annotations
        return type(f"{func.__name__}_Params", (BaseModel,), namespace)

    def get_tool_schemas(self) -> list[dict]:
        """获取所有工具的 OpenAI function calling schema。"""
        return [action.to_openai_schema() for action in self._actions.values()]

    def get_action_names(self) -> list[str]:
        """获取所有工具名称。"""
        return list(self._actions.keys())

    async def execute_action(self, name: str, params: dict[str, Any], **kwargs) -> Any:
        """执行指定工具。"""
        if name not in self._actions:
            raise ValueError(f"Action '{name}' not found. Available: {self.get_action_names()}")

        action = self._actions[name]
        validated = action.param_model(**params)

        result = action.function(params=validated, **kwargs)
        if inspect.isawaitable(result):
            result = await result

        return result

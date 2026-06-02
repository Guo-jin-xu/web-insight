"""web-insight 自定义异常。"""


class WebInsightError(Exception):
    """Base exception for web-insight."""


class RateLimitError(WebInsightError):
    """API 速率限制。"""

    def __init__(self, message: str = "当前请求过于频繁，请稍后再试~"):
        super().__init__(message)


class LLMError(WebInsightError):
    """LLM 调用异常。"""


def is_rate_limit_error(exc: Exception) -> bool:
    """判断异常是否为速率限制错误。"""
    if isinstance(exc, RateLimitError):
        return True
    try:
        from openai import RateLimitError as OpenAIRateLimitError
        if isinstance(exc, OpenAIRateLimitError):
            return True
    except ImportError:
        pass
    text = str(exc).lower()
    return "429" in text or "rate" in text or "频率" in text or "速率" in text

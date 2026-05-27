from langchain_openai import ChatOpenAI

from src.config.settings import settings


def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.llm_model_name,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        timeout=settings.llm_timeout,
        max_retries=settings.llm_max_retries,
    )


def get_vlm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.vlm_model_name,
        api_key=settings.vlm_api_key or settings.llm_api_key,
        base_url=settings.vlm_base_url,
        temperature=settings.vlm_temperature,
        max_tokens=settings.vlm_max_tokens,
        timeout=settings.vlm_timeout,
        max_retries=settings.vlm_max_retries,
    )

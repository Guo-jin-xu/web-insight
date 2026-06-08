from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM
    llm_api_key: str = ""
    llm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    llm_model_name: str = "GLM-4-Flash-250414"
    llm_temperature: float = 0.1
    llm_max_tokens: int | None = None  # None = 不限制，由 API 自行决定
    llm_timeout: int = 30
    llm_max_retries: int = 3

    # VLM
    vlm_api_key: str = ""
    vlm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    vlm_model_name: str = "GLM-4.1V-Thinking-Flash"
    vlm_temperature: float = 0.1
    vlm_max_tokens: int | None = None  # None = 不限制
    vlm_timeout: int = 30
    vlm_max_retries: int = 3

    # Agent
    agent_recursion_limit: int = 16

    @property
    def project_root(self) -> Path:
        return Path(__file__).parent.parent.parent


settings = Settings()

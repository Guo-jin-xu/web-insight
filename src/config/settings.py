from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM
    llm_api_key: str = ""
    llm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    llm_model_name: str = "GLM-4-Flash-250414"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 2048
    llm_timeout: int = 30
    llm_max_retries: int = 3

    # VLM
    vlm_api_key: str = ""
    vlm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    vlm_model_name: str = "GLM-4.1V-Thinking-Flash"
    vlm_temperature: float = 0.1
    vlm_max_tokens: int = 2048
    vlm_timeout: int = 30
    vlm_max_retries: int = 3

    # Agent
    agent_max_steps: int = 15
    agent_recursion_limit: int = 16
    agent_max_failures: int = 5
    agent_vlm_fallback: int = 3

    # Paths
    screenshot_dir: str = "data/screenshots"
    experience_dir: str = "data/experiences"
    chroma_persist_dir: str = "data/chroma"
    log_dir: str = "data/logs"

    # Debug
    debug: bool = True
    log_level: str = "DEBUG"
    save_screenshots: bool = True

    @property
    def project_root(self) -> Path:
        return Path(__file__).parent.parent.parent

    def resolve_path(self, relative: str) -> Path:
        p = Path(relative)
        if not p.is_absolute():
            p = self.project_root / p
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()

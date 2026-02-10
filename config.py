from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    openai_api_key: str
    openai_model: str = "gpt-4o-mini"
    storage_path: Path = Path("./storage")
    max_file_size: int = 100 * 1024 * 1024  # 100MB


settings = Settings()

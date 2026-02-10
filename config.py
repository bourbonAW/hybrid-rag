from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"
    storage_path: Path = Path("./storage")
    max_file_size: int = 100 * 1024 * 1024  # 100MB

    class Config:
        env_file = ".env"


settings = Settings()

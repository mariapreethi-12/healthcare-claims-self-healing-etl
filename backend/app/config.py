from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://claims:claims@db:5432/claims"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    ollama_base_url: str | None = None
    ollama_model: str = "llama3.2:3b"
    llm_timeout_seconds: float = 15.0
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    max_upload_mb: int = 10

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

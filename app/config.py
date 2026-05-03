from enum import StrEnum
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(StrEnum):
    OPENAI = "openai"
    GEMINI = "gemini"
    CLAUDE = "claude"


class Settings(BaseSettings):
    LLM_PROVIDER: LLMProvider = LLMProvider.OPENAI
    LLM_MODEL: str = "gpt-4o"

    OPENAI_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None

    BODY_TRUNCATION_CLASSIFY: int = 500
    BODY_TRUNCATION_SUMMARIZE: int = 2000

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


def get_settings() -> Settings:
    return Settings()

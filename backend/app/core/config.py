"""Application configuration using pydantic-settings."""
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    APP_NAME: str = "Image Dataset Curator"
    DEBUG: bool = False
    DEMO_MODE: bool = False

    # Database
    DATABASE_URL: str = "sqlite:///./data/curator.db"

    # Auth / OIDC
    OIDC_DISCOVERY_URL: str = ""
    OIDC_CLIENT_ID: str = ""
    OIDC_CLIENT_SECRET: str = ""
    SESSION_SECRET: str = ""
    FRONTEND_URL: str = "http://localhost:5173"

    # File storage
    UPLOAD_DIR: str = "./data/uploads"
    MAX_UPLOAD_SIZE_MB: int = 50

    # LLM (optional)
    LLM_API_KEY: str = ""
    LLM_PROVIDER: str = "openai-compatible"
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_BASE_URL: str = "https://api.openai.com/v1"

    @field_validator("DEMO_MODE", mode="before")
    @classmethod
    def refuse_demo_in_production(cls, v: bool) -> bool:
        # Demo mode is only allowed when binding localhost; the check is done at startup.
        return v


settings = Settings()

"""
config.py — Centralised settings for the YouTube pipeline packages.

Context: Loads environment variables from the REPO ROOT .env file.
This is SEPARATE from freerouter/.env which holds provider API keys.
This file holds pipeline-specific config (Zep, YouTube, Notion, etc.)

Usage:
    from packages.core.config import get_settings
    settings = get_settings()
    print(settings.FREEROUTER_URL)  # http://localhost:4000

Imports: pydantic-settings, functools
Imported by: packages/router/client.py, packages/memory/, packages/integrations/
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Pipeline configuration loaded from repo root .env file."""

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # FreeRouter proxy — the LLM gateway (runs as separate process)
    # Never import from freerouter/. Always call this URL via HTTP.
    FREEROUTER_URL: str = "http://localhost:4000"
    FREEROUTER_API_KEY: str = "not-needed"

    # GetZep Cloud — agent memory
    ZEP_API_KEY: str = ""
    ZEP_BASE_URL: str = "https://api.getzep.com"
    ZEP_AUDIENCE_USER_ID: str = "audience_model_v1"
    ZEP_LEARNING_USER_ID: str = "learning_synthesis_v1"

    # External integrations
    YOUTUBE_API_KEY: str = ""
    NOTION_API_KEY: str = ""
    GITHUB_TOKEN: str = ""

    # Internal storage — separate from freerouter/data/conversations.db
    DATA_DIR: str = "packages/data"

    # Logging
    LOG_LEVEL: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings singleton. Call this everywhere."""
    return Settings()

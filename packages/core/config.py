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

from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceStatus(str, Enum):
    """Status of external service configuration."""
    AVAILABLE = "available"
    NOT_CONFIGURED = "not_configured"
    MISCONFIGURED = "misconfigured"


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
    # Whether to perform startup health check (set to False for lazy initialization)
    FREEROUTER_STARTUP_CHECK: bool = True

    # GetZep Cloud — agent memory
    ZEP_API_KEY: str = ""
    ZEP_BASE_URL: str = "https://api.getzep.com"
    ZEP_AUDIENCE_USER_ID: str = "audience_model_v1"
    ZEP_LEARNING_USER_ID: str = "learning_synthesis_v1"
    # Set to true once ZEP_API_KEY is configured and verified working
    ZEP_ENABLED: bool = False

    # Feature flags for pausing pipeline stages
    # Set to false to skip asset creation (Remotion renders, shader backgrounds)
    ASSET_CREATION_ENABLED: bool = True
    # Set to false to skip publishing (Notion pages, YouTube upload prep)
    PUBLISH_ENABLED: bool = True

    # External integrations
    YOUTUBE_API_KEY: str = ""
    NOTION_API_KEY: str = ""
    GITHUB_TOKEN: str = ""

    # Internal storage — separate from freerouter/data/conversations.db
    DATA_DIR: str = "packages/data"

    # Logging
    LOG_LEVEL: str = "INFO"

    # API Authentication Settings
    API_KEYS: str = ""  # Comma-separated list of valid API keys
    API_KEY_HEADER: str = "X-API-Key"
    API_AUTH_ENABLED: bool = True  # Set to False to disable auth (dev mode)

    # CORS Settings
    CORS_ORIGINS: str = "http://localhost:3000"

    @property
    def valid_api_keys(self) -> set[str]:
        """Return set of valid API keys from configuration."""
        if not self.API_KEYS:
            return set()
        return {k.strip() for k in self.API_KEYS.split(",") if k.strip()}

    def is_auth_enabled(self) -> bool:
        """Check if authentication is enabled and configured."""
        return self.API_AUTH_ENABLED and len(self.valid_api_keys) > 0

    @property
    def cors_origins_list(self) -> list[str]:
        """Return list of allowed CORS origins."""
        if not self.CORS_ORIGINS:
            return []
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # Quality thresholds
    SCRIPT_QUALITY_THRESHOLD: float = 85.0  # Target threshold
    SCRIPT_QUALITY_FLOOR: float = 60.0      # Minimum acceptable score
    SCRIPT_MAX_ITERATIONS: int = 20

    def validate_service(self, service: str) -> ServiceStatus:
        """Validate if a service is properly configured.
        
        Args:
            service: Service name (zep, youtube, notion, freerouter)
            
        Returns:
            ServiceStatus indicating configuration state
            
        Raises:
            ValueError: If service name is unknown
        """
        validators = {
            "zep": self._validate_zep,
            "youtube": self._validate_youtube,
            "notion": self._validate_notion,
            "freerouter": self._validate_freerouter,
        }
        validator = validators.get(service.lower())
        if not validator:
            raise ValueError(f"Unknown service: {service}")
        return validator()

    def _validate_zep(self) -> ServiceStatus:
        """Validate Zep memory service configuration."""
        if not self.ZEP_API_KEY:
            return ServiceStatus.NOT_CONFIGURED
        return ServiceStatus.AVAILABLE

    def _validate_youtube(self) -> ServiceStatus:
        """Validate YouTube API configuration."""
        if not self.YOUTUBE_API_KEY:
            return ServiceStatus.NOT_CONFIGURED
        if len(self.YOUTUBE_API_KEY) < 20:
            return ServiceStatus.MISCONFIGURED
        return ServiceStatus.AVAILABLE

    def _validate_notion(self) -> ServiceStatus:
        """Validate Notion API configuration."""
        if not self.NOTION_API_KEY:
            return ServiceStatus.NOT_CONFIGURED
        if not self.NOTION_API_KEY.startswith("secret_"):
            return ServiceStatus.MISCONFIGURED
        return ServiceStatus.AVAILABLE

    def _validate_freerouter(self) -> ServiceStatus:
        """Validate FreeRouter proxy configuration."""
        if not self.FREEROUTER_URL:
            return ServiceStatus.NOT_CONFIGURED
        return ServiceStatus.AVAILABLE

    def get_service_status(self) -> dict[str, str]:
        """Get status of all services.
        
        Returns:
            Dict mapping service names to their status values
        """
        services = ["zep", "youtube", "notion", "freerouter"]
        return {s: self.validate_service(s).value for s in services}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings singleton. Call this everywhere."""
    return Settings()

"""
config.py — Centralised settings for the YouTube pipeline packages.

Context: Loads environment variables from the REPO ROOT .env file.
This is SEPARATE from freerouter/.env which holds provider API keys.
This file holds pipeline-specific config (Zep, YouTube, Notion, etc.)

P2-04: Added environment variable validation with clear error messages.

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
import re

from pydantic import field_validator, ValidationInfo
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceStatus(Enum):
    """Status of an external service configuration."""
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
    NOTION_DATABASE_ID: str = ""  # Database ID for script pages
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

    # ─── P2-04: Field Validators ───────────────────────────────────────────────

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate LOG_LEVEL is a valid Python logging level."""
        import logging
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper_v = v.upper()
        if upper_v not in valid_levels:
            raise ValueError(
                f"LOG_LEVEL must be one of {valid_levels}, got '{v}'. "
                f"Defaulting to INFO."
            )
        return upper_v

    @field_validator("FREEROUTER_URL")
    @classmethod
    def validate_freerouter_url(cls, v: str) -> str:
        """Validate FREEROUTER_URL is a valid HTTP/HTTPS URL."""
        if not v:
            raise ValueError("FREEROUTER_URL cannot be empty")
        if not v.startswith(("http://", "https://")):
            raise ValueError(
                f"FREEROUTER_URL must start with http:// or https://, got '{v}'"
            )
        return v.rstrip("/")

    @field_validator("ZEP_BASE_URL")
    @classmethod
    def validate_zep_base_url(cls, v: str) -> str:
        """Validate ZEP_BASE_URL is a valid HTTPS URL."""
        if not v:
            raise ValueError("ZEP_BASE_URL cannot be empty")
        if not v.startswith(("http://", "https://")):
            raise ValueError(
                f"ZEP_BASE_URL must start with http:// or https://, got '{v}'"
            )
        return v.rstrip("/")

    @field_validator("SCRIPT_QUALITY_THRESHOLD", "SCRIPT_QUALITY_FLOOR")
    @classmethod
    def validate_quality_threshold(cls, v: float, info: ValidationInfo) -> float:
        """Validate quality thresholds are within valid range."""
        if not 0 <= v <= 100:
            raise ValueError(
                f"{info.field_name} must be between 0 and 100, got {v}"
            )
        return v

    @field_validator("SCRIPT_MAX_ITERATIONS")
    @classmethod
    def validate_max_iterations(cls, v: int) -> int:
        """Validate max iterations is positive and reasonable."""
        if v < 1:
            raise ValueError(f"SCRIPT_MAX_ITERATIONS must be at least 1, got {v}")
        if v > 100:
            raise ValueError(
                f"SCRIPT_MAX_ITERATIONS should not exceed 100 (got {v}). "
                f"This may indicate a configuration error."
            )
        return v

    @field_validator("DATA_DIR")
    @classmethod
    def validate_data_dir(cls, v: str) -> str:
        """Validate DATA_DIR is not empty and is a valid path."""
        if not v:
            raise ValueError("DATA_DIR cannot be empty")
        # Check for invalid characters
        invalid_chars = ["<", ">", ":", '"', "|", "?", "*"]
        for char in invalid_chars:
            if char in v:
                raise ValueError(
                    f"DATA_DIR contains invalid character '{char}': {v}"
                )
        return v

    @field_validator("ZEP_AUDIENCE_USER_ID", "ZEP_LEARNING_USER_ID")
    @classmethod
    def validate_user_id(cls, v: str, info: ValidationInfo) -> str:
        """Validate Zep user IDs follow expected format."""
        if not v:
            raise ValueError(f"{info.field_name} cannot be empty")
        # User IDs should be alphanumeric with underscores
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError(
                f"{info.field_name} must contain only alphanumeric characters "
                f"and underscores, got '{v}'"
            )
        return v

    # ─── Existing Properties and Methods ───────────────────────────────────────

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

    # ─── Service Validation ──────────────────────────────────────────────────

    def validate_service(self, service: str) -> ServiceStatus:
        """Validate the configuration of a named service.

        Returns a ServiceStatus indicating whether the service is
        available, not configured, or misconfigured.
        """
        if service == "youtube":
            if not self.YOUTUBE_API_KEY:
                return ServiceStatus.NOT_CONFIGURED
            if len(self.YOUTUBE_API_KEY) < 20:
                return ServiceStatus.MISCONFIGURED
            return ServiceStatus.AVAILABLE

        if service == "notion":
            if not self.NOTION_API_KEY:
                return ServiceStatus.NOT_CONFIGURED
            if not self.NOTION_API_KEY.startswith("secret_"):
                return ServiceStatus.MISCONFIGURED
            return ServiceStatus.AVAILABLE

        if service == "zep":
            if not self.ZEP_API_KEY:
                return ServiceStatus.NOT_CONFIGURED
            return ServiceStatus.AVAILABLE

        if service == "freerouter":
            if not self.FREEROUTER_URL:
                return ServiceStatus.NOT_CONFIGURED
            return ServiceStatus.AVAILABLE

        raise ValueError(f"Unknown service: {service}")

    def get_service_status(self) -> dict[str, str]:
        """Return a dict mapping service names to their status value strings."""
        return {
            service: self.validate_service(service).value
            for service in ("zep", "youtube", "notion", "freerouter")
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings singleton. Call this everywhere."""
    return Settings()

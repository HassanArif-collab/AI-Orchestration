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


class ServiceStatus(str, Enum):
    """Status of external service configuration."""
    AVAILABLE = "available"
    NOT_CONFIGURED = "not_configured"
    MISCONFIGURED = "misconfigured"


class ConfigurationError(Exception):
    """Raised when configuration validation fails."""
    pass


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
        # Database ID is also required for full functionality
        if not self.NOTION_DATABASE_ID:
            return ServiceStatus.NOT_CONFIGURED
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

    def validate_all(self) -> list[str]:
        """Validate all configuration and return list of errors.

        P2-04: Provides comprehensive validation at startup.

        Returns:
            List of error messages (empty if all valid)
        """
        errors = []

        # Validate URL formats
        try:
            self.validate_freerouter_url(self.FREEROUTER_URL)
        except ValueError as e:
            errors.append(str(e))

        try:
            self.validate_zep_base_url(self.ZEP_BASE_URL)
        except ValueError as e:
            errors.append(str(e))

        # Validate log level
        try:
            self.validate_log_level(self.LOG_LEVEL)
        except ValueError as e:
            errors.append(str(e))

        # Validate quality thresholds
        if self.SCRIPT_QUALITY_FLOOR > self.SCRIPT_QUALITY_THRESHOLD:
            errors.append(
                f"SCRIPT_QUALITY_FLOOR ({self.SCRIPT_QUALITY_FLOOR}) cannot exceed "
                f"SCRIPT_QUALITY_THRESHOLD ({self.SCRIPT_QUALITY_THRESHOLD})"
            )

        # Validate max iterations
        try:
            self.validate_max_iterations(self.SCRIPT_MAX_ITERATIONS)
        except ValueError as e:
            errors.append(str(e))

        return errors


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings singleton. Call this everywhere."""
    return Settings()


def validate_startup_config() -> None:
    """Validate configuration at application startup.

    P2-04: Call this at application start to catch config errors early.

    Raises:
        ConfigurationError: If any configuration is invalid
    """
    settings = get_settings()
    errors = settings.validate_all()

    if errors:
        raise ConfigurationError(
            "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        )

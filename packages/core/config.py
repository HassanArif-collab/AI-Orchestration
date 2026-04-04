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

from pydantic import field_validator, model_validator, ValidationInfo
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
    # Fallback router URL used when primary FreeRouter is unreachable after all retries
    FALLBACK_ROUTER_URL: str = ""

    # ─── Supabase (V2 Storage Backend) ────────────────────────────────────────
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_DB_URL: str = ""  # Direct PostgreSQL connection string (session mode, port 5432)

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
    # Set to true to use mock data instead of real pipeline execution
    PIPELINE_DEV_MODE: bool = False

    # ─── LLM Model Selection ──────────────────────────────────────────────
    CHAT_MODEL: str = "auto"

    # External integrations
    YOUTUBE_API_KEY: str = ""
    YOUTUBE_CLIENT_ID: str = ""
    YOUTUBE_CLIENT_SECRET: str = ""
    YOUTUBE_REFRESH_TOKEN: str = ""
    NOTION_API_KEY: str = ""
    NOTION_DATABASE_ID: str = ""  # Database ID for script pages
    GITHUB_TOKEN: str = ""

    # ─── Exa.ai (AI-Native Web Search for Topic Discovery) ──────────────────
    EXA_API_KEY: str = ""

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

    # Escalation settings
    ESCALATION_ENABLED: bool = True
    ESCALATION_MIN_SCORE: float = 50.0
    ESCALATION_WEBHOOK_URL: str = ""
    ESCALATION_WEBHOOK_TYPE: str = "default"

    # Quality thresholds
    SCRIPT_QUALITY_THRESHOLD: float = 85.0  # Target threshold
    SCRIPT_QUALITY_FLOOR: float = 60.0      # Minimum acceptable score
    SCRIPT_MAX_ITERATIONS: int = 20
    SCRIPT_TARGET_PASS_COUNT: int = 32      # Minimum score threshold entries for full script

    # ─── Review/Approval SLA Configuration (Issue 6) ─────────────────────────
    HUMAN_REVIEW_TIMEOUT_HOURS: int = 24
    HUMAN_REVIEW_ESCALATION_EMAIL: str = ""
    RISK_TIER_LOW_SCORE: float = 85.0       # Auto-approve threshold
    RISK_TIER_HIGH_SCORE: float = 65.0      # High-risk threshold
    RISK_TIER_LOW_SLA_HOURS: int = 48
    RISK_TIER_MEDIUM_SLA_HOURS: int = 24
    RISK_TIER_HIGH_SLA_HOURS: int = 12

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

    @field_validator("SUPABASE_URL")
    @classmethod
    def validate_supabase_url(cls, v: str) -> str:
        """Validate SUPABASE_URL format if provided."""
        if v and not v.startswith("https://"):
            raise ValueError(
                f"SUPABASE_URL must start with https://, got '{v}'"
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

    @field_validator("ESCALATION_MIN_SCORE")
    @classmethod
    def validate_escalation_min_score(cls, v: float) -> float:
        """Validate escalation min score is in valid range."""
        if not 0 <= v <= 100:
            raise ValueError(
                f"ESCALATION_MIN_SCORE must be between 0 and 100, got {v}"
            )
        return v

    @field_validator("ESCALATION_WEBHOOK_TYPE")
    @classmethod
    def validate_escalation_webhook_type(cls, v: str) -> str:
        """Validate webhook type is a known value."""
        valid_types = {"default", "slack", "discord"}
        if v.lower() not in valid_types:
            raise ValueError(
                f"ESCALATION_WEBHOOK_TYPE must be one of {valid_types}, got '{v}'"
            )
        return v.lower()

    @model_validator(mode="after")
    def validate_threshold_order(self) -> "Settings":
        """Ensure SCRIPT_QUALITY_THRESHOLD >= SCRIPT_QUALITY_FLOOR."""
        if self.SCRIPT_QUALITY_THRESHOLD < self.SCRIPT_QUALITY_FLOOR:
            raise ValueError(
                f"SCRIPT_QUALITY_THRESHOLD ({self.SCRIPT_QUALITY_THRESHOLD}) must be "
                f">= SCRIPT_QUALITY_FLOOR ({self.SCRIPT_QUALITY_FLOOR}). "
                f"The target threshold cannot be lower than the minimum floor."
            )
        return self

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
            valid_prefixes = ("secret_", "ntn_")
            if not any(self.NOTION_API_KEY.startswith(p) for p in valid_prefixes):
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

        if service == "supabase":
            if not self.SUPABASE_URL or not self.SUPABASE_SERVICE_ROLE_KEY:
                return ServiceStatus.NOT_CONFIGURED
            if not self.SUPABASE_URL.startswith("https://"):
                return ServiceStatus.MISCONFIGURED
            return ServiceStatus.AVAILABLE

        if service == "exa":
            if not self.EXA_API_KEY:
                return ServiceStatus.NOT_CONFIGURED
            if len(self.EXA_API_KEY) < 10:
                return ServiceStatus.MISCONFIGURED
            return ServiceStatus.AVAILABLE

        raise ValueError(f"Unknown service: {service}")

    def get_service_status(self) -> dict[str, str]:
        """Return a dict mapping service names to their status value strings."""
        return {
            service: self.validate_service(service).value
            for service in ("zep", "youtube", "notion", "freerouter", "supabase", "exa")
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings singleton. Call this everywhere."""
    return Settings()

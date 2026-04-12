"""
test_config_comprehensive.py — Deep edge-case tests for packages/core/config.py.

Covers Settings creation without .env, field validators, service validation,
default sanity checks, immutability, and extra env var handling.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from packages.core.config import Settings, ServiceStatus


def _s(**overrides):
    """Shorthand for Settings(_env_file=None, **overrides)."""
    return Settings(_env_file=None, **overrides)


# ═══════════════════════════════════════════════════════════════════════
# Settings Defaults (no .env)
# ═══════════════════════════════════════════════════════════════════════

class TestSettingsDefaults:
    """Verify all defaults are sane when no .env is loaded."""

    def test_freerouter_url_default(self):
        """Default FREEROUTER_URL must be http://localhost:4000."""
        s = _s()
        assert s.FREEROUTER_URL == "http://localhost:4000"

    def test_freerouter_api_key_default(self):
        """Default FREEROUTER_API_KEY should be 'not-needed'."""
        s = _s()
        assert s.FREEROUTER_API_KEY == "not-needed"

    def test_empty_optional_keys_default_to_empty_string(self):
        """All optional API keys default to empty string (not None)."""
        s = _s()
        assert s.ZEP_API_KEY == ""
        assert s.NOTION_API_KEY == ""
        assert s.EXA_API_KEY == ""
        assert s.YOUTUBE_API_KEY == ""
        assert s.SUPABASE_URL == ""
        assert s.SUPABASE_ANON_KEY == ""
        assert s.SUPABASE_SERVICE_ROLE_KEY == ""

    def test_quality_threshold_defaults(self):
        """Quality threshold and floor have sensible defaults."""
        s = _s()
        assert 0 <= s.SCRIPT_QUALITY_THRESHOLD <= 100
        assert 0 <= s.SCRIPT_QUALITY_FLOOR <= 100
        assert s.SCRIPT_QUALITY_THRESHOLD >= s.SCRIPT_QUALITY_FLOOR

    def test_max_iterations_default(self):
        """Max iterations must be a positive integer."""
        s = _s()
        assert s.SCRIPT_MAX_ITERATIONS >= 1

    def test_log_level_default(self):
        """Default log level should be INFO (uppercased)."""
        s = _s()
        assert s.LOG_LEVEL == "INFO"

    def test_feature_flags_defaults(self):
        """Feature flags should have sensible defaults."""
        s = _s()
        assert isinstance(s.ASSET_CREATION_ENABLED, bool)
        assert isinstance(s.PUBLISH_ENABLED, bool)
        assert isinstance(s.PIPELINE_DEV_MODE, bool)
        assert isinstance(s.ESCALATION_ENABLED, bool)

    def test_chat_model_default(self):
        """CHAT_MODEL should default to a non-empty string."""
        s = _s()
        assert isinstance(s.CHAT_MODEL, str)
        assert len(s.CHAT_MODEL) > 0

    def test_data_dir_default(self):
        """DATA_DIR should default to 'packages/data'."""
        s = _s()
        assert s.DATA_DIR == "packages/data"

    def test_cors_origins_default(self):
        """CORS_ORIGINS should default to localhost:3000."""
        s = _s()
        assert "localhost:3000" in s.CORS_ORIGINS


# ═══════════════════════════════════════════════════════════════════════
# FREEROUTER_URL Validation
# ═══════════════════════════════════════════════════════════════════════

class TestFreerouterUrlValidation:
    """Tests for the FREEROUTER_URL field validator."""

    def test_http_url_accepted(self):
        """http:// URLs are valid."""
        s = _s(FREEROUTER_URL="http://example.com:4000")
        assert s.FREEROUTER_URL == "http://example.com:4000"

    def test_https_url_accepted(self):
        """https:// URLs are valid."""
        s = _s(FREEROUTER_URL="https://router.example.com")
        assert s.FREEROUTER_URL == "https://router.example.com"

    def test_trailing_slash_stripped(self):
        """Trailing slash is stripped from FREEROUTER_URL."""
        s = _s(FREEROUTER_URL="http://localhost:4000/")
        assert s.FREEROUTER_URL == "http://localhost:4000"

    def test_empty_url_rejected(self):
        """Empty FREEROUTER_URL raises ValidationError."""
        with pytest.raises(ValidationError):
            _s(FREEROUTER_URL="")

    def test_missing_scheme_rejected(self):
        """URL without http:// or https:// is rejected."""
        with pytest.raises(ValidationError):
            _s(FREEROUTER_URL="localhost:4000")

    def test_ftp_scheme_rejected(self):
        """Non-HTTP schemes are rejected."""
        with pytest.raises(ValidationError):
            _s(FREEROUTER_URL="ftp://localhost:4000")


# ═══════════════════════════════════════════════════════════════════════
# Notion API Key Validation
# ═══════════════════════════════════════════════════════════════════════

class TestNotionApiKeyValidation:
    """Tests for Notion API key validation via validate_service."""

    def test_valid_secret_prefix(self):
        """Notion key starting with 'secret_' is AVAILABLE."""
        s = _s(NOTION_API_KEY="secret_abc123def456")
        assert s.validate_service("notion") == ServiceStatus.AVAILABLE

    def test_valid_ntn_prefix(self):
        """Notion key starting with 'ntn_' is AVAILABLE."""
        s = _s(NOTION_API_KEY="ntn_abc123def456")
        assert s.validate_service("notion") == ServiceStatus.AVAILABLE

    def test_empty_key_not_configured(self):
        """Empty Notion key → NOT_CONFIGURED."""
        s = _s(NOTION_API_KEY="")
        assert s.validate_service("notion") == ServiceStatus.NOT_CONFIGURED

    def test_bad_prefix_misconfigured(self):
        """Notion key without secret_/ntn_ prefix → MISCONFIGURED."""
        s = _s(NOTION_API_KEY="invalid_key_123")
        assert s.validate_service("notion") == ServiceStatus.MISCONFIGURED


# ═══════════════════════════════════════════════════════════════════════
# Exa API Key Validation
# ═══════════════════════════════════════════════════════════════════════

class TestExaApiKeyValidation:
    """Tests for Exa API key validation via validate_service."""

    def test_valid_long_key(self):
        """Exa key with 10+ chars is AVAILABLE."""
        s = _s(EXA_API_KEY="a" * 20)
        assert s.validate_service("exa") == ServiceStatus.AVAILABLE

    def test_minimum_valid_key(self):
        """Exa key with exactly 10 chars is AVAILABLE (boundary)."""
        s = _s(EXA_API_KEY="a" * 10)
        assert s.validate_service("exa") == ServiceStatus.AVAILABLE

    def test_short_key_misconfigured(self):
        """Exa key shorter than 10 chars → MISCONFIGURED."""
        s = _s(EXA_API_KEY="short")
        assert s.validate_service("exa") == ServiceStatus.MISCONFIGURED

    def test_empty_key_not_configured(self):
        """Empty Exa key → NOT_CONFIGURED."""
        s = _s(EXA_API_KEY="")
        assert s.validate_service("exa") == ServiceStatus.NOT_CONFIGURED


# ═══════════════════════════════════════════════════════════════════════
# YouTube API Key Validation
# ═══════════════════════════════════════════════════════════════════════

class TestYouTubeApiKeyValidation:
    """Tests for YouTube API key validation via validate_service."""

    def test_valid_long_key(self):
        """YouTube key with 20+ chars is AVAILABLE."""
        s = _s(YOUTUBE_API_KEY="a" * 39)
        assert s.validate_service("youtube") == ServiceStatus.AVAILABLE

    def test_minimum_valid_key(self):
        """YouTube key with exactly 20 chars is AVAILABLE (boundary)."""
        s = _s(YOUTUBE_API_KEY="a" * 20)
        assert s.validate_service("youtube") == ServiceStatus.AVAILABLE

    def test_short_key_misconfigured(self):
        """YouTube key shorter than 20 chars → MISCONFIGURED."""
        s = _s(YOUTUBE_API_KEY="short_key")
        assert s.validate_service("youtube") == ServiceStatus.MISCONFIGURED

    def test_empty_key_not_configured(self):
        """Empty YouTube key → NOT_CONFIGURED."""
        s = _s(YOUTUBE_API_KEY="")
        assert s.validate_service("youtube") == ServiceStatus.NOT_CONFIGURED


# ═══════════════════════════════════════════════════════════════════════
# Supabase URL Validation
# ═══════════════════════════════════════════════════════════════════════

class TestSupabaseUrlValidation:
    """Tests for Supabase URL validation."""

    def test_valid_https_url_available(self):
        """Supabase https:// URL with service key → AVAILABLE."""
        s = _s(
            SUPABASE_URL="https://test.supabase.co",
            SUPABASE_SERVICE_ROLE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
        )
        assert s.validate_service("supabase") == ServiceStatus.AVAILABLE

    def test_http_url_misconfigured_via_validate_service(self):
        """validate_service checks for https:// prefix on Supabase URL.

        Note: The field validator already rejects http:// URLs at construction
        time, so this code path in validate_service is unreachable via normal
        Settings creation. We test the logic directly by verifying the
        field validator catches it first.
        """
        with pytest.raises(ValidationError):
            _s(
                SUPABASE_URL="http://localhost:54321",
                SUPABASE_SERVICE_ROLE_KEY="some-key",
            )

    def test_empty_url_not_configured(self):
        """Empty Supabase URL → NOT_CONFIGURED."""
        s = _s(SUPABASE_URL="", SUPABASE_SERVICE_ROLE_KEY="key")
        assert s.validate_service("supabase") == ServiceStatus.NOT_CONFIGURED

    def test_empty_service_key_not_configured(self):
        """Supabase URL set but no service key → NOT_CONFIGURED."""
        s = _s(
            SUPABASE_URL="https://test.supabase.co",
            SUPABASE_SERVICE_ROLE_KEY="",
        )
        assert s.validate_service("supabase") == ServiceStatus.NOT_CONFIGURED

    def test_trailing_slash_stripped(self):
        """Trailing slash is stripped from SUPABASE_URL."""
        s = _s(
            SUPABASE_URL="https://test.supabase.co/",
            SUPABASE_SERVICE_ROLE_KEY="key",
        )
        assert s.SUPABASE_URL == "https://test.supabase.co"

    def test_empty_supabase_url_passes_field_validator(self):
        """Empty SUPABASE_URL is allowed by field validator (only checked in validate_service)."""
        s = _s(SUPABASE_URL="")
        assert s.SUPABASE_URL == ""

    def test_http_supabase_rejected_by_field_validator(self):
        """SUPABASE_URL with http:// is rejected by the field validator."""
        with pytest.raises(ValidationError):
            _s(SUPABASE_URL="http://localhost:54321")


# ═══════════════════════════════════════════════════════════════════════
# validate_service for all services
# ═══════════════════════════════════════════════════════════════════════

class TestValidateServiceAllServices:
    """Tests for validate_service() covering all 6 known services."""

    def test_zep_available(self):
        """Zep with API key set → AVAILABLE."""
        s = _s(ZEP_API_KEY="test-zep-key")
        assert s.validate_service("zep") == ServiceStatus.AVAILABLE

    def test_zep_not_configured(self):
        """Zep without API key → NOT_CONFIGURED."""
        s = _s(ZEP_API_KEY="")
        assert s.validate_service("zep") == ServiceStatus.NOT_CONFIGURED

    def test_freerouter_available(self):
        """FreeRouter with URL set → AVAILABLE."""
        s = _s(FREEROUTER_URL="http://localhost:4000")
        assert s.validate_service("freerouter") == ServiceStatus.AVAILABLE

    def test_unknown_service_raises(self):
        """Unknown service name raises ValueError."""
        s = _s()
        with pytest.raises(ValueError, match="Unknown service"):
            s.validate_service("nonexistent_service")

    def test_get_service_status_returns_all_six(self):
        """get_service_status returns dict with all 6 services."""
        s = _s()
        status = s.get_service_status()
        assert set(status.keys()) == {"zep", "youtube", "notion",
                                      "freerouter", "supabase", "exa"}


# ═══════════════════════════════════════════════════════════════════════
# Extra/Unrecognized Environment Variables
# ═══════════════════════════════════════════════════════════════════════

class TestExtraEnvVars:
    """Tests that extra/unrecognized env vars don't cause errors."""

    def test_extra_fields_ignored(self):
        """Settings uses extra='ignore', so unknown fields are silently dropped."""
        s = _s(UNKNOWN_VAR="should_be_ignored", ANOTHER_RANDOM="123")
        assert not hasattr(s, "UNKNOWN_VAR")
        assert not hasattr(s, "ANOTHER_RANDOM")


# ═══════════════════════════════════════════════════════════════════════
# Settings Immutability / Frozen
# ═══════════════════════════════════════════════════════════════════════

class TestSettingsImmutability:
    """Tests that Settings behaves correctly as a pydantic model."""

    def test_settings_is_not_frozen_by_default(self):
        """pydantic-settings BaseSettings is not frozen by default.

        However, modifying settings after creation is generally discouraged.
        This test verifies the current behavior.
        """
        s = _s()
        # pydantic v2 allows attribute assignment unless frozen=True
        original_url = s.FREEROUTER_URL
        s.FREEROUTER_URL = "http://modified:9999"
        assert s.FREEROUTER_URL == "http://modified:9999"
        # Restore to avoid side effects
        s.FREEROUTER_URL = original_url

    def test_model_dump_works(self):
        """model_dump returns a dict representation."""
        s = _s()
        d = s.model_dump()
        assert isinstance(d, dict)
        assert "FREEROUTER_URL" in d

    def test_model_config_extra_ignore(self):
        """model_config has extra='ignore'."""
        s = Settings.__init__.__globals__.get("Settings", Settings)
        assert Settings.model_config.get("extra") == "ignore"


# ═══════════════════════════════════════════════════════════════════════
# Field Validators
# ═══════════════════════════════════════════════════════════════════════

class TestFieldValidators:
    """Tests for individual field validators."""

    def test_log_level_uppercased(self):
        """LOG_LEVEL is uppercased regardless of input case."""
        s = _s(LOG_LEVEL="debug")
        assert s.LOG_LEVEL == "DEBUG"

    def test_log_level_invalid_rejected(self):
        """Invalid LOG_LEVEL raises ValidationError."""
        with pytest.raises(ValidationError):
            _s(LOG_LEVEL="VERBOSE")

    def test_quality_threshold_range_min(self):
        """Quality threshold at 0 is valid."""
        s = _s(SCRIPT_QUALITY_THRESHOLD=0, SCRIPT_QUALITY_FLOOR=0)
        assert s.SCRIPT_QUALITY_THRESHOLD == 0

    def test_quality_threshold_range_max(self):
        """Quality threshold at 100 is valid."""
        s = _s(SCRIPT_QUALITY_THRESHOLD=100, SCRIPT_QUALITY_FLOOR=100)
        assert s.SCRIPT_QUALITY_THRESHOLD == 100

    def test_quality_threshold_negative_rejected(self):
        """Negative quality threshold raises ValidationError."""
        with pytest.raises(ValidationError):
            _s(SCRIPT_QUALITY_THRESHOLD=-1)

    def test_quality_threshold_over_100_rejected(self):
        """Quality threshold over 100 raises ValidationError."""
        with pytest.raises(ValidationError):
            _s(SCRIPT_QUALITY_THRESHOLD=101)

    def test_quality_floor_greater_than_threshold_rejected(self):
        """Floor > threshold raises ValidationError via model_validator."""
        with pytest.raises(ValidationError, match="threshold.*floor"):
            _s(SCRIPT_QUALITY_THRESHOLD=60, SCRIPT_QUALITY_FLOOR=85)

    def test_max_iterations_zero_rejected(self):
        """Max iterations of 0 raises ValidationError."""
        with pytest.raises(ValidationError):
            _s(SCRIPT_MAX_ITERATIONS=0)

    def test_max_iterations_over_100_rejected(self):
        """Max iterations over 100 raises ValidationError."""
        with pytest.raises(ValidationError):
            _s(SCRIPT_MAX_ITERATIONS=101)

    def test_data_dir_empty_rejected(self):
        """Empty DATA_DIR raises ValidationError."""
        with pytest.raises(ValidationError):
            _s(DATA_DIR="")

    def test_data_dir_invalid_chars_rejected(self):
        """DATA_DIR with invalid characters raises ValidationError."""
        with pytest.raises(ValidationError):
            _s(DATA_DIR="path<with>invalid")

    def test_zep_user_id_empty_rejected(self):
        """Empty ZEP_AUDIENCE_USER_ID raises ValidationError."""
        with pytest.raises(ValidationError):
            _s(ZEP_AUDIENCE_USER_ID="")

    def test_zep_user_id_special_chars_rejected(self):
        """ZEP_AUDIENCE_USER_ID with special chars raises ValidationError."""
        with pytest.raises(ValidationError):
            _s(ZEP_AUDIENCE_USER_ID="user-id!")

    def test_escalation_webhook_type_valid(self):
        """Valid escalation webhook types are accepted."""
        for t in ("default", "slack", "discord"):
            s = _s(ESCALATION_WEBHOOK_TYPE=t)
            assert s.ESCALATION_WEBHOOK_TYPE == t

    def test_escalation_webhook_type_invalid_rejected(self):
        """Invalid escalation webhook type raises ValidationError."""
        with pytest.raises(ValidationError):
            _s(ESCALATION_WEBHOOK_TYPE="teams")

    def test_escalation_webhook_type_case_insensitive(self):
        """Webhook type is lowercased."""
        s = _s(ESCALATION_WEBHOOK_TYPE="SLACK")
        assert s.ESCALATION_WEBHOOK_TYPE == "slack"

    def test_valid_api_keys_set(self):
        """valid_api_keys returns set of non-empty key strings."""
        s = _s(API_KEYS="key1, key2, key3")
        assert s.valid_api_keys == {"key1", "key2", "key3"}

    def test_empty_api_keys_empty_set(self):
        """Empty API_KEYS returns empty set."""
        s = _s(API_KEYS="")
        assert s.valid_api_keys == set()

    def test_auth_disabled_when_no_keys(self):
        """is_auth_enabled returns False when no keys configured."""
        s = _s(API_KEYS="", API_AUTH_ENABLED=True)
        assert s.is_auth_enabled() is False

    def test_auth_enabled_with_keys(self):
        """is_auth_enabled returns True when keys are configured."""
        s = _s(API_KEYS="test-key", API_AUTH_ENABLED=True)
        assert s.is_auth_enabled() is True

    def test_auth_disabled_explicitly(self):
        """is_auth_enabled returns False when auth is explicitly disabled."""
        s = _s(API_KEYS="test-key", API_AUTH_ENABLED=False)
        assert s.is_auth_enabled() is False

    def test_cors_origins_list_single(self):
        """Single CORS origin returns list of one."""
        s = _s(CORS_ORIGINS="http://localhost:3000")
        assert s.cors_origins_list == ["http://localhost:3000"]

    def test_cors_origins_list_multiple(self):
        """Multiple comma-separated CORS origins are parsed correctly."""
        s = _s(CORS_ORIGINS="http://a.com, http://b.com, http://c.com")
        assert s.cors_origins_list == ["http://a.com", "http://b.com", "http://c.com"]

    def test_cors_origins_list_empty(self):
        """Empty CORS_ORIGINS returns empty list."""
        s = _s(CORS_ORIGINS="")
        assert s.cors_origins_list == []

    def test_zep_base_url_must_start_with_http(self):
        """ZEP_BASE_URL must start with http:// or https://."""
        s = _s(ZEP_BASE_URL="https://api.getzep.com")
        assert s.ZEP_BASE_URL == "https://api.getzep.com"

    def test_zep_base_url_rejected_without_scheme(self):
        """ZEP_BASE_URL without http/https scheme raises ValidationError."""
        with pytest.raises(ValidationError):
            _s(ZEP_BASE_URL="api.getzep.com")

    def test_zep_base_url_empty_rejected(self):
        """Empty ZEP_BASE_URL raises ValidationError."""
        with pytest.raises(ValidationError):
            _s(ZEP_BASE_URL="")

    def test_zep_base_url_trailing_slash_stripped(self):
        """Trailing slash is stripped from ZEP_BASE_URL."""
        s = _s(ZEP_BASE_URL="https://api.getzep.com/")
        assert s.ZEP_BASE_URL == "https://api.getzep.com"

    def test_fallback_router_url_empty_allowed(self):
        """FALLBACK_ROUTER_URL defaults to empty string (optional)."""
        s = _s()
        assert s.FALLBACK_ROUTER_URL == ""

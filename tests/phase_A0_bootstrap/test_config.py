"""
test_config.py — Phase A.0: Tests for packages/core/config.py

Covers:
  - Settings class instantiation with defaults
  - Field validators (LOG_LEVEL, FREEROUTER_URL, SUPABASE_URL, etc.)
  - Model validators (threshold ordering)
  - ServiceStatus enum and validate_service()
  - get_service_status()
  - Properties: valid_api_keys, cors_origins_list, is_auth_enabled()
  - LRU-cached singleton behaviour of get_settings()
"""

import os
import pytest
from pydantic import ValidationError
from tests.phase_A0_bootstrap.conftest import make_settings


# ─── Clear the cached singleton before each test so env changes take effect ───

@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """Ensure each test gets a fresh Settings instance."""
    from packages.core.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ─── A0.1: Basic instantiation ────────────────────────────────────────────────

class TestSettingsInstantiation:
    """Verify Settings can be created with defaults and env overrides."""

    def test_default_freerouter_url(self):
        s = make_settings(FREEROUTER_URL="http://localhost:4000")
        assert s.FREEROUTER_URL == "http://localhost:4000"

    def test_default_zep_base_url(self):
        s = make_settings(FREEROUTER_URL="http://localhost:4000")
        assert s.ZEP_BASE_URL == "https://api.getzep.com"

    def test_default_zep_enabled_false(self):
        s = make_settings(FREEROUTER_URL="http://localhost:4000")
        assert s.ZEP_ENABLED is False

    def test_default_log_level(self):
        s = make_settings(FREEROUTER_URL="http://localhost:4000")
        # Default from the class definition
        assert s.LOG_LEVEL == "INFO"

    def test_default_feature_flags(self):
        s = make_settings(
            FREEROUTER_URL="http://localhost:4000",
            ASSET_CREATION_ENABLED=True,
            PUBLISH_ENABLED=True,
            PIPELINE_DEV_MODE=False,
        )
        assert s.ASSET_CREATION_ENABLED is True
        assert s.PUBLISH_ENABLED is True
        assert s.PIPELINE_DEV_MODE is False

    def test_default_quality_thresholds(self):
        s = make_settings(FREEROUTER_URL="http://localhost:4000")
        assert s.SCRIPT_QUALITY_THRESHOLD == 85.0
        assert s.SCRIPT_QUALITY_FLOOR == 60.0
        assert s.SCRIPT_MAX_ITERATIONS == 20


# ─── A0.2: Field validators ──────────────────────────────────────────────────

class TestFieldValidators:
    """Verify pydantic field validators reject bad input."""

    def test_log_level_valid_values(self):
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            s = make_settings(FREEROUTER_URL="http://localhost:4000", LOG_LEVEL=level)
            assert s.LOG_LEVEL == level

    def test_log_level_invalid_raises(self):
        with pytest.raises(ValidationError, match="LOG_LEVEL"):
            make_settings(FREEROUTER_URL="http://localhost:4000", LOG_LEVEL="VERBOSE")

    def test_log_level_case_insensitive(self):
        s = make_settings(FREEROUTER_URL="http://localhost:4000", LOG_LEVEL="warning")
        assert s.LOG_LEVEL == "WARNING"

    def test_freerouter_url_must_start_http(self):
        with pytest.raises(ValidationError, match="FREEROUTER_URL"):
            make_settings(FREEROUTER_URL="ftp://localhost:4000")

    def test_freerouter_url_trailing_slash_stripped(self):
        s = make_settings(FREEROUTER_URL="http://localhost:4000/")
        assert s.FREEROUTER_URL == "http://localhost:4000"

    def test_freerouter_url_empty_raises(self):
        with pytest.raises(ValidationError, match="FREEROUTER_URL"):
            make_settings(FREEROUTER_URL="")

    def test_supabase_url_must_start_https(self):
        with pytest.raises(ValidationError, match="SUPABASE_URL"):
            make_settings(FREEROUTER_URL="http://localhost:4000", SUPABASE_URL="http://bad.supabase.co")

    def test_supabase_url_empty_ok(self):
        """Empty SUPABASE_URL is allowed (service is optional)."""
        s = make_settings(FREEROUTER_URL="http://localhost:4000", SUPABASE_URL="")
        assert s.SUPABASE_URL == ""

    def test_zep_base_url_empty_raises(self):
        with pytest.raises(ValidationError, match="ZEP_BASE_URL"):
            make_settings(FREEROUTER_URL="http://localhost:4000", ZEP_BASE_URL="")

    def test_zep_base_url_http_ok(self):
        s = make_settings(FREEROUTER_URL="http://localhost:4000", ZEP_BASE_URL="http://localhost:8080")
        assert s.ZEP_BASE_URL == "http://localhost:8080"

    def test_quality_threshold_out_of_range(self):
        with pytest.raises(ValidationError, match="SCRIPT_QUALITY_THRESHOLD"):
            make_settings(FREEROUTER_URL="http://localhost:4000", SCRIPT_QUALITY_THRESHOLD=150)

    def test_quality_floor_negative(self):
        with pytest.raises(ValidationError, match="SCRIPT_QUALITY_FLOOR"):
            make_settings(FREEROUTER_URL="http://localhost:4000", SCRIPT_QUALITY_FLOOR=-5)

    def test_max_iterations_zero_raises(self):
        with pytest.raises(ValidationError, match="SCRIPT_MAX_ITERATIONS"):
            make_settings(FREEROUTER_URL="http://localhost:4000", SCRIPT_MAX_ITERATIONS=0)

    def test_max_iterations_over_100_warns(self):
        with pytest.raises(ValidationError, match="SCRIPT_MAX_ITERATIONS"):
            make_settings(FREEROUTER_URL="http://localhost:4000", SCRIPT_MAX_ITERATIONS=150)

    def test_data_dir_empty_raises(self):
        with pytest.raises(ValidationError, match="DATA_DIR"):
            make_settings(FREEROUTER_URL="http://localhost:4000", DATA_DIR="")

    def test_data_dir_invalid_chars(self):
        with pytest.raises(ValidationError, match="DATA_DIR"):
            make_settings(FREEROUTER_URL="http://localhost:4000", DATA_DIR="data<bad>")

    def test_zep_user_id_empty_raises(self):
        with pytest.raises(ValidationError, match="ZEP_AUDIENCE_USER_ID"):
            make_settings(FREEROUTER_URL="http://localhost:4000", ZEP_AUDIENCE_USER_ID="")

    def test_zep_user_id_special_chars_raises(self):
        with pytest.raises(ValidationError, match="ZEP_AUDIENCE_USER_ID"):
            make_settings(FREEROUTER_URL="http://localhost:4000", ZEP_AUDIENCE_USER_ID="user@123!")

    def test_zep_user_id_valid(self):
        s = make_settings(FREEROUTER_URL="http://localhost:4000", ZEP_AUDIENCE_USER_ID="user_v2_final")
        assert s.ZEP_AUDIENCE_USER_ID == "user_v2_final"

    def test_escalation_min_score_range(self):
        with pytest.raises(ValidationError, match="ESCALATION_MIN_SCORE"):
            make_settings(FREEROUTER_URL="http://localhost:4000", ESCALATION_MIN_SCORE=200)

    def test_escalation_webhook_type_invalid(self):
        with pytest.raises(ValidationError, match="ESCALATION_WEBHOOK_TYPE"):
            make_settings(FREEROUTER_URL="http://localhost:4000", ESCALATION_WEBHOOK_TYPE="telegram")

    def test_escalation_webhook_type_valid(self):
        for wt in ["default", "slack", "discord"]:
            s = make_settings(FREEROUTER_URL="http://localhost:4000", ESCALATION_WEBHOOK_TYPE=wt)
            assert s.ESCALATION_WEBHOOK_TYPE == wt


# ─── A0.3: Model validators ──────────────────────────────────────────────────

class TestModelValidators:
    """Verify cross-field validators."""

    def test_threshold_order_valid(self):
        """threshold >= floor should pass."""
        s = make_settings(
            FREEROUTER_URL="http://localhost:4000",
            SCRIPT_QUALITY_THRESHOLD=85, SCRIPT_QUALITY_FLOOR=60,
        )
        assert s.SCRIPT_QUALITY_THRESHOLD >= s.SCRIPT_QUALITY_FLOOR

    def test_threshold_order_invalid(self):
        """threshold < floor should fail."""
        with pytest.raises(ValidationError, match="SCRIPT_QUALITY_THRESHOLD"):
            make_settings(
                FREEROUTER_URL="http://localhost:4000",
                SCRIPT_QUALITY_THRESHOLD=50, SCRIPT_QUALITY_FLOOR=60,
            )

    def test_threshold_equal_ok(self):
        """threshold == floor is acceptable."""
        s = make_settings(
            FREEROUTER_URL="http://localhost:4000",
            SCRIPT_QUALITY_THRESHOLD=70, SCRIPT_QUALITY_FLOOR=70,
        )
        assert s.SCRIPT_QUALITY_THRESHOLD == s.SCRIPT_QUALITY_FLOOR


# ─── A0.4: ServiceStatus enum and validate_service ───────────────────────────

class TestServiceValidation:
    """Test the validate_service() method and ServiceStatus enum."""

    def test_service_status_enum_values(self):
        from packages.core.config import ServiceStatus
        assert ServiceStatus.AVAILABLE.value == "available"
        assert ServiceStatus.NOT_CONFIGURED.value == "not_configured"
        assert ServiceStatus.MISCONFIGURED.value == "misconfigured"

    def test_youtube_not_configured(self):
        s = make_settings(FREEROUTER_URL="http://localhost:4000", YOUTUBE_API_KEY="")
        status = s.validate_service("youtube")
        assert status.value == "not_configured"

    def test_youtube_misconfigured_short_key(self):
        s = make_settings(FREEROUTER_URL="http://localhost:4000", YOUTUBE_API_KEY="short")
        status = s.validate_service("youtube")
        assert status.value == "misconfigured"

    def test_youtube_available(self):
        s = make_settings(FREEROUTER_URL="http://localhost:4000", YOUTUBE_API_KEY="AIzaSy" + "x" * 30)
        status = s.validate_service("youtube")
        assert status.value == "available"

    def test_notion_not_configured(self):
        s = make_settings(FREEROUTER_URL="http://localhost:4000", NOTION_API_KEY="")
        status = s.validate_service("notion")
        assert status.value == "not_configured"

    def test_notion_misconfigured_bad_prefix(self):
        s = make_settings(FREEROUTER_URL="http://localhost:4000", NOTION_API_KEY="invalid_prefix_key")
        status = s.validate_service("notion")
        assert status.value == "misconfigured"

    def test_notion_available_secret_prefix(self):
        s = make_settings(FREEROUTER_URL="http://localhost:4000", NOTION_API_KEY="secret_abc123")
        status = s.validate_service("notion")
        assert status.value == "available"

    def test_notion_available_ntn_prefix(self):
        s = make_settings(FREEROUTER_URL="http://localhost:4000", NOTION_API_KEY="ntn_abc123")
        status = s.validate_service("notion")
        assert status.value == "available"

    def test_zep_not_configured(self):
        s = make_settings(FREEROUTER_URL="http://localhost:4000", ZEP_API_KEY="")
        status = s.validate_service("zep")
        assert status.value == "not_configured"

    def test_zep_available(self):
        s = make_settings(FREEROUTER_URL="http://localhost:4000", ZEP_API_KEY="zep_key_12345")
        status = s.validate_service("zep")
        assert status.value == "available"

    def test_freerouter_available(self):
        s = make_settings(FREEROUTER_URL="http://localhost:4000")
        status = s.validate_service("freerouter")
        assert status.value == "available"

    def test_supabase_not_configured(self):
        s = make_settings(FREEROUTER_URL="http://localhost:4000", SUPABASE_URL="", SUPABASE_SERVICE_ROLE_KEY="")
        status = s.validate_service("supabase")
        assert status.value == "not_configured"

    def test_supabase_misconfigured_http(self):
        """http:// URLs are rejected by the field validator, never reaching validate_service."""
        with pytest.raises(ValidationError, match="SUPABASE_URL"):
            make_settings(
                FREEROUTER_URL="http://localhost:4000",
                SUPABASE_URL="http://supabase.co",
                SUPABASE_SERVICE_ROLE_KEY="some_key",
            )

    def test_supabase_available(self):
        s = make_settings(
            FREEROUTER_URL="http://localhost:4000",
            SUPABASE_URL="https://abc.supabase.co",
            SUPABASE_SERVICE_ROLE_KEY="eyJhbGci" + "x" * 30,
        )
        status = s.validate_service("supabase")
        assert status.value == "available"

    def test_exa_not_configured(self):
        s = make_settings(FREEROUTER_URL="http://localhost:4000", EXA_API_KEY="")
        status = s.validate_service("exa")
        assert status.value == "not_configured"

    def test_exa_misconfigured_short_key(self):
        s = make_settings(FREEROUTER_URL="http://localhost:4000", EXA_API_KEY="abc")
        status = s.validate_service("exa")
        assert status.value == "misconfigured"

    def test_exa_available(self):
        s = make_settings(FREEROUTER_URL="http://localhost:4000", EXA_API_KEY="exa_key_1234567890")
        status = s.validate_service("exa")
        assert status.value == "available"

    def test_unknown_service_raises(self):
        s = make_settings(FREEROUTER_URL="http://localhost:4000")
        with pytest.raises(ValueError, match="Unknown service"):
            s.validate_service("nonexistent")

    def test_get_service_status_returns_all(self):
        s = make_settings(FREEROUTER_URL="http://localhost:4000")
        status = s.get_service_status()
        assert isinstance(status, dict)
        expected_services = ("zep", "youtube", "notion", "freerouter", "supabase", "exa")
        for svc in expected_services:
            assert svc in status, f"Missing service: {svc}"
            assert status[svc] in ("available", "not_configured", "misconfigured")


# ─── A0.5: Properties ─────────────────────────────────────────────────────────

class TestSettingsProperties:
    """Test computed properties on Settings."""

    def test_valid_api_keys_empty(self):
        s = make_settings(FREEROUTER_URL="http://localhost:4000", API_KEYS="")
        assert s.valid_api_keys == set()

    def test_valid_api_keys_parsing(self):
        s = make_settings(FREEROUTER_URL="http://localhost:4000", API_KEYS="key1, key2 , key3")
        assert s.valid_api_keys == {"key1", "key2", "key3"}

    def test_cors_origins_empty(self):
        s = make_settings(FREEROUTER_URL="http://localhost:4000", CORS_ORIGINS="")
        assert s.cors_origins_list == []

    def test_cors_origins_parsing(self):
        s = make_settings(FREEROUTER_URL="http://localhost:4000", CORS_ORIGINS="http://a.com,http://b.com")
        assert s.cors_origins_list == ["http://a.com", "http://b.com"]

    def test_is_auth_enabled_false_when_disabled(self):
        s = make_settings(FREEROUTER_URL="http://localhost:4000", API_AUTH_ENABLED=False, API_KEYS="my-key")
        assert s.is_auth_enabled() is False

    def test_is_auth_enabled_false_when_no_keys(self):
        s = make_settings(FREEROUTER_URL="http://localhost:4000", API_AUTH_ENABLED=True, API_KEYS="")
        assert s.is_auth_enabled() is False

    def test_is_auth_enabled_true(self):
        s = make_settings(FREEROUTER_URL="http://localhost:4000", API_AUTH_ENABLED=True, API_KEYS="my-key")
        assert s.is_auth_enabled() is True


# ─── A0.6: Singleton behaviour ───────────────────────────────────────────────

class TestGetSettingsSingleton:
    """Verify get_settings() is cached as a singleton."""

    def test_same_instance_returned(self):
        from packages.core.config import get_settings
        get_settings.cache_clear()
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_cache_clear_returns_new_instance(self):
        from packages.core.config import get_settings
        get_settings.cache_clear()
        s1 = get_settings()
        get_settings.cache_clear()
        s2 = get_settings()
        # Should be a new instance (different object)
        assert s1 is not s2

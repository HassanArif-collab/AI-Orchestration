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

    def test_default_freerouter_url(self, monkeypatch):
        monkeypatch.setenv("FREEROUTER_URL", "http://localhost:4000")
        from packages.core.config import Settings
        s = Settings()
        assert s.FREEROUTER_URL == "http://localhost:4000"

    def test_default_zep_base_url(self, monkeypatch):
        monkeypatch.setenv("FREEROUTER_URL", "http://localhost:4000")
        from packages.core.config import Settings
        s = Settings()
        assert s.ZEP_BASE_URL == "https://api.getzep.com"

    def test_default_zep_enabled_false(self, monkeypatch):
        monkeypatch.setenv("FREEROUTER_URL", "http://localhost:4000")
        from packages.core.config import Settings
        s = Settings()
        assert s.ZEP_ENABLED is False

    def test_default_log_level(self, monkeypatch):
        monkeypatch.setenv("FREEROUTER_URL", "http://localhost:4000")
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        from packages.core.config import Settings
        s = Settings()
        # Default from the class definition
        assert s.LOG_LEVEL == "INFO"

    def test_default_feature_flags(self, monkeypatch):
        monkeypatch.setenv("FREEROUTER_URL", "http://localhost:4000")
        from packages.core.config import Settings
        s = Settings()
        assert s.ASSET_CREATION_ENABLED is True
        assert s.PUBLISH_ENABLED is True
        assert s.PIPELINE_DEV_MODE is False

    def test_default_quality_thresholds(self, monkeypatch):
        monkeypatch.setenv("FREEROUTER_URL", "http://localhost:4000")
        from packages.core.config import Settings
        s = Settings()
        assert s.SCRIPT_QUALITY_THRESHOLD == 85.0
        assert s.SCRIPT_QUALITY_FLOOR == 60.0
        assert s.SCRIPT_MAX_ITERATIONS == 20


# ─── A0.2: Field validators ──────────────────────────────────────────────────

class TestFieldValidators:
    """Verify pydantic field validators reject bad input."""

    def test_log_level_valid_values(self, monkeypatch):
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            monkeypatch.setenv("LOG_LEVEL", level)
            from packages.core.config import Settings
            s = Settings()
            assert s.LOG_LEVEL == level

    def test_log_level_invalid_raises(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "VERBOSE")
        from packages.core.config import Settings
        with pytest.raises(ValidationError, match="LOG_LEVEL"):
            Settings()

    def test_log_level_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "warning")
        from packages.core.config import Settings
        s = Settings()
        assert s.LOG_LEVEL == "WARNING"

    def test_freerouter_url_must_start_http(self, monkeypatch):
        monkeypatch.setenv("FREEROUTER_URL", "ftp://localhost:4000")
        from packages.core.config import Settings
        with pytest.raises(ValidationError, match="FREEROUTER_URL"):
            Settings()

    def test_freerouter_url_trailing_slash_stripped(self, monkeypatch):
        monkeypatch.setenv("FREEROUTER_URL", "http://localhost:4000/")
        from packages.core.config import Settings
        s = Settings()
        assert s.FREEROUTER_URL == "http://localhost:4000"

    def test_freerouter_url_empty_raises(self, monkeypatch):
        monkeypatch.delenv("FREEROUTER_URL", raising=False)
        from packages.core.config import Settings
        # Has a default so shouldn't raise — but empty string should
        monkeypatch.setenv("FREEROUTER_URL", "")
        with pytest.raises(ValidationError, match="FREEROUTER_URL"):
            Settings()

    def test_supabase_url_must_start_https(self, monkeypatch):
        monkeypatch.setenv("SUPABASE_URL", "http://bad.supabase.co")
        from packages.core.config import Settings
        with pytest.raises(ValidationError, match="SUPABASE_URL"):
            Settings()

    def test_supabase_url_empty_ok(self, monkeypatch):
        """Empty SUPABASE_URL is allowed (service is optional)."""
        monkeypatch.setenv("SUPABASE_URL", "")
        from packages.core.config import Settings
        s = Settings()
        assert s.SUPABASE_URL == ""

    def test_zep_base_url_empty_raises(self, monkeypatch):
        monkeypatch.setenv("ZEP_BASE_URL", "")
        from packages.core.config import Settings
        with pytest.raises(ValidationError, match="ZEP_BASE_URL"):
            Settings()

    def test_zep_base_url_http_ok(self, monkeypatch):
        monkeypatch.setenv("ZEP_BASE_URL", "http://localhost:8080")
        from packages.core.config import Settings
        s = Settings()
        assert s.ZEP_BASE_URL == "http://localhost:8080"

    def test_quality_threshold_out_of_range(self, monkeypatch):
        monkeypatch.setenv("SCRIPT_QUALITY_THRESHOLD", "150")
        from packages.core.config import Settings
        with pytest.raises(ValidationError, match="SCRIPT_QUALITY_THRESHOLD"):
            Settings()

    def test_quality_floor_negative(self, monkeypatch):
        monkeypatch.setenv("SCRIPT_QUALITY_FLOOR", "-5")
        from packages.core.config import Settings
        with pytest.raises(ValidationError, match="SCRIPT_QUALITY_FLOOR"):
            Settings()

    def test_max_iterations_zero_raises(self, monkeypatch):
        monkeypatch.setenv("SCRIPT_MAX_ITERATIONS", "0")
        from packages.core.config import Settings
        with pytest.raises(ValidationError, match="SCRIPT_MAX_ITERATIONS"):
            Settings()

    def test_max_iterations_over_100_warns(self, monkeypatch):
        monkeypatch.setenv("SCRIPT_MAX_ITERATIONS", "150")
        from packages.core.config import Settings
        with pytest.raises(ValidationError, match="SCRIPT_MAX_ITERATIONS"):
            Settings()

    def test_data_dir_empty_raises(self, monkeypatch):
        monkeypatch.setenv("DATA_DIR", "")
        from packages.core.config import Settings
        with pytest.raises(ValidationError, match="DATA_DIR"):
            Settings()

    def test_data_dir_invalid_chars(self, monkeypatch):
        monkeypatch.setenv("DATA_DIR", "data<bad>")
        from packages.core.config import Settings
        with pytest.raises(ValidationError, match="DATA_DIR"):
            Settings()

    def test_zep_user_id_empty_raises(self, monkeypatch):
        monkeypatch.setenv("ZEP_AUDIENCE_USER_ID", "")
        from packages.core.config import Settings
        with pytest.raises(ValidationError, match="ZEP_AUDIENCE_USER_ID"):
            Settings()

    def test_zep_user_id_special_chars_raises(self, monkeypatch):
        monkeypatch.setenv("ZEP_AUDIENCE_USER_ID", "user@123!")
        from packages.core.config import Settings
        with pytest.raises(ValidationError, match="ZEP_AUDIENCE_USER_ID"):
            Settings()

    def test_zep_user_id_valid(self, monkeypatch):
        monkeypatch.setenv("ZEP_AUDIENCE_USER_ID", "user_v2_final")
        from packages.core.config import Settings
        s = Settings()
        assert s.ZEP_AUDIENCE_USER_ID == "user_v2_final"

    def test_escalation_min_score_range(self, monkeypatch):
        monkeypatch.setenv("ESCALATION_MIN_SCORE", "200")
        from packages.core.config import Settings
        with pytest.raises(ValidationError, match="ESCALATION_MIN_SCORE"):
            Settings()

    def test_escalation_webhook_type_invalid(self, monkeypatch):
        monkeypatch.setenv("ESCALATION_WEBHOOK_TYPE", "telegram")
        from packages.core.config import Settings
        with pytest.raises(ValidationError, match="ESCALATION_WEBHOOK_TYPE"):
            Settings()

    def test_escalation_webhook_type_valid(self, monkeypatch):
        for wt in ["default", "slack", "discord"]:
            monkeypatch.setenv("ESCALATION_WEBHOOK_TYPE", wt)
            from packages.core.config import Settings
            s = Settings()
            assert s.ESCALATION_WEBHOOK_TYPE == wt


# ─── A0.3: Model validators ──────────────────────────────────────────────────

class TestModelValidators:
    """Verify cross-field validators."""

    def test_threshold_order_valid(self, monkeypatch):
        """threshold >= floor should pass."""
        monkeypatch.setenv("SCRIPT_QUALITY_THRESHOLD", "85")
        monkeypatch.setenv("SCRIPT_QUALITY_FLOOR", "60")
        from packages.core.config import Settings
        s = Settings()
        assert s.SCRIPT_QUALITY_THRESHOLD >= s.SCRIPT_QUALITY_FLOOR

    def test_threshold_order_invalid(self, monkeypatch):
        """threshold < floor should fail."""
        monkeypatch.setenv("SCRIPT_QUALITY_THRESHOLD", "50")
        monkeypatch.setenv("SCRIPT_QUALITY_FLOOR", "60")
        from packages.core.config import Settings
        with pytest.raises(ValidationError, match="SCRIPT_QUALITY_THRESHOLD"):
            Settings()

    def test_threshold_equal_ok(self, monkeypatch):
        """threshold == floor is acceptable."""
        monkeypatch.setenv("SCRIPT_QUALITY_THRESHOLD", "70")
        monkeypatch.setenv("SCRIPT_QUALITY_FLOOR", "70")
        from packages.core.config import Settings
        s = Settings()
        assert s.SCRIPT_QUALITY_THRESHOLD == s.SCRIPT_QUALITY_FLOOR


# ─── A0.4: ServiceStatus enum and validate_service ───────────────────────────

class TestServiceValidation:
    """Test the validate_service() method and ServiceStatus enum."""

    def test_service_status_enum_values(self):
        from packages.core.config import ServiceStatus
        assert ServiceStatus.AVAILABLE.value == "available"
        assert ServiceStatus.NOT_CONFIGURED.value == "not_configured"
        assert ServiceStatus.MISCONFIGURED.value == "misconfigured"

    def test_youtube_not_configured(self, settings_env):
        settings_env.unset("YOUTUBE_API_KEY")
        settings_env.clear_settings_cache()
        from packages.core.config import Settings
        s = Settings()
        status = s.validate_service("youtube")
        assert status == s.__class__.__annotations__.get("youtube", None) or True
        assert status.value == "not_configured"

    def test_youtube_misconfigured_short_key(self, settings_env):
        settings_env.set("YOUTUBE_API_KEY", "short")
        settings_env.clear_settings_cache()
        from packages.core.config import Settings
        s = Settings()
        status = s.validate_service("youtube")
        assert status.value == "misconfigured"

    def test_youtube_available(self, settings_env):
        settings_env.set("YOUTUBE_API_KEY", "AIzaSy" + "x" * 30)
        settings_env.clear_settings_cache()
        from packages.core.config import Settings
        s = Settings()
        status = s.validate_service("youtube")
        assert status.value == "available"

    def test_notion_not_configured(self, settings_env):
        settings_env.unset("NOTION_API_KEY")
        settings_env.clear_settings_cache()
        from packages.core.config import Settings
        s = Settings()
        status = s.validate_service("notion")
        assert status.value == "not_configured"

    def test_notion_misconfigured_bad_prefix(self, settings_env):
        settings_env.set("NOTION_API_KEY", "invalid_prefix_key")
        settings_env.clear_settings_cache()
        from packages.core.config import Settings
        s = Settings()
        status = s.validate_service("notion")
        assert status.value == "misconfigured"

    def test_notion_available_secret_prefix(self, settings_env):
        settings_env.set("NOTION_API_KEY", "secret_abc123")
        settings_env.clear_settings_cache()
        from packages.core.config import Settings
        s = Settings()
        status = s.validate_service("notion")
        assert status.value == "available"

    def test_notion_available_ntn_prefix(self, settings_env):
        settings_env.set("NOTION_API_KEY", "ntn_abc123")
        settings_env.clear_settings_cache()
        from packages.core.config import Settings
        s = Settings()
        status = s.validate_service("notion")
        assert status.value == "available"

    def test_zep_not_configured(self, settings_env):
        settings_env.unset("ZEP_API_KEY")
        settings_env.clear_settings_cache()
        from packages.core.config import Settings
        s = Settings()
        status = s.validate_service("zep")
        assert status.value == "not_configured"

    def test_zep_available(self, settings_env):
        settings_env.set("ZEP_API_KEY", "zep_key_12345")
        settings_env.clear_settings_cache()
        from packages.core.config import Settings
        s = Settings()
        status = s.validate_service("zep")
        assert status.value == "available"

    def test_freerouter_available(self, settings_env):
        settings_env.set("FREEROUTER_URL", "http://localhost:4000")
        settings_env.clear_settings_cache()
        from packages.core.config import Settings
        s = Settings()
        status = s.validate_service("freerouter")
        assert status.value == "available"

    def test_supabase_not_configured(self, settings_env):
        settings_env.unset("SUPABASE_URL")
        settings_env.unset("SUPABASE_SERVICE_ROLE_KEY")
        settings_env.clear_settings_cache()
        from packages.core.config import Settings
        s = Settings()
        status = s.validate_service("supabase")
        assert status.value == "not_configured"

    def test_supabase_misconfigured_http(self, settings_env):
        settings_env.set("SUPABASE_URL", "http://supabase.co")
        settings_env.set("SUPABASE_SERVICE_ROLE_KEY", "some_key")
        settings_env.clear_settings_cache()
        from packages.core.config import Settings
        s = Settings()
        status = s.validate_service("supabase")
        assert status.value == "misconfigured"

    def test_supabase_available(self, settings_env):
        settings_env.set("SUPABASE_URL", "https://abc.supabase.co")
        settings_env.set("SUPABASE_SERVICE_ROLE_KEY", "eyJhbGci" + "x" * 30)
        settings_env.clear_settings_cache()
        from packages.core.config import Settings
        s = Settings()
        status = s.validate_service("supabase")
        assert status.value == "available"

    def test_exa_not_configured(self, settings_env):
        settings_env.unset("EXA_API_KEY")
        settings_env.clear_settings_cache()
        from packages.core.config import Settings
        s = Settings()
        status = s.validate_service("exa")
        assert status.value == "not_configured"

    def test_exa_misconfigured_short_key(self, settings_env):
        settings_env.set("EXA_API_KEY", "abc")
        settings_env.clear_settings_cache()
        from packages.core.config import Settings
        s = Settings()
        status = s.validate_service("exa")
        assert status.value == "misconfigured"

    def test_exa_available(self, settings_env):
        settings_env.set("EXA_API_KEY", "exa_key_1234567890")
        settings_env.clear_settings_cache()
        from packages.core.config import Settings
        s = Settings()
        status = s.validate_service("exa")
        assert status.value == "available"

    def test_unknown_service_raises(self, settings_env):
        settings_env.clear_settings_cache()
        from packages.core.config import Settings
        s = Settings()
        with pytest.raises(ValueError, match="Unknown service"):
            s.validate_service("nonexistent")

    def test_get_service_status_returns_all(self, settings_env):
        settings_env.clear_settings_cache()
        from packages.core.config import Settings
        s = Settings()
        status = s.get_service_status()
        assert isinstance(status, dict)
        expected_services = ("zep", "youtube", "notion", "freerouter", "supabase", "exa")
        for svc in expected_services:
            assert svc in status, f"Missing service: {svc}"
            assert status[svc] in ("available", "not_configured", "misconfigured")


# ─── A0.5: Properties ─────────────────────────────────────────────────────────

class TestSettingsProperties:
    """Test computed properties on Settings."""

    def test_valid_api_keys_empty(self, monkeypatch):
        monkeypatch.setenv("API_KEYS", "")
        from packages.core.config import Settings
        s = Settings()
        assert s.valid_api_keys == set()

    def test_valid_api_keys_parsing(self, monkeypatch):
        monkeypatch.setenv("API_KEYS", "key1, key2 , key3")
        from packages.core.config import Settings
        s = Settings()
        assert s.valid_api_keys == {"key1", "key2", "key3"}

    def test_cors_origins_empty(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", "")
        from packages.core.config import Settings
        s = Settings()
        assert s.cors_origins_list == []

    def test_cors_origins_parsing(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", "http://a.com,http://b.com")
        from packages.core.config import Settings
        s = Settings()
        assert s.cors_origins_list == ["http://a.com", "http://b.com"]

    def test_is_auth_enabled_false_when_disabled(self, monkeypatch):
        monkeypatch.setenv("API_AUTH_ENABLED", "false")
        monkeypatch.setenv("API_KEYS", "my-key")
        from packages.core.config import Settings
        s = Settings()
        assert s.is_auth_enabled() is False

    def test_is_auth_enabled_false_when_no_keys(self, monkeypatch):
        monkeypatch.setenv("API_AUTH_ENABLED", "true")
        monkeypatch.setenv("API_KEYS", "")
        from packages.core.config import Settings
        s = Settings()
        assert s.is_auth_enabled() is False

    def test_is_auth_enabled_true(self, monkeypatch):
        monkeypatch.setenv("API_AUTH_ENABLED", "true")
        monkeypatch.setenv("API_KEYS", "my-key")
        from packages.core.config import Settings
        s = Settings()
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

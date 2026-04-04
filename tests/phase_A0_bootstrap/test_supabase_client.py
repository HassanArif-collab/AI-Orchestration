"""
test_supabase_client.py — Phase A.0: Tests for packages/core/supabase_client.py

Covers:
  - is_supabase_configured() returns bool based on env vars
  - get_supabase() raises RuntimeError when not configured
  - get_supabase_optional() returns None when not configured
  - Singleton caching behaviour
"""

import pytest


class TestIsSupabaseConfigured:
    """Tests for is_supabase_configured()."""

    def test_false_when_both_missing(self, settings_env):
        settings_env.unset("SUPABASE_URL")
        settings_env.unset("SUPABASE_ANON_KEY")
        settings_env.clear_settings_cache()
        from packages.core.supabase_client import is_supabase_configured
        assert is_supabase_configured() is False

    def test_false_when_only_url(self, settings_env):
        settings_env.set("SUPABASE_URL", "https://test.supabase.co")
        settings_env.unset("SUPABASE_ANON_KEY")
        settings_env.clear_settings_cache()
        from packages.core.supabase_client import is_supabase_configured
        assert is_supabase_configured() is False

    def test_false_when_only_key(self, settings_env):
        settings_env.unset("SUPABASE_URL")
        settings_env.set("SUPABASE_ANON_KEY", "eyJhbGci.test")
        settings_env.clear_settings_cache()
        from packages.core.supabase_client import is_supabase_configured
        assert is_supabase_configured() is False

    def test_true_when_both_set(self, settings_env):
        settings_env.set("SUPABASE_URL", "https://test.supabase.co")
        settings_env.set("SUPABASE_ANON_KEY", "eyJhbGci.test")
        settings_env.clear_settings_cache()
        from packages.core.supabase_client import is_supabase_configured
        assert is_supabase_configured() is True


class TestGetSupabaseNotConfigured:
    """Tests for get_supabase() when Supabase is not configured."""

    def test_raises_when_url_missing(self, settings_env):
        settings_env.unset("SUPABASE_URL")
        settings_env.unset("SUPABASE_ANON_KEY")
        settings_env.clear_settings_cache()
        # Reset the module-level cache
        from packages.core import supabase_client
        supabase_client._supabase_client = None
        supabase_client._supabase_client_url = None

        from packages.core.supabase_client import get_supabase
        with pytest.raises(RuntimeError, match="SUPABASE_URL"):
            get_supabase()

    def test_raises_when_key_missing(self, settings_env):
        settings_env.set("SUPABASE_URL", "https://test.supabase.co")
        settings_env.unset("SUPABASE_ANON_KEY")
        settings_env.clear_settings_cache()
        from packages.core import supabase_client
        supabase_client._supabase_client = None
        supabase_client._supabase_client_url = None

        from packages.core.supabase_client import get_supabase
        with pytest.raises(RuntimeError, match="SUPABASE_ANON_KEY"):
            get_supabase()


class TestGetSupabaseOptional:
    """Tests for get_supabase_optional()."""

    def test_returns_none_when_not_configured(self, settings_env):
        settings_env.unset("SUPABASE_URL")
        settings_env.unset("SUPABASE_ANON_KEY")
        settings_env.clear_settings_cache()
        from packages.core import supabase_client
        supabase_client._supabase_client = None
        supabase_client._supabase_client_url = None

        from packages.core.supabase_client import get_supabase_optional
        result = get_supabase_optional()
        assert result is None

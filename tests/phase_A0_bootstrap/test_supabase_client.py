"""
test_supabase_client.py — Phase A.0: Tests for packages/core/supabase_client.py

Covers:
  - is_supabase_configured() returns bool based on env vars
  - get_supabase() raises RuntimeError when not configured
  - get_supabase_optional() returns None when not configured

NOTE: These tests use patch to control what get_settings() returns,
because supabase_client.py calls get_settings() internally.
"""

import pytest
from unittest.mock import patch, MagicMock


def _mock_settings(**overrides):
    """Create a mock Settings object with given attributes."""
    defaults = {
        "SUPABASE_URL": "",
        "SUPABASE_ANON_KEY": "",
        "SUPABASE_SERVICE_ROLE_KEY": "",
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


class TestIsSupabaseConfigured:
    """Tests for is_supabase_configured()."""

    def test_false_when_both_missing(self):
        mock_s = _mock_settings(SUPABASE_URL="", SUPABASE_ANON_KEY="")
        with patch("packages.core.supabase_client.get_settings", return_value=mock_s):
            from packages.core.supabase_client import is_supabase_configured
            assert is_supabase_configured() is False

    def test_false_when_only_url(self):
        mock_s = _mock_settings(SUPABASE_URL="https://test.supabase.co", SUPABASE_ANON_KEY="")
        with patch("packages.core.supabase_client.get_settings", return_value=mock_s):
            from packages.core.supabase_client import is_supabase_configured
            assert is_supabase_configured() is False

    def test_false_when_only_key(self):
        mock_s = _mock_settings(SUPABASE_URL="", SUPABASE_ANON_KEY="eyJhbGci.test")
        with patch("packages.core.supabase_client.get_settings", return_value=mock_s):
            from packages.core.supabase_client import is_supabase_configured
            assert is_supabase_configured() is False

    def test_true_when_both_set(self):
        mock_s = _mock_settings(SUPABASE_URL="https://test.supabase.co", SUPABASE_ANON_KEY="eyJhbGci.test")
        with patch("packages.core.supabase_client.get_settings", return_value=mock_s):
            from packages.core.supabase_client import is_supabase_configured
            assert is_supabase_configured() is True


class TestGetSupabaseNotConfigured:
    """Tests for get_supabase() when Supabase is not configured."""

    def test_raises_when_url_missing(self):
        mock_s = _mock_settings(SUPABASE_URL="", SUPABASE_ANON_KEY="")
        with patch("packages.core.supabase_client.get_settings", return_value=mock_s):
            # Reset module-level cache
            from packages.core import supabase_client
            supabase_client._supabase_client = None
            supabase_client._supabase_client_url = None

            from packages.core.supabase_client import get_supabase
            with pytest.raises(RuntimeError, match="SUPABASE_URL"):
                get_supabase()

    def test_raises_when_key_missing(self):
        mock_s = _mock_settings(SUPABASE_URL="https://test.supabase.co", SUPABASE_ANON_KEY="")
        with patch("packages.core.supabase_client.get_settings", return_value=mock_s):
            from packages.core import supabase_client
            supabase_client._supabase_client = None
            supabase_client._supabase_client_url = None

            from packages.core.supabase_client import get_supabase
            with pytest.raises(RuntimeError, match="SUPABASE_ANON_KEY"):
                get_supabase()


class TestGetSupabaseOptional:
    """Tests for get_supabase_optional()."""

    def test_returns_none_when_not_configured(self):
        mock_s = _mock_settings(SUPABASE_URL="", SUPABASE_ANON_KEY="")
        with patch("packages.core.supabase_client.get_settings", return_value=mock_s):
            from packages.core import supabase_client
            supabase_client._supabase_client = None
            supabase_client._supabase_client_url = None

            from packages.core.supabase_client import get_supabase_optional
            result = get_supabase_optional()
            assert result is None

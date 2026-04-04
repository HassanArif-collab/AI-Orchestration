"""Tests for packages/core/llm.py — LLM abstraction."""

import pytest
from unittest.mock import patch, MagicMock
import os


class TestEnsureFreerouterEnv:
    """Tests for _ensure_freerouter_env()."""

    @patch("packages.core.llm.get_settings")
    def test_sets_openai_api_base(self, mock_settings):
        mock_settings.return_value = MagicMock(
            FREEROUTER_URL="http://localhost:4000",
            FREEROUTER_API_KEY="test-key",
        )
        # Clear env vars first
        os.environ.pop("OPENAI_API_BASE", None)
        os.environ.pop("OPENAI_API_KEY", None)

        from packages.core.llm import _ensure_freerouter_env
        _ensure_freerouter_env()

        assert os.environ["OPENAI_API_BASE"] == "http://localhost:4000/v1"
        assert os.environ["OPENAI_API_KEY"] == "test-key"

        # Cleanup
        os.environ.pop("OPENAI_API_BASE", None)
        os.environ.pop("OPENAI_API_KEY", None)

    @patch("packages.core.llm.get_settings")
    def test_does_not_override_existing_env(self, mock_settings):
        mock_settings.return_value = MagicMock(
            FREEROUTER_URL="http://localhost:4000",
            FREEROUTER_API_KEY="test-key",
        )
        os.environ["OPENAI_API_BASE"] = "http://custom:8000/v1"
        os.environ["OPENAI_API_KEY"] = "custom-key"

        from packages.core.llm import _ensure_freerouter_env
        _ensure_freerouter_env()

        assert os.environ["OPENAI_API_BASE"] == "http://custom:8000/v1"
        assert os.environ["OPENAI_API_KEY"] == "custom-key"

        # Cleanup
        os.environ.pop("OPENAI_API_BASE", None)
        os.environ.pop("OPENAI_API_KEY", None)


class TestFreerouterLlm:
    """Tests for freerouter_llm()."""

    @patch("packages.core.llm.get_settings")
    def test_returns_model_string(self, mock_settings):
        mock_settings.return_value = MagicMock(
            FREEROUTER_URL="http://localhost:4000",
            FREEROUTER_API_KEY="key",
        )
        os.environ.pop("OPENAI_API_BASE", None)
        os.environ.pop("OPENAI_API_KEY", None)

        from packages.core.llm import freerouter_llm
        result = freerouter_llm(model="gpt-4o-mini")
        assert result == "gpt-4o-mini"
        assert os.environ.get("OPENAI_API_BASE") == "http://localhost:4000/v1"

        # Cleanup
        os.environ.pop("OPENAI_API_BASE", None)
        os.environ.pop("OPENAI_API_KEY", None)

    @patch("packages.core.llm.get_settings")
    def test_default_model(self, mock_settings):
        mock_settings.return_value = MagicMock(
            FREEROUTER_URL="http://localhost:4000",
            FREEROUTER_API_KEY="key",
        )
        os.environ.pop("OPENAI_API_BASE", None)
        os.environ.pop("OPENAI_API_KEY", None)

        from packages.core.llm import freerouter_llm
        result = freerouter_llm()
        assert result == "default"

        # Cleanup
        os.environ.pop("OPENAI_API_BASE", None)
        os.environ.pop("OPENAI_API_KEY", None)

    @patch("packages.core.llm.get_settings")
    def test_custom_temperature_accepted(self, mock_settings):
        mock_settings.return_value = MagicMock(
            FREEROUTER_URL="http://localhost:4000",
            FREEROUTER_API_KEY="key",
        )
        os.environ.pop("OPENAI_API_BASE", None)
        os.environ.pop("OPENAI_API_KEY", None)

        from packages.core.llm import freerouter_llm
        result = freerouter_llm(model="test", temperature=0.3, max_tokens=1024)
        assert result == "test"

        # Cleanup
        os.environ.pop("OPENAI_API_BASE", None)
        os.environ.pop("OPENAI_API_KEY", None)

    @patch("packages.core.llm.get_settings")
    def test_full_provider_model_string(self, mock_settings):
        mock_settings.return_value = MagicMock(
            FREEROUTER_URL="http://localhost:4000",
            FREEROUTER_API_KEY="key",
        )
        os.environ.pop("OPENAI_API_BASE", None)
        os.environ.pop("OPENAI_API_KEY", None)

        from packages.core.llm import freerouter_llm
        result = freerouter_llm(model="openrouter/google/gemini-2.0-flash-001")
        assert result == "openrouter/google/gemini-2.0-flash-001"

        # Cleanup
        os.environ.pop("OPENAI_API_BASE", None)
        os.environ.pop("OPENAI_API_KEY", None)

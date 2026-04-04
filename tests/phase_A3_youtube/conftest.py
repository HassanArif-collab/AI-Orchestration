"""
conftest.py — Shared fixtures for Phase A.3 YouTube client tests.

Provides test utilities for mocking the YouTube Data API client
so tests can run in isolation without real API calls or credentials.
"""

import pytest
from unittest.mock import MagicMock, patch


def make_settings(**overrides):
    """Create a Settings instance without reading the .env file.

    Usage:
        from packages.core.config import Settings
        s = make_settings(YOUTUBE_API_KEY="fake-key-123")
    """
    from packages.core.config import Settings
    return Settings(_env_file=None, **overrides)


@pytest.fixture()
def mock_youtube_settings(monkeypatch):
    """Patch get_settings() to return a settings object with a YouTube API key.

    Defaults to a fake key. Pass api_key="" to simulate missing key.

    Usage:
        def test_something(mock_youtube_settings):
            ...
    """
    settings = make_settings(YOUTUBE_API_KEY="fake-youtube-api-key-1234567890")

    with patch("packages.integrations.youtube.client.get_settings", return_value=settings):
        yield settings


@pytest.fixture()
def mock_youtube_no_key(monkeypatch):
    """Patch get_settings() to return settings with empty YOUTUBE_API_KEY."""
    settings = make_settings(YOUTUBE_API_KEY="")

    with patch("packages.integrations.youtube.client.get_settings", return_value=settings):
        yield settings


@pytest.fixture()
def mock_service():
    """Provide a MagicMock that mimics the YouTube API service chain.

    Usage:
        def test_something(mock_service):
            client = YouTubeClient(api_key="")
            client._service = mock_service
            mock_service.channels.return_value.list.return_value.execute.return_value = {...}
            ...
    """
    return MagicMock()

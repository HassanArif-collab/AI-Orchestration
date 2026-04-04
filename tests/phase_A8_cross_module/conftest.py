"""Shared fixtures for Phase A.8 cross-module tests."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from dataclasses import dataclass

import pytest


# ── Environment isolation ──────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """Save and restore key env vars to prevent cross-test leakage."""
    keys_to_track = [
        "FREEROUTER_URL", "FREEROUTER_API_KEY",
        "OPENAI_API_BASE", "OPENAI_API_KEY",
        "ZEP_API_KEY", "ZEP_BASE_URL", "ZEP_ENABLED",
        "SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_KEY",
        "ESCALATION_ENABLED", "ESCALATION_WEBHOOK_URL",
        "ESCALATION_WEBHOOK_TYPE", "ESCALATION_MIN_SCORE",
        "NOTION_API_KEY", "EXA_API_KEY", "YOUTUBE_API_KEY",
    ]
    saved = {k: os.environ.get(k) for k in keys_to_track}
    for k in keys_to_track:
        monkeypatch.delenv(k, raising=False)
    yield
    for k, v in saved.items():
        if v is not None:
            os.environ[k] = v
        else:
            os.environ.pop(k, None)


# ── Settings helper ────────────────────────────────────────────────────────────

def make_settings(**overrides):
    """Create a MagicMock of Settings with sensible defaults."""
    defaults = dict(
        FREEROUTER_URL="http://localhost:4000",
        FREEROUTER_API_KEY="test-key",
        ZEP_API_KEY="test-zep-key",
        ZEP_BASE_URL="https://test.zep.cloud",
        ZEP_ENABLED=False,
        ZEP_AUDIENCE_USER_ID="audience_user",
        ZEP_LEARNING_USER_ID="learning_user",
        SUPABASE_URL="https://test.supabase.co",
        SUPABASE_ANON_KEY="test-anon-key",
        SUPABASE_SERVICE_KEY="test-service-key",
        ESCALATION_ENABLED=True,
        ESCALATION_WEBHOOK_URL="",
        ESCALATION_WEBHOOK_TYPE="default",
        ESCALATION_MIN_SCORE=50.0,
        QUALITY_THRESHOLD=85,
        MAX_ITERATIONS=20,
        LOG_LEVEL="WARNING",
        API_KEYS=[],
    )
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


@pytest.fixture()
def mock_settings():
    """Provide a mock Settings object via get_settings patch."""
    return make_settings()


# ── Temporary directories ──────────────────────────────────────────────────────

@pytest.fixture()
def tmp_cache_dir(tmp_path):
    """Provide a temporary cache directory path."""
    d = tmp_path / "cache"
    d.mkdir()
    return d


@pytest.fixture()
def tmp_db_path(tmp_path):
    """Provide a temporary SQLite database path."""
    return str(tmp_path / "test_pipeline.db")


# ── Mock Supabase client ──────────────────────────────────────────────────────

@pytest.fixture()
def mock_supabase():
    """Provide a mock Supabase client."""
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    return mock_client, mock_table


# ── Mock RouterClient ──────────────────────────────────────────────────────────

@pytest.fixture()
def mock_router_client():
    """Mock RouterClient context manager."""
    mock_client = MagicMock()
    mock_client.complete_text.return_value = "Mocked LLM response"
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = MagicMock(return_value=mock_client)
    mock_ctx.__aexit__ = MagicMock(return_value=False)
    return mock_ctx


# ── Mock Zep Memory Client ────────────────────────────────────────────────────

@pytest.fixture()
def mock_zep_client():
    """Mock AsyncZepMemoryClient."""
    mock = MagicMock()
    mock.add_message = MagicMock()
    mock.search_memory = MagicMock(return_value=[])
    mock.add_facts = MagicMock()
    mock.create_session = MagicMock()
    mock.create_user = MagicMock()
    return mock

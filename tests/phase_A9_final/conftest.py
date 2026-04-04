"""Shared fixtures for Phase A.9 Final — Orchestration Modules Tests."""

import sys
import os
import pytest
from unittest.mock import MagicMock, patch

# ── Pre-import langgraph mocks (required before importing orchestration modules) ──

# langgraph and submodules used by nodes.py, graphs.py, __init__.py, checkpointer.py
for mod_name in [
    "langgraph",
    "langgraph.graph",
    "langgraph.types",
    "langgraph.prebuilt",
    "langgraph.checkpoint",
    "langgraph.checkpoint.memory",
    "langgraph.checkpoint.postgres",
    "langgraph.checkpoint.postgres.aio",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()


@pytest.fixture(autouse=True)
def isolate_env(monkeypatch):
    """Isolate environment variables for each test."""
    for key in [
        "SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_DB_URL",
        "ZEP_API_KEY", "ZEP_ENABLED",
        "EXA_API_KEY", "NOTION_API_KEY",
        "FREEROUTER_URL",
        "RISK_TIER_LOW_SCORE", "RISK_TIER_HIGH_SCORE",
        "RISK_TIER_LOW_SLA_HOURS", "RISK_TIER_MEDIUM_SLA_HOURS",
        "RISK_TIER_HIGH_SLA_HOURS", "HUMAN_REVIEW_TIMEOUT_HOURS",
    ]:
        monkeypatch.setenv(key, "fake_value_for_testing" if "KEY" in key or "URL" in key else "1")


@pytest.fixture
def mock_supabase():
    """Return a mock Supabase client."""
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_result = MagicMock()
    mock_result.data = []
    mock_result.count = 0
    mock_table.insert.return_value = mock_result
    mock_table.select.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.upsert.return_value = mock_result
    mock_table.delete.return_value = mock_result
    mock_table.eq.return_value = mock_table
    mock_table.or_.return_value = mock_table
    mock_table.order.return_value = mock_table
    mock_table.limit.return_value = mock_table
    mock_table.execute.return_value = mock_result
    return mock_client


@pytest.fixture
def mock_settings():
    """Return a mock Settings object with common attributes."""
    settings = MagicMock()
    settings.EXA_API_KEY = "test-exa-key"
    settings.NOTION_API_KEY = "test-notion-key"
    settings.SUPABASE_URL = "http://localhost:54321"
    settings.SUPABASE_KEY = "test-key"
    settings.ZEP_API_KEY = "test-zep-key"
    settings.ZEP_ENABLED = False
    settings.RISK_TIER_LOW_SCORE = 85
    settings.RISK_TIER_HIGH_SCORE = 60
    settings.RISK_TIER_LOW_SLA_HOURS = 24
    settings.RISK_TIER_MEDIUM_SLA_HOURS = 8
    settings.RISK_TIER_HIGH_SLA_HOURS = 4
    settings.HUMAN_REVIEW_TIMEOUT_HOURS = 48
    settings.QUALITY_THRESHOLD = 85
    settings.MAX_ITERATIONS = 20
    return settings


# ── Fixtures for Batch A tests (pure models via direct import) ──

@pytest.fixture(scope="session")
def orch_state():
    """Directly loaded orchestration/state.py (no langgraph dependency)."""
    import importlib.util
    from pathlib import Path
    repo = Path(__file__).resolve().parents[2]
    full = str(repo / "packages/content_factory/orchestration/state.py")
    spec = importlib.util.spec_from_file_location("orch_state", full)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def orch_models():
    """Directly loaded orchestration/models.py (no langgraph dependency)."""
    import importlib.util
    from pathlib import Path
    repo = Path(__file__).resolve().parents[2]
    full = str(repo / "packages/content_factory/orchestration/models.py")
    spec = importlib.util.spec_from_file_location("orch_models", full)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

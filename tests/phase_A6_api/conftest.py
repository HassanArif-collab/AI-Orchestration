"""
conftest.py — Shared fixtures for Phase A.6 API Routes tests.

Uses httpx.AsyncClient with ASGITransport to test FastAPI endpoints
without a running server. All external dependencies are mocked.

CRITICAL: The routers/__init__.py re-exports routers as e.g. `topic_routes = router`,
which shadows module names in the package namespace. To access the actual module
for patching, always use sys.modules[module_path] instead of attribute access.
"""

import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ─── Environment isolation: MUST run before any imports of app modules ──────
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
os.environ.setdefault("FREEROUTER_URL", "http://localhost:4000")
os.environ.setdefault("API_AUTH_ENABLED", "false")
os.environ.setdefault("DATA_DIR", "/tmp/test_phase_A6_data")


def _module(name: str):
    """Get a router module from sys.modules, bypassing __init__.py shadowing.

    The routers/__init__.py does `topic_routes = router`, which means
    `apps.api.routers.topic_routes` resolves to the APIRouter, not the module.
    This helper always returns the actual Python module object.
    """
    key = f"apps.api.routers.{name}"
    if key not in sys.modules:
        __import__(key)
    return sys.modules[key]


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """Clear the cached Settings singleton so each test starts fresh."""
    yield
    try:
        from packages.core.config import get_settings
        get_settings.cache_clear()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _mock_supabase_client():
    """Mock packages.core.supabase_client.get_supabase globally."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    # Patch at source AND at router modules that import it at module level
    with patch("packages.core.supabase_client.get_supabase", return_value=mock_sb):
        yield mock_sb, mock_table


@pytest.fixture(autouse=True)
def _mock_logger():
    """Mock packages.core.logger to avoid logging side effects."""
    mock_logger = MagicMock()
    with patch("packages.core.logger.get_logger", return_value=mock_logger):
        with patch("packages.core.logger.structlog"):
            yield mock_logger


@pytest.fixture()
def mock_memory_client():
    """Mock the memory client returned by get_memory_client.

    Patches at the router module level since memory_routes does
    `from apps.api.dependencies import get_memory_client` at module level.
    """
    mock_client = AsyncMock()
    mod = _module("memory_routes")
    with patch.object(mod, "get_memory_client", return_value=mock_client):
        yield mock_client


@pytest.fixture()
def mock_youtube_client():
    """Mock the YouTube client returned by get_youtube_client.

    Patches at the router module level since analytics_routes does
    `from apps.api.dependencies import get_youtube_client` at module level.
    """
    mock_client = MagicMock()
    mock_client.api_key = "test-youtube-key"
    mod = _module("analytics_routes")
    with patch.object(mod, "get_youtube_client", return_value=mock_client):
        yield mock_client


@pytest.fixture()
def mock_youtube_client_no_key():
    """Mock YouTube client with no API key configured."""
    mock_client = MagicMock()
    mock_client.api_key = ""
    mod = _module("analytics_routes")
    with patch.object(mod, "get_youtube_client", return_value=mock_client):
        yield mock_client


@pytest.fixture()
def mock_radiant_manager():
    """Mock the Radiant manager returned by get_radiant_manager."""
    mock_mgr = MagicMock()
    mod = _module("visual_routes")
    with patch.object(mod, "get_radiant_manager", return_value=mock_mgr):
        yield mock_mgr


@pytest.fixture()
def mock_proxy_client():
    """Mock the proxy client returned by get_proxy_client."""
    mock_client = AsyncMock()
    with patch("apps.api.dependencies.get_proxy_client", return_value=mock_client):
        yield mock_client


@pytest.fixture()
def mock_thoughts():
    """Mock packages.core.thoughts functions."""
    with patch("packages.core.thoughts.get_thoughts_for_card", return_value=[]) as m_get, \
         patch("packages.core.thoughts.report_thought") as m_report, \
         patch("packages.core.thoughts.delete_thoughts_for_card") as m_delete:
        yield m_get, m_report, m_delete


@pytest.fixture()
async def client():
    """Create an httpx AsyncClient for testing the FastAPI app.

    Tests auth-disabled mode by default. Use auth_client fixture for auth tests.
    """
    from httpx import AsyncClient, ASGITransport

    os.environ["API_AUTH_ENABLED"] = "false"
    try:
        from packages.core.config import get_settings
        get_settings.cache_clear()
    except Exception:
        pass

    transport = ASGITransport(app=_get_app())
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture()
async def auth_client():
    """Create an httpx AsyncClient with auth enabled and a valid API key."""
    from httpx import AsyncClient, ASGITransport

    os.environ["API_AUTH_ENABLED"] = "true"
    os.environ["API_KEYS"] = "test-secret-key-123"
    try:
        from packages.core.config import get_settings
        get_settings.cache_clear()
    except Exception:
        pass

    transport = ASGITransport(app=_get_app())
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-API-Key": "test-secret-key-123"},
    ) as ac:
        yield ac

    os.environ["API_AUTH_ENABLED"] = "false"
    os.environ.pop("API_KEYS", None)
    try:
        from packages.core.config import get_settings
        get_settings.cache_clear()
    except Exception:
        pass


@pytest.fixture()
async def unauth_client():
    """Create an httpx AsyncClient with auth enabled but NO API key."""
    from httpx import AsyncClient, ASGITransport

    os.environ["API_AUTH_ENABLED"] = "true"
    os.environ["API_KEYS"] = "test-secret-key-123"
    try:
        from packages.core.config import get_settings
        get_settings.cache_clear()
    except Exception:
        pass

    transport = ASGITransport(app=_get_app())
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    os.environ["API_AUTH_ENABLED"] = "false"
    os.environ.pop("API_KEYS", None)
    try:
        from packages.core.config import get_settings
        get_settings.cache_clear()
    except Exception:
        pass


def _get_app():
    """Lazy-load and return the FastAPI app instance."""
    from apps.api.main import app
    return app


@pytest.fixture()
def mock_dead_letter():
    """Mock dead_letter functions at the dlq_routes module level.

    Since dlq_routes does `from packages.core.dead_letter import get_stats, ...`
    at module level, patching at the source package doesn't affect the router.
    We must patch the router module's namespace directly.
    """
    mod = _module("dlq_routes")
    with patch.object(mod, "get_stats", return_value={"total": 0, "pending": 0, "completed": 0, "by_operation": {}, "by_error_code": {}, "by_severity": {}}) as m_stats, \
         patch.object(mod, "get_all_entries", return_value=[]) as m_all, \
         patch.object(mod, "get_entry", return_value=None) as m_get, \
         patch.object(mod, "delete_entry", return_value=True) as m_delete, \
         patch.object(mod, "mark_retry_attempt", return_value=True) as m_retry:
        yield {
            "get_stats": m_stats,
            "get_all_entries": m_all,
            "get_entry": m_get,
            "delete_entry": m_delete,
            "mark_retry_attempt": m_retry,
        }


@pytest.fixture()
def mock_background_tasks():
    """Mock background task functions from apps.api.background_tasks."""
    with patch("apps.api.background_tasks.start_research_for_topic", new_callable=AsyncMock) as m_research, \
         patch("apps.api.background_tasks.evaluate_script", new_callable=AsyncMock) as m_eval, \
         patch("apps.api.background_tasks.run_daily_scan", new_callable=AsyncMock) as m_scan:
        yield {
            "start_research": m_research,
            "evaluate_script": m_eval,
            "run_daily_scan": m_scan,
        }

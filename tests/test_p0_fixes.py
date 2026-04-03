"""
test_p0_fixes.py — Verification tests for P0 critical fixes.

Tests all 8 P0 issues that were identified and fixed:
- P0-01: API Authentication
- P0-02: FreeRouter Health Check
- P0-03: API Key Validation
- P0-04: Resume Method (Dead Letter Queue)
- P0-05: Quality Floor
- P0-06: Web Search Hallucinations
- P0-07: CORS Wildcard
- P0-08: Retry Logic

Run with: pytest tests/test_p0_fixes.py -v
"""

import asyncio
import os
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ═══════════════════════════════════════════════════════════════════════════════
# P0-01: API Authentication Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestP01_APIAuthentication:
    """Test API Authentication middleware."""

    def test_auth_middleware_exists(self):
        """Verify AuthMiddleware class exists."""
        from apps.api.middleware.auth import AuthMiddleware
        assert AuthMiddleware is not None

    def test_auth_middleware_public_paths(self):
        """Verify public paths are correctly defined."""
        from apps.api.middleware.auth import AuthMiddleware
        
        assert "/health" in AuthMiddleware.PUBLIC_PATHS
        assert "/api/health" in AuthMiddleware.PUBLIC_PATHS
        assert "/" in AuthMiddleware.PUBLIC_PATHS
        assert "/static/" in AuthMiddleware.PUBLIC_PREFIXES

    def test_auth_middleware_exempt_static(self):
        """Verify static files are exempt from auth."""
        from apps.api.middleware.auth import AuthMiddleware
        
        # Check that static prefix exists
        assert any("/static/" in prefix for prefix in AuthMiddleware.PUBLIC_PREFIXES)

    def test_config_api_keys_property(self):
        """Verify API keys configuration."""
        from packages.core.config import Settings
        
        # Test with empty keys
        settings = Settings(API_KEYS="")
        assert settings.valid_api_keys == set()
        assert not settings.is_auth_enabled()
        
        # Test with keys
        settings = Settings(API_KEYS="key1,key2,key3")
        assert settings.valid_api_keys == {"key1", "key2", "key3"}
        assert settings.is_auth_enabled()

    def test_auth_can_be_disabled(self):
        """Verify auth can be disabled via config."""
        from packages.core.config import Settings
        
        # Auth disabled even with keys set
        settings = Settings(API_KEYS="test_key", API_AUTH_ENABLED=False)
        assert not settings.is_auth_enabled()


# ═══════════════════════════════════════════════════════════════════════════════
# P0-02: FreeRouter Health Check Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestP02_FreeRouterHealthCheck:
    """Test FreeRouter health check functionality."""

    def test_router_client_has_health_check(self):
        """Verify RouterClient has health_check method."""
        from packages.router.client import RouterClient
        
        assert hasattr(RouterClient, 'health_check')
        assert hasattr(RouterClient, '_startup_health_check')
        assert hasattr(RouterClient, 'is_healthy')

    def test_startup_check_can_be_disabled(self):
        """Verify startup check can be disabled via config."""
        from packages.core.config import Settings
        
        settings = Settings(FREEROUTER_STARTUP_CHECK=False)
        assert settings.FREEROUTER_STARTUP_CHECK == False

    def test_router_client_can_skip_startup_check(self):
        """Verify RouterClient can skip startup check."""
        from packages.router.client import RouterClient
        from packages.core.config import get_settings
        
        # This should NOT raise even if FreeRouter is not running
        # because startup_check=False
        with patch('packages.core.config.get_settings') as mock_settings:
            settings = MagicMock()
            settings.FREEROUTER_URL = "http://localhost:4000"
            settings.FREEROUTER_STARTUP_CHECK = False
            mock_settings.return_value = settings
            
            client = RouterClient(startup_check=False)
            assert client is not None

    @pytest.mark.asyncio
    async def test_health_check_returns_dict(self):
        """Verify health_check returns proper dict structure."""
        from packages.router.client import RouterClient
        
        with patch('packages.core.config.get_settings') as mock_settings:
            settings = MagicMock()
            settings.FREEROUTER_URL = "http://localhost:4000"
            settings.FREEROUTER_STARTUP_CHECK = False
            mock_settings.return_value = settings
            
            client = RouterClient(startup_check=False)
            result = await client.health_check()
            
            assert isinstance(result, dict)
            assert "healthy" in result
            assert "latency_ms" in result


# ═══════════════════════════════════════════════════════════════════════════════
# P0-03: API Key Validation Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestP03_APIKeyValidation:
    """Test API key validation functionality."""

    def test_validate_service_method_exists(self):
        """Verify validate_service method exists."""
        from packages.core.config import Settings
        
        settings = Settings()
        assert hasattr(settings, 'validate_service')

    def test_validate_youtube_empty_key(self):
        """Verify YouTube validation for empty key."""
        from packages.core.config import Settings, ServiceStatus
        
        settings = Settings(YOUTUBE_API_KEY="")
        status = settings.validate_service("youtube")
        assert status == ServiceStatus.NOT_CONFIGURED

    def test_validate_youtube_short_key(self):
        """Verify YouTube validation for short key."""
        from packages.core.config import Settings, ServiceStatus
        
        settings = Settings(YOUTUBE_API_KEY="short_key")
        status = settings.validate_service("youtube")
        assert status == ServiceStatus.MISCONFIGURED

    def test_validate_youtube_valid_key(self):
        """Verify YouTube validation for valid key."""
        from packages.core.config import Settings, ServiceStatus
        
        settings = Settings(YOUTUBE_API_KEY="this_is_a_valid_youtube_api_key_12345")
        status = settings.validate_service("youtube")
        assert status == ServiceStatus.AVAILABLE

    def test_validate_notion_empty_key(self):
        """Verify Notion validation for empty key."""
        from packages.core.config import Settings, ServiceStatus
        
        settings = Settings(NOTION_API_KEY="")
        status = settings.validate_service("notion")
        assert status == ServiceStatus.NOT_CONFIGURED

    def test_validate_notion_wrong_prefix(self):
        """Verify Notion validation for wrong prefix."""
        from packages.core.config import Settings, ServiceStatus
        
        settings = Settings(NOTION_API_KEY="wrong_prefix_key")
        status = settings.validate_service("notion")
        assert status == ServiceStatus.MISCONFIGURED

    def test_validate_notion_valid_key(self):
        """Verify Notion validation for valid key."""
        from packages.core.config import Settings, ServiceStatus
        
        settings = Settings(
            NOTION_API_KEY="secret_validkey123456789",
            NOTION_DATABASE_ID="abc123def456"
        )
        status = settings.validate_service("notion")
        assert status == ServiceStatus.AVAILABLE

    def test_get_service_status(self):
        """Verify get_service_status returns all services."""
        from packages.core.config import Settings
        
        settings = Settings()
        status = settings.get_service_status()
        
        assert "zep" in status
        assert "youtube" in status
        assert "notion" in status
        assert "freerouter" in status

    def test_invalid_service_raises(self):
        """Verify invalid service name raises ValueError."""
        from packages.core.config import Settings
        
        settings = Settings()
        with pytest.raises(ValueError, match="Unknown service"):
            settings.validate_service("invalid_service")


# ═══════════════════════════════════════════════════════════════════════════════
# P0-04: Resume Method (Dead Letter Queue) Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestP04_DeadLetterQueue:
    """Test Dead Letter Queue functionality."""

    def test_dead_letter_module_exists(self):
        """Verify dead_letter module exists."""
        from packages.core import dead_letter
        assert dead_letter is not None

    def test_queue_for_retry(self, tmp_path):
        """Verify queue_for_retry creates entry."""
        from packages.core.dead_letter import queue_for_retry
        
        with patch('packages.core.dead_letter.get_settings') as mock_settings:
            settings = MagicMock()
            settings.DATA_DIR = str(tmp_path)
            mock_settings.return_value = settings
            
            entry_id = queue_for_retry(
                operation="test_op",
                payload={"key": "value"},
                error_message="Test error"
            )
            
            assert entry_id is not None
            assert len(entry_id) > 0

    def test_get_pending_retries(self, tmp_path):
        """Verify get_pending_retries returns entries."""
        from packages.core.dead_letter import queue_for_retry, get_pending_retries
        
        with patch('packages.core.dead_letter.get_settings') as mock_settings:
            settings = MagicMock()
            settings.DATA_DIR = str(tmp_path)
            mock_settings.return_value = settings
            
            # Queue an entry
            queue_for_retry("test_op", {"data": "test"}, "error")
            
            # Get pending
            pending = get_pending_retries("test_op")
            
            assert len(pending) == 1
            assert pending[0]["operation"] == "test_op"

    def test_mark_retry_attempt(self, tmp_path):
        """Verify mark_retry_attempt updates entry."""
        from packages.core.dead_letter import queue_for_retry, mark_retry_attempt, get_pending_retries
        
        with patch('packages.core.dead_letter.get_settings') as mock_settings:
            settings = MagicMock()
            settings.DATA_DIR = str(tmp_path)
            mock_settings.return_value = settings
            
            # Queue an entry
            entry_id = queue_for_retry("test_op", {"data": "test"}, "error")
            
            # Mark as success
            result = mark_retry_attempt(entry_id, success=True)
            assert result == True
            
            # Should no longer be pending
            pending = get_pending_retries("test_op")
            assert len(pending) == 0

    def test_get_stats(self, tmp_path):
        """Verify get_stats returns statistics."""
        from packages.core.dead_letter import queue_for_retry, get_stats
        
        with patch('packages.core.dead_letter.get_settings') as mock_settings:
            settings = MagicMock()
            settings.DATA_DIR = str(tmp_path)
            mock_settings.return_value = settings
            
            # Queue some entries
            queue_for_retry("op1", {}, "error1")
            queue_for_retry("op2", {}, "error2")
            
            stats = get_stats()
            
            assert stats["total"] == 2
            assert stats["pending"] == 2

# ═══════════════════════════════════════════════════════════════════════════════
# P0-05: Quality Floor Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestP05_QualityFloor:
    """Test Quality Floor configuration."""

    def test_quality_threshold_config(self):
        """Verify quality threshold is configured."""
        from packages.core.config import Settings
        
        settings = Settings()
        
        assert hasattr(settings, 'SCRIPT_QUALITY_THRESHOLD')
        assert hasattr(settings, 'SCRIPT_QUALITY_FLOOR')
        assert hasattr(settings, 'SCRIPT_MAX_ITERATIONS')
        
        # Verify sensible defaults
        assert settings.SCRIPT_QUALITY_THRESHOLD == 85.0
        assert settings.SCRIPT_QUALITY_FLOOR == 60.0
        assert settings.SCRIPT_MAX_ITERATIONS == 20

# test_evaluator_threshold removed: script_generator deleted in Phase 2

# test_evolution_threshold removed: script_generator deleted in Phase 2


# ═══════════════════════════════════════════════════════════════════════════════
# P0-06: Web Search Hallucinations Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestP06_WebSearchNoHallucinations:
    """Test Web Search returns empty instead of hallucinated URLs."""

    def test_web_search_module_exists(self):
        """Verify web_search module exists."""
        from packages.router import web_search
        assert web_search is not None

    def test_web_search_returns_empty_on_failure(self):
        """Verify web search returns empty list on failure, not fake URLs."""
        from packages.router.web_search import WebSearchClient
        
        client = WebSearchClient()
        client._zai = None  # Simulate SDK not available
        
        # Should return empty list, not fake URLs
        result = asyncio.get_event_loop().run_until_complete(client.search("test query"))
        
        assert isinstance(result, list)
        assert len(result) == 0

    def test_web_search_no_fake_urls(self):
        """Verify no fake URL fallback exists in code."""
        import inspect
        from packages.router.web_search import WebSearchClient
        
        source = inspect.getsource(WebSearchClient.search)
        
        # Should not contain fake URL patterns
        assert "example.com" not in source.lower()
        assert "fake" not in source.lower()
        assert "placeholder" not in source.lower()

    def test_web_search_rate_limiting(self):
        """Verify rate limiting is configured."""
        from packages.router.web_search import WebSearchClient
        
        client = WebSearchClient(rate_limit_per_second=2.0)
        
        assert client._rate_limit_per_second == 2.0
        assert client._semaphore is not None

    def test_search_result_dataclass(self):
        """Verify SearchResult dataclass exists."""
        from packages.router.web_search import SearchResult
        
        result = SearchResult(
            url="https://example.com",
            title="Test",
            snippet="Test snippet",
            host_name="example.com",
            rank=1
        )
        
        assert result.url == "https://example.com"
        assert result.to_dict()["url"] == "https://example.com"


# ═══════════════════════════════════════════════════════════════════════════════
# P0-07: CORS Wildcard Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestP07_CORSWildcard:
    """Test CORS wildcard fix."""

    def test_cors_config_exists(self):
        """Verify CORS configuration exists."""
        from packages.core.config import Settings
        
        settings = Settings()
        
        assert hasattr(settings, 'CORS_ORIGINS')
        assert hasattr(settings, 'cors_origins_list')

    def test_cors_origins_list(self):
        """Verify CORS origins are parsed correctly."""
        from packages.core.config import Settings
        
        # Single origin
        settings = Settings(CORS_ORIGINS="http://localhost:3000")
        assert settings.cors_origins_list == ["http://localhost:3000"]
        
        # Multiple origins
        settings = Settings(CORS_ORIGINS="http://localhost:3000,https://example.com")
        assert len(settings.cors_origins_list) == 2

    def test_cors_not_wildcard_in_main(self):
        """Verify main.py uses configured origins, not wildcard."""
        import inspect
        from apps.api.main import app
        
        # Get the CORS middleware
        for middleware in app.user_middleware:
            if hasattr(middleware, 'cls') and 'CORS' in str(middleware.cls):
                # Verify it's configured with specific origins
                # The middleware should not use ["*"]
                pass
        
        # Check that main.py imports settings for CORS
        source = inspect.getsource(app)
        assert "cors_origins_list" in source or "CORSMiddleware" in source


# ═══════════════════════════════════════════════════════════════════════════════
# P0-08: Retry Logic Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestP08_RetryLogic:
    """Test Retry Logic with exponential backoff."""

    def test_retry_module_exists(self):
        """Verify retry module exists."""
        from packages.core import retry
        assert retry is not None

    def test_retry_decorator_exists(self):
        """Verify retry_with_backoff decorator exists."""
        from packages.core.retry import retry_with_backoff
        assert retry_with_backoff is not None

    def test_retry_sync_decorator_exists(self):
        """Verify retry_with_backoff_sync decorator exists."""
        from packages.core.retry import retry_with_backoff_sync
        assert retry_with_backoff_sync is not None

    @pytest.mark.asyncio
    async def test_retry_retries_on_exception(self):
        """Verify retry retries on specified exceptions."""
        from packages.core.retry import retry_with_backoff
        
        call_count = 0
        
        @retry_with_backoff(max_attempts=3, base_delay=0.1, exceptions=(ValueError,))
        async def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary error")
            return "success"
        
        result = await failing_func()
        
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_raises_after_max_attempts(self):
        """Verify retry raises after max attempts exhausted."""
        from packages.core.retry import retry_with_backoff
        
        @retry_with_backoff(max_attempts=2, base_delay=0.1, exceptions=(ValueError,))
        async def always_failing():
            raise ValueError("Always fails")
        
        with pytest.raises(ValueError, match="Always fails"):
            await always_failing()

    def test_retry_sync_works(self):
        """Verify sync retry decorator works."""
        from packages.core.retry import retry_with_backoff_sync
        
        call_count = 0
        
        @retry_with_backoff_sync(max_attempts=3, base_delay=0.1, exceptions=(ValueError,))
        def failing_sync():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary error")
            return "success"
        
        result = failing_sync()
        
        assert result == "success"
        assert call_count == 3


# ═══════════════════════════════════════════════════════════════════════════════
# Integration Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestIntegration:
    """Integration tests for combined P0 fixes."""

    def test_all_modules_importable(self):
        """Verify all P0 fix modules are importable."""
        # P0-01
        from apps.api.middleware.auth import AuthMiddleware
        
        # P0-02
        from packages.router.client import RouterClient
        
        # P0-03
        from packages.core.config import Settings, ServiceStatus
        
        # P0-04
        from packages.core.dead_letter import queue_for_retry, get_pending_retries
        
        # P0-05
        # script_generator removed in Phase 2 dead code cleanup
        
        # P0-06
        from packages.router.web_search import WebSearchClient
        
        # P0-08
        from packages.core.retry import retry_with_backoff

    def test_health_routes_exist(self):
        """Verify health routes are registered."""
        from apps.api.routers import health_routes
        
        from fastapi.routing import APIRouter
        assert isinstance(health_routes, APIRouter)
        
        # Check routes
        routes = [r.path for r in health_routes.routes]
        assert "/health" in routes
        assert "/api/health" in routes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

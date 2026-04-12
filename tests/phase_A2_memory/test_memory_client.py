"""
test_memory_client.py — Unit tests for packages/memory/client.py

Tests cover AsyncZepMemoryClient init, search, add_facts, retry logic,
cache behaviour, and graceful degradation. All tests use mocking —
no real Zep API calls are made.

Classes:
  TestAsyncZepMemoryClientInit — Client initialisation (3 tests)
  TestAsyncContextManager      — __aenter__ / __aexit__ (1 test)
  TestSearchMemory             — search_memory method (4 tests)
  TestAddFacts                 — add_facts chunking (3 tests)
  TestWithRetryAsync           — @with_retry_async decorator (3 tests)
  TestCreateUserAndSession     — Degraded-mode early returns (2 tests)
  TestClearCache               — Cache clearing (1 test)
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from packages.core.operation_result import OperationResult, ErrorSeverity
from packages.memory.client import (
    AsyncZepMemoryClient,
    ZepRetryExhaustedError,
    with_retry_async,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_zep_client():
    """Return a MagicMock that quacks like an AsyncZep instance."""
    client = MagicMock()
    client.graph = MagicMock()
    client.graph.search = AsyncMock()
    client.thread = MagicMock()
    client.thread.add_messages = AsyncMock()
    client.thread.create = AsyncMock()
    client.user = MagicMock()
    client.user.add = AsyncMock()
    return client


def _make_edge(fact: str = "test fact", score: float = 0.95) -> MagicMock:
    """Return a MagicMock mimicking a Zep graph edge."""
    edge = MagicMock()
    edge.fact = fact
    edge.score = score
    return edge


# ===========================================================================
# TestAsyncZepMemoryClientInit
# ===========================================================================

class TestAsyncZepMemoryClientInit:
    """Verify client initialisation with and without an API key."""

    def test_init_with_api_key(self):
        """When api_key is provided, client creates AsyncZep instance."""
        mock_async_zep_cls = MagicMock()
        mock_zep_module = MagicMock(AsyncZep=mock_async_zep_cls)

        with patch.dict("sys.modules", {"zep_cloud": mock_zep_module}):
            client = AsyncZepMemoryClient(api_key="test-key")

        mock_async_zep_cls.assert_called_once_with(api_key="test-key")
        assert client._client is not None
        assert client._api_key == "test-key"

    def test_init_without_api_key(self):
        """When no api_key (empty string), client sets _client = None."""
        mock_get_settings = MagicMock()
        mock_get_settings.return_value.ZEP_API_KEY = ""

        with patch("packages.memory.client.get_settings", mock_get_settings):
            client = AsyncZepMemoryClient()

        assert client._client is None
        assert client._api_key == ""

    def test_init_import_error(self):
        """When zep_cloud raises ImportError, client handles gracefully."""
        mock_zep_module = MagicMock()
        # Make AsyncZep raise ImportError on access
        type(mock_zep_module).AsyncZep = property(lambda self: (_ for _ in ()).throw(ImportError("No module")))

        with patch.dict("sys.modules", {"zep_cloud": mock_zep_module}):
            client = AsyncZepMemoryClient(api_key="test-key")

        assert client._client is None


# ===========================================================================
# TestAsyncContextManager
# ===========================================================================

class TestAsyncContextManager:
    """Verify async context manager protocol."""

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """__aenter__ returns self; __aexit__ clears the cache."""
        mock_get_settings = MagicMock()
        mock_get_settings.return_value.ZEP_API_KEY = ""

        with patch("packages.memory.client.get_settings", mock_get_settings):
            async with AsyncZepMemoryClient() as client:
                assert client is not None
                assert isinstance(client, AsyncZepMemoryClient)
                # Seed the cache so we can verify it's cleared on exit
                client._query_cache[("s1", "q", 5)] = [{"fact": "x"}]

        # After exiting, cache must be empty
        assert client._query_cache == {}


# ===========================================================================
# TestSearchMemory
# ===========================================================================

class TestSearchMemory:
    """Verify search_memory: degraded mode, caching, success, and failure."""

    @pytest.mark.asyncio
    async def test_search_memory_no_client(self):
        """When _client is None, returns OperationResult.fail with ZEP_UNAVAILABLE."""
        mock_get_settings = MagicMock()
        mock_get_settings.return_value.ZEP_API_KEY = ""

        with patch("packages.memory.client.get_settings", mock_get_settings):
            client = AsyncZepMemoryClient()

        result = await client.search_memory("session_1", "test query")

        assert result.success is False
        assert result.error_code == "ZEP_UNAVAILABLE"
        assert result.severity == ErrorSeverity.WARNING

    @pytest.mark.asyncio
    async def test_search_memory_cache_hit(self):
        """Second call with same (session_id, query, limit) returns cached result."""
        mock_zep = _make_mock_zep_client()
        mock_zep.graph.search.return_value = MagicMock(edges=[_make_edge("cached fact")])

        with patch.dict("sys.modules", {"zep_cloud": MagicMock(AsyncZep=MagicMock(return_value=mock_zep))}):
            client = AsyncZepMemoryClient(api_key="key")

        # First call — populates cache
        r1 = await client.search_memory("s1", "query", 5)
        # Second call — should hit cache
        r2 = await client.search_memory("s1", "query", 5)

        # API should have been called exactly once
        mock_zep.graph.search.assert_called_once()
        assert r1.success is True
        assert r2.success is True
        assert r1.data == r2.data

    @pytest.mark.asyncio
    async def test_search_memory_success(self):
        """When API succeeds, returns OperationResult.ok with facts list."""
        edge1 = _make_edge("Python is popular", 0.95)
        edge2 = _make_edge("Async IO improves throughput", 0.87)
        mock_zep = _make_mock_zep_client()
        mock_result = MagicMock()
        mock_result.edges = [edge1, edge2]
        mock_zep.graph.search.return_value = mock_result

        with patch.dict("sys.modules", {"zep_cloud": MagicMock(AsyncZep=MagicMock(return_value=mock_zep))}):
            client = AsyncZepMemoryClient(api_key="key")

        result = await client.search_memory("s1", "programming", limit=10)

        assert result.success is True
        assert len(result.data) == 2
        assert result.data[0]["fact"] == "Python is popular"
        assert result.data[0]["score"] == 0.95
        assert result.data[1]["fact"] == "Async IO improves throughput"

        mock_zep.graph.search.assert_called_once_with(
            query="programming",
            graph_id="s1",
            limit=10,
        )

    @pytest.mark.asyncio
    async def test_search_memory_retry_exhaustion(self):
        """When ZepRetryExhaustedError is raised, returns fail with retryable=True."""
        mock_zep = _make_mock_zep_client()
        mock_zep.graph.search.side_effect = ZepRetryExhaustedError("all retries failed")

        with patch.dict("sys.modules", {"zep_cloud": MagicMock(AsyncZep=MagicMock(return_value=mock_zep))}):
            client = AsyncZepMemoryClient(api_key="key")

        with patch("packages.memory.client.queue_for_retry") as mock_dlq:
            result = await client.search_memory("s1", "query")

        assert result.success is False
        assert result.error_code == "ZEP_UNAVAILABLE"
        assert result.retryable is True
        mock_dlq.assert_called_once()


# ===========================================================================
# TestAddFacts
# ===========================================================================

class TestAddFacts:
    """Verify add_facts: chunking, empty list, and degraded mode."""

    @pytest.mark.asyncio
    async def test_add_facts_chunks(self):
        """75 facts are sent in 2 chunks (50 + 25)."""
        mock_zep = _make_mock_zep_client()
        mock_zep_module = MagicMock()
        # Mock the Message constructor
        mock_zep_module.Message = MagicMock(side_effect=lambda **kw: f"Message({kw.get('content', '')})")

        with patch.dict("sys.modules", {"zep_cloud": mock_zep_module}):
            with patch("packages.memory.client.get_settings"):
                pass  # Not needed — api_key passed directly below

        # Manually construct client with mocked zep
        with patch.dict("sys.modules", {"zep_cloud": MagicMock(
            AsyncZep=MagicMock(return_value=mock_zep),
            Message=MagicMock(side_effect=lambda role, content, metadata=None: {"role": role, "content": content}),
        )}):
            client = AsyncZepMemoryClient(api_key="key")
            facts = [{"fact": f"fact-{i}"} for i in range(75)]
            await client.add_facts("session_1", facts)

        assert mock_zep.thread.add_messages.call_count == 2

    @pytest.mark.asyncio
    async def test_add_facts_empty_list(self):
        """Empty facts list does not make any API call."""
        mock_zep = _make_mock_zep_client()

        with patch.dict("sys.modules", {"zep_cloud": MagicMock(
            AsyncZep=MagicMock(return_value=mock_zep),
            Message=MagicMock(),
        )}):
            client = AsyncZepMemoryClient(api_key="key")
            await client.add_facts("session_1", [])

        mock_zep.thread.add_messages.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_facts_no_client(self):
        """When _client is None, add_facts returns immediately without error."""
        mock_get_settings = MagicMock()
        mock_get_settings.return_value.ZEP_API_KEY = ""

        with patch("packages.memory.client.get_settings", mock_get_settings):
            client = AsyncZepMemoryClient()

        # Should not raise
        await client.add_facts("session_1", [{"fact": "some fact"}])


# ===========================================================================
# TestWithRetryAsync
# ===========================================================================

class TestWithRetryAsync:
    """Verify the @with_retry_async decorator behaviour."""

    @pytest.mark.asyncio
    async def test_with_retry_async_success_first(self):
        """No retry needed when first call succeeds."""
        call_count = 0

        @with_retry_async
        async def flaky_operation():
            nonlocal call_count
            call_count += 1
            return "ok"

        with patch("packages.memory.client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await flaky_operation()

        assert result == "ok"
        assert call_count == 1
        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_with_retry_async_success_after_failures(self):
        """Succeeds after 1-2 failures. Delays are [1, 3]."""
        call_count = 0

        @with_retry_async
        async def flaky_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("temporary failure")
            return "ok"

        sleep_calls = []

        async def fake_sleep(delay):
            sleep_calls.append(delay)

        with patch("packages.memory.client.asyncio.sleep", side_effect=fake_sleep):
            result = await flaky_operation()

        assert result == "ok"
        assert call_count == 3
        assert sleep_calls == [1, 3]

    @pytest.mark.asyncio
    async def test_with_retry_async_all_fail(self):
        """Raises ZepRetryExhaustedError after 4 attempts. Sleep delays: [1, 3, 9]."""
        call_count = 0

        @with_retry_async
        async def always_fail():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("permanent failure")

        sleep_calls = []

        async def fake_sleep(delay):
            sleep_calls.append(delay)

        with patch("packages.memory.client.asyncio.sleep", side_effect=fake_sleep):
            with pytest.raises(ZepRetryExhaustedError):
                await always_fail()

        assert call_count == 4  # 3 retries + 1 final attempt
        assert sleep_calls == [1, 3, 9]


# ===========================================================================
# TestCreateUserAndSession
# ===========================================================================

class TestCreateUserAndSession:
    """Verify create_user and create_session return early when _client is None."""

    @pytest.mark.asyncio
    async def test_create_user_no_client(self):
        """create_user returns immediately when _client is None."""
        mock_get_settings = MagicMock()
        mock_get_settings.return_value.ZEP_API_KEY = ""

        with patch("packages.memory.client.get_settings", mock_get_settings):
            client = AsyncZepMemoryClient()

        # Should not raise — returns None silently
        result = await client.create_user("user_123", {"purpose": "test"})
        assert result is None

    @pytest.mark.asyncio
    async def test_create_session_no_client(self):
        """create_session returns immediately when _client is None."""
        mock_get_settings = MagicMock()
        mock_get_settings.return_value.ZEP_API_KEY = ""

        with patch("packages.memory.client.get_settings", mock_get_settings):
            client = AsyncZepMemoryClient()

        # Should not raise — returns None silently
        result = await client.create_session("session_123", "user_123")
        assert result is None


# ===========================================================================
# TestClearCache
# ===========================================================================

class TestClearCache:
    """Verify clear_cache empties the _query_cache dict."""

    def test_clear_cache(self):
        """clear_cache() empties the _query_cache dict."""
        mock_get_settings = MagicMock()
        mock_get_settings.return_value.ZEP_API_KEY = ""

        with patch("packages.memory.client.get_settings", mock_get_settings):
            client = AsyncZepMemoryClient()

        # Seed the cache
        client._query_cache[("s1", "q1", 5)] = [{"fact": "a"}]
        client._query_cache[("s2", "q2", 10)] = [{"fact": "b"}]
        assert len(client._query_cache) == 2

        client.clear_cache()
        assert client._query_cache == {}

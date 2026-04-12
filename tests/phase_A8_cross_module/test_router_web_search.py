"""Tests for packages/router/web_search.py — Web search integration."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestSearchResult:
    """Tests for the SearchResult dataclass."""

    def test_creation(self):
        from packages.router.web_search import SearchResult
        r = SearchResult(
            url="https://example.com",
            title="Example",
            snippet="A test page",
            host_name="example.com",
            rank=1,
        )
        assert r.url == "https://example.com"
        assert r.title == "Example"
        assert r.snippet == "A test page"
        assert r.rank == 1
        assert r.date == ""
        assert r.favicon == ""

    def test_default_values(self):
        from packages.router.web_search import SearchResult
        r = SearchResult(
            url="", title="", snippet="", host_name="", rank=0,
        )
        assert r.date == ""
        assert r.favicon == ""

    def test_to_dict(self):
        from packages.router.web_search import SearchResult
        r = SearchResult(
            url="https://example.com",
            title="Example",
            snippet="A test page",
            host_name="example.com",
            rank=1,
            date="2024-01-01",
            favicon="/favicon.ico",
        )
        d = r.to_dict()
        assert isinstance(d, dict)
        assert d["url"] == "https://example.com"
        assert d["title"] == "Example"
        assert d["rank"] == 1
        assert d["date"] == "2024-01-01"
        assert d["favicon"] == "/favicon.ico"
        assert len(d) == 7  # all fields


class TestWebSearchClientInit:
    """Tests for WebSearchClient initialization."""

    def test_default_rate_limit(self):
        from packages.router.web_search import WebSearchClient
        client = WebSearchClient()
        assert client._rate_limit_per_second == 2.0
        assert client._zai is None

    def test_custom_rate_limit(self):
        from packages.router.web_search import WebSearchClient
        client = WebSearchClient(rate_limit_per_second=5.0)
        assert client._rate_limit_per_second == 5.0

    def test_semaphore_size(self):
        from packages.router.web_search import WebSearchClient
        client = WebSearchClient(rate_limit_per_second=3.0)
        assert client._semaphore._value == 6  # int(3.0 * 2)

    def test_last_search_time_initially_zero(self):
        from packages.router.web_search import WebSearchClient
        client = WebSearchClient()
        assert client._last_search_time == 0.0


class TestWebSearchClientAsync:
    """Tests for WebSearchClient async methods."""

    @pytest.mark.asyncio
    async def test_context_manager_init(self):
        from packages.router.web_search import WebSearchClient
        client = WebSearchClient()
        # _init_client will fail since no SDK, but context manager should still work
        await client._init_client()
        assert client._zai is None  # graceful degradation

    @pytest.mark.asyncio
    async def test_search_without_sdk_returns_empty(self):
        from packages.router.web_search import WebSearchClient
        client = WebSearchClient()
        client._zai = None
        results = await client.search("test query", num_results=5)
        assert results == []

    @pytest.mark.asyncio
    async def test_search_with_results(self):
        from packages.router.web_search import WebSearchClient
        client = WebSearchClient()
        mock_zai = MagicMock()
        mock_zai.functions.invoke = AsyncMock(return_value=[
            {
                "url": "https://example.com",
                "name": "Example Page",
                "snippet": "Test snippet",
                "host_name": "example.com",
                "rank": 1,
                "date": "2024-01-01",
                "favicon": "/favicon.ico",
            },
            {
                "url": "https://other.com",
                "title": "Other Page",
                "snippet": "Other snippet",
                "host_name": "other.com",
                "rank": 2,
            },
        ])
        client._zai = mock_zai

        results = await client.search("test query", num_results=5)
        assert len(results) == 2
        assert results[0].url == "https://example.com"
        assert results[0].title == "Example Page"  # name field used
        assert results[1].title == "Other Page"  # title field used

    @pytest.mark.asyncio
    async def test_search_handles_exception(self):
        from packages.router.web_search import WebSearchClient
        client = WebSearchClient()
        mock_zai = MagicMock()
        mock_zai.functions.invoke = AsyncMock(side_effect=Exception("API error"))
        client._zai = mock_zai
        results = await client.search("test query")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_handles_non_list_response(self):
        from packages.router.web_search import WebSearchClient
        client = WebSearchClient()
        mock_zai = MagicMock()
        mock_zai.functions.invoke = AsyncMock(return_value="not a list")
        client._zai = mock_zai
        results = await client.search("test query")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_skips_non_dict_items(self):
        from packages.router.web_search import WebSearchClient
        client = WebSearchClient()
        mock_zai = MagicMock()
        mock_zai.functions.invoke = AsyncMock(return_value=[
            {"url": "https://good.com", "name": "Good", "snippet": "", "host_name": "good.com", "rank": 1},
            "not a dict",
            {"url": "https://also.com", "name": "Also", "snippet": "", "host_name": "also.com", "rank": 2},
        ])
        client._zai = mock_zai
        results = await client.search("test")
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_multi_search_sequential(self):
        from packages.router.web_search import WebSearchClient
        client = WebSearchClient()
        client._zai = None  # will return empty
        results = await client.multi_search(
            ["query1", "query2", "query3"],
            num_per_query=3,
            delay_between=0,  # no delay for tests
        )
        assert len(results) == 3
        assert all(v == [] for v in results.values())

    @pytest.mark.asyncio
    async def test_multi_search_handles_individual_failure(self):
        from packages.router.web_search import WebSearchClient
        client = WebSearchClient()

        call_count = 0

        async def mock_search(query, num_results):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise Exception("Search failed")
            return []

        with patch.object(client, "search", side_effect=mock_search):
            results = await client.multi_search(
                ["q1", "q2", "q3"],
                delay_between=0,
            )
        assert len(results) == 3
        assert results["q2"] == []

    @pytest.mark.asyncio
    async def test_multi_search_parallel(self):
        from packages.router.web_search import WebSearchClient
        client = WebSearchClient()
        client._zai = None
        results = await client.multi_search_parallel(["q1", "q2"])
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_multi_search_parallel_handles_exception(self):
        from packages.router.web_search import WebSearchClient
        client = WebSearchClient()
        mock_zai = MagicMock()
        mock_zai.functions.invoke = AsyncMock(side_effect=Exception("fail"))
        client._zai = mock_zai
        # search returns [] on exception, so parallel search will get empty lists
        results = await client.multi_search_parallel(["q1"])
        assert results["q1"] == []

"""
Phase A.5 — ExaResearchClient unit tests.

Tests cover init (eager settings loading, lazy client init),
_get_client caching, search_trending (success, empty, no-key, API error,
snippet truncation), and build_discovery_context (dedup, all-fail, no card_id,
result cap).

All tests are fully mocked — no real Exa API calls.
"""

from unittest.mock import MagicMock, patch, call

import pytest

from packages.core.operation_result import ErrorSeverity
from tests.phase_A5_exa.conftest import make_settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(api_key: str = "test-key"):
    """Create an ExaResearchClient with get_settings patched."""
    with patch("packages.integrations.exa.client.get_settings") as mock_settings:
        mock_settings.return_value = make_settings(EXA_API_KEY=api_key)
        from packages.integrations.exa.client import ExaResearchClient
        return ExaResearchClient()


def _make_mock_result(title="Test Article", url="https://example.com",
                      text="Some snippet text", published_date="2024-01-15"):
    """Create a mock Exa search result object."""
    r = MagicMock()
    r.title = title
    r.url = url
    r.text = text
    r.published_date = published_date
    return r


def _make_mock_response(results=None):
    """Create a mock Exa API response with a .results list."""
    resp = MagicMock()
    resp.results = results or []
    return resp


# ===========================================================================
# TestExaClientInit
# ===========================================================================

class TestExaClientInit:
    """Tests for ExaResearchClient.__init__."""

    def test_init_loads_api_key(self):
        """Client loads EXA_API_KEY from settings on init."""
        with patch("packages.integrations.exa.client.get_settings") as mock_settings:
            mock_settings.return_value = make_settings(EXA_API_KEY="my-secret-key")
            from packages.integrations.exa.client import ExaResearchClient
            client = ExaResearchClient()

        assert client._api_key == "my-secret-key"
        mock_settings.assert_called_once()

    def test_client_lazy_init(self):
        """_client is None after init; only initialised when _get_client() is called."""
        client = _make_client(api_key="test-key")
        assert client._client is None


# ===========================================================================
# TestGetClient
# ===========================================================================

class TestGetClient:
    """Tests for ExaResearchClient._get_client."""

    def test_get_client_with_api_key(self):
        """When _api_key is set, lazy init creates an Exa client."""
        client = _make_client(api_key="test-key")
        mock_exa_cls = MagicMock()

        with patch.dict("sys.modules", {"exa_py": MagicMock(Exa=mock_exa_cls)}):
            result = client._get_client()

        mock_exa_cls.assert_called_once_with(api_key="test-key")
        assert result is not None

    def test_get_client_no_api_key(self):
        """When _api_key is empty, _get_client returns None."""
        client = _make_client(api_key="")
        result = client._get_client()
        assert result is None

    def test_get_client_caches(self):
        """Second call to _get_client returns the same cached instance."""
        client = _make_client(api_key="test-key")
        mock_exa_instance = MagicMock()

        # Manually set _client to a known instance
        client._client = mock_exa_instance

        result1 = client._get_client()
        result2 = client._get_client()

        assert result1 is result2
        assert result1 is mock_exa_instance


# ===========================================================================
# TestSearchTrending
# ===========================================================================

class TestSearchTrending:
    """Tests for ExaResearchClient.search_trending."""

    def test_search_trending_success(self):
        """Returns OperationResult.ok with list of dicts containing expected keys."""
        client = _make_client(api_key="test-key")
        mock_exa = MagicMock()
        client._client = mock_exa

        mock_exa.search_and_contents.return_value = _make_mock_response([
            _make_mock_result(
                title="AI in Pakistan",
                url="https://example.com/ai-pk",
                text="Pakistan is adopting AI rapidly.",
                published_date="2024-06-01",
            ),
            _make_mock_result(
                title="Tech Growth 2024",
                url="https://example.com/tech",
                text="Technology sector grows.",
                published_date="2024-05-20",
            ),
        ])

        result = client.search_trending("Pakistan AI", num_results=5)

        assert result.success is True
        assert len(result.data) == 2

        item = result.data[0]
        assert item["title"] == "AI in Pakistan"
        assert item["url"] == "https://example.com/ai-pk"
        assert "snippet" in item
        assert "published_date" in item

    def test_search_trending_empty_results(self):
        """When API returns no results, returns OperationResult.ok with empty list."""
        client = _make_client(api_key="test-key")
        mock_exa = MagicMock()
        client._client = mock_exa

        mock_exa.search_and_contents.return_value = _make_mock_response([])

        result = client.search_trending("obscure topic", num_results=3)

        assert result.success is True
        assert result.data == []

    def test_search_trending_no_api_key(self):
        """When _api_key is empty, returns OperationResult.fail with EXA_NOT_CONFIGURED."""
        client = _make_client(api_key="")

        result = client.search_trending("test query")

        assert result.success is False
        assert result.error_code == "EXA_NOT_CONFIGURED"
        assert result.severity == ErrorSeverity.WARNING

    def test_search_trending_api_error(self):
        """When API raises exception, returns fail with EXA_SEARCH_FAILED and retryable=True."""
        client = _make_client(api_key="test-key")
        mock_exa = MagicMock()
        client._client = mock_exa

        mock_exa.search_and_contents.side_effect = Exception("API rate limit exceeded")

        with patch("packages.integrations.exa.client.queue_for_retry") as mock_dlq:
            result = client.search_trending("test query")

        assert result.success is False
        assert result.error_code == "EXA_SEARCH_FAILED"
        assert result.retryable is True
        assert "API rate limit exceeded" in result.error_message

        # Verify queue_for_retry was called
        mock_dlq.assert_called_once()
        call_kwargs = mock_dlq.call_args[1]
        assert call_kwargs["operation"] == "exa_search_failed"
        assert call_kwargs["error_code"] == "EXA_SEARCH_FAILED"

    def test_search_trending_truncates_snippet(self):
        """Snippet is truncated to first 500 chars if longer."""
        client = _make_client(api_key="test-key")
        mock_exa = MagicMock()
        client._client = mock_exa

        long_text = "A" * 600
        mock_exa.search_and_contents.return_value = _make_mock_response([
            _make_mock_result(text=long_text),
        ])

        result = client.search_trending("test", num_results=1)

        assert result.success is True
        assert len(result.data[0]["snippet"]) == 500

    def test_search_trending_skips_empty_snippet(self):
        """Results with empty/whitespace text are excluded from output."""
        client = _make_client(api_key="test-key")
        mock_exa = MagicMock()
        client._client = mock_exa

        mock_exa.search_and_contents.return_value = _make_mock_response([
            _make_mock_result(text="   "),  # whitespace only
            _make_mock_result(text=None),    # None text
            _make_mock_result(text="Valid snippet"),
        ])

        result = client.search_trending("test", num_results=3)

        assert result.success is True
        assert len(result.data) == 1
        assert result.data[0]["snippet"] == "Valid snippet"

    def test_search_trending_uses_neural_search(self):
        """Verify search_and_contents is called with type='neural'."""
        client = _make_client(api_key="test-key")
        mock_exa = MagicMock()
        client._client = mock_exa

        mock_exa.search_and_contents.return_value = _make_mock_response([])

        client.search_trending("Pakistan economy", num_results=5, days_back=14)

        mock_exa.search_and_contents.assert_called_once()
        call_kwargs = mock_exa.search_and_contents.call_args[1]
        assert call_kwargs["type"] == "neural"
        assert call_kwargs["num_results"] == 5
        assert call_kwargs["text"] is True


# ===========================================================================
# TestBuildDiscoveryContext
# ===========================================================================

class TestBuildDiscoveryContext:
    """Tests for ExaResearchClient.build_discovery_context."""

    def test_build_discovery_context_success(self):
        """Runs 3 search queries and returns (context_str, results_list)."""
        client = _make_client(api_key="test-key")

        mock_result = {
            "title": "Pakistan AI News",
            "url": "https://example.com/1",
            "snippet": "AI developments in Pakistan.",
            "published_date": "2024-06-01",
        }

        with patch.object(client, "search_trending") as mock_search:
            # All 3 searches succeed with the same result
            mock_search.return_value = __import__(
                "packages.core.operation_result", fromlist=["OperationResult"]
            ).OperationResult.ok([mock_result.copy()])

            context_str, results = client.build_discovery_context(
                seed_query="AI regulation",
            )

        assert isinstance(context_str, str)
        assert "REAL-TIME WEB INTELLIGENCE" in context_str
        assert len(results) >= 1
        # Called 3 times (one per search angle)
        assert mock_search.call_count == 3

    def test_build_discovery_context_deduplicates(self):
        """When multiple searches return the same URL, results are deduplicated."""
        client = _make_client(api_key="test-key")

        same_url_result = {
            "title": "Shared Article",
            "url": "https://example.com/same",
            "snippet": "Dedup test.",
            "published_date": "2024-06-01",
        }

        with patch.object(client, "search_trending") as mock_search:
            from packages.core.operation_result import OperationResult
            mock_search.return_value = OperationResult.ok([same_url_result.copy()])

            context_str, results = client.build_discovery_context(
                seed_query="dedup test",
            )

        # 3 searches return same URL → should be deduplicated to 1
        assert len(results) == 1
        assert results[0]["url"] == "https://example.com/same"

    def test_build_discovery_context_all_fail(self):
        """When all 3 searches fail, returns ('', [])."""
        client = _make_client(api_key="test-key")

        with patch.object(client, "search_trending") as mock_search:
            from packages.core.operation_result import OperationResult
            mock_search.return_value = OperationResult.fail(
                message="API error",
                code="EXA_SEARCH_FAILED",
            )

            context_str, results = client.build_discovery_context(
                seed_query="fail test",
            )

        assert context_str == ""
        assert results == []

    def test_build_discovery_context_no_card_id(self):
        """When card_id is None, report_thought is never called."""
        client = _make_client(api_key="test-key")

        mock_result = {
            "title": "News",
            "url": "https://example.com/n",
            "snippet": "Content.",
            "published_date": "2024-06-01",
        }

        with patch.object(client, "search_trending") as mock_search, \
             patch("packages.core.thoughts.report_thought") as mock_thought:
            from packages.core.operation_result import OperationResult
            mock_search.return_value = OperationResult.ok([mock_result.copy()])

            client.build_discovery_context(
                seed_query="no card",
                card_id=None,
            )

        mock_thought.assert_not_called()

    def test_build_discovery_context_with_card_id_calls_report(self):
        """When card_id is provided, report_thought is called for each search."""
        client = _make_client(api_key="test-key")

        mock_result = {
            "title": "News",
            "url": "https://example.com/n",
            "snippet": "Content.",
            "published_date": "2024-06-01",
        }

        with patch.object(client, "search_trending") as mock_search, \
             patch("packages.core.thoughts.report_thought") as mock_thought:
            from packages.core.operation_result import OperationResult
            mock_search.return_value = OperationResult.ok([mock_result.copy()])

            client.build_discovery_context(
                seed_query="with card",
                card_id="card-123",
            )

        # report_thought should be called: 3 (search start) + 3 (search results) + 1 (final summary) = 7
        assert mock_thought.call_count == 7
        # First call is the "🔍 Exa search [1/3]" thought
        first_call = mock_thought.call_args_list[0]
        assert first_call[1]["card_id"] == "card-123"
        assert first_call[1]["agent_name"] == "topic_finder"

    def test_build_discovery_context_caps_results(self):
        """Results are capped at 10 unique items."""
        client = _make_client(api_key="test-key")

        # Generate 5 unique results per search angle (15 total, 3 angles)
        def make_results(offset):
            return [
                {
                    "title": f"Article {offset + i}",
                    "url": f"https://example.com/{offset + i}",
                    "snippet": f"Content {offset + i}.",
                    "published_date": "2024-06-01",
                }
                for i in range(5)
            ]

        with patch.object(client, "search_trending") as mock_search:
            from packages.core.operation_result import OperationResult

            call_idx = 0
            def side_effect(*args, **kwargs):
                nonlocal call_idx
                offset = call_idx * 5
                call_idx += 1
                return OperationResult.ok(make_results(offset))

            mock_search.side_effect = side_effect

            context_str, results = client.build_discovery_context(
                seed_query="cap test",
            )

        # unique_results list contains all 15 (dedup only, no cap)
        assert len(results) == 15
        # Context string is capped at 10 source entries
        assert context_str.count("[Source ") == 10

    def test_build_discovery_context_partial_success(self):
        """When 1 of 3 searches succeeds, still returns valid context."""
        client = _make_client(api_key="test-key")

        mock_result = {
            "title": "Only Result",
            "url": "https://example.com/only",
            "snippet": "Partial success.",
            "published_date": "2024-06-01",
        }

        with patch.object(client, "search_trending") as mock_search:
            from packages.core.operation_result import OperationResult

            # First fails, second succeeds, third fails
            mock_search.side_effect = [
                OperationResult.fail(message="fail", code="EXA_SEARCH_FAILED"),
                OperationResult.ok([mock_result.copy()]),
                OperationResult.fail(message="fail", code="EXA_SEARCH_FAILED"),
            ]

            context_str, results = client.build_discovery_context(
                seed_query="partial",
            )

        assert len(results) == 1
        assert "REAL-TIME WEB INTELLIGENCE" in context_str

    def test_build_discovery_context_context_format(self):
        """Context string has expected format with Source entries."""
        client = _make_client(api_key="test-key")

        mock_result = {
            "title": "Test Title",
            "url": "https://example.com/test",
            "snippet": "Important info here.",
            "published_date": "2024-03-15",
        }

        with patch.object(client, "search_trending") as mock_search:
            from packages.core.operation_result import OperationResult
            mock_search.return_value = OperationResult.ok([mock_result.copy()])

            context_str, results = client.build_discovery_context(
                seed_query="format test",
            )

        assert "[Source 1] Test Title (2024-03-15)" in context_str
        assert "URL: https://example.com/test" in context_str
        assert "Key Info: Important info here." in context_str

    def test_build_discovery_context_no_published_date(self):
        """Context string handles missing published_date gracefully."""
        client = _make_client(api_key="test-key")

        mock_result = {
            "title": "No Date Article",
            "url": "https://example.com/nodate",
            "snippet": "No date content.",
            "published_date": None,
        }

        with patch.object(client, "search_trending") as mock_search:
            from packages.core.operation_result import OperationResult
            mock_search.return_value = OperationResult.ok([mock_result.copy()])

            context_str, results = client.build_discovery_context(
                seed_query="nodate test",
            )

        # Should not have "(None)" in the context
        assert "(None)" not in context_str
        assert "[Source 1] No Date Article\n" in context_str

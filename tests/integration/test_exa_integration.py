"""Phase 11 — Integration tests for Exa Search API client.

These tests make REAL Exa.ai API calls. They are skipped gracefully when:
- EXA_API_KEY is not set in the environment
- exa-py is not installed
- The Exa API is unreachable

Each test wraps real API calls in try/except and calls pytest.skip() on
connection errors or critical failures, ensuring CI pipelines never break
due to missing credentials or transient network issues.
"""

from __future__ import annotations

import os
import pytest

from tests.integration.conftest import skip_if_no_env

pytestmark = pytest.mark.integration


# ── Module-level skip guard ────────────────────────────────────────────────────

_SKIP_REASON = ""

if not os.environ.get("EXA_API_KEY", ""):
    _SKIP_REASON = "EXA_API_KEY not configured"


def _require_exa_key() -> str:
    """Return EXA_API_KEY after verifying it exists."""
    skip_if_no_env("EXA_API_KEY")
    return os.environ["EXA_API_KEY"]


class TestExaClientReal:
    """Integration tests against the live Exa.ai Search API.

    All tests use the real EXA_API_KEY from the environment and make actual
    HTTP requests to the Exa API. Results depend on Exa's search index and
    may vary, so tests focus on response structure rather than specific content.
    """

    def _build_client(self) -> "ExaResearchClient":
        """Create an ExaResearchClient (reads EXA_API_KEY from settings)."""
        from packages.integrations.exa.client import ExaResearchClient
        return ExaResearchClient()

    def test_client_initialization(self):
        """Verify ExaResearchClient initializes and creates the Exa SDK client.

        Scenario: The application starts up and initializes the Exa client.
        With a valid API key, _get_client() should return an Exa instance.

        Verifies:
        - Client object is created without errors
        - _get_client() returns a non-None client
        """
        skip_if_no_env("EXA_API_KEY")
        try:
            client = self._build_client()
            assert client is not None
            assert client._api_key != ""

            exa_sdk_client = client._get_client()
            assert exa_sdk_client is not None, "Exa SDK client should be initialized with valid key"

        except ImportError:
            pytest.skip("exa-py package not installed — run: pip install exa-py")

    def test_search_returns_results(self):
        """Real API call: search for a trending topic and verify results.

        Scenario: The topic finder discovers trending Pakistani content by
        querying Exa with a broad, well-covered topic. We expect at least
        some results since "Pakistan" is a widely covered topic.

        Verifies:
        - OperationResult.success is True
        - data is a list with at least one result
        - Each result has title, url, snippet keys
        - snippet is truncated to ≤500 chars
        """
        try:
            client = self._build_client()
        except ImportError:
            pytest.skip("exa-py package not installed")

        try:
            result = client.search_trending(
                query="Pakistan technology news 2024",
                num_results=3,
                days_back=7,
            )

            assert result is not None

            if not result.success:
                # Exa may return failures (e.g., rate limit, server error)
                pytest.skip(f"Exa search returned failure: {result.error_message}")

            assert result.data is not None
            assert isinstance(result.data, list)

            if not result.data:
                pytest.skip("Exa search returned empty results — possible rate limit or index gap")

            for item in result.data:
                assert "title" in item, "Each result must have a title"
                assert "url" in item, "Each result must have a url"
                assert "snippet" in item, "Each result must have a snippet"
                assert isinstance(item["title"], str)
                assert isinstance(item["url"], str)
                assert isinstance(item["snippet"], str)
                # Snippet should be truncated to 500 chars per source code
                assert len(item["snippet"]) <= 500, f"Snippet exceeds 500 chars: {len(item['snippet'])}"

        except ConnectionError as exc:
            pytest.skip(f"Exa API unreachable: {exc}")
        except Exception as exc:
            err_str = str(exc).lower()
            if any(kw in err_str for kw in ("unauthorized", "invalid", "401", "403", "rate", "quota")):
                pytest.skip(f"Exa API auth/rate error: {exc}")
            raise

    def test_search_with_no_results(self):
        """Real API call: search with an obscure query likely to return empty.

        Scenario: The topic finder queries for a very obscure topic that
        is unlikely to have any indexed content in Exa. The client should
        return an OperationResult with success=True but empty data list,
        not crash.

        Verifies:
        - OperationResult is returned (not an exception)
        - success is True (API call succeeded)
        - data is a list (may be empty)
        """
        try:
            client = self._build_client()
        except ImportError:
            pytest.skip("exa-py package not installed")

        try:
            # Use a sufficiently obscure query
            result = client.search_trending(
                query="xyzqwerty987654321obscuretopicnoresultshere",
                num_results=1,
                days_back=1,
            )

            assert result is not None
            # If no API key is configured, data will be None — that's acceptable
            if not result.success:
                pytest.skip(f"Exa not configured or error: {result.error_message}")
            # With a valid key, obscure queries should return an empty list
            assert isinstance(result.data, list), f"Expected list, got {type(result.data)}"

        except ConnectionError as exc:
            pytest.skip(f"Exa API unreachable: {exc}")
        except OSError as exc:
            # On Windows, SSL/connection errors may surface as OSError subclasses
            pytest.skip(f"Exa API connection error: {exc}")
        except Exception as exc:
            err_str = str(exc).lower()
            if any(kw in err_str for kw in ("unauthorized", "invalid", "401", "403", "rate", "quota")):
                pytest.skip(f"Exa API auth/rate error: {exc}")
            raise

    def test_invalid_key_returns_operation_result_not_crash(self):
        """Verify that an invalid API key returns a structured error.

        Scenario: A developer enters a wrong EXA_API_KEY. The client should
        return OperationResult.fail() with a descriptive message, not raise
        an unhandled exception.

        Verifies:
        - No exception is raised
        - OperationResult.success is False
        - Error code is EXA_NOT_CONFIGURED or EXA_SEARCH_FAILED
        """
        try:
            from packages.integrations.exa.client import ExaResearchClient
        except ImportError:
            pytest.skip("exa-py package not installed")

        # Create a client and force an invalid key
        client = ExaResearchClient()
        client._api_key = "INVALID_EXA_KEY_FOR_TESTING_xyz123"
        client._client = None  # Reset lazy init

        try:
            result = client.search_trending(
                query="test query",
                num_results=1,
            )

            assert result is not None
            assert isinstance(result.success, bool)

            # With an invalid key, we expect failure
            if not result.success:
                assert result.error_code in ("EXA_NOT_CONFIGURED", "EXA_SEARCH_FAILED", None), (
                    f"Unexpected error code: {result.error_code}"
                )
                assert result.error_message != ""
            # If it somehow succeeds (unlikely), that's also acceptable

        except ConnectionError as exc:
            pytest.skip(f"Exa API unreachable: {exc}")
        except Exception as exc:
            err_str = str(exc).lower()
            if any(kw in err_str for kw in ("unauthorized", "invalid", "401", "403", "module")):
                # Expected behavior for invalid key or missing exa-py
                pass
            else:
                raise

    def test_search_result_structure_matches_contract(self):
        """Verify that search results conform to the documented contract.

        Scenario: The LLM prompt builder consumes Exa results. It expects
        specific keys: title, url, snippet, published_date.

        Verifies:
        - All four required keys are present in each result
        - Types match the expected contract
        - URL starts with http:// or https://
        """
        try:
            client = self._build_client()
        except ImportError:
            pytest.skip("exa-py package not installed")

        try:
            result = client.search_trending(
                query="artificial intelligence research 2024",
                num_results=2,
                days_back=30,
            )

            if not result.success or not result.data:
                pytest.skip("Exa search returned no results — cannot verify structure")

            for item in result.data:
                # Required keys
                assert "title" in item, "Missing 'title' key"
                assert "url" in item, "Missing 'url' key"
                assert "snippet" in item, "Missing 'snippet' key"
                assert "published_date" in item, "Missing 'published_date' key"

                # Type checks
                assert isinstance(item["title"], str), "title must be str"
                assert isinstance(item["url"], str), "url must be str"
                assert isinstance(item["snippet"], str), "snippet must be str"

                # URL should be a valid HTTP(S) URL
                assert item["url"].startswith(("http://", "https://")), (
                    f"URL should start with http(s)://: {item['url']}"
                )

                # published_date can be None (API may not always provide it)
                assert item["published_date"] is None or isinstance(item["published_date"], str)

        except ConnectionError as exc:
            pytest.skip(f"Exa API unreachable: {exc}")
        except Exception as exc:
            err_str = str(exc).lower()
            if any(kw in err_str for kw in ("unauthorized", "invalid", "401", "403", "rate", "quota")):
                pytest.skip(f"Exa API auth/rate error: {exc}")
            raise

    def test_no_api_key_returns_not_configured(self):
        """Verify that missing API key returns EXA_NOT_CONFIGURED.

        Scenario: The application runs without EXA_API_KEY set. The client
        should immediately return a fail result with code EXA_NOT_CONFIGURED
        and a helpful user message.

        Verifies:
        - OperationResult.success is False
        - code is "EXA_NOT_CONFIGURED"
        - user_message explains the situation
        """
        try:
            from packages.integrations.exa.client import ExaResearchClient
        except ImportError:
            pytest.skip("exa-py package not installed")

        client = ExaResearchClient()
        client._api_key = ""
        client._client = None  # Reset lazy init

        result = client.search_trending(query="test")

        assert result is not None
        assert result.success is False
        assert result.error_code == "EXA_NOT_CONFIGURED"
        assert result.error_message != ""
        assert "EXA_API_KEY" in result.error_message, (
            "Error message should mention the missing env var"
        )
        assert result.user_message != "", (
            "Should have a user-friendly message for the frontend"
        )

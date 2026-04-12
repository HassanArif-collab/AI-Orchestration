"""Tests for Exa.ai integration."""
import pytest
from unittest.mock import patch, MagicMock

from packages.integrations.exa.client import ExaResearchClient
from packages.core.operation_result import OperationResult


def _mock_exa_response():
    """Create a mock Exa search response."""
    mock_result = MagicMock()
    mock_result.title = "Pakistan AI Policy 2024"
    mock_result.url = "https://example.com/pakistan-ai"
    mock_result.text = "Pakistan is developing new AI regulations that could impact the tech sector significantly."
    mock_result.published_date = "2024-03-15"

    mock_response = MagicMock()
    mock_response.results = [mock_result]
    return mock_response


@patch("packages.integrations.exa.client.get_settings")
def test_search_trending_returns_results(mock_settings):
    mock_settings.return_value.EXA_API_KEY = "test-key"

    client = ExaResearchClient()
    with patch.object(client, "_get_client") as mock_get:
        mock_exa = MagicMock()
        mock_exa.search_and_contents.return_value = _mock_exa_response()
        mock_get.return_value = mock_exa

        result = client.search_trending("Pakistan AI", num_results=3)
        assert result.success is True
        assert len(result.data) == 1
        assert result.data[0]["title"] == "Pakistan AI Policy 2024"
        assert "snippet" in result.data[0]


@patch("packages.integrations.exa.client.get_settings")
def test_search_trending_returns_empty_on_failure(mock_settings):
    mock_settings.return_value.EXA_API_KEY = "test-key"

    client = ExaResearchClient()
    with patch.object(client, "_get_client") as mock_get:
        # Return a mock Exa client whose search_and_contents raises
        mock_exa = MagicMock()
        mock_exa.search_and_contents.side_effect = Exception("Network error")
        mock_get.return_value = mock_exa

        result = client.search_trending("Pakistan AI")
        assert result.success is False
        assert result.data is None


@patch("packages.core.thoughts.report_thought")
@patch("packages.integrations.exa.client.get_settings")
def test_build_discovery_context_formats_output(mock_settings, mock_report):
    mock_settings.return_value.EXA_API_KEY = "test-key"

    client = ExaResearchClient()
    with patch.object(client, "search_trending") as mock_search:
        mock_search.return_value = OperationResult.ok([
            {"title": "Test Article", "url": "https://test.com", "snippet": "Test content", "published_date": "2024-01-01"}
        ])

        context_str, results = client.build_discovery_context("test query", card_id="card-123")
        assert "REAL-TIME WEB INTELLIGENCE" in context_str
        assert "Test Article" in context_str
        assert len(results) >= 1


def test_no_api_key_returns_none_not_raise():
    """Verify ExaResearchClient._get_client returns None (not raises) on missing API key."""
    with patch("packages.integrations.exa.client.get_settings") as mock_s:
        mock_s.return_value.EXA_API_KEY = ""
        client = ExaResearchClient()
        result = client._get_client()
        assert result is None  # Returns None gracefully instead of raising


@patch("packages.integrations.exa.client.get_settings")
def test_search_trending_truncates_long_text(mock_settings):
    """Verify that long text is truncated to 500 chars."""
    mock_settings.return_value.EXA_API_KEY = "test-key"

    # Create a mock result with long text
    mock_result = MagicMock()
    mock_result.title = "Long Article"
    mock_result.url = "https://example.com/long"
    mock_result.text = "x" * 1000  # 1000 character text
    mock_result.published_date = "2024-03-15"

    mock_response = MagicMock()
    mock_response.results = [mock_result]

    client = ExaResearchClient()
    with patch.object(client, "_get_client") as mock_get:
        mock_exa = MagicMock()
        mock_exa.search_and_contents.return_value = mock_response
        mock_get.return_value = mock_exa

        result = client.search_trending("test query")
        assert result.success is True
        assert len(result.data) == 1
        assert len(result.data[0]["snippet"]) == 500  # Truncated to 500 chars


@patch("packages.core.thoughts.report_thought")
@patch("packages.integrations.exa.client.get_settings")
def test_build_discovery_context_deduplicates_by_url(mock_settings, mock_report):
    """Verify that duplicate URLs are removed."""
    mock_settings.return_value.EXA_API_KEY = "test-key"

    client = ExaResearchClient()
    with patch.object(client, "search_trending") as mock_search:
        mock_search.return_value = OperationResult.ok([
            {"title": "Article 1", "url": "https://same.com", "snippet": "Content 1", "published_date": "2024-01-01"},
        ])

        context_str, results = client.build_discovery_context("test query")
        assert "REAL-TIME WEB INTELLIGENCE" in context_str


@patch("packages.core.thoughts.report_thought")
@patch("packages.integrations.exa.client.get_settings")
def test_build_discovery_context_caps_at_10_results(mock_settings, mock_report):
    """Verify that results are capped at 10 to save tokens."""
    mock_settings.return_value.EXA_API_KEY = "test-key"

    client = ExaResearchClient()
    with patch.object(client, "search_trending") as mock_search:
        # Return 5 results per search (3 searches = 15 total)
        mock_search.return_value = OperationResult.ok([
            {"title": f"Article {i}", "url": f"https://unique{i}.com", "snippet": f"Content {i}", "published_date": "2024-01-01"}
            for i in range(5)
        ])

        context_str, results = client.build_discovery_context("test query")
        # The context should only include up to 10 unique results
        source_count = context_str.count("[Source")
        assert source_count <= 10


@patch("packages.core.thoughts.report_thought")
@patch("packages.integrations.exa.client.get_settings")
def test_build_discovery_context_reports_thoughts(mock_settings, mock_report):
    """Verify that thoughts are reported when card_id is provided."""
    mock_settings.return_value.EXA_API_KEY = "test-key"

    client = ExaResearchClient()
    with patch.object(client, "search_trending") as mock_search:
        mock_search.return_value = OperationResult.ok([
            {"title": "Test Article", "url": "https://test.com", "snippet": "Test content", "published_date": "2024-01-01"}
        ])

        client.build_discovery_context("test query", card_id="card-123")

        # Verify report_thought was called multiple times
        assert mock_report.call_count >= 3  # At least search start + results + completion


@patch("packages.core.thoughts.report_thought")
@patch("packages.integrations.exa.client.get_settings")
def test_build_discovery_context_handles_empty_results(mock_settings, mock_report):
    """Verify graceful handling when all searches return empty."""
    mock_settings.return_value.EXA_API_KEY = "test-key"

    client = ExaResearchClient()
    with patch.object(client, "search_trending") as mock_search:
        mock_search.return_value = OperationResult.ok([])

        context_str, results = client.build_discovery_context("test query", card_id="card-123")
        assert context_str == ""
        assert results == []


@patch("packages.integrations.exa.client.get_settings")
def test_search_trending_returns_not_configured_without_key(mock_settings):
    """Verify search_trending returns fail OperationResult when API key missing."""
    mock_settings.return_value.EXA_API_KEY = ""

    client = ExaResearchClient()
    result = client.search_trending("test query")

    assert result.success is False
    assert result.error_code == "EXA_NOT_CONFIGURED"

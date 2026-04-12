"""
Phase 15 — Web Search Integration Tests
=========================================
Tests for WebSearchClient, SearchResult, ExaResearchClient, DeepResearchEngine,
and ResearchCheckpoint.

Design:
- WebSearchClient wraps z-ai-web-dev-sdk.  The SDK is a private package; when
  not installed the client sets self._zai = None and every search returns [].
  Tests verify this graceful-degradation behaviour explicitly, and also test
  internal logic (rate limiting, multi-search dispatch, context manager)
  without requiring the SDK.
- ExaResearchClient reads EXA_API_KEY from the project .env via get_settings().
  The key IS present, so Exa tests make REAL API calls and assert real results.
  If a call fails (rate-limit, network), the test fails rather than silently
  passing.
- DeepResearch helper tests are pure logic — no API needed.
- Checkpoint tests use tmp_path.
- Rate limiting tests verify semaphore behaviour and timing.
- No tests use pytest.mark.skip.

Run:
    pytest tests/integration/test_web_search_integration.py -v
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Environment probes
# ---------------------------------------------------------------------------

SDK_AVAILABLE = False
try:
    __import__("z-ai-web-dev-sdk")
    SDK_AVAILABLE = True
except ImportError:
    pass

try:
    from packages.core.config import get_settings as _get_settings
    _s = _get_settings()
    EXA_AVAILABLE = bool(_s.EXA_API_KEY and len(_s.EXA_API_KEY) >= 10)
except Exception:
    EXA_AVAILABLE = False

# ---------------------------------------------------------------------------
# Source imports
# ---------------------------------------------------------------------------

from packages.router.web_search import WebSearchClient, SearchResult
from packages.integrations.exa.client import ExaResearchClient
from packages.content_factory.production.deep_research import (
    DeepResearchEngine,
    ResearchCheckpoint,
)
from packages.content_factory.production.models import (
    InformationType,
    PhysicalAnchor,
    ResearchDossier,
    ResearchFact,
    ValidationStatus,
    AnchorType,
    HumanCharacter,
)
from packages.core.operation_result import OperationResult


# ===================================================================
# A. SearchResult Dataclass Tests
# ===================================================================

class TestSearchResult:
    """Tests for the SearchResult dataclass."""

    def test_search_result_creation(self):
        """A1: Create SearchResult with all fields, verify attributes."""
        result = SearchResult(
            url="https://example.com/article",
            title="Test Article Title",
            snippet="This is a test snippet about Python programming.",
            host_name="example.com",
            rank=1,
            date="2024-06-15",
            favicon="https://example.com/favicon.ico",
        )
        assert result.url == "https://example.com/article"
        assert result.title == "Test Article Title"
        assert result.snippet == "This is a test snippet about Python programming."
        assert result.host_name == "example.com"
        assert result.rank == 1
        assert result.date == "2024-06-15"
        assert result.favicon == "https://example.com/favicon.ico"

    def test_search_result_to_dict(self):
        """A2: Verify to_dict() returns correct dictionary with all fields."""
        result = SearchResult(
            url="https://example.com/article",
            title="Test Article Title",
            snippet="This is a test snippet about Python programming.",
            host_name="example.com",
            rank=1,
            date="2024-06-15",
            favicon="https://example.com/favicon.ico",
        )
        d = result.to_dict()
        assert isinstance(d, dict)
        assert d["url"] == "https://example.com/article"
        assert d["title"] == "Test Article Title"
        assert d["snippet"] == "This is a test snippet about Python programming."
        assert d["host_name"] == "example.com"
        assert d["rank"] == 1
        assert d["date"] == "2024-06-15"
        assert d["favicon"] == "https://example.com/favicon.ico"
        assert set(d.keys()) == {"url", "title", "snippet", "host_name", "rank", "date", "favicon"}

    def test_search_result_default_optional_fields(self):
        """A3: Verify optional fields date and favicon default to empty string."""
        result = SearchResult(
            url="https://example.com",
            title="Title",
            snippet="Snippet",
            host_name="example.com",
            rank=1,
        )
        assert result.date == ""
        assert result.favicon == ""
        d = result.to_dict()
        assert d["date"] == ""
        assert d["favicon"] == ""


# ===================================================================
# B. WebSearchClient Single Search Tests
# ===================================================================

class TestWebSearchClientSingle:
    """Tests for WebSearchClient single-query search.

    z-ai-web-dev-sdk is a private package.  When it is not installed the
    client gracefully returns [].  Tests detect this by inspecting
    client._zai after __aenter__ and assert the correct behaviour for
    each scenario.
    """

    @pytest.mark.asyncio
    async def test_web_search_basic_query(self):
        """B1: Search returns correct type and structure based on SDK state."""
        async with WebSearchClient() as client:
            sdk_ready = client._zai is not None
            results = await client.search("Python programming language", num_results=5)

        assert isinstance(results, list), f"search() must return list, got {type(results)}"
        assert len(results) <= 5, f"Requested 5 results, got {len(results)}"

        if sdk_ready:
            assert len(results) > 0, (
                "SDK initialised but search returned 0 results — check SDK health"
            )
            for r in results:
                assert isinstance(r, SearchResult), f"Expected SearchResult, got {type(r)}"
                assert isinstance(r.url, str)
                assert isinstance(r.title, str)
                assert isinstance(r.snippet, str)
                assert r.url or r.title or r.snippet, (
                    "SearchResult must have url, title, or snippet populated"
                )
        else:
            # SDK not installed — graceful degradation: empty list
            assert results == [], (
                "SDK not installed — client should return empty list"
            )

    @pytest.mark.asyncio
    async def test_web_search_returns_results_with_host_name(self):
        """B2: Each result has host_name populated when SDK is ready."""
        async with WebSearchClient() as client:
            sdk_ready = client._zai is not None
            results = await client.search("OpenAI GPT models", num_results=5)

        assert isinstance(results, list)

        if sdk_ready:
            assert len(results) > 0, "SDK ready but returned 0 results"
            for r in results:
                assert isinstance(r, SearchResult)
                assert isinstance(r.host_name, str)
        else:
            assert results == [], "SDK not installed — expected empty list"

    @pytest.mark.asyncio
    async def test_web_search_respects_num_results(self):
        """B3: Request N results — assert exact behaviour based on SDK state."""
        async with WebSearchClient() as client:
            sdk_ready = client._zai is not None
            results = await client.search("Python web frameworks", num_results=3)

        assert isinstance(results, list)
        assert len(results) <= 3, f"Requested 3 results but got {len(results)}"

        if sdk_ready:
            # With SDK, a real search should return at least one result for a
            # broad topic — otherwise the SDK integration is broken.
            assert len(results) > 0, (
                "SDK ready but returned 0 results for a broad topic query"
            )
        else:
            # Without SDK, empty list is the ONLY correct response.
            assert results == [], (
                "SDK not installed — must return empty list, not partial results"
            )

    @pytest.mark.asyncio
    async def test_web_search_empty_query(self):
        """B4: Empty query returns a list; with SDK unavailable it must be empty."""
        async with WebSearchClient() as client:
            sdk_ready = client._zai is not None
            results = await client.search("", num_results=5)

        assert isinstance(results, list)

        if not sdk_ready:
            # Without SDK, even an empty query returns [] — no fake data.
            assert results == [], (
                "SDK not installed — empty query must still return empty list"
            )
        else:
            assert len(results) <= 5


# ===================================================================
# C. WebSearchClient Multi Search Tests
# ===================================================================

class TestWebSearchClientMulti:
    """Tests for WebSearchClient sequential multi-search."""

    @pytest.mark.asyncio
    async def test_multi_search_multiple_queries(self):
        """C1: All query keys present in result dict, values are lists."""
        queries = ["Python programming", "JavaScript frameworks", "Rust language"]
        async with WebSearchClient() as client:
            sdk_ready = client._zai is not None
            results = await client.multi_search(queries, num_per_query=3, delay_between=0.3)

        assert isinstance(results, dict)
        assert set(results.keys()) == set(queries), "All query keys must be in the result"
        for query, result_list in results.items():
            assert isinstance(result_list, list), (
                f"Results for '{query}' should be a list, got {type(result_list)}"
            )
            if sdk_ready:
                for r in result_list:
                    assert isinstance(r, SearchResult), (
                        f"SDK ready — expected SearchResult, got {type(r)}"
                    )
            else:
                # Without SDK, every value must be exactly []
                assert result_list == [], (
                    f"SDK not installed — results for '{query}' must be []"
                )

    @pytest.mark.asyncio
    async def test_multi_search_sequential_with_delay(self):
        """C2: delay_between parameter introduces real wall-clock delay."""
        queries = ["Python basics", "Python advanced"]
        delay = 0.5
        start = time.monotonic()
        async with WebSearchClient() as client:
            results = await client.multi_search(queries, num_per_query=2, delay_between=delay)
        elapsed = time.monotonic() - start

        assert isinstance(results, dict)
        assert len(results) == 2
        # delay_between adds 0.5s between queries (1 delay for 2 queries),
        # so elapsed must reflect at least most of that delay.
        assert elapsed >= 0.3, (
            f"Expected at least 0.3s with delay_between={delay}s, "
            f"but elapsed was {elapsed:.3f}s"
        )

    @pytest.mark.asyncio
    async def test_multi_search_with_rate_limiting(self):
        """C3: Rate limiting does not crash — all queries get a dict entry."""
        queries = ["Python tutorial", "Django tutorial", "Flask tutorial"]
        async with WebSearchClient(rate_limit_per_second=0.5) as client:
            sdk_ready = client._zai is not None
            results = await client.multi_search(queries, num_per_query=2, delay_between=0.2)

        assert isinstance(results, dict)
        assert set(results.keys()) == set(queries), (
            f"Missing query keys: {set(queries) - set(results.keys())}"
        )
        for query in queries:
            assert isinstance(results[query], list)
            if not sdk_ready:
                assert results[query] == [], (
                    f"SDK not installed — results for '{query}' must be []"
                )

    @pytest.mark.asyncio
    async def test_multi_search_empty_queries_list(self):
        """C4: Empty list returns empty dict."""
        async with WebSearchClient() as client:
            results = await client.multi_search([], num_per_query=5)
        assert results == {}


# ===================================================================
# D. WebSearchClient Parallel Search Tests
# ===================================================================

class TestWebSearchClientParallel:
    """Tests for WebSearchClient parallel multi-search."""

    @pytest.mark.asyncio
    async def test_multi_search_parallel_basic(self):
        """D1: Parallel search returns dict with all query keys and list values."""
        queries = ["Python programming", "JavaScript ES2024"]
        async with WebSearchClient() as client:
            sdk_ready = client._zai is not None
            results = await client.multi_search_parallel(queries, num_per_query=3)

        assert isinstance(results, dict)
        assert set(results.keys()) == set(queries), (
            f"Missing keys: {set(queries) - set(results.keys())}"
        )
        for query, result_list in results.items():
            assert isinstance(result_list, list), (
                f"Value for '{query}' must be list, got {type(result_list)}"
            )
            if sdk_ready:
                # With SDK, results should be SearchResult instances
                for r in result_list:
                    assert isinstance(r, SearchResult), (
                        f"SDK ready — expected SearchResult, got {type(r)}"
                    )
            else:
                # Without SDK, every value must be exactly []
                assert result_list == [], (
                    f"SDK not installed — results for '{query}' must be []"
                )

    @pytest.mark.asyncio
    async def test_multi_search_parallel_same_keys_as_sequential(self):
        """D2: Sequential and parallel return the same keys and value types."""
        queries = ["Python async programming"]
        num = 3

        async with WebSearchClient() as client_seq:
            seq_results = await client_seq.multi_search(queries, num_per_query=num)

        async with WebSearchClient() as client_par:
            par_results = await client_par.multi_search_parallel(queries, num_per_query=num)

        assert set(seq_results.keys()) == set(par_results.keys()) == set(queries)

        for q in queries:
            seq_list = seq_results[q]
            par_list = par_results[q]
            assert isinstance(seq_list, list)
            assert isinstance(par_list, list)
            # Both should return the same number of results
            assert len(seq_list) == len(par_list), (
                f"Sequential returned {len(seq_list)} results for '{q}' "
                f"but parallel returned {len(par_list)}"
            )
            # Type consistency: if one has SearchResults, both must
            if seq_list:
                for r in seq_list:
                    assert isinstance(r, SearchResult)
            if par_list:
                for r in par_list:
                    assert isinstance(r, SearchResult)

    @pytest.mark.asyncio
    async def test_multi_search_parallel_handles_exceptions(self):
        """D3: Parallel search catches exceptions — all entries are lists."""
        queries = ["nonexistent_topic_xyz_12345", "another_fake_query_abc"]
        async with WebSearchClient() as client:
            sdk_ready = client._zai is not None
            results = await client.multi_search_parallel(queries, num_per_query=3)

        assert isinstance(results, dict)
        assert set(results.keys()) == set(queries)
        # All entries must be lists (even if empty from failures)
        for query, result_list in results.items():
            assert isinstance(result_list, list), (
                f"Value for '{query}' must be list even on failure, got {type(result_list)}"
            )
            if not sdk_ready:
                assert result_list == [], (
                    f"SDK not installed — results for '{query}' must be []"
                )


# ===================================================================
# E. WebSearchClient Context Manager Tests
# ===================================================================

class TestWebSearchClientContextManager:
    """Tests for WebSearchClient async context manager."""

    @pytest.mark.asyncio
    async def test_web_search_context_manager_init(self):
        """E1: async with WebSearchClient() as client works and initialises state."""
        async with WebSearchClient() as client:
            assert client is not None
            assert isinstance(client, WebSearchClient)
            # After __aenter__, _zai is either a ZAI instance or None.
            # It must have been attempted.
            assert client._zai is None or hasattr(client._zai, "functions"), (
                "After __aenter__, _zai must be None or a ZAI-like object"
            )

    @pytest.mark.asyncio
    async def test_web_search_context_manager_releases(self):
        """E2: Client can be used within context, then exits cleanly."""
        client_used = False
        async with WebSearchClient() as client:
            results = await client.search("Python", num_results=2)
            assert isinstance(results, list)
            client_used = True
        assert client_used, "Client should have been used inside context manager"


# ===================================================================
# F. ExaResearchClient Tests (REAL API calls)
# ===================================================================

class TestExaResearchClient:
    """Tests for ExaResearchClient using REAL API calls.

    EXA_API_KEY is loaded from the project .env file via get_settings().
    All tests make real HTTP calls and assert real results.
    """

    def test_exa_search_trending_real_call(self):
        """F1: Real Exa search returns results with correct OperationResult structure."""
        assert EXA_AVAILABLE, (
            "EXA_API_KEY not found in .env — cannot make real API calls. "
            "Add EXA_API_KEY to .env and re-run."
        )

        client = ExaResearchClient()
        result = client.search_trending("Python programming language", num_results=3)

        assert isinstance(result, OperationResult)
        assert result.success is True, (
            f"Exa search should succeed with API key, got error: "
            f"[{result.error_code}] {result.error_message}"
        )
        assert result.data is not None, "result.data should not be None on success"
        assert isinstance(result.data, list), f"Expected list, got {type(result.data)}"
        assert len(result.data) > 0, (
            f"Exa search returned 0 results — check API key and network. "
            f"Message: {result.error_message}"
        )

        # Verify at least one result has real content
        first = result.data[0]
        assert "title" in first
        assert "url" in first
        assert first["url"].startswith("http"), (
            f"URL should start with http, got: {first['url']}"
        )

    def test_exa_search_trending_structure(self):
        """F2: Results have title, url, snippet, published_date keys."""
        assert EXA_AVAILABLE, "EXA_API_KEY not found — cannot make real API calls."

        client = ExaResearchClient()
        result = client.search_trending("Python programming language", num_results=3)

        assert result.success is True, (
            f"Exa search failed: {result.error_message}"
        )
        assert result.data is not None
        assert len(result.data) > 0, "Expected at least one result from Exa search"

        for item in result.data:
            assert isinstance(item, dict), f"Each result should be a dict, got {type(item)}"
            assert "title" in item, f"Missing 'title' key in result: {item.keys()}"
            assert "url" in item, f"Missing 'url' key in result: {item.keys()}"
            assert "snippet" in item, f"Missing 'snippet' key in result: {item.keys()}"
            assert "published_date" in item, (
                f"Missing 'published_date' key in result: {item.keys()}"
            )
            # Verify snippet is a non-empty string with real content
            assert isinstance(item["snippet"], str)
            assert len(item["snippet"]) > 0, "Snippet should not be empty"

    def test_exa_build_discovery_context_real_call(self):
        """F3: Build discovery context makes real searches and returns structured output."""
        assert EXA_AVAILABLE, "EXA_API_KEY not found — cannot make real API calls."

        client = ExaResearchClient()
        context_str, results = client.build_discovery_context(
            "Python programming language", card_id=None
        )

        assert isinstance(context_str, str)
        assert isinstance(results, list)

        # With API key — expect real results
        assert len(results) > 0, (
            f"Expected results from Exa discovery, got none. "
            f"Context: '{context_str[:100]}...'"
        )
        assert "REAL-TIME WEB INTELLIGENCE" in context_str, (
            "Discovery context should contain 'REAL-TIME WEB INTELLIGENCE' header"
        )
        assert len(context_str) > 50, (
            f"Context string too short ({len(context_str)} chars) for real results"
        )
        for r in results:
            assert "title" in r, f"Missing 'title' in discovery result: {r.keys()}"
            assert "url" in r, f"Missing 'url' in discovery result: {r.keys()}"
            assert r["url"].startswith("http"), (
                f"URL should start with http, got: {r['url']}"
            )

    def test_exa_search_result_urls_are_unique(self):
        """F4: build_discovery_context deduplicates results by URL."""
        assert EXA_AVAILABLE, "EXA_API_KEY not found — cannot make real API calls."

        client = ExaResearchClient()
        _, results = client.build_discovery_context(
            "artificial intelligence research", card_id=None
        )

        assert len(results) > 0, "Expected results from discovery context"

        # Check for URL uniqueness
        urls = [r["url"] for r in results]
        assert len(urls) == len(set(urls)), (
            f"Discovery context should have unique URLs, "
            f"found {len(urls) - len(set(urls))} duplicates"
        )

    def test_exa_search_different_queries_different_results(self):
        """F5: Different queries produce at least partially different results."""
        assert EXA_AVAILABLE, "EXA_API_KEY not found — cannot make real API calls."

        client = ExaResearchClient()
        result_a = client.search_trending("quantum computing physics", num_results=5)
        result_b = client.search_trending("baking sourdough bread recipe", num_results=5)

        assert result_a.success is True, f"Query A failed: {result_a.error_message}"
        assert result_b.success is True, f"Query B failed: {result_b.error_message}"

        urls_a = {r["url"] for r in result_a.data}
        urls_b = {r["url"] for r in result_b.data}

        # Completely unrelated topics should have zero URL overlap
        overlap = urls_a & urls_b
        assert len(overlap) == 0, (
            f"Unrelated queries should not share URLs, but found {len(overlap)} overlap"
        )

    def test_exa_search_num_results_respected(self):
        """F6: num_results parameter controls how many results are returned."""
        assert EXA_AVAILABLE, "EXA_API_KEY not found — cannot make real API calls."

        client = ExaResearchClient()
        result = client.search_trending("Python programming", num_results=2)

        assert result.success is True, f"Search failed: {result.error_message}"
        # API may return fewer results if text is empty for some, but
        # num_results caps the request at 2.
        assert len(result.data) <= 2, (
            f"Requested 2 results, got {len(result.data)}"
        )


# ===================================================================
# G. DeepResearchEngine Tests
# ===================================================================

class TestDeepResearchEngine:
    """Tests for DeepResearchEngine helper methods (no full research pipeline)."""

    def test_research_engine_init(self):
        """G1: DeepResearchEngine initializes without errors."""
        engine = DeepResearchEngine(
            router_client=None,
            max_searches_per_dimension=2,
            max_total_searches=10,
            enable_checkpoints=False,
            enable_fact_validation=False,
        )
        assert engine is not None
        assert engine.max_searches_per_dimension == 2
        assert engine.max_total_searches == 10
        assert engine._search_count == 0
        assert engine._router is None

    @pytest.mark.asyncio
    async def test_extract_facts_heuristics(self):
        """G2: Text with statistics produces FACTS_DATA type facts."""
        engine = DeepResearchEngine(
            router_client=None,
            enable_checkpoints=False,
            enable_fact_validation=False,
        )

        text_with_stat = (
            "Pakistan's GDP grew by 5.3% in fiscal year 2023, "
            "according to the World Bank. The economy showed significant recovery "
            "after the previous year's contraction of 0.5%."
        )
        facts = await engine._extract_facts(
            text=text_with_stat,
            source_url="https://example.com/pakistan-gdp",
            source_name="World Bank Report",
        )
        assert isinstance(facts, list)
        assert len(facts) > 0, "Should extract at least one fact from statistical text"

        stat_facts = [f for f in facts if f.information_type == InformationType.FACTS_DATA]
        assert len(stat_facts) > 0, (
            f"Text with percentages should produce FACTS_DATA facts, got: "
            f"{[f.information_type.value for f in facts]}"
        )

        for fact in facts:
            assert isinstance(fact, ResearchFact)
            assert fact.statement
            assert fact.source_url == "https://example.com/pakistan-gdp"
            assert fact.source_name == "World Bank Report"
            assert fact.confidence > 0

    @pytest.mark.asyncio
    async def test_extract_facts_opinion_detection(self):
        """G3: Expert opinion text detected as EXPERT_OPINIONS type."""
        engine = DeepResearchEngine(
            router_client=None,
            enable_checkpoints=False,
            enable_fact_validation=False,
        )

        text = (
            "According to Professor Ahmed at Lahore University, the education "
            "reforms have significantly improved literacy rates across rural Pakistan. "
            "The expert analysis suggests continued investment is needed."
        )
        facts = await engine._extract_facts(
            text=text,
            source_url="https://example.com/education",
            source_name="Education Report",
        )
        opinion_facts = [f for f in facts if f.information_type == InformationType.EXPERT_OPINIONS]
        assert len(opinion_facts) > 0, (
            "Text with 'Professor' and 'expert' should produce EXPERT_OPINIONS facts"
        )

    @pytest.mark.asyncio
    async def test_extract_facts_trend_detection(self):
        """G4: Forecast/trend text detected as TRENDS type."""
        engine = DeepResearchEngine(
            router_client=None,
            enable_checkpoints=False,
            enable_fact_validation=False,
        )

        text = (
            "The trend in renewable energy adoption is expected to accelerate "
            "in Pakistan by 2025. Future projections indicate solar capacity "
            "will double by the end of next year."
        )
        facts = await engine._extract_facts(
            text=text,
            source_url="https://example.com/energy",
            source_name="Energy Report",
        )
        trend_facts = [f for f in facts if f.information_type == InformationType.TRENDS]
        assert len(trend_facts) > 0, (
            "Text with 'trend', 'expected to', 'future' should produce TRENDS facts"
        )

    @pytest.mark.asyncio
    async def test_extract_facts_example_detection(self):
        """G5: Case study text detected as EXAMPLES_CASES type."""
        engine = DeepResearchEngine(
            router_client=None,
            enable_checkpoints=False,
            enable_fact_validation=False,
        )

        text = (
            "For example, the case study of Bangladesh shows how microfinance "
            "can lift communities out of poverty. Such as the Grameen Bank model "
            "which has been replicated in many developing countries."
        )
        facts = await engine._extract_facts(
            text=text,
            source_url="https://example.com/microfinance",
            source_name="Development Report",
        )
        example_facts = [f for f in facts if f.information_type == InformationType.EXAMPLES_CASES]
        assert len(example_facts) > 0, (
            "Text with 'for example', 'case study' should produce EXAMPLES_CASES facts"
        )

    @pytest.mark.asyncio
    async def test_extract_facts_challenge_detection(self):
        """G6: Critical text detected as CHALLENGES type."""
        engine = DeepResearchEngine(
            router_client=None,
            enable_checkpoints=False,
            enable_fact_validation=False,
        )

        text = (
            "However, critics argue that the policy has significant limitations. "
            "The main problem is that implementation has been inconsistent across provinces. "
            "But the government faces challenges in scaling the program."
        )
        facts = await engine._extract_facts(
            text=text,
            source_url="https://example.com/challenges",
            source_name="Policy Report",
        )
        challenge_facts = [f for f in facts if f.information_type == InformationType.CHALLENGES]
        assert len(challenge_facts) > 0, (
            "Text with 'however', 'critics', 'problem', 'challenges' should produce CHALLENGES facts"
        )

    @pytest.mark.asyncio
    async def test_extract_facts_comparison_detection(self):
        """G7: Comparison text detected as COMPARISONS type."""
        engine = DeepResearchEngine(
            router_client=None,
            enable_checkpoints=False,
            enable_fact_validation=False,
        )

        text = (
            "Compared to India, Pakistan's tech sector is smaller but growing faster. "
            "The GDP per capita versus neighboring countries shows a mixed picture."
        )
        facts = await engine._extract_facts(
            text=text,
            source_url="https://example.com/comparison",
            source_name="Economic Report",
        )
        comparison_facts = [f for f in facts if f.information_type == InformationType.COMPARISONS]
        assert len(comparison_facts) > 0, (
            "Text with 'compared to', 'versus' should produce COMPARISONS facts"
        )

    def test_extract_anchors_from_text(self):
        """G8: Extract physical anchors from text containing document/location references."""
        engine = DeepResearchEngine(
            router_client=None,
            enable_checkpoints=False,
            enable_fact_validation=False,
        )

        text = (
            'The World Bank report titled "Pakistan Economic Outlook 2024" '
            "provides detailed analysis. The study was conducted in Islamabad, Pakistan. "
            "The data visualization shows GDP trends over the last decade."
        )
        anchors = engine._extract_anchors_from_text(
            text=text,
            source_url="https://example.com/article",
        )
        assert isinstance(anchors, list)
        assert len(anchors) > 0, (
            f"Text with document/location/data_viz references should yield anchors, got 0"
        )
        for anchor in anchors:
            assert isinstance(anchor, PhysicalAnchor)
            assert anchor.description
            assert anchor.anchor_type in [
                "document", "location", "object", "data_viz", "archive"
            ]
            assert anchor.source_url == "https://example.com/article"

    def test_extract_anchors_document_type(self):
        """G9: Anchor type detection correctly identifies documents."""
        engine = DeepResearchEngine(
            router_client=None,
            enable_checkpoints=False,
            enable_fact_validation=False,
        )

        text = 'The report titled "National Finance Commission Award" was cited in the Supreme Court decision.'
        anchors = engine._extract_anchors_from_text(text=text, source_url="https://example.com")
        doc_anchors = [a for a in anchors if a.anchor_type == AnchorType.DOCUMENT]
        assert len(doc_anchors) > 0, "Document pattern should match 'report titled'"

    def test_extract_characters_from_text(self):
        """G10: Extract human characters from text mentioning named individuals."""
        engine = DeepResearchEngine(
            router_client=None,
            enable_checkpoints=False,
            enable_fact_validation=False,
        )

        text = (
            "Ahmed Khan, a renowned economist at the State Bank, warned that "
            "inflation could reach 30% without intervention. The expert noted "
            "that similar crises occurred in neighboring countries."
        )
        characters = engine._extract_characters_from_text(
            text=text,
            source_url="https://example.com/economy",
        )
        assert isinstance(characters, list)
        assert len(characters) > 0, (
            "Text with 'FirstName LastName, a [role] expert' should yield a character"
        )
        for char in characters:
            assert char.name
            assert char.role
            assert char.source_url == "https://example.com/economy"

    def test_extract_characters_no_generic_names(self):
        """G11: Generic names like 'the government' are filtered out."""
        engine = DeepResearchEngine(
            router_client=None,
            enable_checkpoints=False,
            enable_fact_validation=False,
        )

        text = "The Government, a central authority, has decided to implement new policies."
        characters = engine._extract_characters_from_text(
            text=text,
            source_url="https://example.com/test",
        )
        # "The Government" should be filtered as generic
        for char in characters:
            assert char.name.lower() != "the government", (
                "Generic names should be filtered out"
            )

    def test_get_current_year(self):
        """G12: _get_current_year returns the current calendar year."""
        engine = DeepResearchEngine(
            router_client=None,
            enable_checkpoints=False,
            enable_fact_validation=False,
        )
        year = engine._get_current_year()
        from datetime import datetime
        assert year == datetime.now().year


# ===================================================================
# H. ResearchCheckpoint Tests
# ===================================================================

class TestResearchCheckpoint:
    """Tests for ResearchCheckpoint save/load/clear using temp directory."""

    def test_research_checkpoint_save_load(self, tmp_path):
        """H1: Save a checkpoint, load it, verify data matches."""
        checkpoint = ResearchCheckpoint(checkpoint_dir=tmp_path)

        dossier = ResearchDossier(
            topic="Pakistan Digital Economy",
            genre_id="current_situation",
        )
        dossier.add_fact_if_unique(ResearchFact(
            statement="Pakistan's IT exports reached $2.6 billion in 2023.",
            source_url="https://example.com/it-exports",
            source_name="Tech Report",
            information_type=InformationType.FACTS_DATA,
        ))
        dossier.all_sources.append("https://example.com/it-exports")

        checkpoint.save(
            topic="Pakistan Digital Economy",
            dossier=dossier,
            phase="phase_1_complete",
            iteration=0,
            search_count=4,
        )

        # Verify file was created
        checkpoint_files = list(tmp_path.glob("*.checkpoint.json"))
        assert len(checkpoint_files) == 1, "Should create exactly one checkpoint file"

        # Load checkpoint
        loaded = checkpoint.load("Pakistan Digital Economy")
        assert loaded is not None, "Checkpoint should load successfully"
        assert loaded["topic"] == "Pakistan Digital Economy"
        assert loaded["phase"] == "phase_1_complete"
        assert loaded["iteration"] == 0
        assert loaded["search_count"] == 4
        assert loaded["dossier"]["topic"] == "Pakistan Digital Economy"
        assert loaded["dossier"]["genre_id"] == "current_situation"
        assert "timestamp" in loaded

    def test_research_checkpoint_clear(self, tmp_path):
        """H2: Save checkpoint, clear it, verify load returns None."""
        checkpoint = ResearchCheckpoint(checkpoint_dir=tmp_path)

        dossier = ResearchDossier(topic="Test Topic")
        checkpoint.save(
            topic="Test Topic",
            dossier=dossier,
            phase="phase_1_complete",
            iteration=0,
            search_count=1,
        )

        loaded = checkpoint.load("Test Topic")
        assert loaded is not None, "Checkpoint should exist before clearing"

        checkpoint.clear("Test Topic")

        loaded_after = checkpoint.load("Test Topic")
        assert loaded_after is None, "Checkpoint should be None after clearing"

        checkpoint_files = list(tmp_path.glob("*.checkpoint.json"))
        assert len(checkpoint_files) == 0, "Checkpoint file should be deleted"

    def test_research_checkpoint_load_nonexistent(self, tmp_path):
        """H3: Loading a non-existent topic returns None."""
        checkpoint = ResearchCheckpoint(checkpoint_dir=tmp_path)
        result = checkpoint.load("Non Existent Topic")
        assert result is None

    def test_research_checkpoint_dossier_serialization(self, tmp_path):
        """H4: Verify dossier model_dump works for complex dossier with anchors/characters."""
        checkpoint = ResearchCheckpoint(checkpoint_dir=tmp_path)

        dossier = ResearchDossier(topic="Complex Topic")
        dossier.add_fact_if_unique(ResearchFact(
            statement="Fact 1 about the economy",
            source_url="https://source1.com",
            information_type=InformationType.FACTS_DATA,
        ))
        dossier.add_fact_if_unique(ResearchFact(
            statement="An expert opinion on the matter",
            source_url="https://source2.com",
            information_type=InformationType.EXPERT_OPINIONS,
        ))
        dossier.add_anchor(PhysicalAnchor(
            description="Central Bank Building in Islamabad",
            anchor_type="location",
            hierarchy_level=2,
            source_url="https://source1.com",
        ))
        dossier.add_character(HumanCharacter(
            name="Dr. Sara Ahmed",
            role="Chief Economist",
            story_summary="Leading economic reform",
            relevance="Expert on monetary policy",
            source_url="https://source2.com",
        ))
        dossier.add_source("https://source1.com")
        dossier.add_source("https://source2.com")
        dossier.big_question = "How will economic reforms affect the common citizen?"
        dossier.mainstream_assumption = "Reforms will benefit everyone equally"

        checkpoint.save(topic="Complex Topic", dossier=dossier, phase="complete", iteration=2, search_count=15)

        loaded = checkpoint.load("Complex Topic")
        assert loaded is not None
        loaded_dossier = loaded["dossier"]
        assert loaded_dossier["topic"] == "Complex Topic"
        assert len(loaded_dossier.get("all_sources", [])) >= 2
        assert loaded_dossier["big_question"] == "How will economic reforms affect the common citizen?"
        assert loaded_dossier["mainstream_assumption"] == "Reforms will benefit everyone equally"

    def test_research_checkpoint_overwrite(self, tmp_path):
        """H5: Saving twice with same topic overwrites the first checkpoint."""
        checkpoint = ResearchCheckpoint(checkpoint_dir=tmp_path)

        dossier1 = ResearchDossier(topic="Overwrite Test")
        checkpoint.save(topic="Overwrite Test", dossier=dossier1, phase="phase_1", iteration=0, search_count=1)

        dossier2 = ResearchDossier(topic="Overwrite Test")
        dossier2.add_source("https://new-source.com")
        checkpoint.save(topic="Overwrite Test", dossier=dossier2, phase="phase_2", iteration=1, search_count=5)

        loaded = checkpoint.load("Overwrite Test")
        assert loaded is not None
        assert loaded["phase"] == "phase_2", "Should have overwritten with phase_2"
        assert loaded["iteration"] == 1
        assert loaded["search_count"] == 5

        # Only one file should exist
        checkpoint_files = list(tmp_path.glob("*.checkpoint.json"))
        assert len(checkpoint_files) == 1


# ===================================================================
# I. Rate Limiting Tests
# ===================================================================

class TestRateLimiting:
    """Tests for WebSearchClient rate limiting configuration and behavior."""

    def test_rate_limit_configurable(self):
        """I1: Custom rate_limit_per_second sets correct internal attributes."""
        # Default rate limit
        client_default = WebSearchClient()
        assert client_default._rate_limit_per_second == 2.0
        assert client_default._min_interval == 0.5  # 1/2.0

        # Custom rate limit
        client_custom = WebSearchClient(rate_limit_per_second=5.0)
        assert client_custom._rate_limit_per_second == 5.0
        assert client_custom._min_interval == 0.2  # 1/5.0

        # Very low rate limit
        client_slow = WebSearchClient(rate_limit_per_second=0.5)
        assert client_slow._rate_limit_per_second == 0.5
        assert client_slow._min_interval == 2.0  # 1/0.5

    def test_rate_limit_zero_division_protection(self):
        """I2: rate_limit_per_second=0 does not cause ZeroDivisionError."""
        client = WebSearchClient(rate_limit_per_second=0)
        assert client._min_interval == 0, "Zero rate limit should set min_interval to 0"
        assert client._semaphore._value == 0, "Zero rate limit should set semaphore to 0"

    def test_rate_limit_semaphore_value(self):
        """I3: Semaphore value is 2x rate_limit_per_second."""
        client = WebSearchClient(rate_limit_per_second=3.0)
        assert client._semaphore._value == 6, "Semaphore should be 2x rate_limit"

    @pytest.mark.asyncio
    async def test_rate_limit_semaphore_concurrency(self):
        """I4: Semaphore value limits concurrent search execution."""
        # Use a very low rate limit (0.5/s → semaphore = 1) so only one
        # search can run at a time.  If the semaphore is working, launching
        # multiple concurrent searches must still complete without deadlock.
        client = WebSearchClient(rate_limit_per_second=0.5)
        # semaphore._value == int(0.5 * 2) == 1
        assert client._semaphore._value == 1, (
            "rate_limit=0.5 → semaphore should allow 1 concurrent slot"
        )

        num_searches = 3
        async with client:
            tasks = [client.search(f"concurrent test {i}", num_results=1) for i in range(num_searches)]
            results = await asyncio.gather(*tasks)

        # All must complete (no deadlock)
        assert len(results) == num_searches
        for r in results:
            assert isinstance(r, list)

    @pytest.mark.asyncio
    async def test_rate_limit_delay_between_searches(self):
        """I5: Multi-search with delay_between adds measurable wall-clock delay."""
        queries = ["delay test A", "delay test B"]
        delay = 0.4

        start = time.monotonic()
        async with WebSearchClient() as client:
            results = await client.multi_search(queries, num_per_query=1, delay_between=delay)
        elapsed = time.monotonic() - start

        assert isinstance(results, dict)
        assert set(results.keys()) == set(queries)
        # With 2 queries, delay_between inserts 1 delay of 0.4s.
        # Even if SDK is unavailable (instant search), the asyncio.sleep runs.
        assert elapsed >= 0.3, (
            f"delay_between={delay}s for 2 queries should take >= 0.3s, "
            f"but elapsed was {elapsed:.3f}s — delay_between may not be working"
        )

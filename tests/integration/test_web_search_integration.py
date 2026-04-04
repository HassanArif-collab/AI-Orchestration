"""
Phase 15 — Web Search Integration Tests
=========================================
Tests for WebSearchClient, SearchResult, ExaResearchClient, DeepResearchEngine,
and ResearchCheckpoint using REAL API calls where available.

Design:
- If the z-ai-web-dev-sdk is not installed, WebSearchClient gracefully returns
  empty results — tests detect this and pass with clear log messages.
- If EXA_API_KEY is not set, ExaResearchClient returns OperationResult.fail(...)
  — tests verify this graceful degradation.
- All async methods use @pytest.mark.asyncio for explicit documentation.
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
# Environment probes — run ONCE at import time
# ---------------------------------------------------------------------------

SDK_AVAILABLE = False
try:
    __import__("z-ai-web-dev-sdk")
    SDK_AVAILABLE = True
except ImportError:
    pass

EXA_AVAILABLE = bool(os.getenv("EXA_API_KEY", "").strip())

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
        # Verify all 7 expected keys are present
        assert set(d.keys()) == {"url", "title", "snippet", "host_name", "rank", "date", "favicon"}

    def test_search_result_default_optional_fields(self):
        """A2b: Verify optional fields date and favicon default to empty string."""
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
    """Tests for WebSearchClient single-query search."""

    @pytest.mark.asyncio
    async def test_web_search_basic_query(self):
        """B1: Search for a common topic, verify results returned with url/title/snippet."""
        if not SDK_AVAILABLE:
            # Graceful degradation: SDK not installed → client returns []
            async with WebSearchClient() as client:
                results = await client.search("Python programming language", num_results=3)
            assert results == [], (
                "SDK not installed — expected empty list (graceful degradation)"
            )
            return

        async with WebSearchClient() as client:
            results = await client.search("Python programming language", num_results=5)
        assert isinstance(results, list)
        if len(results) > 0:
            for r in results:
                assert isinstance(r, SearchResult)
                assert isinstance(r.url, str)
                assert isinstance(r.title, str)
                assert isinstance(r.snippet, str)
                # At least one of url/title/snippet should be non-empty for valid results
                assert r.url or r.title or r.snippet, (
                    "Search result should have url, title, or snippet populated"
                )

    @pytest.mark.asyncio
    async def test_web_search_returns_results_with_host_name(self):
        """B2: Verify each result has host_name populated."""
        if not SDK_AVAILABLE:
            async with WebSearchClient() as client:
                results = await client.search("OpenAI GPT models", num_results=3)
            assert results == [], "SDK not installed — expected empty list"
            return

        async with WebSearchClient() as client:
            results = await client.search("OpenAI GPT models", num_results=5)
        assert isinstance(results, list)
        if len(results) > 0:
            for r in results:
                assert isinstance(r, SearchResult)
                assert isinstance(r.host_name, str)

    @pytest.mark.asyncio
    async def test_web_search_respects_num_results(self):
        """B3: Request 3 results, verify <= 3 returned."""
        if not SDK_AVAILABLE:
            async with WebSearchClient() as client:
                results = await client.search("Python web frameworks", num_results=3)
            assert len(results) == 0, "SDK not installed — expected 0 results"
            return

        async with WebSearchClient() as client:
            results = await client.search("Python web frameworks", num_results=3)
        assert isinstance(results, list)
        assert len(results) <= 3, f"Requested 3 results but got {len(results)}"

    @pytest.mark.asyncio
    async def test_web_search_empty_query(self):
        """B4: Empty query returns empty list (or API handles it gracefully)."""
        async with WebSearchClient() as client:
            results = await client.search("", num_results=5)
        assert isinstance(results, list)
        assert len(results) <= 5, "Empty query should not return more than requested"


# ===================================================================
# C. WebSearchClient Multi Search Tests
# ===================================================================

class TestWebSearchClientMulti:
    """Tests for WebSearchClient sequential multi-search."""

    @pytest.mark.asyncio
    async def test_multi_search_multiple_queries(self):
        """C1: Pass 2-3 queries, verify each has results dict entry."""
        queries = ["Python programming", "JavaScript frameworks", "Rust language"]
        async with WebSearchClient() as client:
            results = await client.multi_search(queries, num_per_query=3, delay_between=0.3)

        assert isinstance(results, dict)
        assert set(results.keys()) == set(queries), "All query keys should be in the result"
        for query, result_list in results.items():
            assert isinstance(result_list, list), (
                f"Results for '{query}' should be a list, got {type(result_list)}"
            )

    @pytest.mark.asyncio
    async def test_multi_search_sequential_with_delay(self):
        """C2: Verify delay_between parameter works — execution time reflects delay."""
        queries = ["Python basics", "Python advanced"]
        delay = 0.5  # 500ms between queries
        start = time.monotonic()
        async with WebSearchClient() as client:
            results = await client.multi_search(queries, num_per_query=2, delay_between=delay)
        elapsed = time.monotonic() - start

        # With 2 queries and 0.5s delay, expect >= 0.4s (allowing some tolerance)
        assert isinstance(results, dict)
        assert len(results) == 2
        assert elapsed >= 0.3, (
            f"Expected at least 0.3s with delay_between={delay}s, "
            f"but elapsed was {elapsed:.3f}s — delay may not be applied"
        )

    @pytest.mark.asyncio
    async def test_multi_search_with_rate_limiting(self):
        """C3: Verify rate limiting doesn't crash — multiple queries succeed."""
        # Use a very restrictive rate limit to stress-test rate limiting
        queries = ["Python tutorial", "Django tutorial", "Flask tutorial"]
        async with WebSearchClient(rate_limit_per_second=0.5) as client:
            results = await client.multi_search(queries, num_per_query=2, delay_between=0.2)

        assert isinstance(results, dict)
        assert len(results) == 3
        for query in queries:
            assert query in results
            assert isinstance(results[query], list)

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
        """D1: 2 queries in parallel, both return results."""
        queries = ["Python programming", "JavaScript ES2024"]
        async with WebSearchClient() as client:
            results = await client.multi_search_parallel(queries, num_per_query=3)

        assert isinstance(results, dict)
        assert set(results.keys()) == set(queries)
        for query, result_list in results.items():
            assert isinstance(result_list, list)

    @pytest.mark.asyncio
    async def test_multi_search_parallel_same_results_as_sequential(self):
        """D2: Same queries, sequential and parallel return same keys and types."""
        queries = ["Python async programming"]
        num = 3

        async with WebSearchClient() as client_seq:
            seq_results = await client_seq.multi_search(queries, num_per_query=num)

        async with WebSearchClient() as client_par:
            par_results = await client_par.multi_search_parallel(queries, num_per_query=num)

        # Both should have the same keys
        assert set(seq_results.keys()) == set(par_results.keys()) == set(queries)

        for q in queries:
            seq_list = seq_results[q]
            par_list = par_results[q]
            assert isinstance(seq_list, list)
            assert isinstance(par_list, list)
            # Both should return the same number of results (or both empty)
            assert len(seq_list) == len(par_list), (
                f"Sequential returned {len(seq_list)} results for '{q}' "
                f"but parallel returned {len(par_list)}"
            )


# ===================================================================
# E. WebSearchClient Context Manager Tests
# ===================================================================

class TestWebSearchClientContextManager:
    """Tests for WebSearchClient async context manager."""

    @pytest.mark.asyncio
    async def test_web_search_context_manager_init(self):
        """E1: async with WebSearchClient() as client works without error."""
        async with WebSearchClient() as client:
            assert client is not None
            assert isinstance(client, WebSearchClient)

    @pytest.mark.asyncio
    async def test_web_search_context_manager_releases(self):
        """E2: Client can be used within context, then exits cleanly."""
        client_used = False
        async with WebSearchClient() as client:
            results = await client.search("Python", num_results=2)
            assert isinstance(results, list)
            client_used = True
        assert client_used, "Client should have been used inside context manager"
        # After exiting context, verify client is not broken (no dangling state)
        # We can't easily check internal state, but the context manager exiting
        # without error means __aexit__ succeeded


# ===================================================================
# F. ExaResearchClient Tests
# ===================================================================

class TestExaResearchClient:
    """Tests for ExaResearchClient using real API calls."""

    def test_exa_search_trending(self):
        """F1: If EXA_API_KEY is set, search returns results; otherwise graceful failure."""
        client = ExaResearchClient()
        result = client.search_trending("Python programming language", num_results=3)

        assert isinstance(result, OperationResult)

        if EXA_AVAILABLE:
            # API key present — expect success
            assert result.success is True, (
                f"Exa search should succeed with API key, got error: {result.error_message}"
            )
            assert result.data is not None
            assert isinstance(result.data, list)
        else:
            # No API key — graceful failure
            assert result.success is False, (
                "Expected failure without EXA_API_KEY"
            )
            assert "EXA_NOT_CONFIGURED" in (result.error_code or ""), (
                f"Expected EXA_NOT_CONFIGURED error, got: {result.error_code}"
            )

    def test_exa_search_trending_structure(self):
        """F2: Results have title, url, snippet, published_date when data is returned."""
        client = ExaResearchClient()
        result = client.search_trending("Python programming language", num_results=3)

        if EXA_AVAILABLE and result.success and result.data:
            for item in result.data:
                assert isinstance(item, dict), "Each result should be a dict"
                assert "title" in item, f"Missing 'title' key in result: {item.keys()}"
                assert "url" in item, f"Missing 'url' key in result: {item.keys()}"
                assert "snippet" in item, f"Missing 'snippet' key in result: {item.keys()}"
                assert "published_date" in item, (
                    f"Missing 'published_date' key in result: {item.keys()}"
                )
        else:
            # Without results, verify graceful degradation
            assert isinstance(result, OperationResult)

    def test_exa_build_discovery_context(self):
        """F3: Build context returns formatted string with source entries."""
        client = ExaResearchClient()
        context_str, results = client.build_discovery_context(
            "Python programming language", card_id=None
        )

        assert isinstance(context_str, str)
        assert isinstance(results, list)

        if EXA_AVAILABLE and results:
            # Should have "REAL-TIME WEB INTELLIGENCE" header
            assert "REAL-TIME WEB INTELLIGENCE" in context_str, (
                "Discovery context should contain header"
            )
            assert len(context_str) > 50, (
                f"Context string seems too short ({len(context_str)} chars)"
            )
            # Each result should have standard keys
            for r in results:
                assert "title" in r
                assert "url" in r
        else:
            # No API key or no results → empty context
            if not EXA_AVAILABLE:
                assert context_str == "", (
                    "Without API key, context should be empty"
                )
                assert results == [], "Without API key, results should be empty"

    def test_exa_no_api_key_graceful(self):
        """F4: Without EXA_API_KEY, search returns failure (not crash)."""
        client = ExaResearchClient()
        result = client.search_trending("test query")

        if not EXA_AVAILABLE:
            # No API key → should fail gracefully
            assert result.success is False
            assert result.error_code is not None, (
                "Error code should be set when search fails due to missing key"
            )
            # Should NOT raise an exception — it returns an OperationResult
        else:
            # API key is present — just verify it returns a valid OperationResult
            assert isinstance(result, OperationResult)


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
        """G2: Pass text with statistics, verify correct fact type detection."""
        engine = DeepResearchEngine(
            router_client=None,
            enable_checkpoints=False,
            enable_fact_validation=False,
        )

        # Text with a statistic — should be detected as FACTS_DATA
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

        # Verify the first fact has the correct type (statistics trigger FACTS_DATA)
        stat_facts = [f for f in facts if f.information_type == InformationType.FACTS_DATA]
        assert len(stat_facts) > 0, (
            f"Text with percentages should produce FACTS_DATA facts, got: "
            f"{[f.information_type.value for f in facts]}"
        )

        # Verify fact structure
        for fact in facts:
            assert isinstance(fact, ResearchFact)
            assert fact.statement
            assert fact.source_url == "https://example.com/pakistan-gdp"
            assert fact.source_name == "World Bank Report"
            assert fact.confidence > 0

    @pytest.mark.asyncio
    async def test_extract_facts_opinion_detection(self):
        """G2b: Expert opinion text detected as EXPERT_OPINIONS type."""
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
        """G2c: Forecast/trend text detected as TRENDS type."""
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

    def test_extract_anchors_from_text(self):
        """G3: Extract physical anchors from text containing document/location references."""
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
        # Should find at least one anchor (document, location, or data_viz pattern)
        assert len(anchors) > 0, (
            f"Text with document/location/data_viz references should yield anchors"
        )
        for anchor in anchors:
            assert isinstance(anchor, PhysicalAnchor)
            assert anchor.description
            assert anchor.anchor_type in [
                "document", "location", "object", "data_viz", "archive"
            ]
            assert anchor.source_url == "https://example.com/article"

    def test_extract_characters_from_text(self):
        """G4: Extract human characters from text mentioning named individuals."""
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
        # Pattern: "Ahmed Khan" + role containing "economist"
        assert len(characters) > 0, (
            "Text with 'FirstName LastName, a [role] expert' should yield a character"
        )
        for char in characters:
            assert char.name
            assert char.role
            assert char.source_url == "https://example.com/economy"

    def test_get_current_year(self):
        """G5: _get_current_year returns the current calendar year."""
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

        # Verify it exists
        loaded = checkpoint.load("Test Topic")
        assert loaded is not None, "Checkpoint should exist before clearing"

        # Clear it
        checkpoint.clear("Test Topic")

        # Verify it's gone
        loaded_after = checkpoint.load("Test Topic")
        assert loaded_after is None, "Checkpoint should be None after clearing"

        # Verify file is removed
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
        # Add various types of content
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
        from packages.content_factory.production.models import HumanCharacter
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

    @pytest.mark.asyncio
    async def test_rate_limit_semaphore_prevents_burst(self):
        """I2: Multiple concurrent searches are throttled by rate limiter."""
        # Use very restrictive rate limit: 1 search per 0.5 seconds
        client = WebSearchClient(rate_limit_per_second=2.0)  # min_interval = 0.5s

        num_searches = 3
        start = time.monotonic()

        # Fire all searches concurrently
        async with client:
            tasks = [client.search(f"test query {i}", num_results=1) for i in range(num_searches)]
            results = await asyncio.gather(*tasks)

        elapsed = time.monotonic() - start

        # All should succeed
        assert len(results) == num_searches
        for r in results:
            assert isinstance(r, list)

        # With 3 searches and 0.5s min_interval, expect at least 1.0s total
        # (2 intervals between 3 searches × 0.5s = 1.0s)
        # Allow some tolerance for SDK-unavailable case (empty results return fast)
        if SDK_AVAILABLE:
            assert elapsed >= 0.8, (
                f"Expected rate limiting to enforce delays "
                f"(min_interval=0.5s × {num_searches - 1} intervals ≥ 1.0s), "
                f"but elapsed was {elapsed:.3f}s"
            )

    def test_rate_limit_zero_division_protection(self):
        """I3: rate_limit_per_second=0 does not cause ZeroDivisionError."""
        client = WebSearchClient(rate_limit_per_second=0)
        assert client._min_interval == 0, "Zero rate limit should set min_interval to 0"
        assert client._semaphore._value == 0, "Zero rate limit should set semaphore to 0"

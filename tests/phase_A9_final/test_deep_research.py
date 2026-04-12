"""
Tests for packages/content_factory/production/deep_research.py
DeepResearchEngine + ResearchCheckpoint unit tests.

Focuses on:
- Pure logic functions (extraction, dedup, agreement, dimension derivation)
- Checkpoint save/load/clear with tmp_path
- Fact extraction heuristics
- Anchor and character regex extraction
- Engine init and config
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from packages.content_factory.production.models import (
    AnchorType,
    DimensionFindings,
    HumanCharacter,
    InformationType,
    PhysicalAnchor,
    ResearchDossier,
    ResearchFact,
    ValidationStatus,
)
from packages.content_factory.production.deep_research import (
    DeepResearchEngine,
    ResearchCheckpoint,
    SYSTEM_RESEARCHER,
    SYSTEM_DIMENSION_EXTRACTOR,
    SYSTEM_FACT_EXTRACTOR,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture()
def mock_router():
    """Provide a mock RouterClient."""
    router = MagicMock()
    router.complete_text = AsyncMock(return_value='["Economic Impact", "Political Response"]')
    router.close = AsyncMock()
    return router


@pytest.fixture()
def engine(mock_router):
    """Create a DeepResearchEngine with mocked router."""
    return DeepResearchEngine(
        router_client=mock_router,
        max_searches_per_dimension=2,
        max_total_searches=5,
        enable_checkpoints=False,
        enable_fact_validation=False,
    )


@pytest.fixture()
def checkpoint(tmp_path):
    """Create a ResearchCheckpoint with tmp_path as checkpoint dir."""
    with patch("packages.content_factory.production.deep_research.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(DATA_DIR=str(tmp_path / "data"))
        return ResearchCheckpoint(checkpoint_dir=tmp_path / "checkpoints")


@pytest.fixture()
def sample_dossier():
    """Create a sample ResearchDossier with some data."""
    return ResearchDossier(topic="Pakistan Digital Currency")


@pytest.fixture()
def sample_fact():
    """Create a sample ResearchFact."""
    return ResearchFact(
        statement="Pakistan's central bank launched a pilot program for digital currency in 2022",
        source_url="https://example.com/pakistan-cbdc",
        source_name="Dawn News",
        information_type=InformationType.FACTS_DATA,
        confidence=0.85,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# DeepResearchEngine.__init__
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeepResearchEngineInit:
    """Test engine initialization."""

    def test_init_with_router(self, mock_router):
        engine = DeepResearchEngine(router_client=mock_router)
        assert engine._router is mock_router
        assert engine._owns_router is False

    def test_init_without_router(self):
        engine = DeepResearchEngine()
        assert engine._router is None
        assert engine._owns_router is True

    def test_init_defaults(self, mock_router):
        engine = DeepResearchEngine(router_client=mock_router)
        assert engine.max_searches_per_dimension == 3
        assert engine.max_total_searches == 20
        assert engine._enable_checkpoints is True
        assert engine._enable_fact_validation is True
        assert engine._search_count == 0

    def test_init_custom_limits(self, mock_router):
        engine = DeepResearchEngine(
            router_client=mock_router,
            max_searches_per_dimension=5,
            max_total_searches=50,
        )
        assert engine.max_searches_per_dimension == 5
        assert engine.max_total_searches == 50

    def test_checkpoints_disabled(self, mock_router):
        engine = DeepResearchEngine(
            router_client=mock_router,
            enable_checkpoints=False,
        )
        assert engine._checkpoint is None

    def test_checkpoints_enabled_creates_checkpoint(self, mock_router):
        with patch("packages.content_factory.production.deep_research.get_settings") as mock_s:
            mock_s.return_value = MagicMock(DATA_DIR="/tmp/data")
            engine = DeepResearchEngine(
                router_client=mock_router,
                enable_checkpoints=True,
            )
            assert engine._checkpoint is not None

    def test_agreement_stopwords_is_frozenset(self, engine):
        assert isinstance(engine._AGREEMENT_STOPWORDS, frozenset)
        assert "The" in engine._AGREEMENT_STOPWORDS
        assert "In" in engine._AGREEMENT_STOPWORDS


# ═══════════════════════════════════════════════════════════════════════════════
# _extract_key_claim
# ═══════════════════════════════════════════════════════════════════════════════

class TestExtractKeyClaim:
    """Test _extract_key_claim logic."""

    def test_single_sentence(self, engine):
        result = engine._extract_key_claim("Pakistan launched digital currency.")
        assert "Pakistan" in result
        assert "launched" in result

    def test_multiple_sentences_takes_first(self, engine):
        result = engine._extract_key_claim("Pakistan launched digital currency. This is the second sentence.")
        assert "second" not in result.lower() or result.index("Pakistan") < len(result) // 2

    def test_removes_numbers(self, engine):
        result = engine._extract_key_claim("The GDP grew by 5.2% in 2023.")
        assert "5.2" not in result
        assert "2023" not in result

    def test_removes_million_billion(self, engine):
        result = engine._extract_key_claim("The project cost 500 million dollars.")
        assert "500" not in result
        assert "million" not in result.lower()

    def test_truncates_to_100_chars(self, engine):
        long_statement = "Word " * 50 + "."
        result = engine._extract_key_claim(long_statement)
        assert len(result) <= 100

    def test_strips_whitespace(self, engine):
        result = engine._extract_key_claim("  Hello World.  ")
        assert result == result.strip()

    def test_preserves_capitalized_words(self, engine):
        result = engine._extract_key_claim("State Bank of Pakistan made an announcement.")
        assert "State Bank" in result or "State" in result


# ═══════════════════════════════════════════════════════════════════════════════
# _statements_agree
# ═══════════════════════════════════════════════════════════════════════════════

class TestStatementsAgree:
    """Test _statements_agree logic."""

    def test_same_topic_agrees(self, engine):
        s1 = "Pakistan launched a digital currency program from Islamabad"
        s2 = "The digital currency program in Pakistan was launched from Islamabad headquarters"
        assert engine._statements_agree(s1, s2) is True

    def test_different_topics_disagree(self, engine):
        s1 = "Pakistan launched a digital currency program"
        s2 = "Apple released a new iPhone model"
        assert engine._statements_agree(s1, s2) is False

    def test_needs_two_overlapping_words(self, engine):
        s1 = "Pakistan launched a program"
        s2 = "Pakistan announced today"
        # "Pakistan" is the only capitalized word overlap
        assert engine._statements_agree(s1, s2) is False

    def test_stopwords_excluded(self, engine):
        # "The" and "In" are stopwords and shouldn't count
        s1 = "The study shows results"
        s2 = "In the study finds data"
        # After removing stopwords, no meaningful overlap
        assert engine._statements_agree(s1, s2) is False

    def test_two_meaningful_words_agree(self, engine):
        s1 = "State Bank issued new guidelines"
        s2 = "The State Bank approved the guidelines"
        # "State", "Bank", "guidelines" overlap
        assert engine._statements_agree(s1, s2) is True

    def test_empty_statements(self, engine):
        assert engine._statements_agree("", "Hello World") is False
        assert engine._statements_agree("", "") is False

    def test_no_capitalized_words(self, engine):
        s1 = "this has no capitals"
        s2 = "also no capitals here"
        assert engine._statements_agree(s1, s2) is False


# ═══════════════════════════════════════════════════════════════════════════════
# _extract_anchors_from_text
# ═══════════════════════════════════════════════════════════════════════════════

class TestExtractAnchorsFromText:
    """Test anchor regex extraction."""

    def test_document_anchor(self, engine):
        text = 'According to the report titled "Digital Currency Framework", Pakistan has...'
        anchors = engine._extract_anchors_from_text(text, "https://example.com")
        assert len(anchors) > 0
        assert any(a.anchor_type == AnchorType.DOCUMENT for a in anchors)

    def test_location_anchor(self, engine):
        text = "The conference held in Islamabad was attended by officials"
        anchors = engine._extract_anchors_from_text(text, "https://example.com")
        assert len(anchors) > 0
        assert any(a.anchor_type == AnchorType.LOCATION for a in anchors)

    def test_data_viz_anchor(self, engine):
        text = "The chart showing economic growth was presented to parliament"
        anchors = engine._extract_anchors_from_text(text, "https://example.com")
        assert len(anchors) > 0
        assert any(a.anchor_type == AnchorType.DATA_VIZ for a in anchors)

    def test_object_anchor(self, engine):
        text = "The old building stands as a testament to the colonial era"
        anchors = engine._extract_anchors_from_text(text, "https://example.com")
        assert len(anchors) > 0
        assert any(a.anchor_type == AnchorType.OBJECT for a in anchors)

    def test_limits_to_3_per_text(self, engine):
        text = """
        The report titled "First Report" was published.
        Located in Karachi, the study found results.
        The chart showing data trends was released.
        The report titled "Second Report" appeared.
        Located in Lahore, the findings were significant.
        The chart showing inflation rates was updated.
        """
        anchors = engine._extract_anchors_from_text(text, "https://example.com")
        assert len(anchors) <= 3

    def test_anchor_has_source_url(self, engine):
        text = 'The document called "CBDC Policy Paper" outlines rules'
        anchors = engine._extract_anchors_from_text(text, "https://source.com/paper")
        assert all(a.source_url == "https://source.com/paper" for a in anchors)

    def test_anchor_description_not_empty(self, engine):
        text = "Located in Islamabad, the central bank made decisions"
        anchors = engine._extract_anchors_from_text(text, "https://example.com")
        assert all(len(a.description) > 0 for a in anchors)


# ═══════════════════════════════════════════════════════════════════════════════
# _extract_characters_from_text
# ═══════════════════════════════════════════════════════════════════════════════

class TestExtractCharactersFromText:
    """Test character regex extraction."""

    def test_expert_character(self, engine):
        text = "Dr Ahmed Khan, a finance expert, testified before the committee"
        characters = engine._extract_characters_from_text(text, "https://example.com")
        assert len(characters) > 0
        assert any("Ahmed" in c.name for c in characters)

    def test_official_character(self, engine):
        text = "Sarah Johnson, the central bank director, announced the policy"
        characters = engine._extract_characters_from_text(text, "https://example.com")
        assert len(characters) > 0
        assert any("Sarah" in c.name for c in characters)

    def test_limits_to_2_per_text(self, engine):
        text = """
        Dr Ahmed Khan, a finance expert, said something.
        Sarah Johnson, an economic minister, made a decision.
        James Brown, a digital advocate, shared his opinion.
        """
        characters = engine._extract_characters_from_text(text, "https://example.com")
        assert len(characters) <= 2

    def test_character_has_source_url(self, engine):
        text = "Dr Ahmed Khan, a finance expert, testified before the committee"
        characters = engine._extract_characters_from_text(text, "https://source.com/article")
        assert all(c.source_url == "https://source.com/article" for c in characters)

    def test_excludes_generic_names(self, engine):
        text = "The Government, an official, made an announcement"
        characters = engine._extract_characters_from_text(text, "https://example.com")
        # "The Government" should be excluded
        assert not any(c.name.lower() == "the government" for c in characters)

    def test_character_has_role(self, engine):
        text = "Dr Ahmed Khan, a finance expert, testified before the committee"
        characters = engine._extract_characters_from_text(text, "https://example.com")
        assert all(len(c.role) > 0 for c in characters)

    def test_no_characters_in_empty_text(self, engine):
        characters = engine._extract_characters_from_text("", "https://example.com")
        assert characters == []

    def test_no_characters_in_generic_text(self, engine):
        characters = engine._extract_characters_from_text(
            "The weather is nice today and everyone is happy",
            "https://example.com"
        )
        assert characters == []


# ═══════════════════════════════════════════════════════════════════════════════
# _derive_dimensions_from_missing
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeriveDimensionsFromMissing:
    """Test deriving research dimensions from missing elements."""

    def test_facts_missing(self, engine):
        missing = ["facts_and_data: need 3+ facts"]
        dims = engine._derive_dimensions_from_missing(missing)
        assert "Statistics and Data" in dims

    def test_examples_missing(self, engine):
        missing = ["examples_cases: need 2+ examples"]
        dims = engine._derive_dimensions_from_missing(missing)
        assert "Case Studies" in dims

    def test_expert_opinions_missing(self, engine):
        missing = ["expert_opinions: need 1+ opinions"]
        dims = engine._derive_dimensions_from_missing(missing)
        assert "Expert Analysis" in dims

    def test_anchors_missing(self, engine):
        missing = ["physical_anchors: need 2+ Level 1-3 anchors"]
        dims = engine._derive_dimensions_from_missing(missing)
        assert "Tangible Evidence" in dims

    def test_characters_missing(self, engine):
        missing = ["human_characters: need 1+ character"]
        dims = engine._derive_dimensions_from_missing(missing)
        assert "Personal Stories" in dims

    def test_challenges_missing(self, engine):
        missing = ["challenges: need counterarguments"]
        dims = engine._derive_dimensions_from_missing(missing)
        assert "Counterarguments" in dims

    def test_multiple_missing(self, engine):
        missing = [
            "facts_and_data: need 3+ facts",
            "human_characters: need 1+ character",
        ]
        dims = engine._derive_dimensions_from_missing(missing)
        assert "Statistics and Data" in dims
        assert "Personal Stories" in dims

    def test_empty_missing_returns_fallback(self, engine):
        dims = engine._derive_dimensions_from_missing([])
        assert dims == ["Additional Research"]

    def test_unknown_missing_returns_fallback(self, engine):
        dims = engine._derive_dimensions_from_missing(["something completely unknown"])
        assert dims == ["Additional Research"]

    def test_no_duplicate_dimensions(self, engine):
        missing = [
            "facts_and_data: need 3+ facts",
            "facts_and_data: need 3+ facts",
        ]
        dims = engine._derive_dimensions_from_missing(missing)
        assert len(dims) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# _extract_facts
# ═══════════════════════════════════════════════════════════════════════════════

class TestExtractFacts:
    """Test fact extraction heuristics."""

    @pytest.mark.asyncio
    async def test_statistics_detected(self, engine):
        text = "Pakistan's GDP grew by 5.2% in 2023 according to official data released by the government."
        facts = await engine._extract_facts(text, "https://example.com", "Dawn News")
        assert len(facts) > 0
        assert facts[0].information_type == InformationType.FACTS_DATA

    @pytest.mark.asyncio
    async def test_expert_opinion_detected(self, engine):
        text = "According to Dr Ahmed Khan, an expert at the central bank, the policy will have significant impact on the economy."
        facts = await engine._extract_facts(text, "https://example.com", "Dawn News")
        assert len(facts) > 0
        assert facts[0].information_type == InformationType.EXPERT_OPINIONS

    @pytest.mark.asyncio
    async def test_example_case_detected(self, engine):
        text = "For example, the case study of Nigeria's eNaira shows that digital currency adoption faces challenges in developing nations."
        facts = await engine._extract_facts(text, "https://example.com", "Dawn News")
        assert len(facts) > 0
        assert facts[0].information_type == InformationType.EXAMPLES_CASES

    @pytest.mark.asyncio
    async def test_trend_detected(self, engine):
        text = "The trend toward digital currencies is expected to accelerate in the coming years as more central banks explore the technology."
        facts = await engine._extract_facts(text, "https://example.com", "Dawn News")
        assert len(facts) > 0
        assert facts[0].information_type == InformationType.TRENDS

    @pytest.mark.asyncio
    async def test_comparison_detected(self, engine):
        text = "Compared to traditional banking, digital currencies offer lower transaction costs and faster settlement times."
        facts = await engine._extract_facts(text, "https://example.com", "Dawn News")
        assert len(facts) > 0
        assert facts[0].information_type == InformationType.COMPARISONS

    @pytest.mark.asyncio
    async def test_challenge_detected(self, engine):
        text = "However, critics argue that digital currencies pose significant privacy challenges for ordinary citizens in developing countries."
        facts = await engine._extract_facts(text, "https://example.com", "Dawn News")
        assert len(facts) > 0
        assert facts[0].information_type == InformationType.CHALLENGES

    @pytest.mark.asyncio
    async def test_short_sentence_skipped(self, engine):
        text = "Too short."
        facts = await engine._extract_facts(text, "https://example.com", "Dawn News")
        assert facts == []

    @pytest.mark.asyncio
    async def test_empty_sentence_skipped(self, engine):
        facts = await engine._extract_facts("   ", "https://example.com", "Dawn News")
        assert facts == []

    @pytest.mark.asyncio
    async def test_default_type_applied(self, engine):
        text = "This is a sentence about the general topic that does not match any specific pattern and is long enough to be considered for extraction."
        facts = await engine._extract_facts(
            text, "https://example.com", "Dawn News",
            default_type=InformationType.FACTS_DATA,
        )
        assert len(facts) > 0
        assert facts[0].information_type == InformationType.FACTS_DATA

    @pytest.mark.asyncio
    async def test_fact_source_attributes(self, engine):
        text = "The government announced a new policy framework for digital banking services across the country."
        facts = await engine._extract_facts(text, "https://example.com/article", "Dawn News")
        assert len(facts) > 0
        assert facts[0].source_url == "https://example.com/article"
        assert facts[0].source_name == "Dawn News"
        assert facts[0].confidence == 0.5

    @pytest.mark.asyncio
    async def test_limited_to_5_per_source(self, engine):
        # Create 6 sentences that are long enough
        text = ". ".join([f"This is a sufficiently long sentence number {i} that should be extracted as a fact." for i in range(6)])
        facts = await engine._extract_facts(text, "https://example.com", "Dawn News")
        assert len(facts) <= 5

    @pytest.mark.asyncio
    async def test_statement_truncated_to_500(self, engine):
        long_word = "word" * 200
        text = f"{long_word}. This is another sentence."
        facts = await engine._extract_facts(text, "https://example.com", "Dawn News")
        assert all(len(f.statement) <= 500 for f in facts)


# ═══════════════════════════════════════════════════════════════════════════════
# _estimate_hierarchy_level
# ═══════════════════════════════════════════════════════════════════════════════

class TestEstimateHierarchyLevel:
    """Test hierarchy level estimation for anchor types."""

    def test_document_level_1(self, engine):
        assert engine._estimate_hierarchy_level(AnchorType.DOCUMENT) == 1

    def test_location_level_2(self, engine):
        assert engine._estimate_hierarchy_level(AnchorType.LOCATION) == 2

    def test_object_level_2(self, engine):
        assert engine._estimate_hierarchy_level(AnchorType.OBJECT) == 2

    def test_archive_level_2(self, engine):
        assert engine._estimate_hierarchy_level(AnchorType.ARCHIVE) == 2

    def test_data_viz_level_4(self, engine):
        assert engine._estimate_hierarchy_level(AnchorType.DATA_VIZ) == 4


# ═══════════════════════════════════════════════════════════════════════════════
# ResearchCheckpoint
# ═══════════════════════════════════════════════════════════════════════════════

class TestResearchCheckpoint:
    """Test checkpoint save/load/clear."""

    def test_topic_hash_deterministic(self, checkpoint):
        h1 = checkpoint._topic_hash("Pakistan Digital Currency")
        h2 = checkpoint._topic_hash("Pakistan Digital Currency")
        assert h1 == h2

    def test_topic_hash_different_topics(self, checkpoint):
        h1 = checkpoint._topic_hash("Topic A")
        h2 = checkpoint._topic_hash("Topic B")
        assert h1 != h2

    def test_topic_hash_case_insensitive(self, checkpoint):
        h1 = checkpoint._topic_hash("Topic A")
        h2 = checkpoint._topic_hash("topic a")
        assert h1 == h2

    def test_topic_hash_strips_whitespace(self, checkpoint):
        h1 = checkpoint._topic_hash("  Topic A  ")
        h2 = checkpoint._topic_hash("Topic A")
        assert h1 == h2

    def test_save_creates_file(self, checkpoint, sample_dossier, tmp_path):
        checkpoint.save("test topic", sample_dossier, "phase_1_complete", 0, 5)
        files = list(tmp_path.glob("checkpoints/*.checkpoint.json"))
        assert len(files) == 1

    def test_save_and_load_roundtrip(self, checkpoint, sample_dossier):
        checkpoint.save("test topic", sample_dossier, "phase_2_economics", 1, 10)
        loaded = checkpoint.load("test topic")
        assert loaded is not None
        assert loaded["phase"] == "phase_2_economics"
        assert loaded["iteration"] == 1
        assert loaded["search_count"] == 10
        assert loaded["topic"] == "test topic"
        assert "dossier" in loaded

    def test_load_nonexistent_returns_none(self, checkpoint):
        loaded = checkpoint.load("nonexistent topic")
        assert loaded is None

    def test_clear_removes_file(self, checkpoint, sample_dossier):
        checkpoint.save("test topic", sample_dossier, "phase_1_complete", 0, 5)
        assert checkpoint.load("test topic") is not None
        checkpoint.clear("test topic")
        assert checkpoint.load("test topic") is None

    def test_clear_missing_ok(self, checkpoint):
        # Should not raise even if file doesn't exist
        checkpoint.clear("nonexistent topic")

    def test_checkpoint_contains_dossier(self, checkpoint, sample_dossier):
        checkpoint.save("test topic", sample_dossier, "phase_1_complete", 0, 5)
        loaded = checkpoint.load("test topic")
        assert loaded["dossier"]["topic"] == "Pakistan Digital Currency"

    def test_checkpoint_has_timestamp(self, checkpoint, sample_dossier):
        checkpoint.save("test topic", sample_dossier, "phase_1_complete", 0, 5)
        loaded = checkpoint.load("test topic")
        assert "timestamp" in loaded

    def test_checkpoint_dir_created_on_init(self, checkpoint, tmp_path):
        assert (tmp_path / "checkpoints").exists()

    def test_checkpoint_different_topics_separate_files(self, checkpoint, sample_dossier):
        checkpoint.save("topic A", sample_dossier, "phase_1", 0, 3)
        checkpoint.save("topic B", sample_dossier, "phase_2", 1, 7)
        files = list(checkpoint.checkpoint_dir.glob("*.checkpoint.json"))
        assert len(files) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# _get_current_year
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetCurrentYear:
    """Test current year helper."""

    def test_returns_int(self, engine):
        year = engine._get_current_year()
        assert isinstance(year, int)

    def test_reasonable_year(self, engine):
        from datetime import datetime
        year = engine._get_current_year()
        assert year >= 2020
        assert year <= datetime.now().year + 1


# ═══════════════════════════════════════════════════════════════════════════════
# _multi_search (mocked)
# ═══════════════════════════════════════════════════════════════════════════════

class TestMultiSearch:
    """Test _multi_search budget enforcement."""

    @pytest.mark.asyncio
    async def test_search_count_increments(self, engine):
        mock_result = MagicMock()
        mock_result.title = "Test"
        mock_result.snippet = "Test snippet"
        mock_result.url = "https://example.com"

        with patch("packages.content_factory.production.deep_research.WebSearchClient") as mock_ws_cls:
            mock_ws = AsyncMock()
            mock_ws.search = AsyncMock(return_value=[mock_result])
            mock_ws.__aenter__ = AsyncMock(return_value=mock_ws)
            mock_ws.__aexit__ = AsyncMock(return_value=False)
            mock_ws_cls.return_value = mock_ws

            await engine._multi_search(["query1", "query2"], num_per_query=2)
            assert engine._search_count == 2

    @pytest.mark.asyncio
    async def test_search_budget_stops_early(self, engine):
        """When budget is reached, search stops."""
        engine.max_total_searches = 1
        engine._search_count = 0

        mock_result = MagicMock()
        mock_result.title = "Test"
        mock_result.snippet = "Test snippet"
        mock_result.url = "https://example.com"

        with patch("packages.content_factory.production.deep_research.WebSearchClient") as mock_ws_cls:
            mock_ws = AsyncMock()
            mock_ws.search = AsyncMock(return_value=[mock_result])
            mock_ws.__aenter__ = AsyncMock(return_value=mock_ws)
            mock_ws.__aexit__ = AsyncMock(return_value=False)
            mock_ws_cls.return_value = mock_ws

            results = await engine._multi_search(["q1", "q2", "q3"], num_per_query=2)
            assert engine._search_count == 1
            # Only first query should have results
            assert len(results) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# System prompts
# ═══════════════════════════════════════════════════════════════════════════════

class TestSystemPrompts:
    """Verify system prompts are defined."""

    def test_researcher_prompt_exists(self):
        assert "investigative researcher" in SYSTEM_RESEARCHER.lower()

    def test_dimension_extractor_prompt_exists(self):
        assert "dimension" in SYSTEM_DIMENSION_EXTRACTOR.lower()

    def test_fact_extractor_prompt_exists(self):
        assert "fact extraction" in SYSTEM_FACT_EXTRACTOR.lower()

"""
production/deep_research.py — Deep Research Engine (from deer-flow methodology).

Context: This engine implements the systematic multi-angle research methodology
from deer-flow's deep-research skill. It replaces the simple single-prompt
research approach with a 4-phase systematic process.

PHASES:
  1. Broad Exploration  — Understand the landscape, identify key dimensions
  2. Deep Dive          — Targeted research on each dimension
  3. Diversity & Validation — Ensure all information types are covered
  4. Synthesis Check    — Verify quality bar before proceeding

Usage:
    from packages.content_factory.production.deep_research import DeepResearchEngine

    engine = DeepResearchEngine(router_client=client)
    dossier = await engine.research(
        topic="Pakistan's Digital Currency",
        genre="current_situation",
        target_completeness=0.8
    )
    markdown = dossier.to_markdown()  # For script writer

Imports: packages.router.web_search, packages.router.client
Imported by: packages/content_factory/production/workflow.py
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any, Optional

from packages.core.logger import get_logger
from packages.router.client import RouterClient
from packages.router.web_search import WebSearchClient, SearchResult

from .models import (
    AnchorType,
    DimensionFindings,
    HumanCharacter,
    InformationType,
    PhysicalAnchor,
    ResearchDossier,
    ResearchFact,
)

log = get_logger(__name__)


# System prompts for different research phases
SYSTEM_RESEARCHER = """You are an elite investigative researcher building the foundation for a Johnny Harris-style documentary.

Your job is to uncover raw truth, tangible physical evidence, and human characters.

CRITICAL RULE: Do NOT write narrative. Do NOT write script prose. You are finding facts.
You must find:
1. Tangible physical objects, historical documents, or specific geographic locations (Anchors).
2. A specific human character whose story illustrates the macro problem.
3. Evidence that contradicts or complicates the mainstream narrative.

Output structured findings in the format requested."""

SYSTEM_DIMENSION_EXTRACTOR = """You are a research analyst. Extract key dimensions and subtopics from search results.

Identify 3-5 distinct angles or aspects that need deeper research.
Return ONLY a JSON array of dimension names.

Example: ["Economic Impact", "Political Response", "Public Opinion", "Historical Context"]"""

SYSTEM_FACT_EXTRACTOR = """You are a fact extraction specialist. Extract factual claims from text.

For each fact, identify:
- The statement itself
- The source or speaker
- The type of information (fact/data, example, opinion, trend, comparison, challenge)

Return ONLY valid JSON."""


class DeepResearchEngine:
    """
    Systematic research engine implementing deer-flow methodology.

    The engine orchestrates multiple search queries, extracts information
    from results, and assembles a comprehensive ResearchDossier.
    """

    def __init__(
        self,
        router_client: Optional[RouterClient] = None,
        max_searches_per_dimension: int = 3,
        max_total_searches: int = 20,
    ) -> None:
        """
        Initialize the research engine.

        Args:
            router_client: Optional RouterClient for LLM calls (creates its own if None)
            max_searches_per_dimension: Maximum searches per dimension
            max_total_searches: Total search budget
        """
        self._router = router_client
        self._owns_router = router_client is None
        self.max_searches_per_dimension = max_searches_per_dimension
        self.max_total_searches = max_total_searches
        self._search_count = 0

    async def research(
        self,
        topic: str,
        genre: str = "",
        references: Optional[list[Any]] = None,
        target_completeness: float = 0.8,
        max_iterations: int = 3,
    ) -> ResearchDossier:
        """
        Execute the full 4-phase research process.

        Args:
            topic: The research topic
            genre: Genre ID for structural reference
            references: Optional list of SourceVideoRecord for structural context
            target_completeness: Minimum completeness score (0.0-1.0)
            max_iterations: Maximum research iterations if completeness not met

        Returns:
            ResearchDossier with all findings
        """
        start_time = time.time()

        dossier = ResearchDossier(topic=topic, genre_id=genre)

        # Initialize router if needed
        if self._router is None:
            self._router = RouterClient()

        try:
            for iteration in range(max_iterations):
                log.info(f"research_iteration_{iteration + 1}: topic='{topic[:50]}...'")

                # Phase 1: Broad Exploration
                if iteration == 0:
                    dimensions = await self._phase_broad_exploration(topic, dossier)
                    dossier.dimensions_explored = dimensions
                else:
                    # Later iterations: find missing dimensions
                    missing = dossier.get_missing_elements()
                    dimensions = self._derive_dimensions_from_missing(missing)

                # Phase 2: Deep Dive
                for dim in dimensions:
                    if self._search_count >= self.max_total_searches:
                        log.warning(f"search_budget_exhausted: {self._search_count}")
                        break
                    await self._phase_deep_dive(topic, dim, dossier)

                # Phase 3: Diversity & Validation
                await self._phase_diversity_validation(topic, dossier)

                # Phase 4: Synthesis Check
                if dossier.is_complete(target_completeness):
                    log.info(f"research_complete: {dossier.to_research_summary()}")
                    break

                log.info(f"research_incomplete: missing={dossier.get_missing_elements()}")

            # Final calculation
            dossier.calculate_completeness()
            dossier.research_duration_seconds = time.time() - start_time
            dossier.search_queries_total = self._search_count

            log.info(
                f"research_finished: completeness={dossier.completeness_score:.0%} "
                f"searches={self._search_count} duration={dossier.research_duration_seconds:.1f}s"
            )

            return dossier

        finally:
            # Close router if we own it
            if self._owns_router and self._router is not None:
                await self._router.close()

    async def _phase_broad_exploration(
        self,
        topic: str,
        dossier: ResearchDossier,
    ) -> list[str]:
        """
        Phase 1: Broad exploration to identify key dimensions.

        Executes multiple broad searches and extracts dimensions from results.
        """
        log.info(f"phase_1_broad_exploration: topic='{topic[:50]}'")

        # Build initial queries with current year for relevance
        current_year = self._get_current_year()
        queries = [
            f"{topic} overview {current_year}",
            f"{topic} key issues challenges",
            f"{topic} stakeholders perspectives",
            f"what is {topic} explained",
        ]

        results = await self._multi_search(queries, num_per_query=5)

        # Extract text content from results
        all_snippets = []
        for query, search_results in results.items():
            for r in search_results:
                dossier.add_source(r.url)
                all_snippets.append(f"{r.title}: {r.snippet}")

        # Use LLM to extract dimensions from snippets
        combined_text = "\n".join(all_snippets[:20])  # Limit context
        dimensions = await self._extract_dimensions(combined_text, topic)

        log.info(f"phase_1_complete: dimensions={dimensions}")
        return dimensions

    async def _phase_deep_dive(
        self,
        topic: str,
        dimension: str,
        dossier: ResearchDossier,
    ) -> None:
        """
        Phase 2: Deep dive into a specific dimension.

        Executes targeted searches and extracts facts, anchors, and characters.
        """
        log.info(f"phase_2_deep_dive: dimension='{dimension}'")

        # Build dimension-specific queries
        queries = [
            f"{topic} {dimension} statistics data",
            f"{topic} {dimension} case study example",
            f"{topic} {dimension} expert analysis opinion",
            f"{topic} {dimension} Pakistan",  # Localize to Pakistan context
        ]

        results = await self._multi_search(queries, num_per_query=3)

        # Process results
        dimension_findings = DimensionFindings(dimension_name=dimension)
        dimension_findings.search_queries_used = queries

        for query, search_results in results.items():
            for r in search_results:
                dossier.add_source(r.url)
                dimension_findings.sources_consulted.append(r.url)

                # Extract facts from each result
                text = f"{r.title}\n{r.snippet}"
                facts = await self._extract_facts(text, r.url, r.title)
                for fact in facts:
                    self._add_fact_to_dossier(dossier, fact)
                    dimension_findings.facts.append(fact)

                # Check for anchors
                anchors = self._extract_anchors_from_text(text, r.url)
                for anchor in anchors:
                    dossier.add_anchor(anchor)

                # Check for human characters
                characters = self._extract_characters_from_text(text, r.url)
                for char in characters:
                    dossier.add_character(char)

        dossier.dimension_findings[dimension] = dimension_findings
        log.info(f"phase_2_dimension_complete: facts={len(dimension_findings.facts)}")

    async def _phase_diversity_validation(
        self,
        topic: str,
        dossier: ResearchDossier,
    ) -> None:
        """
        Phase 3: Ensure all 6 information types are covered.

        Checks for missing types and executes targeted searches.
        """
        log.info("phase_3_diversity_validation")

        # Check current coverage
        info_type_queries = {
            InformationType.FACTS_DATA: f"{topic} statistics numbers data",
            InformationType.EXAMPLES_CASES: f"{topic} case study example real world",
            InformationType.EXPERT_OPINIONS: f"{topic} expert interview analysis opinion",
            InformationType.TRENDS: f"{topic} trends forecast future {self._get_current_year()}",
            InformationType.COMPARISONS: f"{topic} comparison vs alternatives",
            InformationType.CHALLENGES: f"{topic} criticism challenges limitations problems",
        }

        # Determine which types need more coverage
        coverage = {
            InformationType.FACTS_DATA: len(dossier.facts_and_data) >= 3,
            InformationType.EXAMPLES_CASES: len(dossier.examples_cases) >= 2,
            InformationType.EXPERT_OPINIONS: len(dossier.expert_opinions) >= 1,
            InformationType.TRENDS: len(dossier.trends) >= 1,
            InformationType.COMPARISONS: len(dossier.comparisons) >= 1,
            InformationType.CHALLENGES: len(dossier.challenges) >= 1,
        }

        # Update coverage tracking
        dossier.information_type_coverage = {t.value: v for t, v in coverage.items()}

        # Search for missing types
        missing_types = [t for t, covered in coverage.items() if not covered]

        for info_type in missing_types:
            if self._search_count >= self.max_total_searches:
                break

            query = info_type_queries[info_type]
            results = await self._search(query, num_results=5)

            for r in results:
                dossier.add_source(r.url)
                text = f"{r.title}\n{r.snippet}"
                facts = await self._extract_facts(text, r.url, r.title, info_type)
                for fact in facts:
                    self._add_fact_to_dossier(dossier, fact)

        log.info(f"phase_3_complete: coverage={dossier.information_type_coverage}")

    async def _search(self, query: str, num_results: int = 10) -> list[SearchResult]:
        """Execute a single search query."""
        self._search_count += 1

        async with WebSearchClient() as client:
            return await client.search(query, num_results)

    async def _multi_search(
        self,
        queries: list[str],
        num_per_query: int = 5,
    ) -> dict[str, list[SearchResult]]:
        """Execute multiple searches in parallel."""
        self._search_count += len(queries)

        async with WebSearchClient() as client:
            return await client.multi_search(queries, num_per_query)

    async def _extract_dimensions(self, text: str, topic: str) -> list[str]:
        """Use LLM to extract research dimensions from text."""
        try:
            # Use the router client (sync or async depending on setup)
            if self._router is None:
                self._router = RouterClient()

            prompt = f"""Analyze this search result summary about "{topic}" and identify 3-5 key dimensions or subtopics that need deeper research.

Search Results:
{text[:2000]}

Return ONLY a JSON array of dimension names (short phrases).
Example: ["Economic Impact", "Political Response", "Public Opinion"]"""

            response = await self._router.complete_text(
                prompt,
                system=SYSTEM_DIMENSION_EXTRACTOR,
                model="auto",
                max_tokens=500,
            )

            # Parse JSON array
            match = re.search(r'\[.*?\]', response, re.DOTALL)
            if match:
                dimensions = json.loads(match.group(0))
                if isinstance(dimensions, list):
                    return [str(d).strip() for d in dimensions if d]

        except Exception as e:
            log.warning(f"dimension_extraction_failed: {e}")

        # Fallback dimensions
        return ["Overview", "Key Issues", "Impact"]

    async def _extract_facts(
        self,
        text: str,
        source_url: str,
        source_name: str,
        default_type: InformationType = InformationType.FACTS_DATA,
    ) -> list[ResearchFact]:
        """Extract factual claims from text."""
        facts = []

        # Simple heuristic extraction (can be enhanced with LLM)
        sentences = text.split(". ")
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence or len(sentence) < 20:
                continue

            # Heuristics for different fact types
            fact_type = default_type

            # Check for statistics/numbers
            if re.search(r'\d+%|\d+\s*(million|billion|thousand)|\$\d+', sentence, re.I):
                fact_type = InformationType.FACTS_DATA

            # Check for expert/expert opinion indicators
            elif re.search(r'expert|analyst|professor|researcher says|according to', sentence, re.I):
                fact_type = InformationType.EXPERT_OPINIONS

            # Check for case/example indicators
            elif re.search(r'for example|case study|such as|instance of', sentence, re.I):
                fact_type = InformationType.EXAMPLES_CASES

            # Check for trend indicators
            elif re.search(r'trend|forecast|future|will|expected to|projected', sentence, re.I):
                fact_type = InformationType.TRENDS

            # Check for comparison
            elif re.search(r'compared to|versus|vs\.|than|more than|less than', sentence, re.I):
                fact_type = InformationType.COMPARISONS

            # Check for challenges
            elif re.search(r'however|but|challenge|problem|limitation|critics', sentence, re.I):
                fact_type = InformationType.CHALLENGES

            facts.append(ResearchFact(
                statement=sentence[:500],  # Limit length
                source_url=source_url,
                source_name=source_name,
                information_type=fact_type,
                confidence=0.7,  # Default confidence
            ))

        return facts[:5]  # Limit per source

    def _extract_anchors_from_text(
        self,
        text: str,
        source_url: str,
    ) -> list[PhysicalAnchor]:
        """Extract potential physical anchors from text."""
        anchors = []

        # Patterns for different anchor types
        patterns = {
            AnchorType.DOCUMENT: [
                r'(?:report|document|paper|study|file|records?)\s+(?:titled|called|named)?\s*["\']?([^"\']{5,50})["\']?',
                r'(?:according to|cited in)\s+(?:the\s+)?([A-Z][^,]{5,40}(?:Report|Study|Document))',
            ],
            AnchorType.LOCATION: [
                r'(?:in|at|from)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:,\s+[A-Z][a-z]+)?)',
                r'(?:located|headquartered|based)\s+in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            ],
            AnchorType.OBJECT: [
                r'(?:the\s+)?([a-z]+\s+(?:building|monument|statue|artifact|collection))',
                r'(?:physical|tangible)\s+([a-z\s]{5,30})',
            ],
            AnchorType.DATA_VIZ: [
                r'(?:chart|graph|map|diagram|visualization)\s+(?:showing|of)\s+([^,\.]{5,40})',
                r'(?:data\s+shows|statistics\s+reveal)\s+([^,\.]{5,40})',
            ],
        }

        for anchor_type, type_patterns in patterns.items():
            for pattern in type_patterns:
                matches = re.finditer(pattern, text, re.I)
                for match in matches:
                    description = match.group(1).strip()
                    if len(description) > 5:
                        anchors.append(PhysicalAnchor(
                            description=description[:200],
                            anchor_type=anchor_type,
                            hierarchy_level=self._estimate_hierarchy_level(anchor_type),
                            source_url=source_url,
                        ))

        return anchors[:3]  # Limit per text

    def _estimate_hierarchy_level(self, anchor_type: AnchorType) -> int:
        """Estimate Anchor Substitution Hierarchy level based on type."""
        hierarchy = {
            AnchorType.DOCUMENT: 1,  # Primary source artifacts
            AnchorType.LOCATION: 2,  # Geographic proof
            AnchorType.OBJECT: 2,    # Tangible objects
            AnchorType.ARCHIVE: 2,   # Archive footage
            AnchorType.DATA_VIZ: 4,  # Abstract data visualization
        }
        return hierarchy.get(anchor_type, 3)

    def _extract_characters_from_text(
        self,
        text: str,
        source_url: str,
    ) -> list[HumanCharacter]:
        """Extract potential human characters from text."""
        characters = []

        # Pattern for named individuals with roles
        patterns = [
            r'([A-Z][a-z]+\s+[A-Z][a-z]+),?\s+(?:a\s+)?([a-z\s]+(?:expert|official|minister|director|CEO|advocate|victim|witness))',
            r'([A-Z][a-z]+\s+[A-Z][a-z]+),?\s+(?:who\s+)?([^\.]{10,50})',
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                name = match.group(1).strip()
                role_or_story = match.group(2).strip()

                # Avoid duplicates and generic names
                if name.lower() in ("the government", "the ministry"):
                    continue

                characters.append(HumanCharacter(
                    name=name,
                    role=role_or_story[:100],
                    story_summary=f"Mentioned in context: {role_or_story[:100]}",
                    relevance="Potential character illustrating the topic",
                    source_url=source_url,
                ))

        return characters[:2]  # Limit per text

    def _add_fact_to_dossier(
        self,
        dossier: ResearchDossier,
        fact: ResearchFact,
    ) -> None:
        """Add a fact to the appropriate list in the dossier."""
        if fact.information_type == InformationType.FACTS_DATA:
            dossier.facts_and_data.append(fact)
        elif fact.information_type == InformationType.EXAMPLES_CASES:
            dossier.examples_cases.append(fact)
        elif fact.information_type == InformationType.EXPERT_OPINIONS:
            dossier.expert_opinions.append(fact)
        elif fact.information_type == InformationType.TRENDS:
            dossier.trends.append(fact)
        elif fact.information_type == InformationType.COMPARISONS:
            dossier.comparisons.append(fact)
        elif fact.information_type == InformationType.CHALLENGES:
            dossier.challenges.append(fact)

    def _derive_dimensions_from_missing(self, missing: list[str]) -> list[str]:
        """Derive research dimensions from missing elements."""
        dimension_map = {
            "facts_and_data": "Statistics and Data",
            "examples_cases": "Case Studies",
            "expert_opinions": "Expert Analysis",
            "physical_anchors": "Tangible Evidence",
            "human_characters": "Personal Stories",
            "challenges": "Counterarguments",
        }

        dimensions = []
        for missing_item in missing:
            for key, dimension in dimension_map.items():
                if key in missing_item and dimension not in dimensions:
                    dimensions.append(dimension)

        return dimensions if dimensions else ["Additional Research"]

    def _get_current_year(self) -> int:
        """Get the current year for temporal queries."""
        from datetime import datetime
        return datetime.now().year

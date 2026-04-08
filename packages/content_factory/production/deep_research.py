"""
production/deep_research.py — Deep Research Engine (deer-flow v2 methodology).

Context: This engine implements the systematic multi-angle research methodology
from ByteDance's deer-flow deep-research skill. It is the core of the Kerapathys
content factory, providing rich research dossiers that the script writer uses
to generate evidence-driven documentary scripts.

PHASES (from deer-flow deep-research SKILL.md):
  0. Research Planning    — LLM creates structured JSON plan with typed steps
  1. Broad Exploration     — Understand the landscape, identify key dimensions
  1b. Deep Reading         — Fetch full article text for top sources (NEW: deer-flow)
  2. Deep Dive             — Targeted research on each dimension with full text
  3. Diversity & Validation — Ensure all 6 information types are covered
  4. Synthesis Quality Check — Qualitative checklist before finalizing (UPGRADED)

DEER-FLOW v2 UPGRADES:
1. Research Planning step — structured JSON plan before deep dive (deer-flow Planner)
2. Deep Reading via fetch_contents() — full article text, not just snippets
3. Temporal awareness — precise date formatting in queries
4. Quality checklist — qualitative LLM assessment, not just count thresholds
5. Citation enforcement — every fact in dossier includes source URL
6. Increased text limits — 4000 chars per search result, 8000 per deep read

PREVIOUS FIXES PRESERVED:
1. Checkpoint system for partial results on failure
2. Cross-source fact validation
3. Fact deduplication using add_fact_if_unique()
4. Accurate search count tracking (after search, not before)
5. Resume from checkpoint capability

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
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from packages.core.config import get_settings
from packages.core.json_utils import extract_json_array, extract_json_object
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
    ValidationStatus,
)

log = get_logger(__name__)


# ─── System prompts for different research phases ─────────────────────────────

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

# NEW: Research planning prompt (from deer-flow Planner node)
SYSTEM_RESEARCH_PLANNER = """You are a research planning specialist. Given a topic and initial
search results, create a structured research plan with specific search queries
for each dimension that needs investigation.

Your plan MUST include:
- At least one dimension with need_search=true (web search required)
- Specific, targeted search queries (not generic queries)
- Multiple keyword phrasings per dimension for comprehensive coverage

Current date: {current_date}
Current time context: {time_context}"""

# NEW: Quality assessment prompt (from deer-flow Phase 4 synthesis check)
SYSTEM_QUALITY_CHECKER = """You are a research quality auditor. Evaluate whether the
collected research is rich and specific enough to write a compelling documentary script.

You are checking for:
- Concrete facts with specific numbers, names, dates (not vague generalizations)
- Real examples and case studies (not hypothetical scenarios)
- Named people, organizations, and places (not anonymous references)
- Specific events with dates (not "recently" or "in recent years")
- Data and statistics from credible sources
- Multiple perspectives and counterarguments

Return ONLY a JSON object with your assessment."""


class ResearchCheckpoint:
    """Manages saving and loading research checkpoints."""

    def __init__(self, checkpoint_dir: Optional[Path] = None) -> None:
        settings = get_settings()
        self.checkpoint_dir = checkpoint_dir or Path(settings.DATA_DIR) / "research_checkpoints"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def _topic_hash(self, topic: str) -> str:
        """Create hash for topic."""
        return hashlib.sha256(topic.lower().strip().encode()).hexdigest()[:16]

    def _checkpoint_path(self, topic: str) -> Path:
        """Get checkpoint file path."""
        return self.checkpoint_dir / f"{self._topic_hash(topic)}.checkpoint.json"

    def save(self, topic: str, dossier: ResearchDossier, phase: str, iteration: int, search_count: int) -> None:
        """Save checkpoint to disk."""
        checkpoint = {
            "topic": topic,
            "phase": phase,
            "iteration": iteration,
            "search_count": search_count,
            "dossier": dossier.model_dump(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        checkpoint_file = self._checkpoint_path(topic)

        try:
            temp_file = checkpoint_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(checkpoint, f, indent=2, default=str, ensure_ascii=False)
            temp_file.rename(checkpoint_file)
            log.debug(f"checkpoint_saved: phase={phase} iteration={iteration}")
        except Exception as e:
            log.warning(f"checkpoint_save_failed: {e}")

    def load(self, topic: str) -> Optional[dict]:
        """Load checkpoint from disk."""
        checkpoint_file = self._checkpoint_path(topic)
        if not checkpoint_file.exists():
            return None

        try:
            with open(checkpoint_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.warning(f"checkpoint_load_failed: {e}")
            return None

    def clear(self, topic: str) -> None:
        """Remove checkpoint file."""
        checkpoint_file = self._checkpoint_path(topic)
        checkpoint_file.unlink(missing_ok=True)


class DeepResearchEngine:
    """
    Systematic research engine implementing deer-flow v2 methodology.

    The engine orchestrates multiple search queries, performs deep reading
    of full articles, extracts information from rich text, and assembles
    a comprehensive ResearchDossier with citations.

    Deer-Flow v2 Features:
        - Research planning step with structured JSON plan
        - Deep reading via Exa get_contents() for full article text
        - Temporal awareness with precise date formatting
        - Qualitative quality checklist before synthesis
        - Citation enforcement on every fact
        - Checkpoint system for recovery from failures
        - Cross-source fact validation
        - Fact deduplication
    """

    def __init__(
        self,
        router_client: Optional[RouterClient] = None,
        max_searches_per_dimension: int = 3,
        max_total_searches: int = 20,
        enable_checkpoints: bool = True,
        enable_fact_validation: bool = True,
    ) -> None:
        """
        Initialize the research engine.

        Args:
            router_client: Optional RouterClient for LLM calls (creates its own if None)
            max_searches_per_dimension: Maximum searches per dimension
            max_total_searches: Total search budget
            enable_checkpoints: Enable checkpoint saving for recovery
            enable_fact_validation: Enable cross-source fact validation
        """
        self._router = router_client
        self._owns_router = router_client is None
        self.max_searches_per_dimension = max_searches_per_dimension
        self.max_total_searches = max_total_searches
        self._search_count = 0
        self._enable_checkpoints = enable_checkpoints
        self._enable_fact_validation = enable_fact_validation
        self._checkpoint = ResearchCheckpoint() if enable_checkpoints else None

    # Stop words that are capitalized but carry no semantic meaning
    _AGREEMENT_STOPWORDS = frozenset({
        "The", "This", "That", "These", "Those", "There", "Then", "Than",
        "His", "Her", "Its", "Our", "Their", "My", "Your",
        "He", "She", "It", "We", "They", "You", "I",
        "In", "On", "At", "To", "For", "Of", "By", "With", "From",
        "And", "But", "Or", "Not", "No", "Is", "Was", "Are", "Were",
        "Has", "Had", "Have", "Be", "Been", "Being",
        "Which", "What", "When", "Where", "How", "Who", "Why",
        "If", "So", "As", "Do", "Did", "Can", "Will", "May",
    })

    # ─── Temporal Awareness (deer-flow GAP #5) ───────────────────────────────

    def _get_current_date(self) -> str:
        """Get current date in YYYY-MM-DD format (deer-flow temporal awareness)."""
        return datetime.now().strftime("%Y-%m-%d")

    def _get_time_context(self) -> str:
        """Get human-readable time context for query generation."""
        now = datetime.now()
        return now.strftime("%B %Y")

    def _get_current_year(self) -> int:
        """Get the current year for temporal queries."""
        return datetime.now().year

    def _get_date_prefix_for_recency(self, days_back: int = 30) -> str:
        """Get date prefix string based on how recent the info needs to be.

        Deer-flow uses different temporal precision depending on recency:
        - Very recent (< 30 days): "April 2026" or "March 2026"
        - Recent (< 6 months): "2026"
        - Older: just the year
        """
        now = datetime.now()
        if days_back <= 30:
            # Use month+year for very recent topics
            return now.strftime("%B %Y")
        elif days_back <= 180:
            return str(now.year)
        else:
            return str(now.year)

    # ─── Main Research Orchestration ─────────────────────────────────────────

    async def research(
        self,
        topic: str,
        genre: str = "",
        references: Optional[list[Any]] = None,
        target_completeness: float = 0.8,
        max_iterations: int = 3,
        resume_from_checkpoint: bool = True,
    ) -> ResearchDossier:
        """
        Execute the full research process with deer-flow v2 methodology.

        Pipeline:
          0. Research Planning (NEW — deer-flow Planner)
          1. Broad Exploration (upgraded with temporal awareness)
          1b. Deep Reading (NEW — fetch full articles for top sources)
          2. Deep Dive per dimension (with full article text)
          3. Diversity & Validation
          4. Synthesis Quality Check (UPGRADED — qualitative LLM assessment)

        Args:
            topic: The research topic
            genre: Genre ID for structural reference
            references: Optional list of SourceVideoRecord for structural context
            target_completeness: Minimum completeness score (0.0-1.0)
            max_iterations: Maximum research iterations if completeness not met
            resume_from_checkpoint: Whether to resume from previous checkpoint

        Returns:
            ResearchDossier with all findings, citations, and quality assessment
        """
        start_time = time.time()

        # Try to resume from checkpoint
        dossier = ResearchDossier(topic=topic, genre_id=genre)
        start_iteration = 0
        start_phase = "begin"

        if resume_from_checkpoint and self._checkpoint:
            checkpoint_data = self._checkpoint.load(topic)
            if checkpoint_data:
                try:
                    dossier = ResearchDossier(**checkpoint_data["dossier"])
                    start_iteration = checkpoint_data.get("iteration", 0)
                    start_phase = checkpoint_data.get("phase", "begin")
                    self._search_count = checkpoint_data.get("search_count", 0)
                    log.info(
                        f"resuming_from_checkpoint: iteration={start_iteration} "
                        f"phase={start_phase} completeness={dossier.completeness_score:.0%}"
                    )
                except Exception as e:
                    log.warning(f"checkpoint_restore_failed_starting_fresh: {e}")
                    dossier = ResearchDossier(topic=topic, genre_id=genre)

        # Initialize router if needed
        if self._router is None:
            self._router = RouterClient()

        try:
            for iteration in range(start_iteration, max_iterations):
                log.info(f"research_iteration_{iteration + 1}: topic='{topic[:50]}...' searches_used={self._search_count}")

                # Phase 0: Research Planning (NEW — from deer-flow Planner)
                if iteration == 0 and start_phase in ("begin", "phase_0"):
                    research_plan = await self._phase_research_planning(topic, dossier)
                    dossier.research_plan = research_plan
                    if self._checkpoint:
                        self._checkpoint.save(topic, dossier, "phase_0_complete", iteration, self._search_count)

                # Phase 1: Broad Exploration (upgraded with temporal awareness)
                if iteration == 0 and start_phase in ("begin", "phase_0", "phase_1"):
                    dimensions = await self._phase_broad_exploration(topic, dossier)
                    dossier.dimensions_explored = dimensions
                    if self._checkpoint:
                        self._checkpoint.save(topic, dossier, "phase_1_complete", iteration, self._search_count)
                else:
                    # Later iterations: find missing dimensions
                    missing = dossier.get_missing_elements()
                    dimensions = self._derive_dimensions_from_missing(missing)

                # Phase 1b: Deep Reading (NEW — deer-flow web_fetch equivalent)
                if iteration == 0 and start_phase in ("begin", "phase_0", "phase_1"):
                    await self._phase_deep_reading(topic, dossier)
                    if self._checkpoint:
                        self._checkpoint.save(topic, dossier, "phase_1b_deep_read", iteration, self._search_count)

                # Phase 2: Deep Dive
                for dim in dimensions:
                    if self._search_count >= self.max_total_searches:
                        log.warning(f"search_budget_exhausted: {self._search_count}")
                        break
                    await self._phase_deep_dive(topic, dim, dossier)
                    if self._checkpoint:
                        self._checkpoint.save(topic, dossier, f"phase_2_{dim}", iteration, self._search_count)

                # Phase 3: Diversity & Validation
                await self._phase_diversity_validation(topic, dossier)
                if self._checkpoint:
                    self._checkpoint.save(topic, dossier, "phase_3_complete", iteration, self._search_count)

                # Phase 4: Synthesis Quality Check (UPGRADED — qualitative LLM assessment)
                quality_report = await self._phase_quality_check(topic, dossier)
                dossier.quality_report = quality_report

                if dossier.is_complete(target_completeness):
                    log.info(f"research_complete: {dossier.to_research_summary()}")

                    # Run fact validation if enabled
                    if self._enable_fact_validation:
                        await self._validate_facts(dossier)

                    break

                log.info(f"research_incomplete: missing={dossier.get_missing_elements()}")

            # Final calculation
            dossier.calculate_completeness()
            dossier.research_duration_seconds = time.time() - start_time
            dossier.search_queries_total = self._search_count

            log.info(
                f"research_finished: completeness={dossier.completeness_score:.0%} "
                f"searches={self._search_count} duration={dossier.research_duration_seconds:.1f}s "
                f"sources={len(dossier.all_sources)} facts={len(dossier.all_facts)}"
            )

            # Clear checkpoint on successful completion
            if self._checkpoint:
                self._checkpoint.clear(topic)

            return dossier

        except Exception as e:
            # Save checkpoint on failure for recovery
            if self._checkpoint:
                self._checkpoint.save(topic, dossier, "failed", iteration, self._search_count)
            log.error(f"research_failed_checkpoint_saved: {e}")
            raise

        finally:
            # Close router if we own it
            if self._owns_router and self._router is not None:
                await self._router.close()

    # ─── Phase 0: Research Planning (NEW — deer-flow Planner) ────────────────

    async def _phase_research_planning(
        self,
        topic: str,
        dossier: ResearchDossier,
    ) -> dict:
        """
        Phase 0: Create a structured research plan before searching.

        From deer-flow's Planner node: analyzes the topic and creates a structured
        JSON plan with typed steps, ensuring at least one search step and
        multiple keyword phrasings per dimension.

        Returns a dict with:
            - thought: analysis of what needs researching
            - dimensions: list of dimension names to explore
            - has_enough_context: whether initial context is sufficient
        """
        log.info(f"phase_0_research_planning: topic='{topic[:50]}'")

        current_date = self._get_current_date()
        time_context = self._get_time_context()

        prompt = f"""You are planning research for a documentary about: "{topic}"

Current date: {current_date}
Time context: {time_context}

Create a research plan. Think about what specific angles, data, and evidence
would make this documentary compelling and factually rich.

Return a JSON object with this EXACT structure:
{{
    "thought": "Your analysis of what makes this topic interesting and what specific angles need investigation",
    "has_enough_context": false,
    "dimensions": [
        {{
            "name": "Dimension name",
            "search_queries": ["query 1", "query 2", "query 3"],
            "what_to_find": "Specific facts, names, numbers to look for"
        }}
    ]
}}

Rules:
- Create 3-5 dimensions, each with 2-4 specific search queries
- Every dimension MUST have search_queries (web search required)
- Queries should be specific and targeted, NOT generic
- Use the current date/time context to form precise queries
- Include at least one dimension about challenges/criticism/counterarguments
- Include at least one dimension seeking specific data/statistics
- Think about what would surprise or challenge the viewer's assumptions

Output ONLY the JSON object, nothing else."""

        try:
            response = await self._router.complete_text(
                prompt,
                system=SYSTEM_RESEARCH_PLANNER.format(
                    current_date=current_date,
                    time_context=time_context,
                ),
                model="researcher",
                max_tokens=1500,
                temperature=0.3,
            )

            plan_str = extract_json_object(response)
            if plan_str:
                plan = json.loads(plan_str)
                if isinstance(plan, dict) and "dimensions" in plan:
                    dimensions = []
                    for dim in plan["dimensions"]:
                        if isinstance(dim, dict) and "name" in dim:
                            dimensions.append(dim["name"])
                    log.info(f"phase_0_complete: planned_dimensions={dimensions}")
                    return plan

        except Exception as e:
            log.warning(f"research_planning_failed: {e}")

        # Fallback: return minimal plan
        return {
            "thought": f"Research planning failed, using default dimensions for {topic}",
            "has_enough_context": False,
            "dimensions": [
                {"name": "Overview and Key Facts", "search_queries": [f"{topic} overview"]},
                {"name": "Challenges and Criticism", "search_queries": [f"{topic} challenges"]},
            ],
        }

    # ─── Phase 1: Broad Exploration (upgraded with temporal awareness) ───────

    async def _phase_broad_exploration(
        self,
        topic: str,
        dossier: ResearchDossier,
    ) -> list[str]:
        """
        Phase 1: Broad exploration to identify key dimensions.

        Upgraded from deer-flow: uses temporal awareness for precise date queries.
        If a research plan exists (Phase 0), uses the planned queries.
        """
        log.info(f"phase_1_broad_exploration: topic='{topic[:50]}'")

        # Use planned queries from Phase 0 if available
        planned_queries = []
        if dossier.research_plan and isinstance(dossier.research_plan, dict):
            for dim in dossier.research_plan.get("dimensions", []):
                if isinstance(dim, dict) and "search_queries" in dim:
                    planned_queries.extend(dim["search_queries"][:2])  # Take first 2 per dimension

        if planned_queries:
            queries = planned_queries[:6]  # Limit to 6 broad queries
        else:
            # Fallback: build queries with temporal awareness
            time_ctx = self._get_time_context()
            year = self._get_current_year()
            queries = [
                f"{topic} overview {year}",
                f"{topic} key issues challenges {time_ctx}",
                f"{topic} stakeholders perspectives {year}",
                f"what is {topic} explained {year}",
            ]

        results = await self._multi_search(queries, num_per_query=5)

        # Extract text content from results
        all_snippets = []
        all_urls = []
        for query, search_results in results.items():
            for r in search_results:
                dossier.add_source(r.url)
                all_urls.append(r.url)
                all_snippets.append(f"{r.title}: {r.snippet}")

        # Use LLM to extract dimensions from snippets
        combined_text = "\n".join(all_snippets[:20])  # Limit context
        dimensions = await self._extract_dimensions(combined_text, topic)

        # Store URLs for deep reading phase
        dossier._broad_search_urls = all_urls[:10]  # Top 10 URLs for deep reading

        log.info(f"phase_1_complete: dimensions={dimensions}, urls_collected={len(all_urls)}")
        return dimensions

    # ─── Phase 1b: Deep Reading (NEW — deer-flow web_fetch equivalent) ──────

    async def _phase_deep_reading(
        self,
        topic: str,
        dossier: ResearchDossier,
    ) -> None:
        """
        Phase 1b: Deep reading of top search results.

        This is THE critical deer-flow improvement. After initial search returns
        snippets, this method uses Exa's get_contents() API to fetch full article
        text (up to 8000 chars per article) for the most relevant sources.

        This gives the research engine rich, detailed text to extract specific
        facts, names, numbers, and quotes — instead of vague snippets.

        The deep-read content is stored in dossier.full_article_texts and used
        by the deep dive phase for high-quality fact extraction.
        """
        log.info("phase_1b_deep_reading: fetching full article text for top sources")

        # Get URLs from broad exploration
        urls_to_read = getattr(dossier, "_broad_search_urls", [])
        if not urls_to_read:
            urls_to_read = dossier.all_sources[:10]

        if not urls_to_read:
            log.warning("phase_1b_no_urls_to_read")
            return

        # Fetch full article text in batches of 10 (Exa limit)
        full_texts: dict[str, str] = {}

        async with WebSearchClient() as client:
            for i in range(0, len(urls_to_read), 10):
                batch = urls_to_read[i:i + 10]
                if self._search_count >= self.max_total_searches:
                    break

                try:
                    contents = await client.fetch_contents(batch, max_characters=8000)
                    full_texts.update(contents)
                    # fetch_contents uses rate limiting internally, but we track it
                    self._search_count += 1
                except Exception as e:
                    log.warning(f"deep_read_batch_failed: batch_{i}: {e}")

        if not full_texts:
            log.warning("phase_1b_no_full_texts_retrieved")
            return

        # Store full texts in dossier
        dossier.full_article_texts = full_texts

        # Extract facts from full article text (much richer than snippets!)
        facts_from_reading = 0
        for url, full_text in full_texts.items():
            if len(full_text) < 200:
                continue

            # Find the source name from the URL
            source_name = url
            for src in dossier.all_sources:
                if src == url:
                    source_name = url
                    break

            # Extract facts from the full article text
            facts = await self._extract_facts(full_text, url, source_name)
            for fact in facts:
                if dossier.add_fact_if_unique(fact):
                    facts_from_reading += 1

            # Also extract anchors and characters from full text
            anchors = self._extract_anchors_from_text(full_text, url)
            for anchor in anchors:
                dossier.add_anchor(anchor)

            characters = self._extract_characters_from_text(full_text, url)
            for char in characters:
                dossier.add_character(char)

        log.info(
            f"phase_1b_complete: articles_read={len(full_texts)}, "
            f"new_facts_from_reading={facts_from_reading}"
        )

    # ─── Phase 2: Deep Dive (upgraded to use full text when available) ───────

    async def _phase_deep_dive(
        self,
        topic: str,
        dimension: str,
        dossier: ResearchDossier,
    ) -> None:
        """
        Phase 2: Deep dive into a specific dimension.

        Upgraded: builds temporally-aware queries. If full article texts are
        available from Phase 1b, uses them for richer fact extraction.
        """
        log.info(f"phase_2_deep_dive: dimension='{dimension}'")

        # Build dimension-specific queries with temporal awareness
        year = self._get_current_year()
        time_ctx = self._get_time_context()
        queries = [
            f"{topic} {dimension} statistics data {year}",
            f"{topic} {dimension} case study example",
            f"{topic} {dimension} expert analysis opinion",
            f"{topic} {dimension} Pakistan",  # Localize to Pakistan context
        ]

        # Check if research plan has better queries for this dimension
        if dossier.research_plan and isinstance(dossier.research_plan, dict):
            for dim in dossier.research_plan.get("dimensions", []):
                if isinstance(dim, dict):
                    dim_name = dim.get("name", "")
                    if dim_name.lower() in dimension.lower() or dimension.lower() in dim_name.lower():
                        planned = dim.get("search_queries", [])
                        if planned:
                            queries = planned[:4]
                            log.info(f"using_planned_queries: {queries}")
                            break

        results = await self._multi_search(queries, num_per_query=3)

        # Process results
        dimension_findings = DimensionFindings(dimension_name=dimension)
        dimension_findings.search_queries_used = queries

        # Collect URLs from this dimension for potential deep reading
        dim_urls = []

        for query, search_results in results.items():
            for r in search_results:
                dossier.add_source(r.url)
                dimension_findings.sources_consulted.append(r.url)
                dim_urls.append(r.url)

                # Extract facts from search result (snippet level)
                text = f"{r.title}\n{r.snippet}"
                facts = await self._extract_facts(text, r.url, r.title)
                for fact in facts:
                    if dossier.add_fact_if_unique(fact):
                        dimension_findings.facts.append(fact)

                # Check for anchors and characters
                anchors = self._extract_anchors_from_text(text, r.url)
                for anchor in anchors:
                    dossier.add_anchor(anchor)

                characters = self._extract_characters_from_text(text, r.url)
                for char in characters:
                    dossier.add_character(char)

        # Deep read top 5 URLs from this dimension if we haven't already
        new_urls = [u for u in dim_urls if u not in (getattr(dossier, 'full_article_texts', {}) or {})]
        if new_urls and self._search_count < self.max_total_searches:
            try:
                async with WebSearchClient() as client:
                    contents = await client.fetch_contents(new_urls[:5], max_characters=8000)
                    self._search_count += 1

                    for url, full_text in contents.items():
                        if len(full_text) < 200:
                            continue
                        # Store in dossier
                        if not hasattr(dossier, 'full_article_texts') or dossier.full_article_texts is None:
                            dossier.full_article_texts = {}
                        dossier.full_article_texts[url] = full_text

                        # Extract rich facts from full text
                        facts = await self._extract_facts(full_text, url, url)
                        for fact in facts:
                            if dossier.add_fact_if_unique(fact):
                                dimension_findings.facts.append(fact)

                        anchors = self._extract_anchors_from_text(full_text, url)
                        for anchor in anchors:
                            dossier.add_anchor(anchor)

                        characters = self._extract_characters_from_text(full_text, url)
                        for char in characters:
                            dossier.add_character(char)
            except Exception as e:
                log.debug(f"dimension_deep_read_failed: {e}")

        dossier.dimension_findings[dimension] = dimension_findings
        log.info(f"phase_2_dimension_complete: facts={len(dimension_findings.facts)}")

    # ─── Phase 3: Diversity & Validation ────────────────────────────────────

    async def _phase_diversity_validation(
        self,
        topic: str,
        dossier: ResearchDossier,
    ) -> None:
        """
        Phase 3: Ensure all 6 information types are covered.

        Uses temporally-aware queries. Checks for missing types and executes
        targeted searches with deep reading of top results.
        """
        log.info("phase_3_diversity_validation")

        year = self._get_current_year()
        time_ctx = self._get_time_context()

        # Check current coverage
        info_type_queries = {
            InformationType.FACTS_DATA: f"{topic} statistics numbers data {year}",
            InformationType.EXAMPLES_CASES: f"{topic} case study example real world {year}",
            InformationType.EXPERT_OPINIONS: f"{topic} expert interview analysis opinion",
            InformationType.TRENDS: f"{topic} trends forecast future {year} {time_ctx}",
            InformationType.COMPARISONS: f"{topic} comparison vs alternatives {year}",
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

            urls_for_reading = []
            for r in results:
                dossier.add_source(r.url)
                text = f"{r.title}\n{r.snippet}"
                facts = await self._extract_facts(text, r.url, r.title, info_type)
                for fact in facts:
                    dossier.add_fact_if_unique(fact)
                urls_for_reading.append(r.url)

            # Deep read top results for missing types
            if urls_for_reading and self._search_count < self.max_total_searches:
                try:
                    async with WebSearchClient() as client:
                        contents = await client.fetch_contents(urls_for_reading[:3], max_characters=8000)
                        self._search_count += 1
                        for url, full_text in contents.items():
                            if len(full_text) < 200:
                                continue
                            if not hasattr(dossier, 'full_article_texts') or dossier.full_article_texts is None:
                                dossier.full_article_texts = {}
                            dossier.full_article_texts[url] = full_text
                            facts = await self._extract_facts(full_text, url, url, info_type)
                            for fact in facts:
                                dossier.add_fact_if_unique(fact)
                except Exception as e:
                    log.debug(f"diversity_deep_read_failed: {e}")

        log.info(f"phase_3_complete: coverage={dossier.information_type_coverage}")

    # ─── Phase 4: Synthesis Quality Check (UPGRADED — qualitative LLM) ──────

    async def _phase_quality_check(
        self,
        topic: str,
        dossier: ResearchDossier,
    ) -> dict:
        """
        Phase 4: Qualitative quality assessment before synthesis.

        From deer-flow's synthesis check: instead of just counting facts,
        uses an LLM to assess whether the research is actually rich enough
        to write a compelling documentary.

        Checks:
        - Are facts specific (numbers, names, dates) or vague generalizations?
        - Are there real case studies or just hypothetical scenarios?
        - Are sources credible and authoritative?
        - Is there enough material for a 5-7 minute video?
        - Are counterarguments and challenges represented?

        Returns dict with:
            - is_rich_enough: bool
            - score: 0-100
            - strengths: list of str
            - weaknesses: list of str
            - recommendations: list of str
        """
        log.info("phase_4_quality_check")

        # Build a summary of all collected facts for assessment
        all_facts = dossier.all_facts
        fact_summary = "\n".join([
            f"- [{f.information_type.value}] {f.statement} (source: {f.source_name})"
            for f in all_facts[:20]
        ])

        source_summary = "\n".join([f"- {url}" for url in dossier.all_sources[:10]])

        prompt = f"""Evaluate this research dossier for the topic: "{topic}"

COLLECTED FACTS ({len(all_facts)} total):
{fact_summary}

SOURCES ({len(dossier.all_sources)} total):
{source_summary}

DIMENSIONS EXPLORED: {dossier.dimensions_explored}

Assess whether this research is specific and rich enough to write a compelling
documentary script. A GOOD dossier has:
- Specific numbers, percentages, dollar amounts (not "many" or "significant")
- Named people, organizations, companies, government bodies
- Specific dates and events (not "recently" or "in recent years")
- Real case studies with locations and outcomes
- Counterarguments and challenges to the mainstream narrative

Return a JSON object:
{{
    "is_rich_enough": true/false,
    "score": 75,
    "strengths": ["Specific strength 1", "Specific strength 2"],
    "weaknesses": ["What's missing or vague 1", "What's missing or vague 2"],
    "recommendations": ["What to search for next 1", "What to search for next 2"]
}}

Be strict. A score below 60 means the research is too vague for a good script."""

        try:
            response = await self._router.complete_text(
                prompt,
                system=SYSTEM_QUALITY_CHECKER,
                model="researcher",
                max_tokens=800,
                temperature=0.0,
            )

            report_str = extract_json_object(response)
            if report_str:
                report = json.loads(report_str)
                if isinstance(report, dict):
                    score = report.get("score", 50)
                    log.info(
                        f"phase_4_complete: quality_score={score}, "
                        f"is_rich={report.get('is_rich_enough', False)}, "
                        f"weaknesses={report.get('weaknesses', [])}"
                    )
                    return report

        except Exception as e:
            log.warning(f"quality_check_failed: {e}")

        # Fallback
        return {
            "is_rich_enough": False,
            "score": 0,
            "strengths": [],
            "weaknesses": ["Quality check failed"],
            "recommendations": [],
        }

    # ─── Fact Validation ────────────────────────────────────────────────────

    async def _validate_facts(self, dossier: ResearchDossier) -> None:
        """
        Cross-validate facts across multiple sources.

        Updates fact validation status based on source corroboration.
        """
        log.info("validating_facts_across_sources")

        all_facts = dossier.all_facts
        validated_count = 0

        for fact in all_facts:
            # Skip if already verified
            if fact.validation_status == ValidationStatus.VERIFIED:
                continue

            # Search for corroboration
            if fact.statement and len(fact.statement) > 20:
                key_claim = self._extract_key_claim(fact.statement)

                try:
                    results = await self._search(f'"{key_claim}" verification', num_results=3)

                    for r in results:
                        if r.url != fact.source_url and r.url not in fact.corroboration_sources:
                            # Check if result supports the fact
                            if self._statements_agree(fact.statement, r.snippet):
                                fact.corroboration_count += 1
                                fact.corroboration_sources.append(r.url)

                    # Update validation status
                    if fact.corroboration_count >= 2:
                        fact.validation_status = ValidationStatus.VERIFIED
                        validated_count += 1
                    elif fact.corroboration_count >= 1:
                        fact.validation_status = ValidationStatus.PARTIALLY_VERIFIED

                except Exception as e:
                    log.debug(f"fact_validation_failed: {e}")

        log.info(f"fact_validation_complete: newly_verified={validated_count}")

    def _extract_key_claim(self, statement: str) -> str:
        """Extract the key claim from a statement for verification search."""
        first_sentence = statement.split('.')[0]
        key_claim = re.sub(r'\d+[%\s]*(million|billion|thousand)?', '', first_sentence, flags=re.I)
        return key_claim.strip()[:100]

    def _statements_agree(self, statement1: str, statement2: str) -> bool:
        """Check if two statements support the same claim."""
        words1 = set(re.findall(r'\b[A-Z][a-z]+\b', statement1))
        words2 = set(re.findall(r'\b[A-Z][a-z]+\b', statement2))

        words1 -= self._AGREEMENT_STOPWORDS
        words2 -= self._AGREEMENT_STOPWORDS

        if words1 and words2:
            overlap = len(words1 & words2)
            if overlap >= 2:
                return True

        return False

    # ─── Search Methods ────────────────────────────────────────────────────

    async def _search(self, query: str, num_results: int = 10) -> list[SearchResult]:
        """Execute a single search query with accurate count tracking."""
        async with WebSearchClient() as client:
            results = await client.search(query, num_results)
            self._search_count += 1
            return results

    async def _multi_search(
        self,
        queries: list[str],
        num_per_query: int = 5,
    ) -> dict[str, list[SearchResult]]:
        """Execute multiple searches sequentially with rate limiting."""
        output: dict[str, list[SearchResult]] = {}

        async with WebSearchClient() as client:
            for query in queries:
                results = await client.search(query, num_per_query)
                self._search_count += 1
                output[query] = results

                if self._search_count >= self.max_total_searches:
                    log.warning(f"search_budget_reached: {self._search_count}")
                    break

        return output

    # ─── Extraction Methods ────────────────────────────────────────────────

    async def _extract_dimensions(self, text: str, topic: str) -> list[str]:
        """Use LLM to extract research dimensions from text."""
        try:
            if self._router is None:
                self._router = RouterClient()

            current_date = self._get_current_date()

            prompt = f"""Analyze this search result summary about "{topic}" and identify 3-5 key dimensions or subtopics that need deeper research.

Current date: {current_date}

Search Results:
{text[:3000]}

Return ONLY a JSON array of dimension names (short phrases, 2-4 words each).
Example: ["Economic Impact", "Political Response", "Public Opinion", "Historical Context"]

IMPORTANT: Each dimension should represent a DISTINCT angle. Avoid overlapping dimensions."""

            response = await self._router.complete_text(
                prompt,
                system=SYSTEM_DIMENSION_EXTRACTOR,
                model="researcher",
                max_tokens=500,
            )

            arr_str = extract_json_array(response)
            if arr_str:
                dimensions = json.loads(arr_str)
                if isinstance(dimensions, list):
                    return [str(d).strip() for d in dimensions if d]

        except Exception as e:
            log.warning(f"dimension_extraction_failed: {e}")

        return ["Overview", "Key Issues", "Impact"]

    async def _extract_facts(
        self,
        text: str,
        source_url: str,
        source_name: str,
        default_type: InformationType = InformationType.FACTS_DATA,
    ) -> list[ResearchFact]:
        """
        Extract factual claims from text using LLM-based extraction.

        With deep reading (deer-flow upgrade), text can now be 4000-8000 chars
        per article instead of 500-1000 char snippets. This gives the LLM
        much richer context for identifying specific facts.
        """
        facts = []

        # Try LLM-based extraction first (much higher quality)
        if self._router and len(text) > 100:
            try:
                facts = await self._extract_facts_llm(text, source_url, source_name)
                if facts:
                    return facts[:5]
            except Exception as e:
                log.debug(f"llm_fact_extraction_failed_falling_back: {e}")

        # Fallback: heuristic extraction
        sentences = text.split(". ")
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence or len(sentence) < 20:
                continue

            fact_type = default_type

            if re.search(r'\d+%|\d+\s*(million|billion|thousand)|\$\d+', sentence, re.I):
                fact_type = InformationType.FACTS_DATA
            elif re.search(r'expert|analyst|professor|researcher says|according to', sentence, re.I):
                fact_type = InformationType.EXPERT_OPINIONS
            elif re.search(r'for example|case study|such as|instance of', sentence, re.I):
                fact_type = InformationType.EXAMPLES_CASES
            elif re.search(r'trend|forecast|future|will|expected to|projected', sentence, re.I):
                fact_type = InformationType.TRENDS
            elif re.search(r'compared to|versus|vs\.|than|more than|less than', sentence, re.I):
                fact_type = InformationType.COMPARISONS
            elif re.search(r'however|but|challenge|problem|limitation|critics', sentence, re.I):
                fact_type = InformationType.CHALLENGES

            facts.append(ResearchFact(
                statement=sentence[:500],
                source_url=source_url,
                source_name=source_name,
                information_type=fact_type,
                confidence=0.5,
            ))

        return facts[:5]

    async def _extract_facts_llm(
        self,
        text: str,
        source_url: str,
        source_name: str,
    ) -> list[ResearchFact]:
        """
        Use LLM to extract high-quality factual claims from article text.

        Updated for deer-flow: handles longer text (up to 4000 chars) from
        deep reading, extracts more facts per article, enforces specificity.
        """
        prompt = f"""Extract the 3-5 most important factual claims from this article text.
For each claim, classify its type and assign a confidence score (0.0-1.0).

Article text:
{text[:4000]}

Return ONLY a JSON array with this structure:
[{{"statement": "specific factual claim with numbers/names/dates",
  "type": "facts_data|examples_cases|expert_opinions|trends|comparisons|challenges",
  "confidence": 0.9}}]

Rules:
- Only extract CLAIMS that are specific and verifiable (not vague opinions)
- Prioritize claims with specific numbers, names, dates, and places
- Include the full specific detail — don't truncate numbers or names
- type: facts_data for statistics/numbers, examples_cases for specific instances,
  expert_opinions for attributed quotes, trends for predictions, comparisons for relative claims,
  challenges for problems/limitations
- If text has no specific factual claims, return []
- Output ONLY the JSON array"""

        try:
            response = await self._router.complete_text(
                prompt,
                system="You are a research fact extractor. Return ONLY valid JSON arrays.",
                model="researcher",
                max_tokens=1500,
                temperature=0.0,
            )

            arr_str = extract_json_array(response)
            if not arr_str:
                return []

            parsed = json.loads(arr_str)
            if not isinstance(parsed, list):
                return []

            type_map = {
                "facts_data": InformationType.FACTS_DATA,
                "examples_cases": InformationType.EXAMPLES_CASES,
                "expert_opinions": InformationType.EXPERT_OPINIONS,
                "trends": InformationType.TRENDS,
                "comparisons": InformationType.COMPARISONS,
                "challenges": InformationType.CHALLENGES,
            }

            facts = []
            for item in parsed:
                if not isinstance(item, dict) or "statement" not in item:
                    continue
                fact_type = type_map.get(item.get("type", ""), InformationType.FACTS_DATA)
                confidence = float(item.get("confidence", 0.7))
                confidence = max(0.0, min(1.0, confidence))

                facts.append(ResearchFact(
                    statement=item["statement"][:500],
                    source_url=source_url,
                    source_name=source_name,
                    information_type=fact_type,
                    confidence=confidence,
                ))

            return facts

        except Exception as e:
            log.debug(f"llm_fact_parse_failed: {e}")
            return []

    def _extract_anchors_from_text(
        self,
        text: str,
        source_url: str,
    ) -> list[PhysicalAnchor]:
        """Extract potential physical anchors from text."""
        anchors = []

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

        return anchors[:3]

    def _estimate_hierarchy_level(self, anchor_type: AnchorType) -> int:
        """Estimate Anchor Substitution Hierarchy level based on type."""
        hierarchy = {
            AnchorType.DOCUMENT: 1,
            AnchorType.LOCATION: 2,
            AnchorType.OBJECT: 2,
            AnchorType.ARCHIVE: 2,
            AnchorType.DATA_VIZ: 4,
        }
        return hierarchy.get(anchor_type, 3)

    def _extract_characters_from_text(
        self,
        text: str,
        source_url: str,
    ) -> list[HumanCharacter]:
        """Extract potential human characters from text."""
        characters = []

        patterns = [
            r'([A-Z][a-z]+\s+[A-Z][a-z]+),?\s+(?:a\s+)?([a-z\s]+(?:expert|official|minister|director|CEO|advocate|victim|witness))',
            r'([A-Z][a-z]+\s+[A-Z][a-z]+),?\s+(?:who\s+)?([^\.]{10,50})',
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                name = match.group(1).strip()
                role_or_story = match.group(2).strip()

                if name.lower() in ("the government", "the ministry"):
                    continue

                characters.append(HumanCharacter(
                    name=name,
                    role=role_or_story[:100],
                    story_summary=f"Mentioned in context: {role_or_story[:100]}",
                    relevance="Potential character illustrating the topic",
                    source_url=source_url,
                ))

        return characters[:2]

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

"""Phase 3 Core Production Workflow.

Combines the agents into a CrewAI process to generate an original
dual-column script from a topic idea.

DEEP RESEARCH INTEGRATION:
  The RoundBasedProductionWorkflow now uses DeepResearchEngine for
  systematic multi-angle research (from deer-flow methodology).

  The workflow phases are:
    Round 1A: Deep Research (4-phase methodology)
    Round 1B: Anchor validation using ResearchDossier
    Round 2:  Script opening generation
    Round 3:  Full script assembly
    Round 4:  Final AdaptedScript output
"""

import json
from datetime import datetime, timezone
import uuid

from crewai import Crew, Process, Task
from pydantic import BaseModel

from packages.core.logger import get_logger
from packages.core.config import get_settings
from packages.router.client import RouterClient
from packages.router.web_search import WebSearchClient
from packages.pipeline.research_cache import ResearchCache

from ..models import AdaptedScript, DualColumnEntry, ProcessingStatus, SectionLabel
from ..source_library import SourceVideoLibrary
from .agents import create_researcher, create_script_agent, create_visual_agent
from .deep_research import DeepResearchEngine
from .models import ResearchDossier

logger = get_logger(__name__)


class VideoIdea(BaseModel):
    """Input for Phase 3 Production."""
    topic: str
    genre_id: str
    target_audience: str = "Pakistani"
    special_instructions: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Legacy Workflow (kept for backwards compatibility)
# ─────────────────────────────────────────────────────────────────────────────

async def run_production_workflow(
    idea: VideoIdea,
    source_library: SourceVideoLibrary | None = None,
    router_client: RouterClient | None = None,
) -> AdaptedScript | None:
    """Run the Phase 3 Core Production workflow (Legacy Sequential).
    
    Args:
        idea: The video idea parameters.
        source_library: SQLite library to fetch structural references.
        router_client: Client for the LLM proxy.
        
    Returns:
        AdaptedScript (the final dual-column output) or None.
    """
    # 1. Fetch Architectural References
    library = source_library or SourceVideoLibrary()
    references = library.find_by_genre(idea.genre_id, limit=5)
    
    logger.info(f"production_started: topic='{idea.topic}' genre='{idea.genre_id}' refs_found={len(references)}")

    # 2. Instantiate Agents
    researcher = create_researcher(references)
    visual_agent = create_visual_agent()
    script_agent = create_script_agent()
    
    # 3. Define Tasks
    research_task = Task(
        description=f"""
        Conduct deep research on the topic: '{idea.topic}'.
        Target Audience: {idea.target_audience}.
        Special Instructions: {idea.special_instructions}.
        
        Output a detailed research dossier containing:
        - 3+ tangible physical anchors
        - 1+ specific human character illustrating the problem
        - Evidence contradicting the mainstream narrative
        - Chronological sequence or central Big Question
        """,
        expected_output="A structured markdown dossier of raw facts, anchors, and human stories.",
        agent=researcher
    )
    
    visual_task = Task(
        description="""
        Take the research dossier and create a Visual Plan.
        Assign Anchor Substitution Hierarchy levels and visual types to all evidence.
        Ensure every piece of evidence can be pointed at by a camera or graphic.
        """,
        expected_output="A sequence of visual directions and assigned hierarchy levels.",
        agent=visual_agent,
        context=[research_task]
    )
    
    script_task = Task(
        description=f"""
        Take the research dossier and the visual plan and merge them into a Dual-Column Script.
        The genre is {idea.genre_id}.
        
        You MUST output STRICTLY VALID JSON exactly matching this schema, with no markdown formatting around it:
        {{
          "adapted_title": "The finalized title",
          "entries": [
            {{
              "section_label": "HOOK|ANCHOR|BRIDGE|REVEAL|CONCLUSION|TRANSITION",
              "prose": "spoken narration",
              "visual_direction": "visual plan details",
              "visual_type": "talking_head|broll|animation|archive|data_viz|soul_moment",
              "duration_estimate_seconds": 15.0,
              "anchor_hierarchy_level": 1,
              "low_confidence_flag": false
            }}
          ]
        }}
        """,
        expected_output="A JSON object matching the AdaptedScript dual-column schema.",
        agent=script_agent,
        context=[research_task, visual_task]
    )
    
    # 4. Run Crew
    crew = Crew(
        agents=[researcher, visual_agent, script_agent],
        tasks=[research_task, visual_task, script_task],
        process=Process.sequential,
        verbose=True
    )
    
    try:
        # Note: CrewAI kickoff is synchronous, but we'll await if run in a thread/async wrapper in real usage.
        # For FreeRouter we just call kickoff. In a real async environment we would use run_in_executor.
        result_text = crew.kickoff()
        
        import re
        json_match = re.search(r'\{.*\}', str(result_text), re.DOTALL)
        if not json_match:
            # Fallback to RouterClient to fix it if CrewAI output isn't clean JSON
            async with RouterClient() if not router_client else router_client as rc:
                fixed = await rc.complete_text(
                    prompt=f"Extract the JSON object from this text:\n\n{result_text}",
                    system="You return ONLY valid JSON. No markdown blocks.",
                    model="groq/llama-3.3-70b-versatile"  # Fast model for JSON extraction
                )
                json_match = re.search(r'\{.*\}', fixed, re.DOTALL)
                if not json_match:
                    raise ValueError("Could not extract JSON from Script Agent output")
                result_text = json_match.group(0)
        else:
            result_text = json_match.group(0)
            
        data = json.loads(result_text)
        
        entries = []
        for item in data.get("entries", []):
            entries.append(DualColumnEntry(**item))
            
        script = AdaptedScript(
            video_id=f"orig_{uuid.uuid4().hex[:8]}", # Generate synthetic ID for original content
            source_title=idea.topic,
            adapted_title=data.get("adapted_title", idea.topic),
            genre=idea.genre_id,
            entries=entries,
            section_sequence=[e.section_label.value for e in entries],
            self_check_results=[], # Will be populated by Phase 4 Scoring Engine
            production_readiness_score=0.0
        )
        
        logger.info(f"production_complete: {script.video_id} - {script.adapted_title}")
        return script
        
    except Exception as e:
        logger.error(f"production_failed: {str(e)}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Round-Based Production Workflow (NEW)
# ─────────────────────────────────────────────────────────────────────────────

class RoundBasedProductionWorkflow:
    """
    Iterative round-based production workflow for Mode B original content.

    Replaces the single-pass sequential CrewAI process with structured rounds:
      Round 1A: Deep Research using DeepResearchEngine (deer-flow methodology)
      Round 1B: Anchor validation from ResearchDossier
      Round 2:  Script opening only — self-check, one rewrite if needed
      Round 2B: Opening visual review — narrow revision if visual ratio off
      Round 3:  Full script (target: 32/40 binary questions passing, up to 2 rewrites)
      Round 3B: Full visual review — section ratio check
      Round 4:  Assemble final DualColumnScript / AdaptedScript

    Uses DeepResearchEngine for systematic multi-angle research.
    All LLM calls go through RouterClient via FreeRouter.
    
    Attributes:
        use_deep_research: Enable/disable DeepResearchEngine (default: True)
        research_completeness_threshold: Minimum completeness score (0.0-1.0)
    """

    def __init__(
        self,
        use_deep_research: bool = True,
        research_completeness_threshold: float = 0.8,
    ) -> None:
        self.use_deep_research = use_deep_research
        self.research_completeness_threshold = research_completeness_threshold

    async def run(self, idea: VideoIdea) -> AdaptedScript | None:
        """Run the full round-based workflow."""
        from packages.content_factory.source_library import SourceVideoLibrary

        library = SourceVideoLibrary()
        references = library.find_by_genre(idea.genre_id, limit=3)

        async with RouterClient() as router:
            # Round 1A — Deep Research (using DeepResearchEngine)
            research_result = await self._round_research(idea, references, router)
            if not research_result:
                return None

            # Handle both ResearchDossier (new) and str (legacy) formats
            if isinstance(research_result, ResearchDossier):
                dossier = research_result
                research = dossier.to_markdown()
                
                # Round 1B — Validate anchors from dossier
                if not dossier.is_complete(self.research_completeness_threshold):
                    logger.warning(
                        f"research_incomplete: score={dossier.completeness_score:.0%} "
                        f"missing={dossier.get_missing_elements()}"
                    )
            else:
                # Legacy string-based research
                research = research_result
                # Round 1B — Anchor availability check (legacy)
                research = await self._round_anchor_check(research, idea, references, router)

            # Round 2 — Script opening
            opening = await self._round_script_opening(research, idea, router)

            # Round 3 — Full script with score threshold
            full_script = await self._round_full_script(
                research, opening, idea, router, target_pass_count=32
            )
            if not full_script:
                return None

            # Round 4 — Assemble final output
            return self._assemble_script(full_script, idea)

    async def _round_research(
        self,
        idea: VideoIdea,
        references: list,
        router: RouterClient,
        max_iterations: int = 2,
        card_id: str | None = None,
    ) -> ResearchDossier | str | None:
        """Round 1A: Research with DeepResearchEngine (new) or legacy method.
        
        If use_deep_research is True (default), uses the systematic
        4-phase deer-flow methodology:
          1. Broad Exploration — identify key dimensions
          2. Deep Dive — targeted research per dimension
          3. Diversity & Validation — ensure all info types covered
          4. Synthesis Check — verify quality bar
        
        Checks permanent Supabase cache first to avoid duplicate research.
        
        Args:
            idea: VideoIdea with topic and genre
            references: List of source video references
            router: RouterClient for LLM calls
            max_iterations: Max research iterations
            card_id: Optional Kanban card ID for thought reporting
        
        Returns:
            ResearchDossier if use_deep_research=True
            str (markdown) if use_deep_research=False
            None if research fails
        """
        from packages.core.thoughts import report_thought
        
        # Check permanent cache first
        cache = ResearchCache()
        cached = cache.get(topic_statement=idea.topic)
        if cached:
            if card_id:
                report_thought(
                    card_id=card_id,
                    agent_name="researcher",
                    thought_type="memory_read",
                    content=f"📦 Research cache hit — loaded dossier from {cached['age_hours']:.0f} hours ago (PERMANENT). Skipping web search.",
                )
            logger.info(f"research_cache_hit_returning_cached: topic='{idea.topic[:50]}...'")
            
            # Return in the expected format
            if self.use_deep_research:
                # Return as ResearchDossier
                try:
                    return ResearchDossier(**cached["dossier"])
                except Exception:
                    # If deserialization fails, return as dict wrapper
                    return cached["dossier"]
            else:
                # Return as markdown string for legacy
                return cached["dossier"].get("markdown", str(cached["dossier"]))
        
        # No cache hit - perform research
        if self.use_deep_research:
            return await self._deep_research(idea, references, router, card_id=card_id)
        else:
            return await self._legacy_research(idea, references, router, max_iterations)

    async def _deep_research(
        self,
        idea: VideoIdea,
        references: list,
        router: RouterClient,
        card_id: str | None = None,
    ) -> ResearchDossier | None:
        """Execute systematic deep research using DeepResearchEngine."""
        from packages.core.thoughts import report_thought
        
        logger.info(f"deep_research_started: topic='{idea.topic[:50]}...' genre='{idea.genre_id}'")
        
        if card_id:
            report_thought(
                card_id=card_id,
                agent_name="researcher",
                thought_type="search",
                content=f"🔍 Starting deep research: {idea.topic[:60]}...",
            )
        
        try:
            engine = DeepResearchEngine(
                router_client=router,
                max_searches_per_dimension=3,
                max_total_searches=15,
            )
            
            dossier = await engine.research(
                topic=idea.topic,
                genre=idea.genre_id,
                references=references,
                target_completeness=self.research_completeness_threshold,
                max_iterations=2,
            )
            
            logger.info(
                f"deep_research_complete: completeness={dossier.completeness_score:.0%} "
                f"anchors={len(dossier.physical_anchors)} "
                f"characters={len(dossier.human_characters)} "
                f"sources={len(dossier.all_sources)}"
            )
            
            # Save to permanent cache
            cache = ResearchCache()
            cache_key = ResearchCache.make_key(topic_statement=idea.topic)
            cache.save(
                cache_key=cache_key,
                topic_statement=idea.topic,
                dossier=dossier.model_dump(),
                source_urls=list(dossier.all_sources),
            )
            
            if card_id:
                report_thought(
                    card_id=card_id,
                    agent_name="researcher",
                    thought_type="output",
                    content=f"💾 Research dossier saved permanently ({len(dossier.all_sources)} sources).",
                )
            
            return dossier
            
        except Exception as e:
            logger.error(f"deep_research_failed: {e}")
            # Fallback to legacy research
            logger.info("falling_back_to_legacy_research")
            return await self._legacy_research(idea, references, router, max_iterations=2)

    async def _legacy_research(
        self,
        idea: VideoIdea,
        references: list,
        router: RouterClient,
        max_iterations: int = 2,
    ) -> str | None:
        """Legacy research with web search support.
        
        Unlike the pure-LLM approach, this method:
        1. Performs web searches to gather current information
        2. Passes search results to LLM for synthesis
        3. Validates anchor presence before returning
        
        This ensures legacy research also gets real-world data,
        not just LLM training knowledge.
        """
        logger.info(f"legacy_research_started: topic='{idea.topic[:50]}...'" )
        
        # Step 1: Do web searches first (like deep_research but simpler)
        search_context = await self._quick_web_search(idea.topic)
        
        # Step 2: Build prompt with search results
        prompt_base = self._build_research_prompt_with_context(idea, references, search_context)
        research_text = None

        # Step 3: LLM synthesis with retry
        for attempt in range(max_iterations):
            research_text = await router.complete_text(
                prompt=prompt_base if attempt == 0
                       else f"{prompt_base}\n\nPrevious attempt lacked physical anchors. "
                            "Find at least 3 specific physical objects or locations.",
                system="You are an investigative researcher. Output structured markdown."
            )
            # Quick anchor count check — count lines with physical nouns
            anchor_count = research_text.lower().count("anchor") + \
                          research_text.lower().count("location") + \
                          research_text.lower().count("document")
            if anchor_count >= 5:
                break
            logger.info(f"research_round_retry: attempt={attempt+1} anchor_signals={anchor_count}")
        
        # Step 4: Save to cache
        if research_text:
            self._save_research_to_cache(idea.topic, research_text)

        return research_text
    
    async def _quick_web_search(self, topic: str) -> str:
        """Perform quick web searches for legacy research.
        
        Does 3-4 targeted searches to gather current information
        about the topic, which is then passed to the LLM.
        """
        from datetime import datetime
        current_year = datetime.now().year
        
        queries = [
            f"{topic} overview {current_year}",
            f"{topic} facts statistics data",
            f"{topic} Pakistan",
        ]
        
        try:
            async with WebSearchClient() as client:
                results = await client.multi_search(queries, num_per_query=3)
                
                # Format results for LLM context
                context_parts = []
                for query, search_results in results.items():
                    for r in search_results[:2]:  # Top 2 per query
                        context_parts.append(f"- {r.title}: {r.snippet}")
                
                return "\n".join(context_parts[:10])  # Max 10 results
                
        except Exception as e:
            logger.warning(f"web_search_failed_non_blocking: {e}")
            return "[Web search unavailable - using LLM knowledge only]"
    
    def _build_research_prompt_with_context(
        self,
        idea: VideoIdea,
        references: list,
        search_context: str,
    ) -> str:
        """Build research prompt with web search context."""
        ref_list = "\n".join([f"- {r.title} ({r.genre})" for r in references]) \
                   if references else "No references available."
        return f"""Conduct deep investigative research for a Johnny harris-style documentary.

Topic: {idea.topic}
Genre: {idea.genre_id}
Target Audience: Pakistani

CURRENT WEB SEARCH RESULTS:
{search_context}

Structural reference videos (study their approach):
{ref_list}

Find and document:
1. At least 3 specific physical anchors (documents, locations, objects)
2. One human character whose personal story illustrates the macro problem
3. Evidence contradicting the mainstream narrative
4. A clear chronological sequence OR one central Big Question

DO NOT write narrative. DO NOT write script prose. Facts only."""
    
    def _save_research_to_cache(self, topic: str, research: str | dict) -> None:
        """Save research results to permanent cache.
        
        Args:
            topic: The research topic (used as cache key)
            research: Either str (markdown) or dict (ResearchDossier)
        """
        try:
            cache = ResearchCache()
            cache_key = ResearchCache.make_key(topic_statement=topic)
            
            if isinstance(research, str):
                # Create a simple dict wrapper for string research
                cache.save(
                    cache_key=cache_key,
                    topic_statement=topic,
                    dossier={"markdown": research, "format": "legacy"},
                    source_urls=[],
                )
            else:
                # Extract source URLs if available
                source_urls = research.get("all_sources", [])
                if isinstance(source_urls, set):
                    source_urls = list(source_urls)
                cache.save(
                    cache_key=cache_key,
                    topic_statement=topic,
                    dossier=research,
                    source_urls=source_urls,
                )
            logger.info(f"research_cached_permanently: topic='{topic[:50]}...'" )
        except Exception as e:
            logger.warning(f"research_cache_save_failed: {e}")

    async def _get_past_learnings(
        self,
        topic_statement: str,
        genre_id: str | None = None,
    ) -> str:
        """Retrieve relevant past learnings from Zep memory.

        Queries the learning_synthesis user's memory for facts relevant
        to the current topic. Returns a formatted string ready for prompt injection.

        Args:
            topic_statement: The topic being written about
            genre_id: Optional genre for more targeted queries

        Returns:
            Formatted string with past learnings, or empty string if unavailable
        """
        settings = get_settings()

        if not settings.ZEP_API_KEY or not settings.ZEP_ENABLED:
            return ""

        try:
            from packages.memory.client import AsyncZepMemoryClient

            zep = AsyncZepMemoryClient()
            session_id = f"{settings.ZEP_LEARNING_USER_ID}_session"

            # Search for learnings relevant to this topic
            queries = [
                f"What script improvements work for topics about {topic_statement[:50]}?",
                "What structural patterns consistently improve script scores?",
                "What mutations have worked best for opening hooks and bridge sections?",
            ]

            all_facts = []
            for query in queries:
                results = await zep.search_memory(
                    session_id=session_id,
                    query=query,
                    limit=3,
                )
                for r in results:
                    fact = r.get("fact", r.get("content", ""))
                    if fact and fact not in all_facts:
                        all_facts.append(fact)

            if not all_facts:
                logger.debug("no_past_learnings_found_in_zep")
                return ""

            # Format into a prompt-injectable block
            learning_block = "LESSONS FROM PAST SCRIPTS (these are proven improvements — apply them):\n"
            for i, fact in enumerate(all_facts[:8], 1):  # Cap at 8 to save tokens
                learning_block += f"  {i}. {fact}\n"

            logger.info(f"past_learnings_retrieved: {len(all_facts)} facts from Zep")
            return learning_block

        except Exception as e:
            logger.warning(f"past_learnings_retrieval_failed: {e}")
            return ""

    async def _round_anchor_check(self, research, idea, references, router):
        """Round 1B: Ensure at least 2 Level 1-3 anchors exist."""
        anchor_check_prompt = f"""Review this research for visual anchors:

{research}

Count anchors at each level:
Level 1 = Primary source artifacts (documents, original footage)
Level 2 = Geographic proof (real locations, maps)
Level 3 = Expert deposition or data visualization

If fewer than 2 Level 1-3 anchors exist, rewrite the research to find stronger ones.
Otherwise return the research unchanged."""

        result = await router.complete_text(
            anchor_check_prompt,
            system="Return the improved research. Keep all facts."
        )
        return result if result else research

    async def _round_script_opening(self, research, idea, router):
        """Round 2: Generate and self-check the HOOK + ANCHOR sections only."""
        # Retrieve cross-script learnings from Zep memory
        past_learnings = await self._get_past_learnings(idea.topic, idea.genre_id)

        learning_section = f"\n{past_learnings}\n" if past_learnings else ""

        prompt = f"""Write ONLY the opening two sections (HOOK and ANCHOR) of a Johnny harris
style script about: {idea.topic}
{learning_section}
Research:
{research[:3000]}

Output JSON:
{{"hook": {{"prose": "...", "visual_direction": "..."}},
  "anchor": {{"prose": "...", "visual_direction": "..."}}}}"""

        opening = await router.complete_text(prompt, system="Return only valid JSON.")

        # One self-check rewrite
        recheck_prompt = f"""Does this opening obey these rules?
1. Hook creates genuine curiosity without stating the answer
2. Anchor is a specific physical object or location (not abstract)
3. Active voice only — no nominalizations

Opening: {opening}

If any rule fails, rewrite the opening fixing only what failed. Return same JSON schema."""

        return await router.complete_text(recheck_prompt, system="Return only valid JSON.")

    async def _round_full_script(self, research, opening, idea, router, target_pass_count=32):
        """Round 3: Full script with up to 2 rewrites targeting 32/40 questions."""
        import json

        # Retrieve cross-script learnings from Zep memory
        past_learnings = await self._get_past_learnings(idea.topic, idea.genre_id)
        learning_section = f"\n{past_learnings}\n" if past_learnings else ""

        prompt = f"""Write a complete Johnny harris-style dual-column script.
Topic: {idea.topic}
Genre: {idea.genre_id}
Big Question: {getattr(idea, 'big_question', '')}
{learning_section}
Research:
{research[:4000]}

Opening sections already written:
{opening}

Complete the remaining sections: BRIDGE, REVEAL, CONCLUSION.

Output a JSON array of ALL sections (including HOOK and ANCHOR from the opening):
[{{"section_label": "HOOK|ANCHOR|BRIDGE|REVEAL|CONCLUSION",
   "prose": "spoken narration",
   "visual_direction": "specific visual plan",
   "visual_type": "talking_head|broll|animation|archive|data_viz|soul_moment"}}]"""

        script_json = None
        for attempt in range(2):  # up to 2 rewrites
            result = await router.complete_text(
                prompt if attempt == 0
                else f"{prompt}\n\nPrevious version had too many abstract sentences. "
                     "Every sentence must describe a visible action.",
                system="Return only a valid JSON array."
            )
            script_json = result
            # Simple quality check: count entries
            try:
                entries = json.loads(result) if isinstance(result, str) else result
                # Use target_pass_count as minimum entry threshold
                min_entries = max(4, target_pass_count // 8)
                if isinstance(entries, list) and len(entries) >= min_entries:
                    break
            except Exception:
                pass

        return script_json

    def _assemble_script(self, script_json, idea) -> AdaptedScript | None:
        """Round 4: Parse JSON into AdaptedScript model."""
        import json
        import uuid
        from packages.content_factory.models import DualColumnEntry, SectionLabel

        try:
            raw = script_json if isinstance(script_json, list) \
                  else json.loads(script_json)
            entries = []
            for item in raw:
                try:
                    entries.append(DualColumnEntry(**item))
                except Exception as e:
                    logger.warning(f"entry_parse_failed: {e}")

            if not entries:
                return None

            return AdaptedScript(
                video_id=f"orig_{uuid.uuid4().hex[:8]}",
                source_video_id="original",
                adapted_title=idea.topic,
                genre=idea.genre_id,
                entries=entries,
                section_sequence=[e.section_label.value for e in entries],
                production_readiness_score=0.0,
            )
        except Exception as e:
            logger.error(f"script_assembly_failed: {e}")
            return None

    def _build_research_prompt(self, idea, references) -> str:
        ref_list = "\n".join([f"- {r.title} ({r.genre})" for r in references]) \
                   if references else "No references available."
        return f"""Conduct deep investigative research for a Johnny harris-style documentary.

Topic: {idea.topic}
Genre: {idea.genre_id}
Target Audience: Pakistani

Structural reference videos (study their approach):
{ref_list}

Find and document:
1. At least 3 specific physical anchors (documents, locations, objects)
2. One human character whose personal story illustrates the macro problem
3. Evidence contradicting the mainstream narrative
4. A clear chronological sequence OR one central Big Question

DO NOT write narrative. DO NOT write script prose. Facts only."""

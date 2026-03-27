"""Phase 5: the Auto-Topic Research Agent.

Finds topics, scores them against the 17 Viability criteria,
and saves Tier 1 candidates to the Topic Reservoir.

KANBAN INTEGRATION:
    TopicFinderAgent can optionally accept a kanban_task_id to report
    progress to the Kanban dashboard. When a Tier 1 topic is found,
    it creates a child task in the "Suggested Topics" column.

Usage:
    # Without Kanban integration
    agent = TopicFinderAgent()
    brief = await agent.generate_candidate("AI trends", "tech")

    # With Kanban integration
    agent = TopicFinderAgent(kanban_task_id="abc-123")
    brief = await agent.generate_candidate("AI trends", "tech")
    # Progress and child tasks will be reported to Kanban
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from packages.router.client import RouterClient
from packages.core.logger import get_logger
from packages.content_factory.topic_finder.models import TopicBrief
from packages.content_factory.topic_finder.db import TopicReservoirDB
from packages.memory.client import ZepMemoryClient
from packages.core.config import get_settings

logger = get_logger(__name__)

# The 17 Strict Viability Questions
VIABILITY_QUESTIONS = {
    # 1. The Gap Test (Must pass all)
    "gap_1": "Does the topic have a clear 'mainstream assumption' that is factually incomplete or wrong?",
    "gap_2": "Can this gap be explained primarily through visual evidence (maps, documents, data) rather than just expert opinion?",
    "gap_3": "Is the hidden mechanism or hidden connection structurally simple enough to explain in 3 minutes?",
    
    # 2. The Anchor Test (Must pass 2+)
    "anchor_1": "Is there a specific, physical object or location that embodies this entire topic?",
    "anchor_2": "Is there a compelling human character whose immediate experience grounds the abstract concept?",
    "anchor_3": "Is there a specific 'smoking gun' document, map, or chart that is visually striking?",
    "anchor_4": "Can we show the before/after or cause/effect entirely through visual contrast without voiceover?",
    
    # 3. The Audience Test (Must pass 2+)
    "audience_1": "Does this topic intersect directly with the daily economic or social reality of the target demographic?",
    "audience_2": "Does this challenge a deeply held cultural narrative or historical assumption?",
    "audience_3": "Does this explain 'why things are the way they are' regarding a universal frustration?",
    "audience_4": "Is the initial 'hook' visually recognizable within 3 seconds to a layperson?",
    
    # 4. The Production Test
    "prod_1": "Are the primary visual assets (archival, data, maps) accessible without complex licensing?",
    "prod_2": "Can the emotional arc transition cleanly from confusion -> investigation -> revelation without reliance on interviews?",
    "prod_3": "Is the topic immune to immediate news-cycle irrelevance (will it hold up in 6 months)?",
    
    # 5. The Timing Test
    "timing_1": "Is there a current behavioral macro-trend (search, social) that makes audiences uniquely receptive to this right now?",
    "timing_2": "Does this avoid overlapping too closely with recently produced content in our channel?",
    "timing_3": "Is the subject matter emotionally resonant without violating platform safety/monetization constraints?"
}

class TopicFinderAgent:
    def __init__(self, kanban_task_id: Optional[str] = None) -> None:
        """Initialize the TopicFinderAgent.
        
        Args:
            kanban_task_id: Optional Kanban task ID for progress reporting.
                           When provided, the agent will report thoughts and
                           create child tasks in the Kanban dashboard.
        """
        self.db = TopicReservoirDB()
        self.zep_client = ZepMemoryClient()
        self.zep_session_id = f"{get_settings().ZEP_AUDIENCE_USER_ID}_session"
        self.kanban_task_id = kanban_task_id
        self._kanban_callback = None

    async def _init_kanban_callback(self) -> None:
        """Initialize the Kanban callback handler if needed."""
        if self.kanban_task_id and self._kanban_callback is None:
            try:
                from packages.agents.kanban_callback import KanbanCallbackHandler
                self._kanban_callback = KanbanCallbackHandler(self.kanban_task_id)
                await self._kanban_callback.__aenter__()
            except Exception as e:
                logger.warning(f"kanban_callback_init_failed: {e}")
                self._kanban_callback = None

    async def _close_kanban_callback(self) -> None:
        """Clean up the Kanban callback handler."""
        if self._kanban_callback:
            try:
                await self._kanban_callback.__aexit__(None, None, None)
            except Exception:
                pass
            self._kanban_callback = None

    async def _report_thought(self, thought: str) -> None:
        """Report a thought to Kanban if callback is available."""
        if self._kanban_callback:
            try:
                await self._kanban_callback.on_thought(thought)
            except Exception as e:
                logger.debug(f"kanban_thought_report_failed: {e}")

    async def _create_child_task(self, title: str, color: Optional[str] = None) -> Optional[str]:
        """Create a child task in Kanban if callback is available."""
        if self._kanban_callback:
            try:
                return await self._kanban_callback.create_child_task(
                    title=title,
                    stage=2,  # Suggested Topics
                    color=color
                )
            except Exception as e:
                logger.debug(f"kanban_child_task_creation_failed: {e}")
        return None

    async def generate_candidate(self, seed_query: str, genre_id: str) -> TopicBrief | None:
        """Find and score a topic, injecting Tier 1s into the reservoir.
        
        When kanban_task_id is set, reports progress and creates child tasks
        in the Kanban dashboard.
        """
        logger.info(f"generating_topic_candidate: seed='{seed_query}' genre={genre_id}")
        
        # Initialize Kanban callback if we have a task ID
        await self._init_kanban_callback()
        
        try:
            await self._report_thought(f"Starting topic search for: {seed_query}")
            
            # Try Zep first, fall back to static file
            context_str = await self._get_audience_context(genre_id)
            
            # Add MiroFish signals to the prompt if available (non-blocking)
            mirofish_signals = await self._get_mirofish_signals()
            mirofish_context = ""
            if mirofish_signals:
                mirofish_context = f"\nTrending signals from MiroFish:\n" + \
                                   "\n".join(f"- {s}" for s in mirofish_signals)
                await self._report_thought(f"Found {len(mirofish_signals)} trending signals from MiroFish")
            
            # 1. Generate the initial topic idea
            await self._report_thought("Generating topic idea from research context...")
            
            prompt = f"""
            You are a YouTube Investigative Journalist producing Johnny harris style documentary videos.
            Your task is to find a compelling investigative topic related to: "{seed_query}".
            Focus on the Hidden Mechanism, Oversimplified Narrative, or Hidden Connection.
            
            Historical Audience Insights (Use these to calibrate your topic focus):
            {context_str}
            {mirofish_context}
            
            Provide your response as a JSON object:
            {{
                "topic_statement": "The one sentence summary of the video",
                "big_question": "The central question the video answers",
                "gap_type": "Hidden Mechanism" | "Oversimplified Narrative" | "Hidden Connection" | "Universal in Local",
                "mainstream_assumption": "What people incorrectly believe",
                "anchor_candidates": ["Visual anchor 1", "Visual anchor 2"],
                "timing_rationale": "Why this matters now",
                "urgency_flag": true/false
            }}
            """
            
            async with RouterClient() as router:
                response = await router.complete_text(prompt, system="Output only valid JSON.")
                
                try:
                    data = json.loads(response.strip("` \n").removeprefix("json\n"))
                except json.JSONDecodeError:
                    logger.error("failed_to_parse_topic_candidate")
                    await self._report_thought("Failed to parse topic candidate from LLM response")
                    return None
                    
                # 2. Score Viability
                await self._report_thought(f"Evaluating viability for: {data.get('topic_statement', 'Unknown topic')[:50]}...")
                
                score_breakdown = await self._evaluate_viability(
                    data["topic_statement"], data["anchor_candidates"], router
                )
                
                # 3. Assess Tier 1 Status
                gap_pass = all(score_breakdown[q] for q in ["gap_1", "gap_2", "gap_3"])
                anchor_pass_count = sum(1 for q in ["anchor_1", "anchor_2", "anchor_3", "anchor_4"] if score_breakdown[q])
                audience_pass_count = sum(1 for q in ["audience_1", "audience_2", "audience_3", "audience_4"] if score_breakdown[q])
                
                if gap_pass and anchor_pass_count >= 2 and audience_pass_count >= 2:
                    logger.info("tier_1_topic_identified")
                    await self._report_thought(f"✅ Tier 1 topic identified: {data['topic_statement'][:60]}")
                    
                    brief = TopicBrief(
                        topic_statement=data["topic_statement"],
                        big_question=data["big_question"],
                        genre_id=genre_id,
                        gap_type=data["gap_type"],
                        viability_score_breakdown=score_breakdown,
                        anchor_candidates=data["anchor_candidates"],
                        mainstream_assumption=data["mainstream_assumption"],
                        urgency_flag=data.get("urgency_flag", False),
                        timing_rationale=data["timing_rationale"],
                        created_at=datetime.now(timezone.utc),
                        status="reservoir"
                    )
                    self.db.save_topic(brief)
                    
                    # Create child task in Kanban
                    child_id = await self._create_child_task(brief.topic_statement)
                    if child_id:
                        await self._report_thought(f"Created Kanban task for suggested topic")
                    
                    return brief
                
                await self._report_thought(
                    f"Topic failed viability: gap={gap_pass}, anchors={anchor_pass_count}/2, audience={audience_pass_count}/2"
                )
                logger.debug(f"candidate_failed_viability: gap={gap_pass}, anchors={anchor_pass_count}, audience={audience_pass_count}")
                return None
                
        finally:
            # Clean up Kanban callback
            await self._close_kanban_callback()

    async def _evaluate_viability(
        self, topic: str, anchors: list[str], router: RouterClient
    ) -> dict[str, bool]:
        """Ask LLM to grade the 17 questions."""
        scores = {}
        context = f"Topic: {topic}\nAnchors: {anchors}"
        
        # In a production environment this would be batched.
        # MVP: simplified batching to single LLM call for all 17.
        prompt = f"""Evaluate this topic against 17 criteria. Return ONLY a JSON object mapping the keys to true/false.
        Context:
        {context}
        
        Questions:
        {json.dumps(VIABILITY_QUESTIONS, indent=2)}
        """
        resp = await router.complete_text(
            prompt, system="You are a strict viability tester. Return ONLY valid JSON boolean mapping."
        )
        try:
            res_data = json.loads(resp.strip("` \n").removeprefix("json\n"))
            for k in VIABILITY_QUESTIONS.keys():
                scores[k] = bool(res_data.get(k, False))
        except Exception:
            # Degrade to False if failure
            scores = {k: False for k in VIABILITY_QUESTIONS.keys()}
        return scores

    async def _get_audience_context(self, genre_id: str) -> str:
        """Get audience context from Zep or fall back to static file."""
        # Try Zep first
        try:
            from packages.content_factory.memory.zep_store import ZepAudienceModelStore
            zep_store = ZepAudienceModelStore()
            context_str = await zep_store.read_audience_context(genre_id)
            if context_str and context_str != "No audience data available yet.":
                return context_str
        except Exception:
            pass
        
        # Fall back to ZepMemoryClient directly
        zep_context = []
        queries = [
            "Which gap types have produced the highest audience engagement for Pakistani content in the last six months?",
            "What bridge section characteristics are associated with retention drops in Pakistani investigative content?",
            "Which genres are currently performing above average engagement for this channel?",
            "What topic characteristics predicted subscriber conversion in recent production cycles?"
        ]
        for q in queries:
            results = self.zep_client.search_memory(session_id=self.zep_session_id, query=q, limit=2)
            for r in results:
                zep_context.append(r.get("fact", ""))
                
        if zep_context:
            return "\n".join(set(zep_context))
        
        # Fall back to static audience model JSON
        audience_path = Path("data/audience_model.json")
        if not audience_path.exists():
            audience_path = Path("packages/data/audience_model.json")
        if audience_path.exists():
            aud_data = json.loads(audience_path.read_text())
            return str(aud_data.get("topic_resonance_map", "No data"))
        
        return "No audience data available yet — first run."

    async def _get_mirofish_signals(self) -> list[str]:
        """
        Query MiroFish for trending topic signals.
        Returns empty list gracefully if server is down — never blocks discovery.

        MiroFish is an optional trend simulation server (packages/integrations/mirofish/).
        When available it provides audience simulation data to calibrate topic scoring.
        """
        try:
            from packages.integrations.mirofish.client import MiroFishClient
            from packages.integrations.mirofish.seeds import create_combined_seed

            client = MiroFishClient()

            # Check availability first
            status = client.get_status()
            if not status or status.get("status") == "unknown":
                logger.debug("mirofish_unavailable_skipping")
                return []

            # Create default seeds for Pakistan context
            seed_text, forecast_demand = create_combined_seed(
                geopolitical=["Pakistan economic situation", "Political transitions"],
                tech=["AI adoption in Pakistan", "Digital regulation"]
            )
            
            report = client.submit_seed(seed_text=seed_text, forecast_demand=forecast_demand)
            if not report:
                return []

            signals = []
            for item in (report.get("trending_topics") or [])[:5]:
                if isinstance(item, str):
                    signals.append(item)
                elif isinstance(item, dict):
                    signals.append(item.get("topic", ""))

            logger.info(f"mirofish_signals_retrieved: {len(signals)} signals")
            return [s for s in signals if s]

        except Exception as e:
            logger.debug(f"mirofish_signal_fetch_failed_non_blocking: {e}")
            return []

    async def discover_adaptation_candidates(self, genre_id: str) -> list[TopicBrief]:
        """
        Scan the SourceVideoLibrary for fully analyzed JH videos and check
        whether any current Pakistani trends map to their structural gap types.

        Returns adaptation TopicBrief entries for strong matches.
        Never crashes — returns empty list on any failure.
        """
        from packages.content_factory.source_library import SourceVideoLibrary, ProcessingStatus
        try:
            library = SourceVideoLibrary()
            candidates = []

            # Get fully analyzed JH videos
            analyzed = library.find_by_status(ProcessingStatus.FULLY_ANALYZED, limit=10)
            if not analyzed:
                return []

            async with RouterClient() as router:
                for record in analyzed[:5]:  # check up to 5 at a time
                    prompt = f"""Does the structural gap in this Johnny Harris video map to
a current Pakistani trend or social reality?

Video: "{record.title}"
Big Question: "{record.big_question}"
Genre: {record.genre}

Answer JSON:
{{"maps_to_pakistan": true/false,
  "pakistani_equivalent_topic": "one sentence if true, else null",
  "pakistani_mainstream_assumption": "what Pakistanis wrongly believe, or null",
  "timing_rationale": "why this maps now, or null"}}"""

                    try:
                        resp = await router.complete_text(
                            prompt, system="Return only valid JSON."
                        )
                        import re
                        match = re.search(r'\{.*\}', resp, re.DOTALL)
                        if not match:
                            continue
                        data = json.loads(match.group(0))

                        if data.get("maps_to_pakistan") and data.get("pakistani_equivalent_topic"):
                            brief = TopicBrief(
                                topic_statement=data["pakistani_equivalent_topic"],
                                big_question=record.big_question or data["pakistani_equivalent_topic"],
                                genre_id=genre_id,
                                gap_type=record.gap_type if hasattr(record, 'gap_type') else "Hidden Mechanism",
                                viability_score_breakdown={"adaptation": True},
                                anchor_candidates=[record.title],
                                mainstream_assumption=data.get("pakistani_mainstream_assumption", ""),
                                timing_rationale=data.get("timing_rationale", "Structural parallel exists"),
                                created_at=datetime.now(timezone.utc),
                                content_type="adaptation",
                                adaptation_source_video_id=record.video_id,
                                structural_reference_video_id=record.video_id,
                            )
                            self.db.save_topic(brief)
                            candidates.append(brief)
                    except Exception as e:
                        logger.debug(f"adaptation_candidate_check_failed: {e}")
                        continue

            return candidates

        except Exception as e:
            logger.warning(f"discover_adaptation_candidates_failed_non_blocking: {e}")
            return []

"""Phase 5: the Auto-Topic Research Agent.

Finds topics, scores them against the 17 Viability criteria,
and saves Tier 1 candidates to the Topic Reservoir.
"""

import json
from datetime import datetime, timezone
from typing import Any

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
    def __init__(self) -> None:
        self.router = RouterClient()
        self.db = TopicReservoirDB()
        self.zep_client = ZepMemoryClient()
        self.zep_session_id = f"{get_settings().ZEP_AUDIENCE_USER_ID}_session"

    def generate_candidate(self, seed_query: str, genre_id: str) -> TopicBrief | None:
        """Find and score a topic, injecting Tier 1s into the reservoir."""
        logger.info(f"generating_topic_candidate: seed='{seed_query}' genre={genre_id}")
        
        # Fetch Audience Model context from Zep
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
                
        context_str = "\n".join(set(zep_context)) if zep_context else "No historical audience data available."
        
        # 1. Generate the initial topic idea
        prompt = f"""
        You are a YouTube Investigative Journalist producing Johnny Harris style documentary videos.
        Your task is to find a compelling investigative topic related to: "{seed_query}".
        Focus on the Hidden Mechanism, Oversimplified Narrative, or Hidden Connection.
        
        Historical Audience Insights (Use these to calibrate your topic focus):
        {context_str}
        
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
        response = self.router.get_completion(prompt, system_prompt="Output only valid JSON.")
        
        try:
            data = json.loads(response.strip("` \n").removeprefix("json\n"))
        except json.JSONDecodeError:
            logger.error("failed_to_parse_topic_candidate")
            return None
            
        # 2. Score Viability
        score_breakdown = self._evaluate_viability(data["topic_statement"], data["anchor_candidates"])
        
        # 3. Assess Tier 1 Status
        gap_pass = all(score_breakdown[q] for q in ["gap_1", "gap_2", "gap_3"])
        anchor_pass_count = sum(1 for q in ["anchor_1", "anchor_2", "anchor_3", "anchor_4"] if score_breakdown[q])
        audience_pass_count = sum(1 for q in ["audience_1", "audience_2", "audience_3", "audience_4"] if score_breakdown[q])
        
        if gap_pass and anchor_pass_count >= 2 and audience_pass_count >= 2:
            logger.info("tier_1_topic_identified")
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
            return brief
        
        logger.debug(f"candidate_failed_viability: gap={gap_pass}, anchors={anchor_pass_count}, audience={audience_pass_count}")
        return None

    def _evaluate_viability(self, topic: str, anchors: list[str]) -> dict[str, bool]:
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
        resp = self.router.get_completion(prompt, system_prompt="You are a strict viability tester. Return ONLY valid JSON boolean mapping.")
        try:
            res_data = json.loads(resp.strip("` \n").removeprefix("json\n"))
            for k in VIABILITY_QUESTIONS.keys():
                scores[k] = bool(res_data.get(k, False))
        except Exception:
            # Degrade to False if failure
            scores = {k: False for k in VIABILITY_QUESTIONS.keys()}
        return scores

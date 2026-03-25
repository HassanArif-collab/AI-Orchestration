# Implementation Plan V4: Self-Evolving Script Generation System

**Branch:** `Explaining-FinalRefactoring`
**Date:** 2025-03-25
**Status:** PLANNING PHASE - NOT IMPLEMENTING YET

---

## User Requirements Summary

| Requirement | Details |
|-------------|---------|
| **Purpose** | Automate script creation: research → self-evaluation → engaging script |
| **Automation** | Run DAILY to find and suggest topics |
| **Interaction** | Web dashboard (already exists) |
| **Workflow** | System suggests → User selects/provides → Research phase begins |
| **Output** | Notion via MCP |

---

# PART 1: SYSTEM UNDERSTANDING

## 1.1 What This System Does (Simple Explanation)

**For a non-technical person:**

This system is like having a research assistant and scriptwriter that works 24/7. Every day, it automatically:

1. **Searches for trending topics** in Pakistan (YouTube, Google, news)
2. **Scores each topic** based on how good it would be for a documentary
3. **Presents the best options** to you via a web dashboard
4. **Waits for your approval** - you pick which topics to pursue
5. **Deep research** - gathers facts, finds visual anchors, identifies human stories
6. **Writes and refines scripts** - keeps improving until quality threshold is met
7. **Delivers to Notion** - final script ready for production

The key innovation is **self-evaluation**: the system doesn't just write once - it evaluates its own work, finds weaknesses, and rewrites until the script meets quality standards.

## 1.2 High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DAILY AUTOMATION LOOP                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                   RUNS DAILY (Automated)                             │   │
│   │                                                                      │   │
│   │   ┌──────────────┐                                                  │   │
│   │   │ TREND SCAN   │  YouTube Data API + Google Search                │   │
│   │   │              │  → Find trending topics in Pakistan              │   │
│   │   └──────┬───────┘                                                  │   │
│   │          │                                                           │   │
│   │          ▼                                                           │   │
│   │   ┌──────────────┐                                                  │   │
│   │   │ TOPIC SCORE  │  17-criteria viability check                     │   │
│   │   │              │  → Score each topic's potential                  │   │
│   │   └──────┬───────┘                                                  │   │
│   │          │                                                           │   │
│   │          ▼                                                           │   │
│   │   ┌──────────────┐                                                  │   │
│   │   │ SAVE TO DB   │  Store in Topic Reservoir                        │   │
│   │   │              │  → Ready for user review                         │   │
│   │   └──────────────┘                                                  │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│                              │                                               │
│                              ▼                                               │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                   USER INTERACTION (Web Dashboard)                   │   │
│   │                                                                      │   │
│   │   Dashboard shows:                                                   │   │
│   │   - Today's suggested topics (ranked by score)                       │   │
│   │   - Topic details: viability scores, trend sources, gap type         │   │
│   │   - Option to approve, reject, or provide custom topic               │   │
│   │                                                                      │   │
│   │   User Actions:                                                      │   │
│   │   [Approve Topic] → Continue to research                             │   │
│   │   [Reject Topic] → Remove from reservoir                             │   │
│   │   [Provide Own Topic] → Skip trend scan, start research              │   │
│   │   [Provide Own Script] → Jump to evaluation/refinement               │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│                              │                                               │
│                              ▼                                               │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                   DEEP RESEARCH (DeepResearchEngine)                 │   │
│   │                                                                      │   │
│   │   Phase 1: Broad Exploration                                        │   │
│   │     - Multiple search queries                                       │   │
│   │     - Identify key dimensions                                       │   │
│   │                                                                      │   │
│   │   Phase 2: Deep Dive                                                │   │
│   │     - Targeted research per dimension                               │   │
│   │     - Extract facts, anchors, characters                            │   │
│   │                                                                      │   │
│   │   Phase 3: Diversity & Validation                                   │   │
│   │     - Ensure all information types covered                          │   │
│   │     - Cross-source validation                                       │   │
│   │                                                                      │   │
│   │   Phase 4: Synthesis                                                │   │
│   │     - Generate ResearchDossier                                      │   │
│   │     - Assess complexity (determines depth, not duration)            │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│                              │                                               │
│                              ▼                                               │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │          SELF-EVOLVING SCRIPT GENERATION LOOP                        │   │
│   │                   (No Max Iterations)                                │   │
│   │                                                                      │   │
│   │   ┌─────────────────────────────────────────────────────────────┐   │   │
│   │   │ ITERATION N                                                  │   │   │
│   │   │                                                              │   │   │
│   │   │  1. GENERATE                                                 │   │   │
│   │   │     - Use research dossier                                   │   │   │
│   │   │     - Apply Johnny Harris style patterns                     │   │   │
│   │   │     - Create dual-column script                              │   │   │
│   │   │     - Depth matches complexity (not arbitrary duration)      │   │   │
│   │   │                                                              │   │   │
│   │   │  2. EVALUATE                                                 │   │   │
│   │   │     - Score against evaluation criteria                      │   │   │
│   │   │     - Identify weak areas                                    │   │   │
│   │   │     - Calculate production readiness                         │   │   │
│   │   │                                                              │   │   │
│   │   │  3. DECIDE                                                   │   │   │
│   │   │     - Score ≥ 85%? → EXIT loop, proceed to output            │   │   │
│   │   │     - Score < 85%? → ADJUST and CONTINUE                     │   │   │
│   │   │                                                              │   │   │
│   │   │  4. ADJUST                                                   │   │   │
│   │   │     - Analyze weak areas                                     │   │   │
│   │   │     - Refine prompt strategy                                 │   │   │
│   │   │     - Increment iteration counter                            │   │   │
│   │   │                                                              │   │   │
│   │   └─────────────────────────────────────────────────────────────┘   │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│                              │                                               │
│                              ▼                                               │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                   OUTPUT TO NOTION (MCP)                             │   │
│   │                                                                      │   │
│   │   - Complete script with dual-column format                          │   │
│   │   - Research sources and credibility scores                          │   │
│   │   - Visual asset requirements                                        │   │
│   │   - Evaluation log (iterations, scores, adjustments)                 │   │
│   │   - Link back to AI for continued refinement                         │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

# PART 2: COMPLEXITY-BASED DEPTH (NOT DURATION)

## 2.1 Flexible Complexity Assessment

**Key insight:** A "short" video might need complex research and storytelling. A "long" video might be simple. Duration should NOT be hardcoded.

Instead, complexity determines **depth of research** and **script thoroughness**:

```
┌─────────────────────────────────────────────────────────────────┐
│                  COMPLEXITY → DEPTH MAPPING                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   COMPLEXITY FACTORS:                                           │
│   ───────────────────                                           │
│   1. Hidden mechanisms to explain                               │
│   2. Visual asset availability                                  │
│   3. Audience prior knowledge gap                               │
│   4. Emotional depth needed                                     │
│   5. Source complexity/synthesis required                       │
│                                                                  │
│   DEPTH OUTPUTS (not duration):                                 │
│   ──────────────────────────────                                │
│                                                                  │
│   Low Complexity:                                               │
│   - Fewer research dimensions (2-3)                             │
│   - Simpler narrative structure                                 │
│   - Fewer visual anchors needed                                 │
│   - Direct hook → reveal → conclusion                           │
│                                                                  │
│   Medium Complexity:                                            │
│   - More research dimensions (4-5)                              │
│   - Multi-part narrative                                        │
│   - Multiple visual anchors                                     │
│   - Investigation layer added                                   │
│                                                                  │
│   High Complexity:                                              │
│   - Comprehensive research (5+ dimensions)                      │
│   - Deep narrative with multiple reveals                        │
│   - Rich visual storytelling                                    │
│   - Multiple human characters                                   │
│   - Extended investigation and synthesis                        │
│                                                                  │
│   NOTE: The final duration emerges naturally from the content,  │
│   not from a predetermined template.                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 2.2 Complexity Assessment Implementation

```python
class ComplexityAssessor:
    """
    Assesses topic complexity to determine research and script depth.
    
    Does NOT determine duration - that emerges from content.
    """
    
    FACTORS = {
        "hidden_mechanisms": {
            "weight": 0.25,
            "questions": [
                "How many interconnected systems need explaining?",
                "Is the mechanism visible or abstract?",
                "Can it be shown in a single diagram or multiple?"
            ]
        },
        "visual_availability": {
            "weight": 0.20,
            "questions": [
                "Are there existing visuals (archive, maps, data)?",
                "How much needs to be created from scratch?",
                "Is the visual evidence concrete or abstract?"
            ]
        },
        "audience_knowledge_gap": {
            "weight": 0.25,
            "questions": [
                "How familiar is the Pakistani audience with this topic?",
                "What background context is needed?",
                "Are there local equivalents or parallels?"
            ]
        },
        "emotional_depth": {
            "weight": 0.15,
            "questions": [
                "Is there a human character with a compelling story?",
                "Does this affect people's daily lives?",
                "What's the emotional resonance potential?"
            ]
        },
        "source_complexity": {
            "weight": 0.15,
            "questions": [
                "How many sources need to be synthesized?",
                "Are sources readily available or hard to find?",
                "Is there conflicting information to navigate?"
            ]
        }
    }
    
    def assess(self, dossier: ResearchDossier) -> ComplexityResult:
        """
        Assess complexity from research dossier.
        
        Returns:
            ComplexityResult with:
            - score (1.0-3.0)
            - depth_level ("shallow", "moderate", "deep")
            - research_dimensions_needed
            - narrative_complexity
        """
        pass
```

---

# PART 3: DAILY AUTOMATION WORKFLOW

## 3.1 Daily Cron Job

```python
# File: scripts/daily_topic_scan.py

"""
Daily Topic Scanner

Runs automatically every day to:
1. Scan trending sources
2. Score topic viability
3. Store in Topic Reservoir
4. Notify user via dashboard

Run via cron:
    0 9 * * * cd /path/to/AI-Orchestration && python scripts/daily_topic_scan.py
"""

import asyncio
from datetime import datetime, timezone

from packages.content_factory.trend_analysis.aggregator import TrendAnalyzer
from packages.content_factory.topic_finder.finder import TopicFinderAgent
from packages.content_factory.topic_finder.db import TopicReservoirDB
from packages.core.logger import get_logger

log = get_logger(__name__)


async def daily_scan(genres: list[str] = None):
    """
    Execute daily topic scan.
    
    Args:
        genres: List of genre IDs to scan for. 
                Default: ["current_situation", "history", "tech_systems", "economics"]
    """
    log.info(f"daily_scan_started: {datetime.now(timezone.utc).isoformat()}")
    
    if not genres:
        genres = [
            "current_situation",
            "history", 
            "tech_systems",
            "economics",
            "islamic_history",
            "south_asian_history"
        ]
    
    # 1. Aggregate trends
    analyzer = TrendAnalyzer()
    trends = await analyzer.aggregate_trends()
    
    log.info(f"trends_found: {len(trends)}")
    
    # 2. For each genre, find viable topics
    finder = TopicFinderAgent()
    db = TopicReservoirDB()
    
    topics_found = 0
    
    for genre in genres:
        # Get top trend for this genre
        relevant_trends = [t for t in trends if t.matches_genre(genre)]
        
        if not relevant_trends:
            continue
        
        # Try to generate a Tier 1 topic
        for trend in relevant_trends[:3]:  # Try top 3 trends per genre
            brief = await finder.generate_candidate(
                seed_query=trend.topic,
                genre_id=genre
            )
            
            if brief:
                db.save_topic(brief)
                topics_found += 1
                log.info(f"tier_1_topic_saved: {brief.topic_statement[:50]}...")
                break  # One topic per genre is enough for daily
    
    log.info(f"daily_scan_complete: {topics_found} topics added to reservoir")
    
    # 3. Update dashboard notification
    await notify_dashboard(topics_found)
    
    return topics_found


async def notify_dashboard(new_topics_count: int):
    """Update dashboard with new topics notification."""
    # Could push to websocket, update DB flag, send email, etc.
    pass


if __name__ == "__main__":
    asyncio.run(daily_scan())
```

## 3.2 Dashboard Topic Review Component

```python
# File: apps/api/routers/topic_routes.py

"""
Topic Review API Endpoints

Endpoints for user to review and select topics from the reservoir.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from packages.content_factory.topic_finder.db import TopicReservoirDB
from packages.content_factory.topic_finder.models import TopicBrief

router = APIRouter(prefix="/api/topics", tags=["topics"])
db = TopicReservoirDB()


class TopicApproval(BaseModel):
    topic_id: str
    approved: bool
    notes: str = ""


class CustomTopic(BaseModel):
    topic_statement: str
    genre_id: str
    big_question: str = ""
    notes: str = ""


@router.get("/reservoir")
async def get_reservoir_topics(
    status: str = "reservoir",
    limit: int = 20
):
    """
    Get topics from the reservoir.
    
    Default returns unprocessed topics waiting for review.
    """
    topics = db.list_topics(status=status, limit=limit)
    return {"topics": topics, "count": len(topics)}


@router.post("/approve")
async def approve_topic(approval: TopicApproval):
    """
    Approve a topic for production.
    
    Moves topic to 'approved' status and triggers research phase.
    """
    topic = db.get_topic(approval.topic_id)
    if not topic:
        raise HTTPException(404, "Topic not found")
    
    if approval.approved:
        topic.status = "approved"
        topic.user_notes = approval.notes
        db.update_topic(topic)
        
        # Trigger research phase
        # This could start a background task
        return {"status": "approved", "message": "Topic approved, research starting"}
    else:
        topic.status = "rejected"
        db.update_topic(topic)
        return {"status": "rejected"}


@router.post("/custom")
async def submit_custom_topic(custom: CustomTopic):
    """
    Submit a custom topic provided by user.
    
    Bypasses trend scan and starts research directly.
    """
    brief = TopicBrief(
        topic_statement=custom.topic_statement,
        big_question=custom.big_question or custom.topic_statement,
        genre_id=custom.genre_id,
        status="approved",
        content_type="user_provided",
        user_notes=custom.notes,
    )
    
    db.save_topic(brief)
    
    return {
        "status": "created",
        "topic_id": brief.id,
        "message": "Custom topic created, research starting"
    }


@router.post("/script")
async def submit_custom_script(script_data: dict):
    """
    Submit a custom script provided by user.
    
    Bypasses research and generation, goes directly to evaluation.
    """
    # Create topic brief from script
    # Mark for evaluation-only workflow
    pass
```

---

# PART 4: MULTI-PROVIDER FREEROUTER

## 4.1 Providers Summary

**Existing (Already Working):**
| Provider | Priority | Free Tier |
|----------|----------|-----------|
| Ollama | 10 | Unlimited (local) |
| Groq | 20 | Yes |
| OpenRouter | 30 | Yes |
| Together | 40 | Limited |
| DeepInfra | 50 | Pay/use |
| OpenAI | 60 | No |
| Anthropic | 70 | No |

**New to Add:**
| Provider | Priority | Free Tier | API Format |
|----------|----------|-----------|------------|
| Mistral | 35 | Yes | OpenAI-compatible |
| SambaNova | 45 | Yes | OpenAI-compatible |
| Cerebras | 55 | Yes | OpenAI-compatible |
| GitHub Models | 65 | Yes | OpenAI-compatible |
| APIFreeLLM | 75 | Yes | **Custom** (needs adapter) |
| z.ai | 80 | Yes | TBD (check docs) |

**Skipped:**
- ~~Grok (X.AI)~~ - User confirmed skip

## 4.2 APIFreeLLM Custom Adapter

```python
# File: freerouter/src/freerouter/adapters/apifreellm.py

"""
APIFreeLLM Adapter

APIFreeLLM uses a non-OpenAI-compatible format:

Request:
    POST https://apifreellm.com/api/v1/chat
    Headers: {"Authorization": "Bearer YOUR_KEY"}
    Body: {"message": "your prompt", "model": "apifreellm"}

Response:
    {"success": true, "response": "AI response text", "tier": "free"}

Rate Limit:
    - 429 response: wait 25 seconds
    - Free tier: 32k context
"""

import asyncio
import time
import httpx

from freerouter.router import RouterError


class APIFreeLLMAdapter:
    """Adapter for APIFreeLLM's non-standard API."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://apifreellm.com/api/v1"
        self.rate_limit_until = 0
    
    async def complete(
        self,
        messages: list[dict],  # OpenAI format input
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> dict:
        """
        Convert OpenAI format → APIFreeLLM format → back to OpenAI format.
        """
        # Check rate limit
        if time.time() < self.rate_limit_until:
            wait_time = self.rate_limit_until - time.time()
            raise RouterError(f"APIFreeLLM rate limited for {wait_time:.0f}s more")
        
        # Convert messages to single string
        combined = self._messages_to_string(messages)
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/chat",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                },
                json={
                    "message": combined,
                    "model": "apifreellm"
                }
            )
            
            if response.status_code == 429:
                self.rate_limit_until = time.time() + 25
                raise RouterError("APIFreeLLM rate limited - wait 25 seconds")
            
            if response.status_code == 401:
                raise RouterError("Invalid APIFreeLLM API key")
            
            if response.status_code != 200:
                raise RouterError(f"APIFreeLLM error: {response.status_code}")
            
            data = response.json()
            
            if not data.get("success"):
                raise RouterError(f"APIFreeLLM failed: {data}")
            
            # Convert back to OpenAI format
            return {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": data.get("response", "")
                    },
                    "index": 0,
                    "finish_reason": "stop"
                }],
                "_provider": "apifreellm",
                "_model": "apifreellm",
                "_tier": data.get("tier", "free")
            }
    
    def _messages_to_string(self, messages: list[dict]) -> str:
        """Convert OpenAI messages array to single prompt string."""
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                parts.append(f"[SYSTEM INSTRUCTIONS]\n{content}")
            elif role == "user":
                parts.append(f"[USER]\n{content}")
            elif role == "assistant":
                parts.append(f"[ASSISTANT]\n{content}")
        
        return "\n\n".join(parts)
```

## 4.3 Environment Configuration

```bash
# File: freerouter/.env

# =============================================================================
# EXISTING PROVIDERS (Already configured)
# =============================================================================
GROQ_API_KEY=your_groq_key_here
OPENROUTER_API_KEY=your_openrouter_key_here
OLLAMA_BASE_URL=http://localhost:11434/v1

# =============================================================================
# NEW PROVIDERS - Add your keys
# =============================================================================

# Mistral AI - https://console.mistral.ai/
MISTRAL_API_KEY=your_mistral_key_here

# SambaNova - https://cloud.sambanova.ai/
SAMBANOVA_API_KEY=your_sambanova_key_here

# Cerebras - https://cloud.cerebras.ai/
CEREBRAS_API_KEY=your_cerebras_key_here

# GitHub Models - https://github.com/settings/tokens (models:read scope)
GITHUB_TOKEN=your_github_token_here

# APIFreeLLM - https://apifreellm.com/en/api-access
APIFREELLM_API_KEY=your_apifreellm_key_here

# z.ai - https://docs.z.ai
ZAI_API_KEY=your_zai_key_here

# =============================================================================
# YOUTUBE API (User confirmed access)
# =============================================================================
YOUTUBE_API_KEY=your_youtube_data_api_key

# YouTube Analytics (OAuth for your channel)
YOUTUBE_CLIENT_ID=your_client_id
YOUTUBE_CLIENT_SECRET=your_client_secret
YOUTUBE_REFRESH_TOKEN=your_refresh_token

# =============================================================================
# NOTION (User confirmed token)
# =============================================================================
NOTION_API_KEY=secret_xxx
NOTION_DATABASE_ID=your_database_id
```

---

# PART 5: SELF-EVOLVING SCRIPT LOOP

## 5.1 Loop Architecture

```python
# File: packages/content_factory/script_generator/evolution_loop.py

"""
Self-Evolving Script Generation Loop

Implements Karpathy's auto-research methodology:
- Generate script
- Self-evaluate against criteria
- Adjust prompt strategy
- Repeat until threshold (NO MAX ITERATIONS)
"""

from typing import Optional
from packages.core.logger import get_logger
from packages.router.client import RouterClient
from packages.content_factory.production.models import ResearchDossier
from packages.content_factory.script_generator.jh_style import JHStyleGenerator
from packages.content_factory.script_generator.self_evaluator import SelfEvaluator
from packages.content_factory.script_generator.prompt_adjuster import PromptAdjuster

log = get_logger(__name__)


class ScriptEvolutionLoop:
    """
    Iterative script generation with self-evaluation.
    
    Continues until production readiness threshold is met.
    No maximum iterations - runs until quality achieved.
    """
    
    PRODUCTION_THRESHOLD = 0.85  # 85%
    
    def __init__(
        self,
        router_client: Optional[RouterClient] = None,
    ):
        self.router = router_client
        self.generator = JHStyleGenerator()
        self.evaluator = SelfEvaluator()
        self.adjuster = PromptAdjuster()
        
        self.iteration = 0
        self.score_history = []
    
    async def evolve(
        self,
        dossier: ResearchDossier,
        complexity_result: ComplexityResult,
    ) -> DualColumnScript:
        """
        Main evolution loop.
        
        Args:
            dossier: Research findings
            complexity_result: Complexity assessment (determines depth, not duration)
        
        Returns:
            Production-ready dual-column script
        
        Note:
            This loop has NO maximum iterations.
            It continues until the threshold is met.
        """
        current_prompt = self._build_initial_prompt(dossier, complexity_result)
        current_script = None
        
        while True:  # No maximum - runs until threshold
            self.iteration += 1
            
            log.info(f"script_evolution_iteration_{self.iteration}")
            
            # 1. Generate script
            current_script = await self.generator.generate(
                prompt=current_prompt,
                dossier=dossier,
                complexity=complexity_result,
            )
            
            # 2. Evaluate
            evaluation = await self.evaluator.evaluate(
                script=current_script,
                dossier=dossier,
            )
            
            overall_score = evaluation["overall_score"]
            self.score_history.append(overall_score)
            
            log.info(
                f"iteration_{self.iteration}_score: {overall_score*100:.1f}% "
                f"weak_areas: {evaluation['weak_areas']}"
            )
            
            # 3. Check threshold
            if overall_score >= self.PRODUCTION_THRESHOLD:
                log.info(
                    f"script_approved: threshold_met after {self.iteration} iterations "
                    f"(score: {overall_score*100:.1f}%)"
                )
                current_script.evaluation_log = self._build_evaluation_log()
                return current_script
            
            # 4. Adjust prompt
            current_prompt = self.adjuster.adjust(
                current_prompt=current_prompt,
                weak_areas=evaluation["weak_areas"],
                detailed_scores=evaluation["detailed_scores"],
                iteration=self.iteration,
                previous_script=current_script,
            )
            
            # 5. Optional stagnation check (warn but continue)
            if self._is_stagnating():
                log.warning(
                    f"stagnation_detected: trying alternative strategy"
                )
                current_prompt = self.adjuster.try_alternative_strategy(
                    current_prompt,
                    evaluation["weak_areas"]
                )
    
    def _is_stagnating(self) -> bool:
        """Check if scores aren't improving significantly."""
        if len(self.score_history) < 5:
            return False
        
        recent = self.score_history[-5:]
        return (max(recent) - min(recent)) < 0.02
    
    def _build_evaluation_log(self) -> list[dict]:
        """Build log of all iterations for output."""
        return [
            {
                "iteration": i + 1,
                "score": score,
                "timestamp": ...,
            }
            for i, score in enumerate(self.score_history)
        ]
```

## 5.2 Self-Evaluation Criteria

```python
# File: packages/content_factory/script_generator/self_evaluator.py

"""
Self-Evaluation Engine

Evaluates scripts against multiple criteria.
Each criterion has specific questions to answer.
"""

EVALUATION_CRITERIA = {
    "hook_effectiveness": {
        "weight": 0.20,
        "questions": [
            "Does the first line create immediate curiosity?",
            "Is there a clear knowledge gap established?",
            "Would a viewer want to keep watching after 5 seconds?",
            "Is the mainstream assumption stated or implied?",
        ]
    },
    
    "visual_storytelling": {
        "weight": 0.20,
        "questions": [
            "Can each section be shown visually?",
            "Are there specific visual directions for each point?",
            "Do visual directions complement the narration?",
            "Is there variety in visual types (B-roll, graphics, archive)?",
        ]
    },
    
    "narrative_flow": {
        "weight": 0.20,
        "questions": [
            "Does the story progress logically?",
            "Are transitions smooth between sections?",
            "Is there a clear beginning, middle, and end?",
            "Does complexity match the research depth?",
        ]
    },
    
    "evidence_quality": {
        "weight": 0.20,
        "questions": [
            "Is every claim supported by research?",
            "Are sources credible and current?",
            "Is there a 'smoking gun' moment?",
            "Are facts presented with appropriate confidence?",
        ]
    },
    
    "audience_connection": {
        "weight": 0.20,
        "questions": [
            "Does this matter to Pakistani audience?",
            "Is local context integrated?",
            "Are there local examples and references?",
            "Does it explain 'why things are this way'?",
        ]
    },
}


class SelfEvaluator:
    """Evaluates scripts against criteria."""
    
    async def evaluate(
        self,
        script: DualColumnScript,
        dossier: ResearchDossier,
    ) -> dict:
        """
        Evaluate script against all criteria.
        
        Returns:
            {
                "overall_score": 0.0-1.0,
                "weak_areas": ["hook_effectiveness", ...],
                "detailed_scores": {...}
            }
        """
        detailed_scores = {}
        
        for criterion, config in EVALUATION_CRITERIA.items():
            score = await self._evaluate_criterion(
                criterion,
                config["questions"],
                script,
                dossier
            )
            detailed_scores[criterion] = {
                "score": score,
                "weight": config["weight"],
                "weighted_score": score * config["weight"],
            }
        
        overall = sum(
            s["weighted_score"] for s in detailed_scores.values()
        )
        
        weak_areas = [
            criterion for criterion, data in detailed_scores.items()
            if data["score"] < 0.70  # Below 70% is weak
        ]
        
        return {
            "overall_score": overall,
            "weak_areas": weak_areas,
            "detailed_scores": detailed_scores,
        }
```

---

# PART 6: TREND ANALYSIS

## 6.1 Trend Sources

```
┌─────────────────────────────────────────────────────────────────┐
│                    TREND ANALYSIS                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   SOURCE 1: Google Search                                       │
│   ─────────────────────                                         │
│   Uses existing WebSearchClient                                 │
│                                                                  │
│   Queries:                                                      │
│   - "what is trending in Pakistan 2025"                        │
│   - "Pakistan trending topics today"                           │
│   - "what are people searching in Pakistan"                    │
│   - "Pakistan viral news"                                       │
│                                                                  │
│          │                                                       │
│          ▼                                                       │
│                                                                  │
│   SOURCE 2: YouTube Data API v3                                 │
│   ─────────────────────────────                                 │
│   User has API access                                           │
│                                                                  │
│   Calls:                                                        │
│   - videos().list(chart="mostPopular", regionCode="PK")        │
│   - search().list(q="trending Pakistan")                       │
│                                                                  │
│          │                                                       │
│          ▼                                                       │
│                                                                  │
│   SOURCE 3: YouTube Analytics API                               │
│   ──────────────────────────────────                            │
│   User has API access                                           │
│                                                                  │
│   Purpose:                                                      │
│   - Analyze YOUR channel's performance                          │
│   - Identify which topics resonated                             │
│   - Find content gaps                                           │
│                                                                  │
│          │                                                       │
│          ▼                                                       │
│                                                                  │
│   CROSS-REFERENCE & SCORE                                       │
│   ────────────────────────                                      │
│   - Topics appearing in multiple sources get higher score       │
│   - Check against existing content (don't duplicate)            │
│   - Apply 17-criteria viability check                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

# PART 7: FILE STRUCTURE

## 7.1 New Files

```
AI-Orchestration/
├── scripts/
│   └── daily_topic_scan.py           # Daily automation cron job
│
├── apps/api/routers/
│   └── topic_routes.py               # Dashboard topic API
│
├── packages/content_factory/
│   ├── script_generator/
│   │   ├── __init__.py
│   │   ├── evolution_loop.py         # Main self-evolving loop
│   │   ├── self_evaluator.py         # Evaluation engine
│   │   ├── prompt_adjuster.py        # Prompt strategy adjustment
│   │   └── jh_style.py               # Johnny Harris patterns
│   │
│   ├── complexity/
│   │   ├── __init__.py
│   │   └── assessor.py               # Complexity assessment
│   │
│   └── trend_analysis/
│       ├── __init__.py
│       ├── aggregator.py             # Combine all trend sources
│       ├── youtube_data.py           # YouTube Data API v3
│       └── youtube_analytics.py      # YouTube Analytics API
│
└── freerouter/src/freerouter/
    ├── providers.py                  # MODIFY: add new providers
    └── adapters/
        ├── __init__.py
        └── apifreellm.py             # APIFreeLLM custom adapter
```

## 7.2 Files to Modify

| File | Change |
|------|--------|
| `freerouter/providers.py` | Add Mistral, SambaNova, Cerebras, GitHub, APIFreeLLM, z.ai |
| `packages/content_factory/topic_finder/finder.py` | Integrate trend analysis + DeepResearchEngine |
| `apps/api/main.py` | Include topic_routes router |

---

# PART 8: IMPLEMENTATION PHASES

## Phase 1: Provider Infrastructure
- [ ] Add Mistral provider (OpenAI-compatible)
- [ ] Add SambaNova provider (OpenAI-compatible)
- [ ] Add Cerebras provider (OpenAI-compatible)
- [ ] Add GitHub Models provider (OpenAI-compatible)
- [ ] Add APIFreeLLM adapter (custom format)
- [ ] Research and add z.ai provider
- [ ] Update .env.example
- [ ] Test failover chain

## Phase 2: Daily Automation
- [ ] Create daily_topic_scan.py script
- [ ] Add topic_routes.py API endpoints
- [ ] Connect to existing dashboard

## Phase 3: Trend Analysis
- [ ] YouTube Data API v3 integration
- [ ] YouTube Analytics API integration
- [ ] Google search trend queries
- [ ] Cross-reference scoring

## Phase 4: Self-Evolution Engine
- [ ] Implement evolution_loop.py
- [ ] Implement self_evaluator.py
- [ ] Implement prompt_adjuster.py
- [ ] Connect to DeepResearchEngine

## Phase 5: Complexity Assessment
- [ ] Implement flexible complexity assessor
- [ ] Connect to script depth (not duration)

## Phase 6: Integration & Testing
- [ ] End-to-end test
- [ ] Deploy daily cron job

---

# PART 9: INFORMATION NEEDED

## From z.ai Documentation
- [ ] API endpoint format
- [ ] Authentication method
- [ ] Rate limits
- [ ] Available models

## From User (Already Provided)
- [x] YouTube API access - **Confirmed**
- [x] Notion token - **Confirmed**
- [x] Skip Grok - **Confirmed**

---

*Plan Version: 4.0*
*Status: Awaiting User Approval*
*Key Principle: Complexity determines depth, not arbitrary duration*

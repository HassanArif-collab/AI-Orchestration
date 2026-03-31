"""LangGraph Node Functions for Pipeline Orchestration.

Each node wraps an existing agent. The node's job is:
1. Read what it needs from state
2. Call the existing agent logic (ONE call, no loops)
3. Report thoughts at key milestones
4. Return a dict of state updates

CRITICAL: DO NOT copy-paste the old while/for loop from evaluation/loop.py into any node.
Each node calls the agent's core method ONCE. LangGraph handles repetition via conditional edges.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from .state import DiscoveryState, ProductionState
from .thoughts import pipeline_node, report_thought, update_card_stage

logger = logging.getLogger(__name__)


# ============================================================
# DISCOVERY GRAPH NODES
# ============================================================

@pipeline_node("topic_finder")
async def gather_context_node(state: DiscoveryState) -> dict:
    """
    Load historical audience preferences from Zep memory.
    This gives the topic finder context about what worked before.
    """
    card_id = state.get("card_id", "unknown")
    
    try:
        from packages.content_factory.memory.zep_store import ZepAudienceModelStore
        zep = ZepAudienceModelStore()
        # Get audience context for discovery
        context = await zep.read_audience_context("discovery")
        
        if context:
            await report_thought(
                card_id, "topic_finder", 
                f"📚 Loaded {len(context)} chars of audience history from Zep"
            )
        else:
            context = ""
            await report_thought(
                card_id, "topic_finder",
                "📚 No prior audience context found (first run or Zep unavailable)"
            )
    except Exception as e:
        logger.warning(f"zep_context_load_failed: {e}")
        context = ""
        await report_thought(card_id, "topic_finder", f"📚 Zep unavailable, continuing without context")
    
    return {"zep_context": context, "pipeline_status": "discovering"}


@pipeline_node("topic_finder")
async def search_web_node(state: DiscoveryState) -> dict:
    """
    Query Exa.ai for trending Pakistani topics.
    Uses seed_hint if provided, otherwise uses generic Pakistani tech/geopolitics queries.
    """
    card_id = state.get("card_id", "unknown")
    seed_hint = state.get("seed_hint", "")
    zep_context = state.get("zep_context", "")
    
    await report_thought(
        card_id, "topic_finder",
        "🔍 Searching Exa.ai for trending Pakistani discussions..."
    )
    
    try:
        from packages.integrations.exa.client import ExaResearchClient
        from packages.core.config import get_settings
        
        settings = get_settings()
        client = ExaResearchClient(api_key=settings.EXA_API_KEY)
        
        # Build search queries from seed_hint and context
        queries = []
        if seed_hint:
            queries.append(f"{seed_hint} Pakistan trending discussion")
        
        # Add default queries for Pakistani topics
        default_queries = [
            "Pakistan technology innovation 2024",
            "Pakistan economy news analysis",
            "Pakistan social issues trending",
        ]
        queries.extend(default_queries[:2])  # Limit to avoid API limits
        
        # Execute searches
        results = []
        for query in queries[:3]:
            try:
                search_results = await client.search(query, num_results=5)
                results.extend(search_results)
            except Exception as e:
                logger.debug(f"search_query_failed: {query} - {e}")
        
        await report_thought(
            card_id, "topic_finder",
            f"🔍 Found {len(results)} search results",
            metadata={"result_count": len(results)}
        )
        
        return {"search_results": results}
        
    except Exception as e:
        logger.error(f"web_search_failed: {e}")
        return {"search_results": [], "error": f"Web search failed: {str(e)}"}


@pipeline_node("topic_finder") 
async def generate_topics_node(state: DiscoveryState) -> dict:
    """
    Send web results + audience context to LLM to generate topic ideas.
    Uses model assigned in Phase 3 (gemini-flash for topic finder).
    """
    card_id = state.get("card_id", "unknown")
    search_results = state.get("search_results", [])
    zep_context = state.get("zep_context", "")
    seed_hint = state.get("seed_hint", "")
    
    await report_thought(card_id, "topic_finder", "💡 Generating topic candidates...")
    
    try:
        from packages.router.client import RouterClient
        
        # Build prompt from search results
        search_text = "\n".join([
            f"- {r.get('title', r.get('name', 'Unknown'))}: {r.get('snippet', '')[:200]}"
            for r in search_results[:10]
        ])
        
        prompt = f"""Based on these search results about Pakistan, generate 3-5 compelling documentary topic ideas.
Each topic should have a clear gap between mainstream belief and reality.

Search Results:
{search_text}

{f"User Hint: {seed_hint}" if seed_hint else ""}

{f"Past Successful Patterns: {zep_context[:500]}" if zep_context else ""}

Return a JSON array of topics. Each topic should have:
- title: A catchy title for the documentary
- description: One sentence describing the story angle  
- gap_type: One of "Hidden Mechanism", "Invisible Victim", "False Binary", "Wrong Villain"
- mainstream_assumption: What most people wrongly believe
- reality: What's actually true
- urgency: Why this matters NOW

Output ONLY valid JSON array, no markdown."""
        
        async with RouterClient() as router:
            response = await router.complete_text(
                prompt,
                system="You are a documentary topic researcher. Output ONLY valid JSON.",
                model="openrouter/google/gemini-2.0-flash-001"
            )
        
        # Parse JSON response
        import json
        from packages.core.json_utils import extract_json_array
        json_str = extract_json_array(response)
        if json_str:
            topics = json.loads(json_str)
        else:
            topics = []
        
        await report_thought(
            card_id, "topic_finder",
            f"💡 Generated {len(topics)} topic candidates",
            metadata={"topic_count": len(topics)}
        )
        
        return {"generated_topics": topics}
        
    except Exception as e:
        logger.error(f"topic_generation_failed: {e}")
        return {"generated_topics": [], "error": f"Topic generation failed: {str(e)}"}


@pipeline_node("topic_finder")
async def grade_viability_node(state: DiscoveryState) -> dict:
    """
    Run each topic through the 17-question Johnny Harris viability test.
    Stream each question evaluation as a thought so the UI shows progress.
    """
    card_id = state.get("card_id", "unknown")
    generated_topics = state.get("generated_topics", [])
    
    if not generated_topics:
        await report_thought(card_id, "topic_finder", "⚠️ No topics to grade")
        return {"graded_topics": [], "pipeline_status": "complete"}
    
    graded = []
    
    for i, topic in enumerate(generated_topics):
        title = topic.get("title", "Unknown")
        await report_thought(
            card_id, "topic_finder",
            f"📊 Grading topic {i+1}/{len(generated_topics)}: {title[:50]}...",
            "thinking"
        )
        
        try:
            from packages.content_factory.topic_finder.finder import TopicFinderAgent
            from packages.router.client import RouterClient
            
            async with RouterClient() as router:
                # Use the existing viability evaluation
                finder = TopicFinderAgent()
                # Build a minimal brief for grading
                from packages.content_factory.topic_finder.models import TopicBrief
                brief = TopicBrief(
                    topic_statement=title,
                    big_question=topic.get("description", ""),
                    genre_id="current_situation",
                    gap_type=topic.get("gap_type", "Hidden Mechanism"),
                    viability_score_breakdown={},
                    anchor_candidates=[],
                    mainstream_assumption=topic.get("mainstream_assumption", ""),
                    timing_rationale=topic.get("urgency", ""),
                    created_at=datetime.now(timezone.utc),
                    content_type="original",
                )
                
                # Grade viability
                scores = await finder._evaluate_viability(title, [], router)
                
                # Calculate overall score
                passed_count = sum(1 for v in scores.values() if v)
                score = int((passed_count / len(scores)) * 100) if scores else 0
                
                # Check if it passes threshold (e.g., 60%)
                if score >= 60:
                    graded.append({
                        **topic,
                        "viability_score": score,
                        "score_breakdown": scores,
                        "passed": True,
                    })
                    await report_thought(
                        card_id, "topic_finder",
                        f"✅ '{title[:40]}...' passed ({score}%)"
                    )
                else:
                    await report_thought(
                        card_id, "topic_finder",
                        f"❌ '{title[:40]}...' failed ({score}%)"
                    )
                    
        except Exception as e:
            logger.warning(f"topic_grading_failed: {title} - {e}")
            # Include with low score on failure
            graded.append({
                **topic,
                "viability_score": 0,
                "passed": False,
                "error": str(e),
            })
    
    passed_count = sum(1 for t in graded if t.get("passed"))
    await report_thought(
        card_id, "topic_finder",
        f"✅ {passed_count}/{len(generated_topics)} topics passed viability",
        "success"
    )
    
    return {"graded_topics": graded, "pipeline_status": "complete"}


@pipeline_node("topic_finder")
async def save_topics_node(state: DiscoveryState) -> dict:
    """
    Save passing topics as new Kanban cards in Column 2 (Suggested Topics).
    Each card gets a 3-hour expiration timer.
    """
    card_id = state.get("card_id", "unknown")
    graded_topics = state.get("graded_topics", [])
    
    # Filter only topics that passed
    passing_topics = [t for t in graded_topics if t.get("passed")]
    
    if not passing_topics:
        await report_thought(card_id, "topic_finder", "⚠️ No passing topics to save")
        return {"pipeline_status": "complete"}
    
    try:
        from packages.core.supabase_client import get_supabase
        sb = get_supabase()
        
        saved_ids = []
        for topic in passing_topics:
            result = sb.table("kanban_cards").insert({
                "title": topic.get("title", "Untitled"),
                "topic_brief": topic,
                "column": 2,  # Suggested Topics
                "status": "suggested",
                "viability_score": topic.get("viability_score", 0),
                "expires_at": (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }).execute()
            
            if result.data:
                saved_ids.append(result.data[0].get("id"))
        
        await report_thought(
            card_id, "topic_finder",
            f"💾 Saved {len(saved_ids)} topic cards to Kanban",
            "success",
            metadata={"saved_count": len(saved_ids)}
        )
        
    except Exception as e:
        logger.error(f"save_topics_failed: {e}")
        return {"error": f"Failed to save topics: {str(e)}"}
    
    return {"pipeline_status": "complete"}


# ============================================================
# PRODUCTION GRAPH NODES
# ============================================================

@pipeline_node("system")
async def load_learnings_node(state: ProductionState) -> dict:
    """
    Before anything else, query Zep for past winning mutations.
    These get injected into the ScriptWriter's prompt later.
    
    From Phase 2c: retrieves relevant facts about past successful patterns.
    """
    card_id = state.get("card_id", "unknown")
    topic_brief = state.get("topic_brief", {})
    
    try:
        from packages.content_factory.memory.zep_store import ZepAudienceModelStore
        zep = ZepAudienceModelStore()
        
        # Get past learnings relevant to this topic
        topic_text = topic_brief.get("title", "") if isinstance(topic_brief, dict) else str(topic_brief)
        learnings = await zep.read_learnings(topic_text)
        
        if learnings:
            await report_thought(
                card_id, "system",
                f"🧠 Loaded {len(learnings.split('PROVEN'))} past learnings from cross-script memory"
            )
        else:
            learnings = ""
            await report_thought(
                card_id, "system",
                "🧠 No past learnings found (first run or Zep unavailable)"
            )
    except Exception as e:
        logger.warning(f"zep_learnings_load_failed: {e}")
        learnings = ""
        await report_thought(card_id, "system", "🧠 Zep unavailable, continuing without learnings")
    
    return {"zep_learnings": learnings}


@pipeline_node("researcher")
async def research_node(state: ProductionState) -> dict:
    """
    Execute deep research on the topic.
    
    IMPORTANT: Check Phase 2b's cache first.
    If a fresh dossier exists (<24hr), skip re-scraping.
    If not, scrape and save a NEW dossier (dossiers accumulate, never overwrite).
    
    Uses model: openrouter/google/gemini-1.5-pro (Phase 3)
    """
    card_id = state.get("card_id", "unknown")
    topic_brief = state.get("topic_brief", {})
    
    topic_title = topic_brief.get("title", "Unknown topic") if isinstance(topic_brief, dict) else str(topic_brief)
    
    # Step 1: Check research cache
    await report_thought(card_id, "researcher", "🔍 Checking for existing research cache...")
    
    try:
        from packages.pipeline.research_cache import ResearchCache
        cache = ResearchCache()
        
        cached = cache.get(topic_title)
        if cached:
            await report_thought(
                card_id, "researcher",
                f"📄 Using cached research ({len(cached)} chars)",
                "success"
            )
            return {
                "research_dossier": cached,
                "research_sources": [],
                "pipeline_status": "researching",
            }
    except Exception as e:
        logger.debug(f"cache_check_failed: {e}")
    
    # Step 2: Execute research
    await report_thought(card_id, "researcher", f"🔍 Researching: {topic_title}")
    
    try:
        from packages.content_factory.production.deep_research import DeepResearchEngine
        from packages.router.client import RouterClient
        
        async with RouterClient() as router:
            engine = DeepResearchEngine(router_client=router)
            
            # Run deep research
            dossier = await engine.run(topic_title)
            
            if dossier:
                dossier_text = dossier.to_markdown() if hasattr(dossier, 'to_markdown') else str(dossier)
                sources = dossier.sources if hasattr(dossier, 'sources') else []
            else:
                dossier_text = f"Research for {topic_title}"
                sources = []
        
        # Step 3: Save dossier permanently to cache
        try:
            cache.set(topic_title, dossier_text)
        except Exception as e:
            logger.warning(f"cache_save_failed: {e}")
        
        await report_thought(
            card_id, "researcher",
            f"📄 Research complete: {len(dossier_text)} chars, {len(sources)} sources",
            "success",
            metadata={"source_count": len(sources)}
        )
        
        return {
            "research_dossier": dossier_text,
            "research_sources": sources,
            "pipeline_status": "researching",
        }
        
    except Exception as e:
        logger.error(f"research_failed: {e}")
        return {"error": f"Research failed: {str(e)}"}


@pipeline_node("script_writer")
async def draft_node(state: ProductionState) -> dict:
    """
    Generate a script draft.
    
    On FIRST call (iteration_count == 0):
      - Uses research_dossier + zep_learnings + topic_brief
      - ScriptWriter creates initial draft from scratch
    
    On SUBSEQUENT calls (after mutation or human revision):
      - Uses evaluation_feedback or human_feedback to guide rewrite
      - Research dossier and learnings still available
    
    Uses model: groq/llama-3.3-70b-versatile (Phase 3)
    """
    card_id = state.get("card_id", "unknown")
    topic_brief = state.get("topic_brief", {})
    research = state.get("research_dossier", "")
    learnings = state.get("zep_learnings", "")
    human_feedback = state.get("human_feedback")
    evaluation_feedback = state.get("evaluation_feedback")
    iteration = state.get("iteration_count", 0)
    
    topic_title = topic_brief.get("title", "Unknown") if isinstance(topic_brief, dict) else str(topic_brief)
    
    if human_feedback:
        await report_thought(card_id, "script_writer", "✍️ Rewriting based on human feedback...")
    elif iteration > 0 and evaluation_feedback:
        await report_thought(card_id, "script_writer", f"✍️ Writing iteration {iteration + 1}...")
    else:
        await report_thought(card_id, "script_writer", "✍️ Writing first draft...")
    
    try:
        from packages.router.client import RouterClient
        
        # Build context
        context_parts = []
        if learnings:
            context_parts.append(f"PAST WINNING PATTERNS:\n{learnings[:1000]}")
        if research:
            context_parts.append(f"RESEARCH:\n{research[:3000]}")
        if human_feedback:
            context_parts.append(f"HUMAN FEEDBACK TO ADDRESS:\n{human_feedback}")
        elif evaluation_feedback:
            context_parts.append(f"EVALUATION FEEDBACK:\n{evaluation_feedback}")
        
        context = "\n\n---\n\n".join(context_parts)
        
        prompt = f"""Write a compelling documentary script about: {topic_title}

{context}

Create a script with these sections:
1. HOOK - A startling opening that grabs attention
2. ANCHOR - The core evidence/data that grounds the story
3. BRIDGE - Connect the evidence to broader implications
4. REVEAL - The key insight that changes understanding
5. CONCLUSION - A memorable closing that lingers

Output ONLY the script narration text. Keep it conversational, active voice, and under 300 words total."""
        
        async with RouterClient() as router:
            draft = await router.complete_text(
                prompt,
                system="You are a documentary scriptwriter. Write engaging, conversational narration.",
                model="groq/llama-3.3-70b-versatile"
            )
        
        await report_thought(
            card_id, "script_writer",
            f"✍️ Draft complete: {len(draft.split())} words",
            "success"
        )
        
        # C7 FIX: When human rejects, reset iteration_count so revised draft
        # gets a fresh mutation budget. Track revision_count separately.
        if human_feedback:
            return {
                "current_draft": draft,
                "iteration_count": 0,  # Reset for fresh mutation budget
                "revision_count": state.get("revision_count", 0) + 1,  # Track revision cycles
                "pipeline_status": "drafting",
                "human_feedback": None,  # Clear after using
            }
        else:
            return {
                "current_draft": draft,
                "iteration_count": iteration,
                "pipeline_status": "drafting",
                "human_feedback": None,  # Clear after using
            }
        
    except Exception as e:
        logger.error(f"draft_failed: {e}")
        return {"error": f"Draft generation failed: {str(e)}"}


@pipeline_node("scorer")
async def score_node(state: ProductionState) -> dict:
    """
    Evaluate the current draft against the binary checklist.
    Returns a score (0-100) and text feedback describing weak zones.
    
    Also tracks best_draft: if this score beats the previous best,
    save this draft as the new best.
    
    Uses model: groq/llama-3.3-70b-versatile (Phase 3)
    """
    card_id = state.get("card_id", "unknown")
    draft = state.get("current_draft", "")
    iteration = state.get("iteration_count", 0)
    best_score = state.get("best_score", 0)
    best_draft = state.get("best_draft", "")
    
    await report_thought(
        card_id, "scorer",
        f"📊 Scoring draft (iteration {iteration}/20)...",
        "thinking"
    )
    
    try:
        from packages.router.client import RouterClient
        
        prompt = f"""Evaluate this documentary script draft on a 0-100 scale.

DRAFT:
{draft}

Check these criteria (each worth 10 points):
1. HOOK opens with a startling fact or question
2. Active voice throughout (no passive constructions)
3. Each sentence has a clear agent doing something
4. Technical terms are explained or avoided
5. Viewer can form mental images
6. Clear progression from problem to insight
7. Emotional moments are highlighted
8. Ending provides closure or call to action
9. No jargon without explanation
10. Overall engagement and flow

Return JSON:
{{"score": 85, "feedback": "Brief description of strengths and what needs improvement"}}"""
        
        async with RouterClient() as router:
            import json
            from packages.core.json_utils import extract_json_object
            response = await router.complete_text(
                prompt,
                system="You are a strict script evaluator. Return ONLY valid JSON.",
                model="groq/llama-3.3-70b-versatile",
                temperature=0.0
            )

            json_str = extract_json_object(response)
            if json_str:
                result = json.loads(json_str)
                score = result.get("score", 0)
                feedback = result.get("feedback", "")
            else:
                score = 50
                feedback = "Could not parse evaluation"
        
        updates = {
            "evaluation_score": score,
            "evaluation_feedback": feedback,
            "pipeline_status": "scoring",
        }
        
        # Track best draft
        if score > best_score:
            updates["best_draft"] = draft
            updates["best_score"] = score
            await report_thought(
                card_id, "scorer",
                f"📊 New best! Score: {score}% (previous: {best_score}%)",
                "milestone",
                metadata={"score": score, "iteration": iteration, "is_new_best": True}
            )
        else:
            await report_thought(
                card_id, "scorer",
                f"📊 Score: {score}% (best remains: {best_score}%)",
                metadata={"score": score, "iteration": iteration, "is_new_best": False}
            )
        
        return updates
        
    except Exception as e:
        logger.error(f"scoring_failed: {e}")
        return {"error": f"Scoring failed: {str(e)}"}


@pipeline_node("challenger")
async def mutate_node(state: ProductionState) -> dict:
    """
    The Challenger Generator: takes the current draft + scorer feedback,
    mutates the WEAKEST sections to produce a challenger draft.
    
    Uses model: groq/llama-3.3-70b-versatile (Phase 3)
    """
    card_id = state.get("card_id", "unknown")
    draft = state.get("current_draft", "")
    feedback = state.get("evaluation_feedback", "")
    iteration = state.get("iteration_count", 0)
    
    iteration = iteration + 1  # Increment here
    
    await report_thought(
        card_id, "challenger",
        f"🔄 Generating challenger mutation (iteration {iteration}/20)...",
        "thinking",
        metadata={"target_zones": feedback[:200] if feedback else ""}
    )
    
    try:
        from packages.router.client import RouterClient
        
        prompt = f"""You are improving a documentary script. Here is the current draft and feedback.

CURRENT DRAFT:
{draft}

FEEDBACK ON WEAKNESS:
{feedback}

Improve the WEAK sections while keeping strong sections intact.
Focus on addressing the specific issues mentioned in feedback.

Output the improved script narration text only."""
        
        async with RouterClient() as router:
            challenger_draft = await router.complete_text(
                prompt,
                system="You are a script improvement specialist. Output improved script only.",
                model="groq/llama-3.3-70b-versatile"
            )
        
        await report_thought(
            card_id, "challenger",
            "🔄 Challenger ready for scoring",
            "info"
        )
        
        return {
            "current_draft": challenger_draft,
            "iteration_count": iteration,
            "pipeline_status": "mutating",
        }
        
    except Exception as e:
        logger.error(f"mutation_failed: {e}")
        return {"error": f"Mutation failed: {str(e)}"}


@pipeline_node("system")
async def capture_learning_node(state: ProductionState) -> dict:
    """
    Called when the Karpathy loop ends.
    
    Two jobs:
    1. If we exhausted iterations, swap in the best_draft (not the last draft)
    2. If best_score >= 85%, capture what worked and store in Zep
    """
    card_id = state.get("card_id", "unknown")
    current_score = state.get("evaluation_score", 0)
    best_score = state.get("best_score", 0)
    best_draft = state.get("best_draft", "")
    current_draft = state.get("current_draft", "")
    
    updates = {}
    
    # Job 1: Ensure we're using the best draft
    if best_score > current_score and best_draft:
        await report_thought(
            card_id, "system",
            f"📋 Using best draft ({best_score}%) over last draft ({current_score}%)"
        )
        updates["current_draft"] = best_draft
        updates["evaluation_score"] = best_score
    
    # Job 2: Store winning learnings in Zep
    final_score = best_score if best_score > current_score else current_score
    if final_score >= 85:
        await report_thought(
            card_id, "system",
            f"🧠 Score {final_score}% qualifies for cross-script learning capture!"
        )
        
        try:
            from packages.content_factory.memory.zep_store import ZepAudienceModelStore
            zep = ZepAudienceModelStore()
            
            # Save the winning pattern
            topic_brief = state.get("topic_brief", {})
            topic_title = topic_brief.get("title", "") if isinstance(topic_brief, dict) else str(topic_brief)
            
            await zep.write_learning(
                f"PROVEN SCRIPT PATTERN ({final_score}%): {topic_title}\n"
                f"Key success factors: {state.get('evaluation_feedback', 'N/A')[:500]}"
            )
            
            await report_thought(
                card_id, "system",
                "🧠 Winning mutations saved to Zep — future scripts will be smarter",
                "success"
            )
        except Exception as e:
            logger.warning(f"learning_capture_failed: {e}")
    else:
        await report_thought(
            card_id, "system",
            f"📋 Score {final_score}% below 85% threshold — no learning captured"
        )
    
    return updates


@pipeline_node("visual_annotator")
async def visual_node(state: ProductionState) -> dict:
    """
    Read the finished script and add simple text visual directions.
    
    From Phase 2d: Output is flowing text with labels like [B-ROLL], [MAP], [DATA], [SOUND].
    NO JSON. Just human-readable suggestions for a video editor.
    
    Uses model: ollama/llama3.2 (Phase 3 — simple task, save cloud tokens)
    """
    card_id = state.get("card_id", "unknown")
    draft = state.get("current_draft", "")
    
    await report_thought(card_id, "visual_annotator", "🎬 Adding visual cues to script...")
    
    try:
        from packages.router.client import RouterClient
        from pathlib import Path
        
        # Load skill prompt from file (Code is Truth)
        skill_path = Path(__file__).parent.parent.parent / "data" / "skills" / "visual_planner.md"
        if skill_path.exists():
            skill_prompt = skill_path.read_text()
        else:
            skill_prompt = """You are a video director. Add visual cues to this script.
Use labels: [B-ROLL], [MAP], [DATA], [ARCHIVAL], [GRAPHIC], [TRANSITION], [SOUND].
Keep notes short — one sentence each."""
        
        prompt = f"""{skill_prompt}

---

SCRIPT:
{draft}

Add visual directions to each section."""
        
        async with RouterClient() as router:
            annotated = await router.complete_text(
                prompt,
                system="You are a video director. Output ONLY visual notes in plain text. NO JSON.",
                model="ollama/llama3.2"
            )
        
        await report_thought(
            card_id, "visual_annotator",
            "🎬 Visual annotations complete — ready for human review",
            "success"
        )
        
        return {
            "visual_plan": annotated,
            "pipeline_status": "visuals",
        }
        
    except Exception as e:
        logger.error(f"visual_annotation_failed: {e}")
        # Return original draft on failure
        return {"visual_plan": draft, "pipeline_status": "visuals"}


@pipeline_node("system")
async def human_review_node(state: ProductionState) -> dict:
    """
    PAUSE the graph and wait for human decision.
    
    Uses LangGraph's interrupt() — this saves the checkpoint and stops execution.
    The graph stays frozen until the human calls the /resume endpoint.
    """
    from langgraph.types import interrupt
    
    card_id = state.get("card_id", "unknown")
    
    await report_thought(
        card_id, "system",
        "⏸️ Waiting for human review...",
        "milestone",
        metadata={
            "score": state.get("evaluation_score", 0),
            "iterations": state.get("iteration_count", 0),
            "draft_words": len(state.get("current_draft", "").split()),
        }
    )
    
    await update_card_stage(card_id, "review")
    
    # THIS LINE PAUSES THE GRAPH
    # Execution stops here. State is checkpointed.
    # Resume happens via: graph.ainvoke(Command(resume={...}), config)
    decision = interrupt({
        "message": "Please review the script with visual annotations",
        "draft": state.get("current_draft", ""),
        "visual_plan": state.get("visual_plan", ""),
        "score": state.get("evaluation_score", 0),
        "iterations": state.get("iteration_count", 0),
    })
    
    # When resumed, `decision` contains the human's response
    return {
        "approved": decision.get("approved", False),
        "human_feedback": decision.get("feedback", ""),
        "pipeline_status": "review",
    }


@pipeline_node("system")
async def publish_notion_node(state: ProductionState) -> dict:
    """
    Publish the approved script + visual plan to Notion.
    Uses the Notion integration from packages/integrations/notion/
    """
    card_id = state.get("card_id", "unknown")
    topic_brief = state.get("topic_brief", {})
    draft = state.get("current_draft", "")
    visual_plan = state.get("visual_plan", "")
    
    await report_thought(card_id, "system", "📤 Publishing to Notion...")
    
    try:
        from packages.integrations.notion.client import NotionScriptClient
        from packages.core.config import get_settings
        
        settings = get_settings()
        if not settings.NOTION_API_KEY:
            await report_thought(card_id, "system", "⚠️ Notion API key not configured, skipping publish")
            return {"pipeline_status": "complete"}
        
        notion = NotionScriptClient()
        
        title = topic_brief.get("title", "Untitled") if isinstance(topic_brief, dict) else str(topic_brief)
        
        # Create the page
        page = await notion.create_script_page(
            title=title,
            script_data={"entries": [{"prose": draft, "visual_direction": visual_plan}]},
            seo_data={},
        )
        
        await report_thought(
            card_id, "system",
            "📤 Published to Notion successfully!",
            "success"
        )
        
        await update_card_stage(card_id, "completed")

        # C14 FIX: Return success ONLY from inside the try block
        return {"pipeline_status": "complete"}
        
    except Exception as e:
        logger.warning(f"notion_publish_failed: {e}")
        await report_thought(card_id, "system", f"⚠️ Notion publish failed: {str(e)[:100]}")
        # C14 FIX: Return error status instead of falling through to success
        return {"pipeline_status": "error", "error": f"Notion publish failed: {str(e)}"}


# ============================================================
# ERROR HANDLER NODE
# ============================================================

@pipeline_node("system")
async def error_handler_node(state) -> dict:
    """
    Catches any node failure that wrote to state["error"].
    Logs to dead letter queue, updates Kanban card with error status.
    
    Does NOT crash — the card stays visible with an error badge
    so the human can investigate and retry.
    """
    card_id = state.get("card_id", "unknown")
    error = state.get("error", "Unknown error")
    
    await report_thought(card_id, "system", f"💀 Pipeline failed: {error}", "error")
    
    # Update Kanban card with error status
    try:
        from packages.core.supabase_client import get_supabase
        sb = get_supabase()
        sb.table("kanban_cards").update({
            "status": "error",
            "error_message": error,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", card_id).execute()
    except Exception as e:
        logger.debug(f"card_error_update_failed: {e}")
    
    return {"pipeline_status": "error"}

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

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from .state import DiscoveryState, ProductionState
from .thoughts import pipeline_node, report_thought, update_card_stage

logger = logging.getLogger(__name__)


# ============================================================
# STYLE & GENRE LOADING (cached at module level)
# ============================================================

def _load_style_reference() -> dict:
    """Load style_reference.json — the Johnny Harris constitution."""
    style_path = Path(__file__).parent.parent / "style_reference.json"
    try:
        return json.loads(style_path.read_text())
    except Exception as e:
        logger.warning(f"style_reference_load_failed: {e}")
        return {}


def _load_genre_schema() -> dict:
    """Load genre_schema.json — genre-specific structural rules."""
    genre_path = Path(__file__).parent.parent / "genre_schema.json"
    try:
        return json.loads(genre_path.read_text())
    except Exception as e:
        logger.warning(f"genre_schema_load_failed: {e}")
        return {}


def _build_style_context(style: dict) -> str:
    """Extract key style rules into a compact prompt block."""
    if not style:
        return ""
    
    parts = []
    
    # Core philosophy
    philosophy = style.get("core_philosophy", {})
    if philosophy:
        parts.append(f"CORE PHILOSOPHY: {philosophy.get('summary', '')}")
    
    # Anchor-Bridge formula
    anchor_bridge = style.get("anchor_bridge_formula", {})
    if anchor_bridge:
        parts.append(f"RHYTHM: {anchor_bridge.get('rhythm', {}).get('rule', '')}")
        anchor_reqs = anchor_bridge.get("visual_anchor", {}).get("requirements", [])
        if anchor_reqs:
            parts.append(f"ANCHOR REQUIREMENTS: {'; '.join(anchor_reqs[:4])}")
    
    # Classic Style Writing rules
    csw = style.get("classic_style_writing", {})
    if csw:
        rules = csw.get("rules", [])
        for r in rules[:5]:
            parts.append(f"WRITING RULE [{r.get('name', '')}]: {r.get('description', '')}")
            if r.get('bad_example') and r.get('good_example'):
                parts.append(f"  BAD: {r['bad_example']}")
                parts.append(f"  GOOD: {r['good_example']}")
    
    # Peer-to-peer framing
    p2p = style.get("peer_to_peer_framing", {})
    if p2p:
        phrases = p2p.get("direction_phrases", [])
        if phrases:
            parts.append(f"USE THESE PHRASES (pick 2-3): {', '.join(phrases[:6])}")
        anti = p2p.get("anti_patterns", [])
        if anti:
            parts.append(f"NEVER sound like: {'; '.join(anti[:3])}")
    
    # Motive loading
    ml = style.get("motive_loading", {})
    if ml:
        parts.append(f"MOTIVE LOADING: {ml.get('rule', '')}")
        parts.append(f"  GOOD EXAMPLE: {ml.get('good_example', '')}")
    
    # Conclusion shift
    cs = style.get("conclusion_shift", {})
    if cs:
        struct = cs.get("structure", {})
        thinky = cs.get("thinky_mode", {}).get("description", "")
        feely = cs.get("feely_mode", {}).get("description", "")
        parts.append(f"CONCLUSION SHIFT: First {struct.get('thinky_percent', '80%')} {thinky}")
        parts.append(f"  Then shift to {struct.get('feely_percent', '10-20%')} {feely}")
        parts.append(f"  FINAL LINE RULE: {cs.get('final_line_rule', '')}")
    
    # Pakistani adaptation
    pa = style.get("pakistani_adaptation", {})
    if pa:
        rules = pa.get("rules", [])
        if rules:
            parts.append(f"PAKISTANI ADAPTATION: {'; '.join(rules)}")
    
    return "\n".join(parts)


def _get_genre_rules(genre_id: str, genre_schema: dict) -> str:
    """Get genre-specific structural backbone and rules."""
    if not genre_schema:
        return ""
    
    genres = genre_schema.get("genres", [])
    for g in genres:
        if g.get("genre_id") == genre_id:
            parts = [f"GENRE: {g.get('name', genre_id)}"]
            parts.append(f"STRUCTURAL BACKBONE: {g.get('structural_backbone', '')}")
            parts.append(f"KEY CHALLENGE: {g.get('key_challenge', '')}")
            parts.append(f"CONCLUSION PATTERN: {g.get('conclusion_pattern', '')}")
            desc = g.get("description", "")
            if desc:
                parts.append(f"GENRE DESCRIPTION: {desc}")
            return "\n".join(parts)
    
    return ""


# Cache loaded files at module level (reloaded on server restart)
_STYLE_REFERENCE = _load_style_reference()
_GENRE_SCHEMA = _load_genre_schema()
_STYLE_CONTEXT = _build_style_context(_STYLE_REFERENCE)


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
        current_year = datetime.now().year
        default_queries = [
            f"Pakistan technology innovation {current_year}",
            f"Pakistan economy news analysis {current_year}",
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
- gap_type: One of "Hidden Mechanism", "Oversimplified Narrative", "Hidden Connection", "Universal in Local"
- mainstream_assumption: What most people wrongly believe
- reality: What's actually true
- urgency: Why this matters NOW

Output ONLY valid JSON array, no markdown."""
        
        async with RouterClient() as router:
            response = await router.complete_text(
                prompt,
                system="You are a documentary topic researcher. Output ONLY valid JSON.",
                model="topic_finder",
                max_tokens=1500,
            )
        
        # Parse JSON response
        import json
        from packages.core.json_utils import extract_json_array
        json_str = extract_json_array(response)
        if json_str:
            try:
                parsed = json.loads(json_str)
                if isinstance(parsed, list) and len(parsed) > 0:
                    topics = parsed
                else:
                    topics = []
            except json.JSONDecodeError as e:
                logger.warning(f"topic_json_parse_failed: {e}")
                logger.warning(f"topic_json_raw_response: {response[:500]}")
                topics = []
        else:
            # Log raw response for debugging when extraction fails
            logger.warning(f"topic_json_extract_failed: {response[:500]}")
            topics = []

        if not topics:
            logger.warning(f"topic_generation_empty: LLM returned unparseable response for card {card_id}")
            logger.warning(f"topic_generation_raw_response: {response[:500]}")
            return {"generated_topics": [], "error": "LLM returned empty or unparseable topic list"}
        
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
        return {"graded_topics": [], "pipeline_status": "complete", "error": "No topics generated by LLM (empty response or unparseable JSON)"}
    
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

                # NOTE: Topics are saved to kanban_cards by save_topics_node (next step).
                # We don't insert here to avoid duplicates.
                # LangGraph checkpointing handles crash recovery — if this node fails
                # partway, the graph will restart from this node on retry.
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
                "column_index": 2,  # Suggested Topics
                "status": "suggested",
                "metadata": {
                    "topic_brief": topic,
                    "viability_score": topic.get("viability_score", 0),
                },
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
    
    Uses model: researcher
    """
    card_id = state.get("card_id", "unknown")
    topic_brief = state.get("topic_brief", {})
    
    topic_title = topic_brief.get("title", "Unknown topic") if isinstance(topic_brief, dict) else str(topic_brief)
    
    # Step 1: Check research cache (skip if topic_brief has force_research flag)
    force_research = False
    if isinstance(topic_brief, dict):
        force_research = topic_brief.get("force_research", False)

    if not force_research:
        await report_thought(card_id, "researcher", "🔍 Checking for existing research cache...")
    else:
        await report_thought(card_id, "researcher", "🔍 Force-research requested, skipping cache...")
    
    try:
        from packages.core.research_cache import ResearchCache
        cache = ResearchCache()
        
        cached = cache.get(topic_statement=topic_title) if not force_research else None
        if cached:
            dossier_text = cached.get("dossier", "")
            # Handle string or dict dossier from cache
            if isinstance(dossier_text, dict):
                # Reconstruct markdown from cached dict
                from packages.content_factory.production.models import ResearchDossier
                try:
                    dossier_obj = ResearchDossier(**dossier_text)
                    dossier_text = dossier_obj.to_markdown()
                except Exception:
                    dossier_text = str(dossier_text)
            await report_thought(
                card_id, "researcher",
                f"📄 Using cached research ({len(dossier_text)} chars)",
                "success"
            )
            return {
                "research_dossier": dossier_text,
                "research_sources": cached.get("source_urls", []),
                "pipeline_status": "researching",
            }
    except Exception as e:
        logger.warning(f"cache_check_failed: {e}")
    
    # Step 2: Execute research
    await report_thought(card_id, "researcher", f"🔍 Researching: {topic_title}")
    
    try:
        from packages.content_factory.production.deep_research import DeepResearchEngine
        from packages.router.client import RouterClient
        
        async with RouterClient() as router:
            engine = DeepResearchEngine(
                router_client=router,
                max_searches_per_dimension=4,   # More searches per dimension
                max_total_searches=30,           # Bigger search budget
            )
            
            # Run deep research with higher completeness target
            dossier = await engine.research(
                topic_title,
                target_completeness=0.7,  # Slightly lower to avoid excessive retries
                max_iterations=3,
                resume_from_checkpoint=False,  # Fresh research each time
            )
            
            if dossier:
                dossier_text = dossier.to_markdown() if hasattr(dossier, 'to_markdown') else str(dossier)
                sources = dossier.all_sources if hasattr(dossier, 'all_sources') else []
            else:
                dossier_text = f"Research for {topic_title}"
                sources = []
        
        # Step 3: Save dossier permanently to cache
        try:
            cache.save(
                cache_key=ResearchCache.make_key(topic_statement=topic_title),
                topic_statement=topic_title,
                dossier=dossier.model_dump() if hasattr(dossier, 'model_dump') else {"text": dossier_text},
                source_urls=sources,
            )
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


@pipeline_node("researcher")
async def research_gap_node(state: ProductionState) -> dict:
    """
    FIX #3: Research Feedback Loop.
    
    When the scorer detects thin evidence (credibility < 60%), this node
    runs a targeted supplementary search on the weak area, appends findings
    to the existing dossier, then routes back to draft.
    
    Only runs ONCE per pipeline (research_round == 1) to avoid infinite loops.
    Uses model: researcher
    """
    card_id = state.get("card_id", "unknown")
    topic_brief = state.get("topic_brief", {})
    current_dossier = state.get("research_dossier", "")
    score_categories = state.get("score_categories", {})
    evaluation_feedback = state.get("evaluation_feedback", "")
    research_round = state.get("research_round", 1)
    
    topic_title = topic_brief.get("title", "Unknown topic") if isinstance(topic_brief, dict) else str(topic_brief)
    
    await report_thought(card_id, "researcher", "🔍 Research gap detected — running targeted supplementary search...")
    
    try:
        from packages.router.client import RouterClient
        
        # Build a targeted research query from the scorer's feedback
        async with RouterClient() as router:
            gap_prompt = f"""Based on this script evaluation, identify what specific information is missing or thin.

EVALUATION FEEDBACK:
{evaluation_feedback}

SCORE CATEGORIES: {json.dumps(score_categories)}

CURRENT RESEARCH DOSSIER (first 3000 chars):
{current_dossier[:3000]}

Identify the TOP 2-3 specific things the research is missing. For each, write a targeted search query.
Return JSON: {{"gaps": [{{"area": "...", "query": "..."}}, ...]}}"""
            
            gap_analysis = await router.complete_text(
                gap_prompt,
                system="You are a research gap analyst. Identify what specific facts, names, numbers, or examples are missing from research. Return ONLY valid JSON.",
                model="researcher",
                temperature=0.0,
            )
            
            from packages.core.json_utils import extract_json_object
            gap_json = extract_json_object(gap_analysis)
            
            if not gap_json:
                await report_thought(card_id, "researcher", "⚠️ Could not parse research gaps, skipping supplementary search")
                return {"pipeline_status": "researching"}
            
            gaps = json.loads(gap_json).get("gaps", [])
            if not gaps:
                await report_thought(card_id, "researcher", "⚠️ No specific gaps identified, skipping supplementary search")
                return {"pipeline_status": "researching"}
            
            await report_thought(
                card_id, "researcher",
                f"🔍 Found {len(gaps)} research gaps: {', '.join(g.get('area', '?') for g in gaps[:3])}"
            )
            
            # Run targeted searches for each gap
            from packages.router.web_search import WebSearchClient
            search_client = WebSearchClient()
            
            supplementary_facts = []
            for gap in gaps[:3]:
                query = gap.get("query", "")
                if not query:
                    continue
                try:
                    results = await search_client.search(query, num_results=5)
                    for r in results:
                        text = getattr(r, 'text', '') or ''
                        if text:
                            supplementary_facts.append(f"### {getattr(r, 'title', 'Source')}:\n{text}")
                except Exception as e:
                    logger.warning(f"supplementary_search_failed: {e}")
            
            if supplementary_facts:
                # Append supplementary findings to the existing dossier
                supplementary_section = f"\n\n---\n\n## SUPPLEMENTARY RESEARCH (Round 2 — Gap Fill)\n\n" + "\n\n".join(supplementary_facts)
                enriched_dossier = current_dossier + supplementary_section
                
                await report_thought(
                    card_id, "researcher",
                    f"📄 Supplementary research complete: +{len(supplementary_section)} chars added to dossier",
                    "success",
                    metadata={"gap_count": len(gaps), "chars_added": len(supplementary_section)}
                )
                
                return {
                    "research_dossier": enriched_dossier,
                    "research_round": 2,  # Mark that we've done round 2
                    "pipeline_status": "researching",
                }
            else:
                await report_thought(card_id, "researcher", "⚠️ Supplementary searches returned no results")
                return {"research_round": 2, "pipeline_status": "researching"}
    
    except Exception as e:
        logger.error(f"research_gap_failed: {e}")
        # Don't fail the pipeline — just continue with what we have
        await report_thought(card_id, "researcher", f"⚠️ Research gap search failed: {str(e)[:100]}")
        return {"research_round": 2, "pipeline_status": "researching"}


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
    
    Uses model: script_writer
    """
    card_id = state.get("card_id", "unknown")
    topic_brief = state.get("topic_brief", {})
    research = state.get("research_dossier", "")
    learnings = state.get("zep_learnings", "")
    human_feedback = state.get("human_feedback")
    evaluation_feedback = state.get("evaluation_feedback")
    visual_feedback = state.get("visual_feedback")
    research_round = state.get("research_round", 1)
    iteration = state.get("iteration_count", 0)
    
    topic_title = topic_brief.get("title", "Unknown") if isinstance(topic_brief, dict) else str(topic_brief)
    
    if human_feedback:
        await report_thought(card_id, "script_writer", "✍️ Rewriting based on human feedback...")
    elif visual_feedback:
        await report_thought(card_id, "script_writer", "✍️ Rewriting based on visual annotator feedback...")
    elif research_round > 1 and iteration == 0:
        await report_thought(card_id, "script_writer", "✍️ Rewriting with enriched research (round 2)...")
    elif iteration > 0 and evaluation_feedback:
        await report_thought(card_id, "script_writer", f"✍️ Writing iteration {iteration + 1}...")
    else:
        await report_thought(card_id, "script_writer", "✍️ Writing first draft...")
    
    try:
        from packages.router.client import RouterClient
        
        # Build context — give the LLM maximum research material
        # FIX #4: Increased research window from 8000 → 16000 chars
        context_parts = []
        if learnings:
            context_parts.append(f"PAST WINNING PATTERNS:\n{learnings[:1500]}")
        if research:
            context_parts.append(f"RESEARCH DOSSIER:\n{research[:16000]}")
        if human_feedback:
            context_parts.append(f"HUMAN FEEDBACK TO ADDRESS:\n{human_feedback}")
        elif visual_feedback:
            context_parts.append(f"VISUAL ANNOTATOR FEEDBACK TO ADDRESS:\n{visual_feedback}")
        elif evaluation_feedback:
            context_parts.append(f"EVALUATION FEEDBACK:\n{evaluation_feedback}")
        
        context = "\n\n---\n\n".join(context_parts)
        
        # FIX #1 & #6: Inject style reference and genre-specific rules
        genre_id = topic_brief.get("genre_id", "current_situation") if isinstance(topic_brief, dict) else "current_situation"
        genre_rules = _get_genre_rules(genre_id, _GENRE_SCHEMA)
        
        style_block = _STYLE_CONTEXT or ""
        if style_block:
            style_block = f"\n\n=== JOHNNY HARRIS STYLE CONSTITUTION ===\n{style_block}"
        
        genre_block = f"\n\n=== GENRE-SPECIFIC RULES ===\n{genre_rules}" if genre_rules else ""
        
        prompt = f"""You are writing a Johnny Harris-style documentary script. This is NOT a generic overview — this is a specific, evidence-driven story.

TOPIC: {topic_title}
{genre_block}
{style_block}

{context}

CRITICAL RULES — YOUR SCRIPT WILL BE REJECTED IF YOU VIOLATE THESE:
1. You MUST cite at least 3 specific numbers, statistics, or data points from the research above
2. You MUST name at least 2 real people, organizations, companies, or places mentioned in the research
3. You MUST reference at least 1 specific event, case study, or real-world example
4. NEVER write vague statements like "a new generation is emerging" or "things are changing" — be SPECIFIC
5. NEVER write filler like "in a country often defined by its tumultuous politics" — get straight to the point
6. Every paragraph must contain a concrete fact, name, number, or specific example from the research
7. Use active voice. Name who did what. Give numbers. Be specific about where and when.

VOICE RULES:
- Write like a friend who just discovered something fascinating: "Look at this." "Wait, come with me on this."
- Assign HUMAN MOTIVES to every entity (fear, ambition, desperation, pride). Entities without motives are abstract forces.
- Use Anchor-Bridge rhythm: drop the viewer into something REAL (an object, a document, a person), THEN explain.
- NEVER use nominalizations (globalization, implementation, utilization). Replace with plain actions.
- The last 10-20% of the script must shift from precise evidence to personal, poetic, emotionally resonant.

STRUCTURE:
**HOOK** — Open IN MEDIAS RES. Drop the viewer into a surprising action, a specific number, a physical object. NOT an abstract intro.
**ANCHOR** — Ground in something tangible the camera can point at: a document, a place, a person's face.
**BRIDGE** — Connect the anchor evidence to the bigger picture. Show the mechanism. Who did what to whom.
**REVEAL** — The key insight that challenges the mainstream assumption. Back it with evidence. Name who loses and who wins.
**CONCLUSION** — Shift to personal/poetic mode. Include unexpected praise. End with a resonant line, not a summary.

Write 500-700 words of narration text. Output ONLY the script with section headers. No meta-commentary."""
        
        system_prompt = """You are an elite documentary scriptwriter in the style of Johnny Harris.

Your writing obeys these IRON RULES:
1. INVESTIGATION OVER EXPLANATION — Show the audience something real. Let meaning emerge from what they see.
2. EXPERIENCE OVER INFORMATION — Viewers retain experiences, not lectures. Create discovery, not instruction.
3. AGENT-ACTION-OBJECT — Every sentence has a visible agent doing something to a visible object. Can the viewer form a mental image? If not, rewrite.
4. ANTI-ABSTRACTION — Never use nominalizations ("the globalization of trade led to..."). Write "America sent its factories to China and a million workers in Ohio lost their jobs."
5. PEER-TO-PEER — You are NOT a professor or journalist. You are a friend saying "wait, look at this."
6. CONCRETE FACTS ONLY — Every sentence carries specific names, numbers, dates, or places. NO vague generalizations.
7. PAKISTANI AUDIENCE — Use PKR, Pakistani locations, Pakistani cultural context. No Western defaults.

You NEVER write: "In a country often defined by...", "Things are changing", "A new era is dawning", "The stakes are high", "It's not just about X, it's about Y."
You ALWAYS write: "On February 14th, 2025, the federal cabinet approved...", "i2i PSER's report shows...", "Hub Copilot increased completed tasks by 26%..."""

        async with RouterClient() as router:
            draft = await router.complete_text(
                prompt,
                system=system_prompt,
                model="script_writer",
                max_tokens=2000,
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
                "visual_feedback": None,  # Clear visual feedback too
                "visual_needs_revision": False,
            }
        elif visual_feedback:
            return {
                "current_draft": draft,
                "iteration_count": 0,  # Fresh mutation budget for visual revision
                "pipeline_status": "drafting",
                "visual_feedback": None,  # Clear after using
                "visual_needs_revision": False,
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
    Evaluate the current draft against the 56-question binary checklist.
    Returns a score (0-100) representing percentage of questions passed,
    and text feedback describing weak zones.
    
    Also tracks best_draft: if this score beats the previous best,
    save this draft as the new best.
    
    Uses model: scorer
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
        
        prompt = f"""Evaluate this documentary script draft against the 56-question binary checklist.

DRAFT:
{draft}

Answer YES or NO to each question. Each YES counts as 1 point (max 56 points).
Score = (points / 56) * 100, rounded to nearest integer.

=== STRUCTURE (8 questions) ===
1. Does the hook appear in the first 15 seconds?
2. Is there a clear narrative arc (setup → conflict → resolution)?
3. Does each section flow logically to the next?
4. Is the script divided into clear segments/acts?
5. Does the ending tie back to the opening hook?
6. Is the total length appropriate (3-10 minutes when read)?
7. Are transitions smooth between topics?
8. Is there a clear thesis statement?

=== HOOK & OPENING (6 questions) ===
9. Does the opening create immediate curiosity?
10. Is the hook relevant to the main topic?
11. Does the hook avoid clickbait tactics?
12. Is the opening visually descriptive?
13. Does the hook promise value to the viewer?
14. Is the opening tone appropriate for the subject?

=== CLARITY & COMPREHENSION (8 questions) ===
15. Are technical terms explained on first use?
16. Is jargon minimized or defined?
17. Would a general audience understand every sentence?
18. Are analogies used to explain complex concepts?
19. Is there no ambiguity in key claims?
20. Are statistics properly contextualized?
21. Is the reading level appropriate (8th-10th grade)?
22. Are cause-and-effect relationships clear?

=== ENGAGEMENT & PACING (7 questions) ===
23. Does the script maintain tension/interest throughout?
24. Are there moments of surprise or revelation?
25. Is the pacing varied (not monotonous)?
26. Are there specific, concrete details (not abstractions)?
27. Does the script use active voice predominantly?
28. Are sentences varied in length?
29. Is there a rhythm to the language when read aloud?

=== CREDIBILITY & EVIDENCE (7 questions) ===
30. Are claims supported by specific evidence?
31. Are sources credible and relevant?
32. Does the script acknowledge uncertainty where appropriate?
33. Are counter-arguments addressed?
34. Is the evidence proportionate to the claims?
35. Are expert quotes used effectively?
36. Is there no unsupported speculation?

=== EMOTIONAL RESONANCE (6 questions) ===
37. Does the script evoke an emotional response?
38. Are human stories/characters present?
39. Is the emotional tone appropriate (not manipulative)?
40. Does the script create empathy for subjects?
41. Are emotional moments earned (not forced)?
42. Is there a satisfying emotional arc?

=== VISUAL POTENTIAL (6 questions) ===
43. Are scenes visually describable (B-roll friendly)?
44. Is there variety in visual opportunities?
45. Are locations/settings clearly established?
46. Are characters visually distinct?
47. Are action moments described specifically?
48. Is there visual contrast between scenes?

=== CONCLUSION & TAKEAWAY (5 questions) ===
49. Does the ending provide closure?
50. Is there a clear takeaway for the viewer?
51. Does the conclusion reinforce key points?
52. Is there a call to action or reflection prompt?
53. Does the ending feel earned (not abrupt)?

=== OVERALL IMPACT (3 questions) ===
54. Would this script stand out from similar content?
55. Does it offer a unique perspective or insight?
56. Would viewers recommend this to others?

Count YES answers, calculate score as (YES_count / 56) * 100.

For each category, calculate the percentage of YES answers within that category.

Return JSON with this EXACT structure:
{{"score": 85, "feedback": "Brief description of strengths and what needs improvement", "score_categories": {{"structure": 88, "hook": 83, "clarity": 75, "engagement": 86, "credibility": 71, "emotional": 67, "visual": 83, "conclusion": 80, "impact": 67}}}}

Where each category value is: (YES_in_category / total_in_category) * 100, rounded to nearest integer.
Category question counts: structure=8, hook=6, clarity=8, engagement=7, credibility=7, emotional=6, visual=6, conclusion=5, impact=3."""
        
        async with RouterClient() as router:
            import json
            from packages.core.json_utils import extract_json_object
            response = await router.complete_text(
                prompt,
                system="You are a strict script evaluator. Return ONLY valid JSON.",
                model="scorer",
                temperature=0.0
            )

            json_str = extract_json_object(response)
            if json_str:
                result = json.loads(json_str)
                score = result.get("score", 0)
                # Clamp score to 0-100 (LLM may return out-of-bounds values)
                score = max(0, min(100, int(score)))
                feedback = result.get("feedback", "")
                score_categories = result.get("score_categories", {})
            else:
                score = 50
                feedback = "Could not parse evaluation"
                score_categories = {}
        
        updates = {
            "evaluation_score": score,
            "evaluation_feedback": feedback,
            "score_categories": score_categories,
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
    
    Uses model: challenger
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
        
        # FIX #2: Inject Johnny Harris style rules into the mutator too
        style_block = _STYLE_CONTEXT or ""
        if style_block:
            style_block = f"\n\n=== JOHNNY HARRIS STYLE CONSTITUTION ===\n{style_block}"
        
        # Also give the mutator access to the research for fact-checking
        research = state.get("research_dossier", "")
        research_block = f"\n\nRESEARCH FACTS (use these to replace vague claims):\n{research[:8000]}" if research else ""
        
        prompt = f"""You are improving a Johnny Harris-style documentary script. Preserve the voice. Kill the generic AI sound.

CURRENT DRAFT:
{draft}

FEEDBACK ON WEAKNESS:
{feedback}
{style_block}
{research_block}

MUTATION RULES:
1. ONLY rewrite the sections the feedback calls out as weak. Keep strong sections EXACTLY as they are.
2. Replace any vague/abstract sentences with concrete facts from the research above.
3. If a sentence has no specific name, number, date, or place — it MUST be replaced.
4. Use active voice: Name who did what to whom.
5. Use peer-to-peer phrases: "Look at this", "Wait, come with me", "Here's what I found"
6. Assign human motives to every entity mentioned (fear, ambition, desperation, pride).
7. NEVER add filler like "the stakes are high", "in a country defined by", "things are changing"
8. The conclusion should shift from evidence to personal/poetic mode.

Output ONLY the complete improved script with section headers. Do NOT add meta-commentary."""
        
        system_prompt = """You are a Johnny Harris script doctor. You fix weak writing by making it more specific, more human, more grounded in evidence.

Your fixes follow these rules:
- Replace abstractions with Agent-Action-Object sentences
- Replace vague claims with specific numbers, names, dates from the research
- Add peer-to-peer framing ("wait, look at this")
- Add human motives to entities
- Kill all filler phrases and AI-sounding generalizations
- Preserve the strong sections exactly as-is

Output the complete improved script only. No commentary."""

        async with RouterClient() as router:
            challenger_draft = await router.complete_text(
                prompt,
                system=system_prompt,
                model="challenger"
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
    
    # Always use the best draft and sync score
    final_score = max(best_score, current_score)
    final_draft = best_draft if best_draft and best_score >= current_score else current_draft
    
    updates = {
        "current_draft": final_draft,
        "evaluation_score": final_score,  # Always sync score to best
    }
    
    # Job 1: Report if we swapped drafts
    if best_score > current_score and best_draft:
        await report_thought(
            card_id, "system",
            f"📋 Using best draft ({best_score}%) over last draft ({current_score}%)"
        )
    
    # Job 2: Store winning learnings in Zep
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
    
    FIX #5: Also acts as a STRUCTURAL REVIEWER — if the script has
    structural problems that visual annotations can't fix, it sets
    visual_needs_revision=True and provides feedback for the writer.
    
    From Phase 2d: Output is flowing text with labels like [B-ROLL], [MAP], [DATA], [SOUND].
    NO JSON. Just human-readable suggestions for a video editor.
    
    Uses model: annotator
    """
    card_id = state.get("card_id", "unknown")
    draft = state.get("current_draft", "")
    
    await report_thought(card_id, "visual_annotator", "🎬 Adding visual cues and reviewing script structure...")
    
    try:
        from packages.router.client import RouterClient
        from pathlib import Path
        from packages.core.json_utils import extract_json_object
        
        # Load skill prompt from file (Code is Truth)
        skill_path = Path(__file__).parent.parent.parent / "data" / "skills" / "visual_planner.md"
        if skill_path.exists():
            skill_prompt = skill_path.read_text()
        else:
            skill_prompt = """You are a video director. Add visual cues to this script.
Use labels: [B-ROLL], [MAP], [DATA], [ARCHIVAL], [GRAPHIC], [TRANSITION], [SOUND].
Keep notes short — one sentence each."""
        
        # Step 1: Structural review — does the script need rewriting?
        review_prompt = f"""You are a video director reviewing a script for producibility.

SCRIPT:
{draft}

As a director, check if this script has STRUCTURAL issues that would make it impossible or very difficult to produce as a video:
- Is it too abstract (no visual anchors, no physical objects/places/people the camera can point at)?
- Is the structure broken (no clear sections, no narrative arc)?
- Does it read like an essay rather than a script (too much telling, not enough showing)?
- Are there sections that are visually unproduceable?

Return JSON: {{
  "needs_revision": true/false,
  "reason": "Brief explanation if revision needed",
  "feedback": "Specific feedback for the script writer about what to change"
}}"""
        
        async with RouterClient() as router:
            review_response = await router.complete_text(
                review_prompt,
                system="You are a video director reviewing scripts for producibility. Return ONLY valid JSON.",
                model="annotator",
                temperature=0.0,
            )
            
            review_json = extract_json_object(review_response)
            needs_revision = False
            visual_feedback_text = ""
            
            if review_json:
                try:
                    review = json.loads(review_json)
                    needs_revision = review.get("needs_revision", False)
                    visual_feedback_text = review.get("feedback", "")
                    if needs_revision:
                        await report_thought(
                            card_id, "visual_annotator",
                            f"🎬 Script needs structural revision: {visual_feedback_text[:100]}",
                            "warning"
                        )
                except Exception:
                    pass
        
        # Step 2: Add visual annotations
        prompt = f"""{skill_prompt}

---

SCRIPT:
{draft}

Add visual directions to each section."""
        
        async with RouterClient() as router:
            annotated = await router.complete_text(
                prompt,
                system="You are a video director. Output ONLY visual notes in plain text. NO JSON.",
                model="annotator"
            )
        
        result = {
            "visual_plan": annotated,
            "pipeline_status": "visuals",
            "visual_needs_revision": needs_revision,
        }
        
        if needs_revision and visual_feedback_text:
            result["visual_feedback"] = visual_feedback_text
        
        if not needs_revision:
            await report_thought(
                card_id, "visual_annotator",
                "🎬 Visual annotations complete — script structure OK, ready for human review",
                "success"
            )
        else:
            await report_thought(
                card_id, "visual_annotator",
                "🎬 Visual annotations done — routing script back for structural revision",
                "warning"
            )
        
        return result
        
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
    
    Includes risk tier classification and SLA tracking (Issue 6):
    - Classifies the evaluation score into risk tiers (low/medium/high)
    - Computes a review SLA deadline based on risk tier
    - Passes risk_tier and sla_deadline to the frontend via interrupt data
    """
    from langgraph.types import interrupt
    from packages.core.config import get_settings
    
    card_id = state.get("card_id", "unknown")
    evaluation_score = state.get("evaluation_score", 0)
    settings = get_settings()
    
    # ── Risk tier classification (Issue 6) ──
    if evaluation_score >= settings.RISK_TIER_LOW_SCORE:
        risk_tier = "low"
    elif evaluation_score >= settings.RISK_TIER_HIGH_SCORE:
        risk_tier = "medium"
    else:
        risk_tier = "high"
    
    # ── SLA deadline based on risk tier ──
    sla_hours_map = {
        "low": settings.RISK_TIER_LOW_SLA_HOURS,
        "medium": settings.RISK_TIER_MEDIUM_SLA_HOURS,
        "high": settings.RISK_TIER_HIGH_SLA_HOURS,
    }
    sla_hours = sla_hours_map.get(risk_tier, settings.HUMAN_REVIEW_TIMEOUT_HOURS)
    review_requested_at = datetime.now(timezone.utc)
    sla_deadline = review_requested_at + timedelta(hours=sla_hours)
    
    await report_thought(
        card_id, "system",
        f"⏸️ Waiting for human review... [risk={risk_tier}, SLA={sla_hours}h]",
        "milestone",
        metadata={
            "score": evaluation_score,
            "iterations": state.get("iteration_count", 0),
            "draft_words": len(state.get("current_draft", "").split()),
            "risk_tier": risk_tier,
            "sla_hours": sla_hours,
            "sla_deadline": sla_deadline.isoformat(),
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
        "score": evaluation_score,
        "iterations": state.get("iteration_count", 0),
        "risk_tier": risk_tier,
        "sla_deadline": sla_deadline.isoformat(),
        "review_requested_at": review_requested_at.isoformat(),
    })
    
    # When resumed, `decision` contains the human's response
    # Handle both dict and Pydantic model objects (ResumeDecision)
    if hasattr(decision, 'approved'):
        # Pydantic model (ResumeDecision)
        approved = decision.approved
        feedback = getattr(decision, 'feedback', '')
    else:
        # Dict object
        approved = decision.get("approved", False)
        feedback = decision.get("feedback", "")
    
    return {
        "approved": approved,
        "human_feedback": feedback,
        "pipeline_status": "review",
        "risk_tier": risk_tier,
        "review_requested_at": review_requested_at.isoformat(),
        "sla_deadline": sla_deadline.isoformat(),
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
        
        # Build script entries in the format Notion client expects:
        # {section_type, narration, visual_cue, visual_type}
        script_entries = [
            {
                "section_type": "Script",
                "narration": draft,
                "visual_cue": visual_plan,
                "visual_type": "broll",
            }
        ]
        
        # Create the page — returns OperationResult[str]
        result = await notion.create_script_page(
            title=title,
            script_data={"entries": script_entries},
            seo_data={},
        )
        
        if result.success:
            notion_url = result.data or ""
            await report_thought(
                card_id, "system",
                f"📤 Published to Notion! {notion_url[:80] if notion_url else ''}",
                "success",
                metadata={"notion_url": notion_url}
            )
        else:
            # OperationResult indicates failure — log but still mark complete
            # since the retry policy handles transient errors above
            await report_thought(
                card_id, "system",
                f"⚠️ Notion publish issue: {result.user_message or result.error_message or 'Unknown error'}",
                "error"
            )
        
        await update_card_stage(card_id, "completed")

        # C14 FIX: Return success ONLY from inside the try block
        # Include final state so downstream consumers see correct values
        return {
            "pipeline_status": "complete",
            "current_draft": draft,
            "visual_plan": visual_plan,
        }
        
    except Exception as e:
        logger.warning(f"notion_publish_failed: {e}")
        await report_thought(card_id, "system", f"⚠️ Notion publish failed: {str(e)[:100]}")
        # C15 FIX: Don't set error field here - let the retry policy handle retries.
        # The PUBLISH_RETRY policy will retry up to 5 times. Only if all retries fail
        # will LangGraph mark the node as failed and route to error_handler.
        # Setting error here would cause immediate routing to error_handler on retry.
        raise  # Re-raise to trigger retry policy


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
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", card_id).execute()
    except Exception as e:
        logger.warning(f"card_error_update_failed: {e}")
    
    return {"pipeline_status": "error"}

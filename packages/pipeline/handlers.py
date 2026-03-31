"""Stage handlers for pipeline execution.

All handlers are wired with real implementations that connect
to the content_factory agents and evaluation loop.

DEEP RESEARCH INTEGRATION:
  The research handler now supports caching to avoid re-researching
  the same topic. Cache TTL is 24 hours by default.

FIXES APPLIED:
  1. Cache hit now actually returns cached script instead of ignoring it
  2. Added separate script cache for AdaptedScript objects
  3. Proper cache invalidation and refresh

REFACTORED:
  - ScriptCache replaced with unified FileCache from packages.core.cache
"""

from typing import Any, Callable
import json
from datetime import datetime, timezone
from pathlib import Path

from packages.core.json_utils import extract_json_object
from packages.pipeline.stages import Stage
from packages.pipeline.state import PipelineRun
from packages.pipeline.research_cache import ResearchCache
from packages.content_factory.topic_finder.finder import TopicFinderAgent
from packages.core.config import get_settings
from packages.core.cache import FileCache
from packages.core.logger import get_logger

logger = get_logger(__name__)


async def handle_trend_analysis(run: PipelineRun, context: dict = None) -> list[dict]:
    """Uses TopicFinderAgent to generate Tier 1 topic candidates.

    Args:
        run: Current pipeline run
        context: Additional context (expects 'seed_query' and 'genre_id')

    Returns:
        List of topic candidates as dictionaries
    """
    finder = TopicFinderAgent()
    seed = (context or {}).get("seed_query", "Pakistan economy")
    genre = (context or {}).get("genre_id", "current_situation")

    logger.info(f"running_trend_analysis: seed='{seed}' genre='{genre}'")

    # Generate 3 candidates for the user to choose from
    candidates = []
    for _ in range(3):
        brief = await finder.generate_candidate(seed, genre)
        if brief:
            candidates.append(brief.model_dump())

    # Also discover adaptation candidates from Source Library
    try:
        adaptation_briefs = await finder.discover_adaptation_candidates(genre)
        for brief in adaptation_briefs[:1]:  # max 1 adaptation candidate per run
            candidates.append(brief.model_dump())
    except Exception as e:
        logger.warning(f"adaptation_discovery_failed_non_blocking: {e}")

    if not candidates:
        # Fallback to mock if nothing found to keep pipeline moving in dev
        logger.warning("no_tier1_topics_found_using_mock_fallback")
        return [
            {
                "topic_statement": "Why Pakistan's AI Policy Matters",
                "big_question": "Is the new AI draft actually enforceable?",
                "genre_id": genre,
                "gap_type": "Hidden Mechanism",
                "viability_score_breakdown": {"total": 15},
                "anchor_candidates": ["National AI Policy PDF"],
                "mainstream_assumption": "It's just another paper trail",
                "urgency_flag": True,
                "timing_rationale": "Recent cabinet approval",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "reservoir",
                "content_type": "original",
            }
        ]

    return candidates


async def handle_research(run: PipelineRun, context: dict = None) -> dict:
    """Routes to Mode A or Mode B via ContentCreationRouter, then scores baseline.

    Includes optional research caching to avoid re-researching the same topic.
    Cache TTL is 24 hours by default.

    FIX: Cache hit now actually returns cached script instead of ignoring it.

    Args:
        run: Current pipeline run
        context: Additional context (supports 'use_cache' and 'cache_ttl_hours')

    Returns:
        AdaptedScript object as dict
    """
    from packages.content_factory.router import ContentCreationRouter
    from packages.content_factory.topic_finder.models import TopicBrief
    from packages.content_factory.evaluation.baseline import BaselineManager

    settings = get_settings()
    
    topic_data = run.get_output(Stage.HUMAN_TOPIC_APPROVAL)
    if not topic_data:
        logger.error("research_handler_missing_approved_topic")
        return {}

    try:
        brief = TopicBrief(**topic_data) if isinstance(topic_data, dict) else topic_data
    except Exception:
        # Build a minimal brief from whatever was approved
        brief = TopicBrief(
            topic_statement=str(topic_data.get("topic_statement", "Unknown")),
            big_question=str(topic_data.get("big_question", "")),
            genre_id=str(topic_data.get("genre_id", "current_situation")),
            gap_type=topic_data.get("gap_type", "Hidden Mechanism"),
            viability_score_breakdown={},
            anchor_candidates=[],
            mainstream_assumption="",
            timing_rationale="",
            created_at=datetime.now(timezone.utc),
            content_type=topic_data.get("content_type", "original"),
        )

    # Check if caching is enabled (default: True)
    use_cache = (context or {}).get("use_cache", True)
    cache_ttl_hours = (context or {}).get("cache_ttl_hours", 24)

    if use_cache:
        # Check script cache first (full AdaptedScript)
        script_cache = FileCache(
            cache_dir=Path(settings.DATA_DIR) / "script_cache",
            ttl_hours=cache_ttl_hours,
        )
        cached_script = script_cache.get(brief.topic_statement, brief.genre_id)

        if cached_script:
            logger.info(
                f"research_script_cache_hit: topic='{brief.topic_statement[:50]}...' "
                f"genre='{brief.genre_id}'"
            )
            # Update baseline with cached script
            try:
                from packages.content_factory.models import AdaptedScript
                script = AdaptedScript(**cached_script)
                bm = BaselineManager()
                bm.process_challenger(script)
            except Exception as e:
                logger.warning(f"baseline_update_from_cache_failed: {e}")

            return cached_script

        # Also check research cache for logging purposes
        research_cache = ResearchCache(ttl_hours=cache_ttl_hours)
        cached_research = research_cache.get(brief.topic_statement)
        if cached_research:
            logger.info(
                f"research_dossier_cache_hit: topic='{brief.topic_statement[:50]}...' "
                f"(will still generate script)"
            )

    router = ContentCreationRouter()
    script = await router.route(brief)

    if not script:
        return {"error": "content_creation_failed", "topic": brief.topic_statement}

    # Record initial baseline score (pre-experiment-loop)
    try:
        bm = BaselineManager()
        bm.process_challenger(script)
    except Exception as e:
        logger.warning(f"baseline_record_failed_non_blocking: {e}")

    # Cache the full script if caching is enabled
    if use_cache:
        script_cache = FileCache(
            cache_dir=Path(settings.DATA_DIR) / "script_cache",
            ttl_hours=cache_ttl_hours,
        )
        script_cache.set(brief.topic_statement, brief.genre_id, script.model_dump())

    return script.model_dump()


async def handle_script_writing(run: PipelineRun, context: dict = None) -> dict:
    """Runs the self-correction ExperimentLoop on the script from research stage.

    Args:
        run: Current pipeline run
        context: Additional context

    Returns:
        Refined script data as dict
    """
    from packages.content_factory.router import ContentCreationRouter
    from packages.content_factory.models import AdaptedScript

    script_data = run.get_output(Stage.RESEARCH)
    if not script_data or "error" in (script_data or {}):
        logger.warning("script_writing_no_research_data")
        return script_data or {}

    try:
        script = AdaptedScript(**script_data)
    except Exception as e:
        logger.error(f"script_writing_model_parse_failed: {e}")
        return script_data

    router = ContentCreationRouter()
    
    threshold = (context or {}).get("threshold", 85.0)
    max_iterations = (context or {}).get("max_iterations", 20)

    refined = await router.run_experiment_loop(
        script,
        max_iterations=max_iterations,
        threshold=threshold,
        run_id=run.run_id,
    )

    logger.info(f"script_writing_complete: final_score={refined.production_readiness_score:.1f}%")

    # Non-blocking Zep write
    try:
        from packages.content_factory.memory.zep_store import ZepAudienceModelStore
        zep = ZepAudienceModelStore()
        await zep.write_experiment_result(
            refined, refined.production_readiness_score, refined.genre
        )
    except Exception as e:
        logger.debug(f"zep_write_non_blocking_failed: {e}")

    return refined.model_dump()


async def handle_visual_planning(run: PipelineRun, context: dict = None) -> str:
    """Generates visual annotations for a human video editor.

    Uses the visual_planner skill prompt to produce plain-text visual notes.
    Output is meant for direct display to a video editor — no JSON parsing needed.

    Args:
        run: Current pipeline run
        context: Additional context (supports 'card_id' for thought reporting)

    Returns:
        Plain text visual annotations (NOT JSON)
    """
    from packages.router.client import RouterClient
    from packages.content_factory.models import AdaptedScript
    from packages.core.thoughts import report_thought

    script_data = run.get_output(Stage.SCRIPT_WRITING)
    if not script_data or "error" in (script_data or {}):
        return "Visual planning skipped: no script available."

    # Build script text for visual annotation
    try:
        script = AdaptedScript(**script_data)
    except Exception as e:
        logger.warning(f"visual_planning_script_parse_failed: {e}")
        script_text = str(script_data)[:2000]
    else:
        # Format script entries for the visual planner
        lines = []
        for entry in script.entries:
            lines.append(f"> \"{entry.prose}\"\n")
        script_text = "\n".join(lines)

    # Load the skill prompt
    skill_path = Path(__file__).parent.parent.parent / "data" / "skills" / "visual_planner.md"
    if skill_path.exists():
        skill_prompt = skill_path.read_text()
    else:
        # Fallback inline prompt
        skill_prompt = """You are a documentary video director speaking to a human video editor.
Read the script and add visual suggestions in plain text.
Use labels: [B-ROLL], [MAP], [DATA], [ARCHIVAL], [GRAPHIC], [TRANSITION], [SOUND].
Keep notes short — one sentence each. NO JSON."""

    prompt = f"""{skill_prompt}

---

Here is the finished script. Add visual directions to each section:

{script_text}
"""

    try:
        async with RouterClient() as client:
            visual_annotations = await client.complete_text(
                prompt,
                system="You are a video director. Output ONLY visual notes in plain text. NO JSON.",
                model="ollama/llama3.2"  # Local Ollama for simple visual text categorization
            )

        # Report thought to Kanban if card_id provided
        card_id = (context or {}).get("card_id")
        if card_id:
            line_count = visual_annotations.count('\n')
            report_thought(
                card_id=card_id,
                agent_name="visual_annotator",
                thought_type="output",
                content=f"🎬 Visual annotations complete ({line_count} lines of direction for the editor).",
            )

        logger.info(f"visual_planning_complete: {len(visual_annotations)} chars")
        return visual_annotations.strip()

    except Exception as e:
        logger.error(f"visual_planning_failed: {e}")
        return f"Visual planning error: {str(e)}"


async def handle_seo(run: PipelineRun, context: dict = None) -> dict:
    """Generates 7 title options, description, tags, thumbnail concepts via LLM.

    Args:
        run: Current pipeline run
        context: Additional context

    Returns:
        SEO package data as dict
    """
    from packages.router.client import RouterClient

    script_data = run.get_output(Stage.SCRIPT_WRITING) or {}
    title = script_data.get("adapted_title", "Untitled")
    genre = script_data.get("genre", "documentary")
    entries = script_data.get("entries", [])
    hook_prose = entries[0].get("prose", "") if entries else ""

    prompt = f"""You are an expert YouTube SEO strategist for Pakistani documentary content.

Video title: "{title}"
Genre: {genre}
Hook: "{hook_prose[:200]}"

Generate a JSON object with:
- titles: list of 7 title variations (main + 6 alternatives, each under 70 chars,
          mix of curiosity-gap, how/why, number-based styles)
- description: 200-word compelling description with natural keyword placement
- tags: list of 20 relevant tags (mix English + Roman Urdu)
- thumbnail_concepts: list of 3 specific visual thumbnail ideas
- optimal_upload_time: best day+time for Pakistani audience

Return ONLY valid JSON."""

    try:
        async with RouterClient() as client:
            raw = await client.complete_text(
                prompt, system="Return only valid JSON. No markdown blocks."
            )
        obj_str = extract_json_object(raw)
        return json.loads(obj_str) if obj_str else {"titles": [title]}
    except Exception as e:
        logger.error(f"seo_handler_failed: {e}")
        return {"titles": [title], "description": "", "tags": [], "thumbnail_concepts": []}


async def handle_asset_creation(run: PipelineRun, context: dict = None) -> dict:
    """Registers render jobs with the VisualManifest.

    NOTE: After Option A refactoring, visual_planning outputs plain text for human
    editors. This handler now skips automated render job registration. The visual
    annotations are displayed in the Kanban drawer for manual review.

    Args:
        run: Current pipeline run
        context: Additional context

    Returns:
        Asset creation status as dict
    """
    settings = get_settings()

    # Feature flag: skip asset creation if disabled
    if not settings.ASSET_CREATION_ENABLED:
        logger.info("asset_creation_skipped_feature_disabled")
        return {"status": "skipped", "assets": [], "reason": "feature_disabled"}

    visual_data = run.get_output(Stage.VISUAL_PLANNING) or {}

    # After Option A refactoring: visual_data is plain text (str), not dict
    # Automated render job registration is no longer supported
    # Visual annotations are now for human editors only
    if isinstance(visual_data, str):
        logger.info("asset_creation_skipped_visual_is_plain_text")
        return {
            "status": "skipped",
            "reason": "visual_output_is_plain_text_for_human_editors",
            "visual_length": len(visual_data),
        }

    # Legacy dict format handling (for backwards compatibility if needed)
    if isinstance(visual_data, dict):
        try:
            from packages.visual.manifest import VisualManifest
            manifest = VisualManifest(run_id=run.run_id)

            section_briefs = visual_data.get("section_briefs", [])
            for brief in section_briefs:
                if brief.get("tool") in ("remotion", "animation"):
                    manifest.add_pending(
                        asset_id=f"{run.run_id}_{brief.get('section_index', 0)}",
                        description=str(brief.get("sonic_palette", "render job")),
                    )

            summary = manifest.summary()
            logger.info(f"asset_creation_registered: {summary}")
            return {"manifest_summary": summary, "status": "registered"}
        except Exception as e:
            logger.warning(f"visual_manifest_not_available: {e}")

    return {"status": "stub", "assets": []}


async def handle_publish(run: PipelineRun, context: dict = None) -> dict:
    """Publishes script to Notion and optionally prepares YouTube upload.

    Args:
        run: Current pipeline run
        context: Additional context

    Returns:
        Publish status as dict
    """
    settings = get_settings()

    # Feature flag: skip publishing if disabled
    if not settings.PUBLISH_ENABLED:
        logger.info("publish_skipped_feature_disabled")
        return {"status": "skipped", "reason": "feature_disabled"}

    script_data = run.get_output(Stage.SCRIPT_WRITING) or {}
    seo_data = run.get_output(Stage.SEO) or {}

    result = {
        "video_title": script_data.get("adapted_title", "Untitled"),
        "final_score": script_data.get("production_readiness_score", 0),
        "titles": seo_data.get("titles", []),
    }

    # Notion publish (if configured)
    if settings.NOTION_API_KEY:
        try:
            from packages.integrations.notion.client import NotionScriptClient
            notion = NotionScriptClient()
            page = await notion.create_script_page(
                title=result["video_title"],
                script_data=script_data,
                seo_data=seo_data,
            )
            result["notion_page_id"] = page.get("id") if page else None
            result["status"] = "published_to_notion"
        except Exception as e:
            logger.warning(f"notion_publish_failed_non_blocking: {e}")
            result["status"] = "notion_failed"
    else:
        result["status"] = "dry_run_no_notion_key"
        logger.info("publish_skipped: NOTION_API_KEY not configured")

    return result


# Registry mapping stage value -> handler function
STAGE_HANDLERS: dict[str, Callable] = {
    Stage.TREND_ANALYSIS.value: handle_trend_analysis,
    Stage.RESEARCH.value: handle_research,
    Stage.SCRIPT_WRITING.value: handle_script_writing,
    Stage.VISUAL_PLANNING.value: handle_visual_planning,
    Stage.SEO.value: handle_seo,
    Stage.ASSET_CREATION.value: handle_asset_creation,
    Stage.PUBLISH.value: handle_publish,
}

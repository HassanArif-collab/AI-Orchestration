"""Stage handlers for pipeline execution.

STUB implementations that return mock data.
Real agent implementations will replace these later.
"""

from typing import Any, Callable
import json
from datetime import datetime, timezone

from packages.pipeline.stages import Stage
from packages.pipeline.state import PipelineRun
from packages.content_factory.topic_finder.finder import TopicFinderAgent
from packages.content_factory.adaptation.runner import run_adaptation
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
        brief = finder.generate_candidate(seed, genre)
        if brief:
            candidates.append(brief.model_dump())
            
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
                "status": "reservoir"
            }
        ]
        
    return candidates


async def handle_research(run: PipelineRun, context: dict = None) -> dict:
    """Uses Adaptation Runner to analyze a source video.

    Args:
        run: Current pipeline run
        context: Additional context

    Returns:
        AdaptedScript object as dict
    """
    # 1. Get approved topic
    topic = run.get_output(Stage.HUMAN_TOPIC_APPROVAL)
    if not topic:
        logger.error("research_handler_missing_approved_topic")
        return {}

    # 2. Extract source URL/ID (for now use a default or from topic if it has a reference)
    url = topic.get("source_url") or topic.get("url")
    if not url and topic.get("structural_reference"):
        ref = topic["structural_reference"]
        url = f"https://youtube.com/watch?v={ref['video_id']}"
    
    if not url:
        # Fallback for dev: Johnny Harris video on the Suez Canal
        url = "https://www.youtube.com/watch?v=S2uS6MOfWCI"
        logger.warning(f"research_handler_no_url_found_using_fallback: {url}")

    # 3. Run the complete 4-stage adaptation
    logger.info(f"running_adaptation_pipeline for: {url}")
    try:
        script = await run_adaptation(url, cycle_id=run.run_id)
        if script:
            return script.model_dump()
    except Exception as e:
        logger.error(f"adaptation_pipeline_failed: {str(e)}")
        
    return {"error": "adaptation_failed", "url": url}


async def handle_script_writing(run: PipelineRun, context: dict = None) -> dict:
    """Refines the adapted script.

    Args:
        run: Current pipeline run
        context: Additional context

    Returns:
        Mock script data (placeholder for refined version)
    """
    # For now, research stage produces the AdaptedScript
    # This stage could be used for final human-like polish or localization tweaks
    script_data = run.get_output(Stage.RESEARCH)
    return script_data or {"status": "no_research_data"}


async def handle_visual_planning(run: PipelineRun, context: dict = None) -> dict:
    """STUB: Returns mock visual plan.

    Args:
        run: Current pipeline run
        context: Additional context

    Returns:
        Mock visual plan data
    """
    return {
        "decisions": [
            {
                "timestamp_start": 0,
                "timestamp_end": 15,
                "visual_type": "animation",
                "tool": "remotion",
                "description": "Animated map zoom into Pakistan",
            },
            {
                "timestamp_start": 15,
                "timestamp_end": 135,
                "visual_type": "talking_head",
                "tool": "camera",
                "description": "Medium shot, studio lighting",
            },
            {
                "timestamp_start": 135,
                "timestamp_end": 165,
                "visual_type": "data_viz",
                "tool": "remotion",
                "description": "Summary statistics animation",
            },
        ],
        "asset_list": ["map_animation.mp4", "stats_graphic.mp4"],
    }


async def handle_seo(run: PipelineRun, context: dict = None) -> dict:
    """STUB: Returns mock SEO package.

    Args:
        run: Current pipeline run
        context: Additional context

    Returns:
        Mock SEO data
    """
    return {
        "titles": ["Main Title", "Alt Title 1", "Alt Title 2"],
        "description": "In this video we explore...",
        "tags": ["pakistan", "geopolitics", "explained"],
        "thumbnail_concepts": ["Split comparison", "Map with arrow"],
    }


async def handle_asset_creation(run: PipelineRun, context: dict = None) -> dict:
    """STUB: Returns mock asset list.

    Args:
        run: Current pipeline run
        context: Additional context

    Returns:
        Mock asset creation data
    """
    return {"assets_created": ["intro.mp4", "map_zoom.mp4"], "status": "mock"}


async def handle_publish(run: PipelineRun, context: dict = None) -> dict:
    """STUB: Would upload to YouTube. Returns mock.

    Args:
        run: Current pipeline run
        context: Additional context

    Returns:
        Mock publish data
    """
    return {"youtube_video_id": "MOCK_ID", "status": "draft"}


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

"""
background_tasks.py — Background task implementations for topic_routes.

These functions connect the API endpoints to the pipeline infrastructure.
Each function is designed to be called via FastAPI BackgroundTasks.

The functions are intentionally defensive:
- They handle errors gracefully without crashing
- They update topic/script status as they progress
- They leverage existing pipeline infrastructure

Imports: asyncio, json, datetime
Imported by: apps/api/routers/topic_routes.py
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from packages.core.config import get_settings
from packages.core.logger import get_logger

logger = get_logger(__name__)

# Global scheduler instance (initialized by start_scheduler)
_scheduler = None


def _get_reservoir_paths() -> tuple[Path, Path]:
    """Get paths to reservoir files."""
    settings = get_settings()
    data_dir = Path(settings.DATA_DIR)
    topics_file = data_dir / "topic_reservoir" / "topics.json"
    scripts_file = data_dir / "topic_reservoir" / "scripts.json"
    return topics_file, scripts_file


def _load_json_file(file_path: Path, default=None):
    """Load JSON file with error handling."""
    if default is None:
        default = []
    if not file_path.exists():
        return default
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"json_load_failed: {file_path} - {e}")
        return default


def _save_json_file(file_path: Path, data) -> bool:
    """Save JSON file with error handling."""
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"json_save_failed: {file_path} - {e}")
        return False


def _update_topic_status(topic_id: str, status: str, extra: dict = None) -> bool:
    """Update a topic's status in the reservoir.
    
    Args:
        topic_id: The topic ID to update
        status: New status value
        extra: Additional fields to update
        
    Returns:
        True if update succeeded, False otherwise
    """
    topics_file, _ = _get_reservoir_paths()
    topics = _load_json_file(topics_file)
    
    for i, topic in enumerate(topics):
        if topic.get("id") == topic_id:
            topic["status"] = status
            topic["updated_at"] = datetime.now(timezone.utc).isoformat()
            if extra:
                topic.update(extra)
            topics[i] = topic
            return _save_json_file(topics_file, topics)
    
    logger.warning(f"topic_not_found_for_update: {topic_id}")
    return False


def _update_script_status(script_id: str, status: str, extra: dict = None) -> bool:
    """Update a script's status in the reservoir.
    
    Args:
        script_id: The script ID to update
        status: New status value
        extra: Additional fields to update
        
    Returns:
        True if update succeeded, False otherwise
    """
    _, scripts_file = _get_reservoir_paths()
    scripts = _load_json_file(scripts_file)
    
    for i, script in enumerate(scripts):
        if script.get("id") == script_id:
            script["status"] = status
            script["updated_at"] = datetime.now(timezone.utc).isoformat()
            if extra:
                script.update(extra)
            scripts[i] = script
            return _save_json_file(scripts_file, scripts)
    
    logger.warning(f"script_not_found_for_update: {script_id}")
    return False


async def start_research_for_topic(topic_id: str) -> None:
    """Start the research pipeline for an approved topic.

    This is called as a background task after topic approval.
    It creates a new pipeline run and begins the research stage.

    Args:
        topic_id: The ID of the approved topic
    """
    logger.info(f"research_task_started: topic_id={topic_id}")
    
    try:
        _update_topic_status(
            topic_id, 
            "researching",
            {"research_started_at": datetime.now(timezone.utc).isoformat()}
        )
        
        topics_file, _ = _get_reservoir_paths()
        topics = _load_json_file(topics_file)
        topic = next((t for t in topics if t.get("id") == topic_id), None)
        
        if not topic:
            logger.error(f"topic_not_found: {topic_id}")
            return
        
        await _run_research_pipeline(topic_id, topic)
            
    except Exception as e:
        logger.error(f"research_task_error: topic_id={topic_id} error={e}")
        _update_topic_status(topic_id, "research_failed", {"error": str(e)})


async def _run_research_pipeline(topic_id: str, topic: dict) -> None:
    """Async function to run the research pipeline."""
    try:
        from packages.pipeline.runner import PipelineRunner
        from packages.pipeline.stages import Stage
        
        runner = PipelineRunner()
        run = await runner.create_run()
        
        logger.info(f"pipeline_run_created: run_id={run.run_id} topic_id={topic_id}")
        
        if not hasattr(run, 'context'):
            run.context = {}
        run.context["topic"] = topic
        
        try:
            await runner.execute_stage(run, Stage.RESEARCH, {"topic": topic})
            logger.info(f"research_stage_complete: topic_id={topic_id} run_id={run.run_id}")
            _update_topic_status(
                topic_id, "researched",
                {"research_completed_at": datetime.now(timezone.utc).isoformat(), "run_id": run.run_id}
            )
        except Exception as e:
            logger.error(f"research_stage_failed: topic_id={topic_id} error={e}")
            _update_topic_status(topic_id, "research_failed", {"error": str(e)})
            
    except ImportError as e:
        logger.warning(f"pipeline_import_failed: {e} - marking as queued")
        _update_topic_status(topic_id, "queued_for_research")
    except Exception as e:
        logger.error(f"research_pipeline_error: topic_id={topic_id} error={e}")
        _update_topic_status(topic_id, "research_failed", {"error": str(e)})


async def evaluate_script(script_id: str) -> None:
    """Evaluate a user-provided script through the quality loop.

    Args:
        script_id: The ID of the script to evaluate
    """
    logger.info(f"script_evaluation_started: script_id={script_id}")
    
    try:
        _update_script_status(
            script_id, "evaluating",
            {"evaluation_started_at": datetime.now(timezone.utc).isoformat()}
        )
        
        _, scripts_file = _get_reservoir_paths()
        scripts = _load_json_file(scripts_file)
        script = next((s for s in scripts if s.get("id") == script_id), None)
        
        if not script:
            logger.error(f"script_not_found: {script_id}")
            return
        
        await _run_evaluation(script_id, script)
            
    except Exception as e:
        logger.error(f"evaluation_task_error: script_id={script_id} error={e}")
        _update_script_status(script_id, "evaluation_failed", {"error": str(e)})


async def _run_evaluation(script_id: str, script: dict) -> None:
    """Async function to run script evaluation."""
    try:
        from packages.content_factory.evaluation.loop import ExperimentLoop
        from packages.content_factory.models import AdaptedScript
        
        adapted = AdaptedScript(
            video_id=script_id,
            title=script.get("title", "Untitled"),
            genre=script.get("genre_id", "current_situation"),
            sections=[{"type": "content", "text": script.get("content", "")}],
            narration_script=script.get("content", ""),
        )
        
        settings = get_settings()
        
        loop_inst = ExperimentLoop()
        result = await loop_inst.run_iterations(
            adapted,
            iterations=3,
            target_threshold=settings.SCRIPT_QUALITY_THRESHOLD,
        )
        
        score = result.production_readiness_score
        
        if score >= settings.SCRIPT_QUALITY_THRESHOLD:
            final_status = "production_ready"
        elif score >= settings.SCRIPT_QUALITY_FLOOR:
            final_status = "acceptable"
        else:
            final_status = "below_threshold"
        
        _update_script_status(
            script_id, final_status,
            {
                "score": score,
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "quality_threshold": settings.SCRIPT_QUALITY_THRESHOLD,
                "quality_floor": settings.SCRIPT_QUALITY_FLOOR,
            }
        )
        
        logger.info(f"script_evaluation_complete: script_id={script_id} score={score} status={final_status}")
        
    except ImportError as e:
        logger.warning(f"evaluation_import_failed: {e} - marking as queued")
        _update_script_status(script_id, "queued_for_evaluation")
    except Exception as e:
        logger.error(f"evaluation_run_failed: script_id={script_id} error={e}")
        _update_script_status(script_id, "evaluation_failed", {"error": str(e)})


async def run_daily_scan(genres: Optional[list[str]] = None) -> Optional[int]:
    """Run the daily topic discovery scan."""
    logger.info(f"daily_scan_task_started: genres={genres}")
    
    try:
        try:
            from scripts.daily_topic_scan import run_daily_scan as async_scan
            count = await async_scan(genres)
            logger.info(f"daily_scan_complete: topics_found={count}")
            return count
        except ImportError as e:
            logger.warning(f"scan_import_failed: {e}")
            return None
        except Exception as e:
            logger.error(f"daily_scan_error: {e}")
            return None
    except Exception as e:
        logger.error(f"daily_scan_task_error: {e}")
        return None


def start_scheduler() -> bool:
    """Start the orchestration scheduler.
    
    This initializes the Scheduler with a MasterOrchestrator and
    registers all cron jobs. The scheduler will periodically call
    MasterOrchestrator.check_and_start_new_cycle() to process topics.
    
    This function is defensive:
    - Handles all errors gracefully
    - Returns True if scheduler started, False otherwise
    - Logs all actions for debugging
    
    Returns:
        True if scheduler started successfully, False otherwise
    """
    global _scheduler
    
    if _scheduler is not None:
        logger.info("scheduler_already_running")
        return True
    
    logger.info("scheduler_startup_initiated")
    
    try:
        from packages.content_factory.orchestration.scheduler import Scheduler
        from packages.content_factory.orchestration.master import MasterOrchestrator
        
        # Create the master orchestrator
        orchestrator = MasterOrchestrator()
        
        # Create the scheduler with the orchestrator
        _scheduler = Scheduler(master=orchestrator)
        
        # Register all cron jobs
        _scheduler.boot_schedule()
        
        logger.info("scheduler_started_successfully")
        return True
        
    except ImportError as e:
        logger.warning(f"scheduler_import_failed: {e}")
        return False
        
    except Exception as e:
        logger.error(f"scheduler_startup_failed: {e}")
        _scheduler = None
        return False


def get_scheduler():
    """Get the current scheduler instance.
    
    Returns:
        The Scheduler instance, or None if not started.
    """
    return _scheduler


async def cleanup_expired_cards():
    """
    Background task: Delete expired topic cards from Column 2.
    
    Runs every 10 minutes. Deletes kanban_cards in Column 2
    whose expires_at has passed and haven't been saved (expires_at is not null).
    
    This ensures the 3-hour timer is enforced server-side even if
    no one has the dashboard open.
    """
    while True:
        try:
            from packages.core.supabase_client import get_supabase
            sb = get_supabase()
            
            now = datetime.now(timezone.utc).isoformat()
            
            # Delete expired cards in Column 2 that haven't been saved
            result = sb.table("kanban_cards") \
                .delete() \
                .eq("column_index", 2) \
                .not_.is_("expires_at", "null") \
                .lt("expires_at", now) \
                .execute()
            
            if result.data:
                logger.info(f"cleanup_expired_cards: deleted {len(result.data)} expired cards")
                
        except Exception as e:
            logger.warning(f"card_cleanup_failed (non-fatal): {e}")
        
        # Sleep for 10 minutes
        await asyncio.sleep(600)


# Module-level reference for graceful shutdown
_cleanup_task: asyncio.Task | None = None


def start_cleanup_task():
    """Start the expired card cleanup background task."""
    global _cleanup_task
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.error(
            "start_cleanup_task: No running event loop — cleanup not started. "
            "Must be called within an async context (e.g., FastAPI lifespan)."
        )
        raise
    _cleanup_task = loop.create_task(cleanup_expired_cards())
    logger.info("cleanup_task_scheduled: expired card cleanup started")


async def stop_cleanup_task():
    """Cancel the cleanup task for graceful shutdown.
    
    Should be called during application shutdown (e.g., FastAPI lifespan).
    """
    global _cleanup_task
    if _cleanup_task is not None and not _cleanup_task.done():
        _cleanup_task.cancel()
        try:
            await _cleanup_task
        except asyncio.CancelledError:
            pass
        logger.info("expired_card_cleanup_task_stopped")
    _cleanup_task = None

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


def start_research_for_topic(topic_id: str) -> None:
    """Start the research pipeline for an approved topic.

    This is called as a background task after topic approval.
    It creates a new pipeline run and begins the research stage.

    This function is defensive:
    - Updates topic status to track progress
    - Handles all errors gracefully
    - Logs all actions for debugging

    Args:
        topic_id: The ID of the approved topic
    """
    logger.info(f"research_task_started: topic_id={topic_id}")
    
    try:
        # Update status to researching
        _update_topic_status(
            topic_id, 
            "researching",
            {"research_started_at": datetime.now(timezone.utc).isoformat()}
        )
        
        # Load topic details
        topics_file, _ = _get_reservoir_paths()
        topics = _load_json_file(topics_file)
        topic = next((t for t in topics if t.get("id") == topic_id), None)
        
        if not topic:
            logger.error(f"topic_not_found: {topic_id}")
            return
        
        # Set up async handling for the pipeline
        try:
            import nest_asyncio
            nest_asyncio.apply()
        except ImportError:
            logger.debug("nest_asyncio not available, using standard event loop")
        
        async def _run_research_pipeline():
            """Async function to run the research pipeline."""
            try:
                from packages.pipeline.runner import PipelineRunner
                from packages.pipeline.stages import Stage
                
                # Create a new pipeline run
                runner = PipelineRunner()
                run = await runner.create_run()
                
                logger.info(f"pipeline_run_created: run_id={run.run_id} topic_id={topic_id}")
                
                # Store topic context
                if not hasattr(run, 'context'):
                    run.context = {}
                run.context["topic"] = topic
                
                # Execute research stage
                try:
                    await runner.execute_stage(run, Stage.RESEARCH, {"topic": topic})
                    logger.info(f"research_stage_complete: topic_id={topic_id} run_id={run.run_id}")
                    
                    # Update topic status
                    _update_topic_status(
                        topic_id,
                        "researched",
                        {
                            "research_completed_at": datetime.now(timezone.utc).isoformat(),
                            "run_id": run.run_id,
                        }
                    )
                    
                except Exception as e:
                    logger.error(f"research_stage_failed: topic_id={topic_id} error={e}")
                    _update_topic_status(
                        topic_id,
                        "research_failed",
                        {"error": str(e)}
                    )
                    
            except ImportError as e:
                logger.warning(f"pipeline_import_failed: {e} - marking as queued")
                # Pipeline not available, mark as queued for later
                _update_topic_status(topic_id, "queued_for_research")
                
            except Exception as e:
                logger.error(f"research_pipeline_error: topic_id={topic_id} error={e}")
                _update_topic_status(
                    topic_id,
                    "research_failed",
                    {"error": str(e)}
                )
        
        # Run async in sync context
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Create new loop if current one is running
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run, 
                        _run_research_pipeline()
                    )
                    future.result(timeout=300)  # 5 minute timeout
            else:
                loop.run_until_complete(_run_research_pipeline())
        except RuntimeError:
            # No event loop exists
            asyncio.run(_run_research_pipeline())
            
    except Exception as e:
        logger.error(f"research_task_error: topic_id={topic_id} error={e}")
        _update_topic_status(
            topic_id,
            "research_failed",
            {"error": str(e)}
        )


def evaluate_script(script_id: str) -> None:
    """Evaluate a user-provided script through the quality loop.

    This is called as a background task after script submission.
    It runs the script through the ExperimentLoop for quality assessment.

    This function is defensive:
    - Updates script status to track progress
    - Handles all errors gracefully
    - Uses quality thresholds from config

    Args:
        script_id: The ID of the script to evaluate
    """
    logger.info(f"script_evaluation_started: script_id={script_id}")
    
    try:
        # Update status to evaluating
        _update_script_status(
            script_id,
            "evaluating",
            {"evaluation_started_at": datetime.now(timezone.utc).isoformat()}
        )
        
        # Load script details
        _, scripts_file = _get_reservoir_paths()
        scripts = _load_json_file(scripts_file)
        script = next((s for s in scripts if s.get("id") == script_id), None)
        
        if not script:
            logger.error(f"script_not_found: {script_id}")
            return
        
        # Set up async handling
        try:
            import nest_asyncio
            nest_asyncio.apply()
        except ImportError:
            logger.debug("nest_asyncio not available")
        
        async def _run_evaluation():
            """Async function to run script evaluation."""
            try:
                from packages.content_factory.evaluation.loop import ExperimentLoop
                from packages.content_factory.models import AdaptedScript
                
                # Create AdaptedScript from user content
                adapted = AdaptedScript(
                    video_id=script_id,
                    title=script.get("title", "Untitled"),
                    genre=script.get("genre_id", "current_situation"),
                    sections=[{"type": "content", "text": script.get("content", "")}],
                    narration_script=script.get("content", ""),
                )
                
                # Get settings for thresholds
                settings = get_settings()
                
                # Run evaluation loop
                loop = ExperimentLoop()
                result = await loop.run_iterations(
                    adapted,
                    iterations=3,
                    target_threshold=settings.SCRIPT_QUALITY_THRESHOLD,
                )
                
                score = result.production_readiness_score
                
                # Determine final status
                if score >= settings.SCRIPT_QUALITY_THRESHOLD:
                    final_status = "production_ready"
                elif score >= settings.SCRIPT_QUALITY_FLOOR:
                    final_status = "acceptable"
                else:
                    final_status = "below_threshold"
                
                # Update script with results
                _update_script_status(
                    script_id,
                    final_status,
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
                _update_script_status(
                    script_id,
                    "evaluation_failed",
                    {"error": str(e)}
                )
        
        # Run async in sync context
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, _run_evaluation())
                    future.result(timeout=300)
            else:
                loop.run_until_complete(_run_evaluation())
        except RuntimeError:
            asyncio.run(_run_evaluation())
            
    except Exception as e:
        logger.error(f"evaluation_task_error: script_id={script_id} error={e}")
        _update_script_status(
            script_id,
            "evaluation_failed",
            {"error": str(e)}
        )


def run_daily_scan(genres: Optional[list[str]] = None) -> Optional[int]:
    """Run the daily topic discovery scan.

    This is a sync wrapper around the async run_daily_scan from scripts.
    It scans trending sources for new topic candidates.

    This function is defensive:
    - Handles all errors gracefully
    - Returns count of topics found (or None on error)
    - Logs all actions for debugging

    Args:
        genres: Optional list of genre IDs to scan
        
    Returns:
        Number of topics found, or None on error
    """
    logger.info(f"daily_scan_task_started: genres={genres}")
    
    try:
        # Set up async handling
        try:
            import nest_asyncio
            nest_asyncio.apply()
        except ImportError:
            logger.debug("nest_asyncio not available")
        
        async def _run_scan():
            """Async function to run the daily scan."""
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
        
        # Run async in sync context
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, _run_scan())
                    return future.result(timeout=600)  # 10 minute timeout for scan
            else:
                return loop.run_until_complete(_run_scan())
        except RuntimeError:
            return asyncio.run(_run_scan())
            
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

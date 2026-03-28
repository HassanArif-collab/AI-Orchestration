"""
Kanban task management routes — Refactored to use PipelineRunner.

These endpoints handle the Kanban board operations for the YouTube Pipeline
dashboard. The Kanban board is a view-only (mostly) representation of the
Pipeline runs stored in pipeline.db.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from apps.api.dependencies import get_pipeline_runner, get_run_store
from apps.api.events import emit_task_created

router = APIRouter()

# Map pipeline stage names to Kanban column numbers (1-6)
PIPELINE_TO_KANBAN_STAGE = {
    "trend_analysis": 1,        # Topic Finding
    "human_topic_approval": 2,  # Suggested Topics (human gate)
    "research": 3,              # Researching
    "script_writing": 4,        # Script
    "visual_planning": 5,       # Visual
    "seo": 4,                   # Script (parallel stage)
    "human_review": 5,          # Visual (human gate)
    "asset_creation": 6,        # Notion
    "publish": 6,               # Notion (final)
}

def get_kanban_stage(pipeline_stage: str) -> int:
    """Convert pipeline stage name to Kanban column number."""
    return PIPELINE_TO_KANBAN_STAGE.get(pipeline_stage, 1)

def _run_to_kanban_dict(run) -> dict:
    """Convert a PipelineRun to a Kanban-friendly dictionary."""
    d = run.to_dict() if hasattr(run, "to_dict") else vars(run)
    stage_name = d.get("current_stage", "trend_analysis")
    
    # Extract title
    video_title = "Untitled"
    outputs = d.get("stage_outputs", {})
    approval = outputs.get("human_topic_approval")
    if isinstance(approval, dict):
        video_title = approval.get("topic_statement") or approval.get("title") or "Untitled"
    else:
        trend = outputs.get("trend_analysis")
        if isinstance(trend, list) and trend:
            video_title = trend[0].get("topic_statement") or trend[0].get("title") or "Untitled"
    
    # Status mapping to Kanban visual states
    status = d.get("status", "idle")
    if status == "running":
        kanban_status = "thinking"
    elif status == "waiting_human":
        kanban_status = "waiting"
    elif status == "complete":
        kanban_status = "complete"
    elif status == "error":
        kanban_status = "error"
    else:
        kanban_status = "idle"

    # Color mapping (simple palette based on stage)
    colors = ["#1D9E75", "#378ADD", "#BA7517", "#D4A017", "#D1242F", "#0969DA"]
    stage_num = get_kanban_stage(stage_name)
    color = colors[stage_num - 1] if 1 <= stage_num <= 6 else colors[0]

    # Thoughts mapping
    thoughts = "[]"
    
    return {
        "id": d.get("run_id"),
        "title": video_title,
        "stage": stage_num,
        "status": kanban_status,
        "color": color,
        "updated_at": d.get("updated_at"),
        "created_at": d.get("created_at"),
        "notion_url": outputs.get("publish", {}).get("notion_url") if isinstance(outputs.get("publish"), dict) else None,
        "research": str(outputs.get("research", ""))[:1000],
        "script": str(outputs.get("script_writing", ""))[:1000],
        "visual_cues": str(outputs.get("visual_planning", ""))[:1000],
        "thoughts": thoughts
    }

# ─── Pydantic Models ────────────────────────────────────────────────────────────

class KanbanTaskUpdate(BaseModel):
    """Request model for updating a Kanban task."""
    stage: Optional[int] = Field(default=None, ge=1, le=6)

class TopicFinderRequest(BaseModel):
    """Request model for triggering Topic Finder."""
    seed_query: str = Field(..., min_length=3, max_length=500)
    genre_id: str = Field(default="default", max_length=50)

# ─── API Endpoints ──────────────────────────────────────────────────────────────

@router.get("/tasks")
async def list_tasks(limit: int = 100) -> dict:
    """List all pipeline runs as Kanban tasks."""
    store = get_run_store()
    if not store:
        return {"tasks": []}
    
    runs = store.list_runs(limit=limit)
    tasks = []
    for summary in runs:
        try:
            run = store.load(summary["run_id"])
            if run:
                tasks.append(_run_to_kanban_dict(run))
        except Exception as e:
            print(f"Error loading task {summary.get('run_id')}: {e}")
            continue
    
    return {"tasks": tasks}

@router.get("/tasks/{task_id}")
async def get_task(task_id: str) -> dict:
    """Get a single PipelineRun as a Kanban task."""
    store = get_run_store()
    if not store:
        raise HTTPException(503, "Store not available")
    
    run = store.load(task_id)
    if not run:
        raise HTTPException(404, f"Task {task_id} not found")
    
    return _run_to_kanban_dict(run)

@router.patch("/tasks/{task_id}")
async def update_task(task_id: str, data: KanbanTaskUpdate, bg: BackgroundTasks) -> dict:
    """Update a Kanban task by potentially triggering a pipeline action."""
    runner = get_pipeline_runner()
    store = get_run_store()
    if not runner or not store:
        raise HTTPException(503, "Pipeline runner not available")
    
    run = store.load(task_id)
    if not run:
        raise HTTPException(404, f"Task {task_id} not found")

    if data.stage is not None:
        current_kanban_stage = get_kanban_stage(run.current_stage)
        if data.stage > current_kanban_stage:
            if run.status in ("error", "waiting_human"):
                from apps.api.routers.pipeline_routes import _run_pipeline_bg
                bg.add_task(_run_pipeline_bg, task_id)
                return {"message": "Resuming pipeline run...", "id": task_id}

    return _run_to_kanban_dict(run)

@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str) -> dict:
    """Delete the underlying pipeline run."""
    store = get_run_store()
    if not store:
        raise HTTPException(503, "Store not available")
    
    store.delete(task_id)
    return {"success": True, "deleted_id": task_id}

@router.post("/topic-finder")
async def trigger_topic_finder(data: TopicFinderRequest, bg: BackgroundTasks) -> dict:
    """Start a new PipelineRun."""
    runner = get_pipeline_runner()
    if not runner:
        raise HTTPException(503, "Pipeline runner not available")
    
    run = await runner.create_run()
    from apps.api.routers.pipeline_routes import _run_pipeline_bg
    bg.add_task(_run_pipeline_bg, run.run_id)
    
    # Bug B Fix: Emit task_created immediately for Kanban board
    task_data = _run_to_kanban_dict(run)
    bg.add_task(emit_task_created, task_data)
    
    return {
        "id": run.run_id,
        "status": "thinking",
        "message": f"Pipeline started for: {data.seed_query}"
    }

@router.get("/stats")
async def get_stats() -> dict:
    """Get statistics from the RunStore."""
    store = get_run_store()
    if not store:
        return {"total_tasks": 0, "by_stage": {}, "by_status": {}}
    
    summaries = store.list_runs(limit=1000)
    total = len(summaries)
    by_stage = {}
    by_status = {}
    
    for s in summaries:
        stage_num = get_kanban_stage(s.get("current_stage", "trend_analysis"))
        by_stage[stage_num] = by_stage.get(stage_num, 0) + 1
        status = s.get("status", "idle")
        by_status[status] = by_status.get(status, 0) + 1
        
    return {
        "total_tasks": total,
        "by_stage": by_stage,
        "by_status": by_status
    }

def init_kanban_db() -> None:
    """No-op for backward compatibility."""
    pass

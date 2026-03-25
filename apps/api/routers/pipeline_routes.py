"""
pipeline_routes.py — Pipeline management API.

Endpoints for creating runs, approving human gates, viewing stage outputs,
and requesting feedback loops. The pipeline runs in background tasks with
SSE events emitted as stages complete.

All endpoints handle missing PipelineRunner gracefully — returns mock
data so the UI always renders something useful.
"""

from __future__ import annotations
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from apps.api.dependencies import get_pipeline_runner, get_run_store
from apps.api.events import (
    emit_pipeline_update, emit_stage_complete,
    emit_human_gate, emit_pipeline_complete,
)

router = APIRouter()

# ─── Request models ───────────────────────────────────────────────────────────

class StartPipelineRequest(BaseModel):
    topic: str = ""

class ApproveGateRequest(BaseModel):
    selection: dict | None = None
    feedback: str = ""

class FeedbackRequest(BaseModel):
    from_stage: str
    to_stage: str
    feedback: str

# ─── Stage definitions (hardcoded for when pipeline package unavailable) ──────

STAGE_DEFINITIONS = {
    "stages": [
        {"name": "trend_analysis",       "label": "Trend Analysis",  "is_human_gate": False, "dependencies": [],                         "feedback_targets": []},
        {"name": "human_topic_approval", "label": "Pick Topic",      "is_human_gate": True,  "dependencies": ["trend_analysis"],         "feedback_targets": []},
        {"name": "research",             "label": "Research",        "is_human_gate": False, "dependencies": ["human_topic_approval"],   "feedback_targets": []},
        {"name": "script_writing",       "label": "Script",          "is_human_gate": False, "dependencies": ["research"],              "feedback_targets": ["research"]},
        {"name": "visual_planning",      "label": "Visual Plan",     "is_human_gate": False, "dependencies": ["script_writing"],        "feedback_targets": ["script_writing"]},
        {"name": "seo",                  "label": "SEO",             "is_human_gate": False, "dependencies": ["script_writing"],        "feedback_targets": []},
        {"name": "human_review",         "label": "Review",          "is_human_gate": True,  "dependencies": ["visual_planning", "seo"], "feedback_targets": []},
        {"name": "asset_creation",       "label": "Assets",          "is_human_gate": False, "dependencies": ["human_review"],          "feedback_targets": []},
        {"name": "publish",              "label": "Publish",         "is_human_gate": False, "dependencies": ["asset_creation"],        "feedback_targets": []},
    ],
    "execution_order": [
        "trend_analysis", "human_topic_approval", "research", "script_writing",
        "visual_planning", "seo", "human_review", "asset_creation", "publish",
    ],
    "parallel_stages": [["seo", "visual_planning"]],
}


def _run_to_dict(run) -> dict:
    """Convert PipelineRun to API response dict."""
    d = run.to_dict() if hasattr(run, "to_dict") else vars(run)
    # Build stages dict from stage_status + stage_outputs
    stages = {}
    for stage_name in STAGE_DEFINITIONS["execution_order"]:
        stages[stage_name] = {
            "status": d.get("stage_status", {}).get(stage_name, "pending"),
            "output": d.get("stage_outputs", {}).get(stage_name),
        }
    return {
        "run_id": d.get("run_id", ""),
        "current_stage": d.get("current_stage", ""),
        "status": d.get("status", ""),
        "video_title": _extract_title(d),
        "created_at": str(d.get("created_at", "")),
        "updated_at": str(d.get("updated_at", "")),
        "stages": stages,
        "error_message": d.get("error_message", ""),
    }


def _extract_title(run_dict: dict) -> str:
    """Extract video title from stage outputs."""
    outputs = run_dict.get("stage_outputs", {})
    approval = outputs.get("human_topic_approval")
    if isinstance(approval, dict):
        return approval.get("title", "Untitled")
    trend = outputs.get("trend_analysis")
    if isinstance(trend, list) and trend:
        return trend[0].get("title", "Untitled")
    return "New Pipeline Run"


# ─── Background pipeline runner ───────────────────────────────────────────────

async def _run_pipeline_bg(run_id: str) -> None:
    """Background task: run pipeline until gate or completion, emitting SSE."""
    runner = get_pipeline_runner()
    store = get_run_store()
    if not runner or not store:
        return

    run = store.load(run_id)
    if not run:
        return

    try:
        from packages.pipeline.stages import Stage, is_human_gate

        while True:
            runnable = run.get_runnable_stages()
            if not runnable:
                # Check for human gates
                for stage in Stage:
                    if (run.stage_status.get(stage.value) == "pending"
                            and is_human_gate(stage)
                            and run.can_start(stage)):
                        await emit_pipeline_update(run_id, stage.value, "waiting_human")
                        await runner.execute_stage(run, stage)
                        await emit_human_gate(run_id, stage.value)
                        return
                # Complete
                run.status = "complete"
                store.save(run)
                await emit_pipeline_complete(run_id)
                return

            if len(runnable) > 1:
                await emit_pipeline_update(run_id, str([s.value for s in runnable]), "running")
                await asyncio.gather(*[runner.execute_stage(run, s) for s in runnable])
                for s in runnable:
                    await emit_stage_complete(run_id, s.value)
            else:
                stage = runnable[0]
                await emit_pipeline_update(run_id, stage.value, "running")
                await runner.execute_stage(run, stage)
                await emit_stage_complete(run_id, stage.value)

    except Exception as e:
        run.status = "error"
        run.error_message = str(e)
        store.save(run)
        await emit_pipeline_update(run_id, run.current_stage or "", "error")


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/stages")
async def get_stage_definitions():
    """Return the full pipeline stage graph definition."""
    return STAGE_DEFINITIONS


@router.get("/runs")
async def list_runs(limit: int = 20):
    """List all pipeline runs, newest first."""
    store = get_run_store()
    if not store:
        return [{"run_id": "demo-001", "current_stage": "human_topic_approval",
                 "status": "waiting_human", "video_title": "Demo Run (pipeline package loading)",
                 "updated_at": datetime.now(timezone.utc).isoformat(), "stages": {}}]
    try:
        import sqlite3 as _sql
        from pathlib import Path as _Path
        db = getattr(store, "db_path", "packages/data/pipeline.db")
        if not _Path(str(db)).exists():
            return []
        conn = _sql.connect(str(db))
        rows = conn.execute(
            "SELECT run_id FROM pipeline_runs ORDER BY updated_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        conn.close()
        result = []
        for (run_id,) in rows:
            try:
                run = store.load(run_id)
                if run:
                    result.append(_run_to_dict(run))
            except Exception:
                pass
        return result
    except Exception:
        return []


@router.post("/runs")
async def start_run(req: StartPipelineRequest, bg: BackgroundTasks):
    """Start a new pipeline run. Returns run_id immediately."""
    runner = get_pipeline_runner()
    store = get_run_store()

    if not runner or not store:
        mock_id = f"mock-{uuid.uuid4().hex[:8]}"
        return {"run_id": mock_id, "status": "started (mock — pipeline package loading)"}

    run = await runner.create_run()
    bg.add_task(_run_pipeline_bg, run.run_id)
    return {"run_id": run.run_id, "status": "started"}


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    """Get full details of a pipeline run including all stage outputs."""
    store = get_run_store()
    if not store:
        raise HTTPException(503, "Pipeline package not available")
    run = store.load(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")
    return _run_to_dict(run)


@router.delete("/runs/{run_id}")
async def delete_run(run_id: str):
    """Delete a pipeline run."""
    store = get_run_store()
    if not store:
        raise HTTPException(503, "Pipeline package not available")
    store.delete(run_id)
    return {"deleted": run_id}


@router.post("/runs/{run_id}/approve")
async def approve_gate(run_id: str, req: ApproveGateRequest, bg: BackgroundTasks):
    """Approve the current human gate and continue the pipeline."""
    runner = get_pipeline_runner()
    store = get_run_store()
    if not runner or not store:
        raise HTTPException(503, "Pipeline package not available")

    run = store.load(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")

    try:
        from packages.pipeline.stages import Stage, is_human_gate
        current = Stage(run.current_stage)
        if not is_human_gate(current):
            raise HTTPException(400, f"{run.current_stage} is not a human gate")
        await runner.approve_gate(run, current, True, req.selection)
    except (ImportError, ValueError):
        # Fallback if pipeline package not fully available
        run.stage_status[run.current_stage] = "complete"
        run.stage_outputs[run.current_stage] = req.selection or True
        run.status = "running"
        store.save(run)

    bg.add_task(_run_pipeline_bg, run_id)
    return _run_to_dict(run)


@router.post("/runs/{run_id}/reject")
async def reject_gate(run_id: str, req: ApproveGateRequest):
    """Reject at a human gate with feedback."""
    store = get_run_store()
    if not store:
        raise HTTPException(503, "Pipeline package not available")
    run = store.load(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")
    run.stage_status[run.current_stage] = "pending"
    run.status = "running"
    store.save(run)
    return _run_to_dict(run)


@router.post("/runs/{run_id}/feedback")
async def request_feedback(run_id: str, req: FeedbackRequest, bg: BackgroundTasks):
    """Request a feedback loop between two stages."""
    runner = get_pipeline_runner()
    store = get_run_store()
    if not runner or not store:
        raise HTTPException(503, "Pipeline package not available")
    run = store.load(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")
    try:
        from packages.pipeline.stages import Stage
        await runner.request_feedback(run, Stage(req.from_stage),
                                       Stage(req.to_stage), req.feedback)
    except (ImportError, ValueError) as e:
        raise HTTPException(400, str(e))
    bg.add_task(_run_pipeline_bg, run_id)
    return _run_to_dict(run)


@router.get("/runs/{run_id}/output/{stage}")
async def get_stage_output(run_id: str, stage: str):
    """Get the raw output of a specific pipeline stage."""
    store = get_run_store()
    if not store:
        raise HTTPException(503, "Pipeline package not available")
    run = store.load(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")
    output = run.stage_outputs.get(stage)
    if output is None:
        raise HTTPException(404, f"No output for stage {stage}")
    return {"stage": stage, "output": output}


# ─── Resume/Recovery endpoints ─────────────────────────────────────────────────

@router.get("/runs/resumable")
async def list_resumable_runs():
    """List all pipeline runs that can be resumed.

    Returns runs in 'error' or 'waiting_human' states that can be recovered.
    Useful for dashboards to show failed runs that need attention.
    """
    runner = get_pipeline_runner()
    if not runner:
        raise HTTPException(503, "Pipeline package not available")

    try:
        resumable = runner.list_resumable_runs()
        return {"runs": resumable, "count": len(resumable)}
    except Exception as e:
        raise HTTPException(500, f"Failed to list resumable runs: {e}")


@router.post("/runs/{run_id}/resume")
async def resume_pipeline_run(run_id: str, bg: BackgroundTasks):
    """Resume a crashed or paused pipeline run.

    Recovers a pipeline run from:
    - 'error' state: Resets failed stage and continues execution
    - 'waiting_human' state: Returns the gate stage for approval

    Returns the current stage after resume attempt.
    """
    runner = get_pipeline_runner()
    store = get_run_store()
    if not runner or not store:
        raise HTTPException(503, "Pipeline package not available")

    run = store.load(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")

    try:
        result = await runner.resume_run(run_id)
        if result is None:
            # Could be already completed or not resumable
            if run.status == "completed":
                raise HTTPException(400, f"Run {run_id} is already completed")
            raise HTTPException(400, f"Run {run_id} cannot be resumed")

        # If we recovered and got a stage, start background execution
        if run.status == "running":
            bg.add_task(_run_pipeline_bg, run_id)

        return {
            "status": "resumed",
            "run_id": run_id,
            "current_stage": result.value if result else None,
            "run_status": run.status,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to resume run: {e}")


@router.post("/runs/recover-all")
async def recover_all_failed_runs(bg: BackgroundTasks):
    """Attempt to recover all failed pipeline runs.

    Finds all runs in error state and attempts to resume them.
    Useful after system restart or transient failure resolution.
    """
    runner = get_pipeline_runner()
    if not runner:
        raise HTTPException(503, "Pipeline package not available")

    try:
        results = await runner.recover_all_failed()

        # Start background tasks for successfully recovered runs
        for result in results:
            if result.get("success"):
                bg.add_task(_run_pipeline_bg, result["run_id"])

        return {
            "status": "recovery_attempted",
            "recovered": sum(1 for r in results if r.get("success")),
            "failed": sum(1 for r in results if not r.get("success")),
            "details": results,
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to recover runs: {e}")

"""
pipeline_routes.py — Pipeline management API.

Endpoints for creating runs, approving human gates, viewing stage outputs,
and requesting feedback loops. The pipeline runs in background tasks with
SSE events emitted as stages complete.

All endpoints handle missing PipelineRunner gracefully — returns mock
data so the UI always renders something useful.

KANBAN INTEGRATION:
    Pipeline runs automatically create Kanban tasks and report progress.
    Stage mapping: pipeline stage -> kanban column (1-6)
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

# ─── Kanban Stage Mapping ──────────────────────────────────────────────────────

# Map pipeline stage names to Kanban column numbers (1-6)
# 1: Topic Finding | 2: Suggested Topics | 3: Researching
# 4: Script | 5: Visual | 6: Notion
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


async def create_kanban_task_for_run(run, run_id: str) -> str:
    """Create a Kanban task for a pipeline run.
    
    Returns the Kanban task ID.
    """
    title = _extract_title(run.to_dict() if hasattr(run, 'to_dict') else vars(run))
    task_id = str(uuid.uuid4())
    
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "http://localhost:3000/api/kanban/tasks",
                json={
                    "id": task_id,  # Use same ID for linking
                    "title": title,
                    "stage": 1,  # Start at Topic Finding
                }
            )
            if response.status_code == 200:
                return task_id
    except Exception as e:
        print(f"Warning: Failed to create Kanban task: {e}")
    
    return task_id


async def update_kanban_task_stage(task_id: str, stage: int, status: str = "idle"):
    """Update Kanban task stage and status."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.patch(
                f"http://localhost:3000/api/kanban/tasks/{task_id}",
                json={"stage": stage, "status": status}
            )
    except Exception as e:
        print(f"Warning: Failed to update Kanban task: {e}")


async def report_kanban_thought(task_id: str, thought: str):
    """Report an agent thought to Kanban."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                "http://localhost:3000/api/kanban/events",
                json={
                    "task_id": task_id,
                    "event_type": "thought",
                    "data": {"content": thought}
                }
            )
    except Exception as e:
        print(f"Warning: Failed to report Kanban thought: {e}")


async def report_kanban_artifact(task_id: str, key: str, value: str):
    """Report an artifact (research, script, etc.) to Kanban."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                "http://localhost:3000/api/kanban/events",
                json={
                    "task_id": task_id,
                    "event_type": "artifact",
                    "data": {"key": key, "value": value}
                }
            )
    except Exception as e:
        print(f"Warning: Failed to report Kanban artifact: {e}")

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
    
    # Normalize trend_analysis output (TopicBrief → frontend-friendly)
    if stages.get("trend_analysis", {}).get("output"):
        out = stages["trend_analysis"]["output"]
        if isinstance(out, list):
            stages["trend_analysis"]["output"] = [_normalize_topic_candidate(t) for t in out]
    
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
        return trend[0].get("title") or trend[0].get("topic_statement", "Untitled")
    return "New Pipeline Run"


def _normalize_topic_candidate(raw: dict) -> dict:
    """Normalize TopicBrief dict to frontend-friendly format.
    
    Maps backend field names to what the frontend expects:
    - topic_statement → title
    - big_question → subtitle
    - viability_score_breakdown → viability_total, gap_pass, anchor_pass, audience_pass
    """
    sb = raw.get("viability_score_breakdown", {})
    total = sb.get("total", 0)
    gap_pass = all(sb.get(k, False) for k in ["gap_1", "gap_2", "gap_3"])
    anchor_pass = sum(1 for k in ["anchor_1", "anchor_2", "anchor_3", "anchor_4"] if sb.get(k))
    audience_pass = sum(1 for k in ["audience_1", "audience_2", "audience_3", "audience_4"] if sb.get(k))
    
    return {
        **raw,
        "title": raw.get("topic_statement", "Untitled"),
        "subtitle": raw.get("big_question", ""),
        "gap_type": raw.get("gap_type", ""),
        "mainstream_assumption": raw.get("mainstream_assumption", ""),
        "anchors": raw.get("anchor_candidates", []),
        "timing": raw.get("timing_rationale", ""),
        "urgency": raw.get("urgency_flag", False),
        "viability_total": total,
        "viability_max": 17,
        "gap_pass": gap_pass,
        "anchor_pass": anchor_pass,
        "audience_pass": audience_pass,
    }


# ─── Background pipeline runner ───────────────────────────────────────────────

async def _run_pipeline_bg(run_id: str) -> None:
    """Background task: run pipeline until gate or completion, emitting SSE.
    
    Also creates and updates a corresponding Kanban task for visual tracking.
    """
    runner = get_pipeline_runner()
    store = get_run_store()
    if not runner or not store:
        return

    run = store.load(run_id)
    if not run:
        return

    # Create Kanban task for this pipeline run
    kanban_task_id = None
    try:
        kanban_task_id = await create_kanban_task_for_run(run, run_id)
    except Exception as e:
        print(f"Warning: Could not create Kanban task: {e}")

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
                        
                        # Update Kanban - at human gate
                        kanban_stage = get_kanban_stage(stage.value)
                        if kanban_task_id:
                            await update_kanban_task_stage(kanban_task_id, kanban_stage, "waiting")
                            await report_kanban_thought(kanban_task_id, f"Waiting for human approval at {stage.value}")
                        
                        await emit_pipeline_update(run_id, stage.value, "waiting_human")
                        await runner.execute_stage(run, stage)
                        await emit_human_gate(run_id, stage.value)
                        return
                
                # Complete
                run.status = "complete"
                store.save(run)
                
                # Update Kanban - completed
                if kanban_task_id:
                    await update_kanban_task_stage(kanban_task_id, 6, "complete")
                    await report_kanban_thought(kanban_task_id, "Pipeline completed successfully!")
                
                await emit_pipeline_complete(run_id)
                return

            if len(runnable) > 1:
                # Parallel stages running
                await emit_pipeline_update(run_id, str([s.value for s in runnable]), "running")
                
                # Update Kanban for first parallel stage
                if kanban_task_id:
                    first_stage = runnable[0].value
                    kanban_stage = get_kanban_stage(first_stage)
                    await update_kanban_task_stage(kanban_task_id, kanban_stage, "thinking")
                    await report_kanban_thought(kanban_task_id, f"Running parallel stages: {', '.join(s.value for s in runnable)}")
                
                await asyncio.gather(*[runner.execute_stage(run, s) for s in runnable])
                
                for s in runnable:
                    await emit_stage_complete(run_id, s.value)
                    
                    # Report artifacts to Kanban
                    if kanban_task_id:
                        output = run.get_output(s)
                        if output:
                            if s.value == "research":
                                await report_kanban_artifact(kanban_task_id, "research", str(output)[:2000])
                            elif s.value == "script_writing":
                                await report_kanban_artifact(kanban_task_id, "script", str(output)[:2000])
                            elif s.value == "visual_planning":
                                await report_kanban_artifact(kanban_task_id, "visual_cues", str(output)[:2000])
            else:
                stage = runnable[0]
                
                # Update Kanban - stage change
                kanban_stage = get_kanban_stage(stage.value)
                if kanban_task_id:
                    await update_kanban_task_stage(kanban_task_id, kanban_stage, "thinking")
                    await report_kanban_thought(kanban_task_id, f"Starting stage: {stage.value}")
                
                await emit_pipeline_update(run_id, stage.value, "running")
                await runner.execute_stage(run, stage)
                
                # Report completion and artifacts
                if kanban_task_id:
                    await update_kanban_task_stage(kanban_task_id, kanban_stage, "idle")
                    await report_kanban_thought(kanban_task_id, f"Completed stage: {stage.value}")
                    
                    output = run.get_output(stage)
                    if output:
                        if stage.value == "research":
                            await report_kanban_artifact(kanban_task_id, "research", str(output)[:2000])
                        elif stage.value == "script_writing":
                            await report_kanban_artifact(kanban_task_id, "script", str(output)[:2000])
                        elif stage.value == "visual_planning":
                            await report_kanban_artifact(kanban_task_id, "visual_cues", str(output)[:2000])
                        elif stage.value == "publish":
                            # Notion URL
                            if isinstance(output, dict) and output.get("notion_url"):
                                await report_kanban_artifact(kanban_task_id, "notion_url", output["notion_url"])
                
                await emit_stage_complete(run_id, stage.value)

    except Exception as e:
        run.status = "error"
        run.error_message = str(e)
        store.save(run)
        
        # Update Kanban - error
        if kanban_task_id:
            await update_kanban_task_stage(kanban_task_id, get_kanban_stage(run.current_stage or ""), "error")
            await report_kanban_thought(kanban_task_id, f"Error: {str(e)}")
        
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


@router.get("/runs/{run_id}/iterations")
async def get_iterations(run_id: str):
    """Get all iteration logs for a pipeline run.
    
    Returns the iteration history from the ExperimentLoop,
    including scores, mutation zones, and baseline comparisons.
    """
    try:
        from packages.pipeline.iteration_store import IterationLogStore
        store = IterationLogStore()
        return {"run_id": run_id, "iterations": store.get_all(run_id)}
    except Exception as e:
        return {"run_id": run_id, "iterations": [], "error": str(e)}


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

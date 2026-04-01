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

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Path, Body
from pydantic import BaseModel, field_validator

from apps.api.dependencies import get_pipeline_runner, get_run_store
from apps.api.events import (
    emit_pipeline_update, emit_stage_complete,
    emit_human_gate, emit_pipeline_complete,
)
from apps.api.events import event_bus

router = APIRouter()

# Kanban integration is now handled directly by kanban_routes.py
# querying the same PipelineRun objects. No explicit sync required.

# ─── Request models ───────────────────────────────────────────────────────────

class StartPipelineRequest(BaseModel):
    topic: str = ""

    @field_validator('topic')
    @classmethod
    def validate_topic(cls, v: str) -> str:
        """Validate that topic is non-empty, meaningful text."""
        if not v or not v.strip():
            raise ValueError("Topic is required and cannot be empty or whitespace.")
        stripped = v.strip()
        if len(stripped) < 5:
            raise ValueError(
                f"Topic is too short ({len(stripped)} chars). "
                f"Please provide at least 5 characters describing your video idea."
            )
        if len(stripped) > 200:
            raise ValueError(
                f"Topic is too long ({len(stripped)} chars). "
                f"Please keep it under 200 characters."
            )
        return stripped

class ApproveGateRequest(BaseModel):
    selection: dict | None = None
    feedback: str = ""

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

# Valid pipeline stage names for validation (derived from STAGE_DEFINITIONS)
VALID_STAGE_NAMES = [s["name"] for s in STAGE_DEFINITIONS["stages"]]


class FeedbackRequest(BaseModel):
    from_stage: str
    to_stage: str
    feedback: str = ""

    @field_validator('from_stage', 'to_stage')
    @classmethod
    def validate_stage(cls, v: str) -> str:
        """Validate that stage names are valid pipeline stages."""
        if v not in VALID_STAGE_NAMES:
            raise ValueError(
                f"Invalid stage '{v}'. Must be one of: {', '.join(VALID_STAGE_NAMES)}"
            )
        return v

    @field_validator('feedback')
    @classmethod
    def validate_feedback(cls, v: str) -> str:
        """Validate feedback is meaningful if provided."""
        if v and len(v.strip()) < 10:
            raise ValueError(
                f"Feedback is too short ({len(v.strip())} chars). "
                f"Please provide at least 10 characters of feedback."
            )
        return v


def _run_to_dict(run) -> dict:
    """Convert PipelineRun or run dict to API response dict."""
    if isinstance(run, dict):
        d = run
    else:
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

    # Kanban sync removed — uses unified store

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
                # C12 FIX: Use "completed" to match PipelineRunner.resume_run() check
                run.status = "completed"
                store.save(run)
                
                
                await emit_pipeline_complete(run_id)
                return

            if len(runnable) > 1:
                # Parallel stages running
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


MAX_LIST_LIMIT = 100

@router.get("/runs")
async def list_runs(limit: int = Query(default=20, ge=1, le=MAX_LIST_LIMIT)):
    """List all pipeline runs, newest first."""
    store = get_run_store()
    if not store:
        return [{"run_id": "demo-001", "current_stage": "human_topic_approval",
                 "status": "waiting_human", "video_title": "Demo Run (pipeline package loading)",
                 "updated_at": datetime.now(timezone.utc).isoformat(), "stages": {}}]
    try:
        # 3.7 FIX: Use include_details=True to fetch all columns in one query,
        # avoiding N+1 per-run load() calls
        runs = store.list_runs(limit=limit, include_details=True)
        result = []
        for run_data in runs:
            try:
                result.append(_run_to_dict(run_data))
            except Exception:
                pass
        return result
    except Exception:
        return []


@router.post("/runs")
async def start_run(req: StartPipelineRequest, bg: BackgroundTasks):
    """Start a new pipeline run. Returns run_id immediately."""
    # Input validation is handled by Pydantic field_validator on StartPipelineRequest.
    # FastAPI automatically returns 422 with user-friendly messages on validation failure.
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
async def get_stage_output(
    run_id: str,
    stage: str = Path(..., pattern=r'^[a-zA-Z0-9_]+$'),
):
    """Get the raw output of a specific pipeline stage."""
    # 3.4 FIX: Validate stage against known definitions
    valid_stages = [s["name"] for s in STAGE_DEFINITIONS["stages"]]
    if stage not in valid_stages:
        raise HTTPException(400, f"Invalid stage '{stage}'. Must be one of: {valid_stages}")
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


# ─── LangGraph Pipeline Endpoints (Phase 4) ────────────────────────────────────

# Module-level graph holders (initialized at startup)
_discovery_graph = None
_production_graph = None


async def _init_graphs():
    """Initialize LangGraph graphs at startup."""
    global _discovery_graph, _production_graph
    try:
        from packages.content_factory.orchestration import (
            get_discovery_graph,
            get_production_graph,
        )
        _discovery_graph = await get_discovery_graph()
        _production_graph = await get_production_graph()
    except Exception as e:
        # Graphs will be None if Supabase is not configured
        import logging
        logging.getLogger(__name__).warning(f"langgraph_init_failed: {e}")


class ResumeDecision(BaseModel):
    """Pydantic model for LangGraph pipeline resume decision.

    Replaces untyped dict with validated fields to prevent injection of
    arbitrary keys into the LangGraph state machine.
    """
    approved: bool
    feedback: str = ""


@router.post("/discover")
async def discover_topics(
    background_tasks: BackgroundTasks,
    seed_hint: str = Query(default=None, max_length=200),
):
    """
    Kick off the LangGraph discovery graph asynchronously.
    Returns immediately — progress streams via Supabase WebSocket.
    
    This is the NEW Phase 4 endpoint using LangGraph state machine.
    """
    global _discovery_graph
    
    if _discovery_graph is None:
        await _init_graphs()
    
    if _discovery_graph is None:
        raise HTTPException(503, "LangGraph not initialized (check Supabase DB connection)")
    
    card_id = str(uuid.uuid4())
    
    initial_state = {
        "card_id": card_id,
        "seed_hint": seed_hint,
        "zep_context": "",
        "search_results": [],
        "generated_topics": [],
        "graded_topics": [],
        "pipeline_status": "discovering",
        "error": None,
    }
    
    config = {"configurable": {"thread_id": card_id}}
    
    # Run in background so API responds instantly
    background_tasks.add_task(
        _discovery_graph.ainvoke, initial_state, config
    )
    
    return {"status": "started", "card_id": card_id}


@router.post("/produce/{card_id}")
async def produce_content(
    card_id: str,
    background_tasks: BackgroundTasks,
):
    """
    Start the LangGraph production pipeline for an approved topic card.
    
    The card must exist in kanban_cards with a topic_brief.
    Returns immediately — progress streams via Supabase WebSocket.
    The graph will pause at human_review and wait for /langgraph/resume.
    """
    global _production_graph
    
    if _production_graph is None:
        await _init_graphs()
    
    if _production_graph is None:
        raise HTTPException(503, "LangGraph not initialized (check Supabase DB connection)")
    
    try:
        from packages.core.supabase_client import get_supabase
        sb = get_supabase()
        result = sb.table("kanban_cards").select("*").eq("id", card_id).execute()
        
        if not result.data:
            raise HTTPException(404, f"Card {card_id} not found")
        
        card = result.data[0]
    except Exception as e:
        raise HTTPException(500, f"Failed to fetch card: {e}")
    
    initial_state = {
        "card_id": card_id,
        "topic_brief": card.get("topic_brief", {"title": card.get("title", "Unknown")}),
        "research_dossier": "",
        "research_sources": [],
        "zep_learnings": "",
        "current_draft": "",
        "best_draft": "",
        "best_score": 0,
        "evaluation_score": 0,
        "evaluation_feedback": "",
        "iteration_count": 0,
        "visual_plan": "",
        "human_feedback": None,
        "approved": False,
        "pipeline_status": "starting",
        "error": None,
    }
    
    config = {"configurable": {"thread_id": card_id}}
    
    background_tasks.add_task(
        _production_graph.ainvoke, initial_state, config
    )
    
    return {"status": "started", "card_id": card_id}


@router.post("/langgraph/resume/{card_id}")
async def resume_langgraph_pipeline(
    card_id: str,
    decision: ResumeDecision = Body(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """
    Resume the LangGraph production pipeline after human review.
    
    decision format:
      {"approved": true}                          → publishes to Notion
      {"approved": false, "feedback": "..."}      → sends back to drafting
    """
    global _production_graph
    
    if _production_graph is None:
        await _init_graphs()
    
    if _production_graph is None:
        raise HTTPException(503, "LangGraph not initialized (check Supabase DB connection)")
    
    from langgraph.types import Command
    
    config = {"configurable": {"thread_id": card_id}}
    
    background_tasks.add_task(
        _production_graph.ainvoke,
        Command(resume=decision),
        config,
    )
    
    return {"status": "resumed", "card_id": card_id, "decision": decision}


@router.get("/langgraph/state/{card_id}")
async def get_langgraph_state(card_id: str):
    """
    Fetch the current checkpointed state of a LangGraph pipeline run.
    Useful for the frontend to display current score, iteration count, etc.
    """
    global _production_graph
    
    if _production_graph is None:
        await _init_graphs()
    
    if _production_graph is None:
        raise HTTPException(503, "LangGraph not initialized")
    
    config = {"configurable": {"thread_id": card_id}}
    
    try:
        state = await _production_graph.aget_state(config)
        values = state.values if hasattr(state, 'values') else {}
        return {
            "card_id": card_id,
            "values": values,
            "next": list(state.next) if state.next else [],
            "risk_tier": values.get("risk_tier"),
            "sla_deadline": values.get("sla_deadline"),
            "review_requested_at": values.get("review_requested_at"),
        }
    except Exception as e:
        raise HTTPException(404, f"No pipeline state found for {card_id}: {e}")

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
import logging

logger = logging.getLogger(__name__)
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

# ─── In-memory audit trail store (Issue 22) ────────────────────────────────────
# Resets on server restart — acceptable for MVP.
# run_id -> list of audit entries
_audit_trail: dict[str, list[dict]] = {}

# ─── In-memory feedback history store (Issue 23) ───────────────────────────────
# run_id -> list of feedback entries
_feedback_history: dict[str, list[dict]] = {}


def _record_audit(
    run_id: str,
    decision_type: str,
    stage: str = "",
    actor: str = "system",
    feedback_text: str = "",
    score_at_decision: float | None = None,
    risk_tier: str | None = None,
    iteration_count: int | None = None,
    metadata: dict | None = None,
) -> dict:
    """Record an audit trail entry for a human decision.

    Returns the created audit entry dict.
    """
    entry = {
        "id": uuid.uuid4().hex,
        "run_id": run_id,
        "decision_type": decision_type,
        "stage": stage,
        "actor": actor,
        "feedback_text": feedback_text,
        "score_at_decision": score_at_decision,
        "risk_tier": risk_tier,
        "iteration_count": iteration_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata or {},
    }
    if run_id not in _audit_trail:
        _audit_trail[run_id] = []
    _audit_trail[run_id].append(entry)
    logger.info(
        f"audit_recorded: run_id={run_id} decision={decision_type} "
        f"stage={stage} actor={actor}"
    )
    return entry


def _record_feedback_history(
    run_id: str,
    feedback_text: str,
    from_stage: str,
    to_stage: str,
    iteration_before: int = 0,
    score_before: float = 0,
    script_snippet_before: str = "",
) -> dict:
    """Record a feedback history entry capturing the state before revision.

    Returns the created feedback entry dict. Note: score_after and
    script_snippet_after are left as placeholders here; they are updated
    lazily when a subsequent score is observed.
    """
    entry = {
        "id": uuid.uuid4().hex,
        "run_id": run_id,
        "feedback_text": feedback_text,
        "from_stage": from_stage,
        "to_stage": to_stage,
        "iteration_before": iteration_before,
        "score_before": score_before,
        "score_after": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "script_snippet_before": script_snippet_before[:200] if script_snippet_before else "",
        "script_snippet_after": "",
    }
    if run_id not in _feedback_history:
        _feedback_history[run_id] = []
    _feedback_history[run_id].append(entry)
    logger.info(
        f"feedback_history_recorded: run_id={run_id} from={from_stage} "
        f"to={to_stage} score_before={score_before}"
    )
    return entry


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
    """Convert PipelineRun or run dict to API response dict.

    Enhanced (Issue 21): Each stage now includes started_at, completed_at,
    duration_seconds, is_parallel, is_human_gate, and error_message so the
    frontend can render a horizontal step progress indicator.
    Top-level total_stages and completed_stages counts are also provided.
    """
    if isinstance(run, dict):
        d = run
    else:
        d = run.to_dict() if hasattr(run, "to_dict") else vars(run)

    # Pre-compute parallel stage lookup for O(1) access
    parallel_set: set[str] = set()
    for group in STAGE_DEFINITIONS.get("parallel_stages", []):
        for s in group:
            parallel_set.add(s)

    # Build stage-def lookup: name -> stage def
    _stage_def_map = {s["name"]: s for s in STAGE_DEFINITIONS["stages"]}

    # Stage timestamps may live in stage_outputs or stage_status metadata.
    # Legacy data won't have them — defaults are None.
    stage_timings: dict = d.get("stage_timings", {})
    stage_status: dict = d.get("stage_status", {})
    stage_outputs: dict = d.get("stage_outputs", {})
    error_message: str = d.get("error_message", "")

    # Build enriched stages dict
    stages: dict[str, dict] = {}
    for stage_name in STAGE_DEFINITIONS["execution_order"]:
        status = stage_status.get(stage_name, "pending")
        timing = stage_timings.get(stage_name, {})
        started_at = timing.get("started_at") or None
        completed_at = timing.get("completed_at") or None

        # Compute duration
        duration_seconds: float | None = None
        if started_at and completed_at:
            try:
                started = datetime.fromisoformat(str(started_at))
                completed = datetime.fromisoformat(str(completed_at))
                duration_seconds = (completed - started).total_seconds()
            except (ValueError, TypeError):
                duration_seconds = None

        # Per-stage error message (if stage errored)
        stage_error = None
        if status == "error":
            # Could come from stage_outputs._error or top-level error_message
            stage_out = stage_outputs.get(stage_name)
            if isinstance(stage_out, dict):
                stage_error = stage_out.get("_error") or stage_out.get("error_message")
            if not stage_error and stage_name == d.get("current_stage", ""):
                stage_error = error_message

        stage_def = _stage_def_map.get(stage_name, {})

        stages[stage_name] = {
            "status": status,
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_seconds": duration_seconds,
            "is_parallel": stage_name in parallel_set,
            "is_human_gate": stage_def.get("is_human_gate", False),
            "error_message": stage_error,
            "output": stage_outputs.get(stage_name),
        }

    # Normalize trend_analysis output (TopicBrief → frontend-friendly)
    if stages.get("trend_analysis", {}).get("output"):
        out = stages["trend_analysis"]["output"]
        if isinstance(out, list):
            stages["trend_analysis"]["output"] = [
                _normalize_topic_candidate(t) for t in out
            ]

    # Top-level progress counts (Issue 21)
    total_stages = len(STAGE_DEFINITIONS["execution_order"])
    completed_stages = sum(
        1 for s in stages.values() if s["status"] in ("complete", "completed")
    )

    return {
        "run_id": d.get("run_id", ""),
        "current_stage": d.get("current_stage", ""),
        "status": d.get("status", ""),
        "video_title": _extract_title(d),
        "created_at": str(d.get("created_at", "")),
        "updated_at": str(d.get("updated_at", "")),
        "stages": stages,
        "error_message": error_message,
        "total_stages": total_stages,
        "completed_stages": completed_stages,
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

async def _run_pipeline_bg(run_id: str, context: dict = None) -> None:
    """Background task: run pipeline until gate or completion, emitting SSE.
    
    Also creates and updates a corresponding Kanban task for visual tracking.
    
    Args:
        run_id: The pipeline run ID to execute.
        context: Optional context dict passed to stage handlers (e.g., seed_query, genre_id).
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
                        await runner.execute_stage(run, stage, context)
                        await emit_human_gate(run_id, stage.value)
                        return

                # ── BUGFIX: Check for errored stages before declaring complete ──
                # Previous code blindly set "completed" when no stages were runnable,
                # even if a stage had errored. This caused the kanban to show
                # "completed" while the card was stuck on the errored stage.
                has_errors = any(
                    st == "error"
                    for st in run.stage_status.values()
                )
                if has_errors:
                    run.status = "error"
                    # Find the first errored stage for the error message
                    for stage in Stage:
                        if run.stage_status.get(stage.value) == "error":
                            run.current_stage = stage
                            run.error_message = f"Stage {stage.value} failed — pipeline cannot continue"
                            break
                    store.save(run)
                    await emit_pipeline_update(run_id, run.current_stage.value if run.current_stage else "", "error")
                    logger.error(f"pipeline_stalled_with_errors: run_id={run_id} errored_stages={[s.value for s in Stage if run.stage_status.get(s.value)=='error']}")
                    return

                # Truly complete — all stages finished successfully
                run.status = "complete"
                store.save(run)

                await emit_pipeline_complete(run_id)
                return

            if len(runnable) > 1:
                # Parallel stages running
                # BUGFIX: Reset circuit breaker before parallel stage batch too
                try:
                    from packages.router.client import RouterClient
                    RouterClient.reset_circuit_breaker()
                except Exception:
                    pass

                await emit_pipeline_update(run_id, str([s.value for s in runnable]), "running")

                await asyncio.gather(*[runner.execute_stage(run, s, context) for s in runnable])

                for s in runnable:
                    await emit_stage_complete(run_id, s.value)

            else:
                stage = runnable[0]

                # BUGFIX: Reset circuit breaker before each new stage.
                # Without this, failures in trend_analysis (which makes 6+ LLM
                # calls) trip the class-level breaker and block ALL subsequent
                # stages (research, script_writing, etc.) immediately.
                try:
                    from packages.router.client import RouterClient
                    RouterClient.reset_circuit_breaker()
                except Exception:
                    pass  # Non-critical: don't let this block the pipeline

                await emit_pipeline_update(run_id, stage.value, "running")
                try:
                    await runner.execute_stage(run, stage, context)
                except Exception as stage_err:
                    # Stage handler raised — execute_stage already marked it "error".
                    # Re-raise so the outer try/except in _run_pipeline_bg() stops
                    # the pipeline instead of continuing to the next stage.
                    logger.error(f"stage_execution_failed: stage={stage.value} error={stage_err}")
                    raise

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
async def list_runs(
    limit: int = Query(default=20, ge=1, le=MAX_LIST_LIMIT),
    include_deleted: bool = Query(default=False, description="Include soft-deleted runs"),
):
    """List all pipeline runs, newest first.

    By default, soft-deleted runs are excluded. Pass include_deleted=true
    to show them (e.g. for a trash bin view).
    """
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
                d = _run_to_dict(run_data)
                # Filter out soft-deleted runs unless explicitly requested
                if not include_deleted and run_data.get("deleted_at"):
                    continue
                result.append(d)
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
        _record_audit(
            run_id=mock_id, decision_type="create",
            metadata={"mode": "mock", "topic": req.topic},
        )
        return {"run_id": mock_id, "status": "started (mock — pipeline package loading)"}

    run = await runner.create_run()
    _record_audit(
        run_id=run.run_id, decision_type="create",
        metadata={"topic": req.topic},
    )
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
    """Soft-delete a pipeline run by setting deleted_at timestamp.

    The run is hidden from default list views but can be restored via
    undo-delete. For permanent hard delete, use /hard-delete endpoint.
    """
    store = get_run_store()
    if not store:
        raise HTTPException(503, "Pipeline package not available")
    run = store.load(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")

    deleted_at = datetime.now(timezone.utc).isoformat()
    # Set deleted_at on the run object and save
    if hasattr(run, "deleted_at"):
        run.deleted_at = deleted_at
    if hasattr(run, "stage_status"):
        run.stage_status["_deleted"] = True
    store.save(run)

    _record_audit(
        run_id=run_id, decision_type="delete",
        stage=getattr(run, "current_stage", ""),
        metadata={"mode": "soft", "deleted_at": deleted_at},
    )
    logger.info(f"run_soft_deleted: run_id={run_id} deleted_at={deleted_at}")
    return {"deleted": run_id, "deleted_at": deleted_at, "mode": "soft"}


@router.post("/runs/{run_id}/soft-delete")
async def soft_delete_run(run_id: str):
    """Explicitly soft-delete a pipeline run (same as DELETE but more descriptive).

    Marks the run as deleted without permanently removing it.
    The run can be restored via /undo-delete/{run_id}.
    """
    return await delete_run(run_id)


@router.post("/runs/undo-delete/{run_id}")
async def undo_delete_run(run_id: str):
    """Restore a soft-deleted pipeline run.

    Clears the deleted_at timestamp, making the run visible again
    in default list views.
    """
    store = get_run_store()
    if not store:
        raise HTTPException(503, "Pipeline package not available")

    run = store.load(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")

    # Check if actually soft-deleted
    deleted_at = None
    if hasattr(run, "deleted_at"):
        deleted_at = run.deleted_at
    if not deleted_at:
        raise HTTPException(400, f"Run {run_id} is not soft-deleted")

    # Restore: clear deleted_at
    run.deleted_at = None
    if hasattr(run, "stage_status") and "_deleted" in run.stage_status:
        del run.stage_status["_deleted"]
    store.save(run)

    logger.info(f"run_undeleted: run_id={run_id}")
    return {"restored": run_id, "previously_deleted_at": deleted_at}


@router.post("/runs/{run_id}/hard-delete")
async def hard_delete_run(run_id: str):
    """Permanently delete a pipeline run (irreversible).

    Unlike the default DELETE (soft-delete), this permanently removes
    the run from storage. Use with caution.
    """
    store = get_run_store()
    if not store:
        raise HTTPException(503, "Pipeline package not available")
    run = store.load(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")
    store.delete(run_id)
    logger.info(f"run_hard_deleted: run_id={run_id}")
    return {"deleted": run_id, "mode": "hard"}


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

    # Extract score/risk metadata for audit (best-effort)
    _eval_score = None
    _risk_tier = None
    _iter_count = None
    outputs = getattr(run, "stage_outputs", {})
    if isinstance(outputs, dict):
        _eval_score = outputs.get("_evaluation_score")
        _risk_tier = outputs.get("_risk_tier")
    _iter_count = getattr(run, "iteration_count", None)

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

    _record_audit(
        run_id=run_id, decision_type="approve",
        stage=getattr(run, "current_stage", ""),
        feedback_text=req.feedback,
        score_at_decision=_eval_score,
        risk_tier=_risk_tier,
        iteration_count=_iter_count,
        metadata={"selection": req.selection},
    )
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

    # Extract score metadata for audit
    _eval_score = None
    outputs = getattr(run, "stage_outputs", {})
    if isinstance(outputs, dict):
        _eval_score = outputs.get("_evaluation_score")

    run.stage_status[run.current_stage] = "pending"
    run.status = "running"
    store.save(run)

    _record_audit(
        run_id=run_id, decision_type="reject",
        stage=getattr(run, "current_stage", ""),
        feedback_text=req.feedback,
        score_at_decision=_eval_score,
    )
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

    # Capture state BEFORE feedback is processed (Issue 23)
    _score_before = None
    _iteration_before = 0
    _script_before = ""
    _risk_tier = None
    outputs = getattr(run, "stage_outputs", {})
    if isinstance(outputs, dict):
        _score_before = outputs.get("_evaluation_score") or outputs.get("evaluation_score")
        _risk_tier = outputs.get("_risk_tier")
        draft = outputs.get("script_writing", "")
        if isinstance(draft, str):
            _script_before = draft[:200]
    _iteration_before = getattr(run, "iteration_count", 0) or 0

    try:
        from packages.pipeline.stages import Stage
        await runner.request_feedback(run, Stage(req.from_stage),
                                       Stage(req.to_stage), req.feedback)
    except (ImportError, ValueError) as e:
        raise HTTPException(400, str(e))

    # Record audit trail entry (Issue 22)
    _record_audit(
        run_id=run_id, decision_type="feedback",
        stage=req.from_stage,
        feedback_text=req.feedback,
        score_at_decision=_score_before,
        risk_tier=_risk_tier,
        iteration_count=_iteration_before,
        metadata={"to_stage": req.to_stage},
    )

    # Record feedback history entry (Issue 23)
    _record_feedback_history(
        run_id=run_id,
        feedback_text=req.feedback,
        from_stage=req.from_stage,
        to_stage=req.to_stage,
        iteration_before=_iteration_before,
        score_before=_score_before or 0,
        script_snippet_before=_script_before,
    )

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

    Enhanced (Issue 23c): Cross-references feedback history to annotate
    iterations that were triggered by feedback loops.
    """
    try:
        from packages.pipeline.iteration_store import IterationLogStore
        iter_store = IterationLogStore()
        iterations = iter_store.get_all(run_id)
    except Exception as e:
        iterations = []

    # Cross-reference with feedback history (Issue 23c)
    fb_entries = _feedback_history.get(run_id, [])
    if fb_entries and iterations:
        # Build a map of score_before for matching
        for iteration in iterations:
            iter_score = iteration.get("score")
            # Find feedback entries whose score_before matches this iteration
            matching_fb = [
                fb for fb in fb_entries
                if fb["score_before"] is not None
                and iter_score is not None
                and abs(float(fb["score_before"]) - float(iter_score)) < 0.1
            ]
            if matching_fb:
                iteration["feedback_context"] = [
                    {
                        "feedback_id": fb["id"],
                        "feedback_text": fb["feedback_text"],
                        "from_stage": fb["from_stage"],
                        "to_stage": fb["to_stage"],
                    }
                    for fb in matching_fb
                ]

    return {
        "run_id": run_id,
        "iterations": iterations,
        "feedback_entries_count": len(fb_entries),
    }


# ─── Audit Trail & Feedback History endpoints (Issues 22-23) ────────────────────

@router.get("/runs/{run_id}/audit-trail")
async def get_audit_trail(run_id: str):
    """Return the audit trail for a pipeline run.

    Every human decision (approve, reject, feedback, delete, resume, create)
    is recorded with timestamp, stage, score context, and risk tier.
    """
    entries = _audit_trail.get(run_id, [])
    return {
        "run_id": run_id,
        "entries": entries,
        "count": len(entries),
    }


@router.get("/runs/{run_id}/feedback-history")
async def get_feedback_history(run_id: str):
    """Return the feedback history showing how the script evolved.

    Each entry captures the feedback text, the stage that was sent back,
    the score before and after the revision, and snippets of the draft
    before and after for diff comparison.
    """
    entries = _feedback_history.get(run_id, [])
    return {
        "run_id": run_id,
        "entries": entries,
        "count": len(entries),
    }


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

    Returns explanation data including which stages are complete,
    which will be retried, and whether expensive operations re-run.
    """
    runner = get_pipeline_runner()
    store = get_run_store()
    if not runner or not store:
        raise HTTPException(503, "Pipeline package not available")

    run = store.load(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")

    # Build resume explanation
    stage_status = getattr(run, "stage_status", {})
    completed_stages = [s for s, st in stage_status.items() if st in ("complete", "completed") and not s.startswith("_")]
    failed_stages = [s for s, st in stage_status.items() if st == "error"]
    pending_stages = [s for s, st in stage_status.items() if st == "pending"]
    current_stage = getattr(run, "current_stage", "")
    run_status = getattr(run, "status", "")

    # Expensive stages that should ideally not be re-run
    expensive_stages = {"research", "script_writing", "visual_planning", "asset_creation"}
    will_rerun_expensive = bool(set(failed_stages) & expensive_stages)

    # Estimate remaining time based on pending stages
    stage_time_estimates = {
        "trend_analysis": 10, "human_topic_approval": 0, "research": 30,
        "script_writing": 45, "visual_planning": 20, "seo": 15,
        "human_review": 0, "asset_creation": 120, "publish": 30,
    }
    estimated_seconds = sum(
        stage_time_estimates.get(s, 30)
        for s in pending_stages
        if s in stage_time_estimates
    )
    if current_stage and current_stage in stage_time_estimates:
        estimated_seconds = max(estimated_seconds, stage_time_estimates[current_stage])

    resume_explanation = {
        "explanation": {
            "completed_stages": completed_stages,
            "failed_stages": failed_stages,
            "pending_stages": pending_stages,
            "stage_to_retry": current_stage if run_status == "error" else None,
            "will_rerun_expensive_operations": will_rerun_expensive,
            "estimated_remaining_seconds": estimated_seconds,
            "run_status_before_resume": run_status,
        }
    }

    try:
        result = await runner.resume_run(run_id)
        if result is None:
            # Could be already completed or not resumable
            if run.status == "completed":
                raise HTTPException(400, f"Run {run_id} is already completed")
            raise HTTPException(400, f"Run {run_id} cannot be resumed")

        # BUGFIX: Reset circuit breaker on resume — the breaker may be OPEN
        # from the original failure. Without this reset, the resumed stage
        # would get immediately rejected with "Circuit breaker is OPEN".
        try:
            from packages.router.client import RouterClient
            RouterClient.reset_circuit_breaker()
            logger.info(f"circuit_breaker_reset_on_resume: run_id={run_id}")
        except Exception:
            pass

        # Record audit trail (Issue 22)
        _record_audit(
            run_id=run_id, decision_type="resume",
            stage=current_stage,
            metadata={
                "run_status_before": run_status,
                "failed_stages": failed_stages,
                "will_rerun_expensive": will_rerun_expensive,
            },
        )

        # If we recovered and got a stage, start background execution
        if run.status == "running":
            bg.add_task(_run_pipeline_bg, run_id)

        return {
            "status": "resumed",
            "run_id": run_id,
            "current_stage": result.value if result else None,
            "run_status": run.status,
            **resume_explanation,
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

    # Build resume explanation from current state
    resume_explanation = {}
    try:
        current_state = await _production_graph.aget_state(config)
        values = current_state.values if hasattr(current_state, "values") else {}
        pipeline_status = values.get("pipeline_status", "unknown")
        evaluation_score = values.get("evaluation_score", 0)
        iteration_count = values.get("iteration_count", 0)

        # Determine what will happen on resume
        if decision.approved:
            next_action = "Publish approved script to Notion"
            will_rerun_expensive = False
        else:
            next_action = "Return to drafting stage with human feedback"
            will_rerun_expensive = True

        resume_explanation = {
            "explanation": {
                "current_pipeline_status": pipeline_status,
                "evaluation_score": evaluation_score,
                "iterations_completed": iteration_count,
                "decision": "approved" if decision.approved else "rejected_with_feedback",
                "next_action": next_action,
                "will_rerun_expensive_operations": will_rerun_expensive,
                "estimated_remaining_seconds": 30 if not decision.approved else 30,
            }
        }
    except Exception:
        pass  # Non-critical: explanation is best-effort

    background_tasks.add_task(
        _production_graph.ainvoke,
        Command(resume=decision),
        config,
    )
    
    return {"status": "resumed", "card_id": card_id, "decision": decision, **resume_explanation}


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
            "score_categories": values.get("score_categories"),
        }
    except Exception as e:
        raise HTTPException(404, f"No pipeline state found for {card_id}: {e}")


# ─── Preview Before Publish (Issue 13) ─────────────────────────────────────────

@router.get("/runs/{run_id}/preview")
async def preview_run(run_id: str):
    """Preview how a pipeline run would appear when published to Notion.

    Returns the formatted script, visual plan, score, and feedback
    in a structured preview format. Does NOT publish to Notion.
    This is a read-only preview for the frontend to display before
    the user confirms publishing.
    """
    store = get_run_store()
    if not store:
        raise HTTPException(503, "Pipeline package not available")
    run = store.load(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")

    outputs = run.stage_outputs if hasattr(run, "stage_outputs") else {}
    current_draft = outputs.get("script_writing", "")
    visual_plan = outputs.get("visual_planning", "")
    evaluation_score = outputs.get("_evaluation_score", 0)
    evaluation_feedback = outputs.get("_evaluation_feedback", "")

    # Extract title
    title = "Untitled"
    approval = outputs.get("human_topic_approval")
    if isinstance(approval, dict):
        title = approval.get("title", "Untitled")

    # Build the preview response
    preview = {
        "run_id": run_id,
        "title": title,
        "draft": current_draft if isinstance(current_draft, str) else str(current_draft),
        "visual_plan": visual_plan if isinstance(visual_plan, str) else str(visual_plan),
        "score": evaluation_score,
        "feedback": evaluation_feedback,
        "status": getattr(run, "status", "unknown"),
        "current_stage": getattr(run, "current_stage", ""),
        "publishable": isinstance(current_draft, str) and len(current_draft.strip()) > 0,
    }

    return preview


# ─── Preview LangGraph Pipeline Before Publish ────────────────────────────────

@router.get("/langgraph/preview/{card_id}")
async def preview_langgraph_run(card_id: str):
    """Preview how a LangGraph production run would appear when published.

    Fetches the current checkpointed state and returns the draft,
    visual plan, score breakdown, and feedback in a structured preview.
    Does NOT publish to Notion.
    """
    global _production_graph

    if _production_graph is None:
        await _init_graphs()

    if _production_graph is None:
        raise HTTPException(503, "LangGraph not initialized")

    config = {"configurable": {"thread_id": card_id}}

    try:
        state = await _production_graph.aget_state(config)
        values = state.values if hasattr(state, "values") else {}

        draft = values.get("current_draft", "") or values.get("best_draft", "")
        visual_plan = values.get("visual_plan", "")
        evaluation_score = values.get("evaluation_score", 0)
        evaluation_feedback = values.get("evaluation_feedback", "")
        score_categories = values.get("score_categories", {})
        topic_brief = values.get("topic_brief", {})

        title = "Untitled"
        if isinstance(topic_brief, dict):
            title = topic_brief.get("title", "Untitled")

        return {
            "card_id": card_id,
            "title": title,
            "draft": draft,
            "visual_plan": visual_plan,
            "score": evaluation_score,
            "score_categories": score_categories,
            "feedback": evaluation_feedback,
            "iteration_count": values.get("iteration_count", 0),
            "best_score": values.get("best_score", 0),
            "pipeline_status": values.get("pipeline_status", ""),
            "publishable": isinstance(draft, str) and len(draft.strip()) > 0,
        }
    except Exception as e:
        raise HTTPException(404, f"No pipeline state found for {card_id}: {e}")

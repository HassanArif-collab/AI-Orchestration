"""
pipeline_routes.py — Pipeline management API.

ACTIVE ENDPOINTS:
    /stages                  — Return pipeline stage graph definition (static)
    /discover                — Start LangGraph discovery graph (topic generation)
    /produce/{card_id}       — Start LangGraph production pipeline
    /langgraph/resume/{card_id}  — Resume pipeline after human review
    /langgraph/state/{card_id}   — Get checkpointed pipeline state
    /langgraph/preview/{card_id} — Preview production output before publish

REMOVED (Phase 3 dead code cleanup):
    /runs/*                  — Legacy PipelineRunner CRUD (deprecated, use LangGraph)
    /runs/{run_id}/approve   — Gate approval (now handled by LangGraph human_review)
    /runs/{run_id}/reject    — Gate rejection (now handled by LangGraph human_review)
    /runs/{run_id}/feedback  — Feedback loop (now handled by LangGraph iteration)
    /runs/{run_id}/iterations — ExperimentLoop (deleted in Phase 2)
    _run_pipeline_bg         — Legacy PipelineRunner background task
"""

from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Body
import logging

logger = logging.getLogger(__name__)
from pydantic import BaseModel

router = APIRouter()


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


# ─── Utility functions (used by LangGraph endpoints and frontend) ─────────────

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


# ─── Stage definitions endpoint ───────────────────────────────────────────────

@router.get("/stages")
async def get_stage_definitions():
    """Return the full pipeline stage graph definition."""
    return STAGE_DEFINITIONS


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
    card_id: str | None = Query(default=None, description="Pre-existing card ID to reuse (e.g. from kanban_cards)")
):
    """
    Kick off the LangGraph discovery graph asynchronously.
    Returns immediately — progress streams via Supabase WebSocket.

    This is the NEW Phase 4 endpoint using LangGraph state machine.

    If card_id is provided (e.g. from kanban_routes.topic_finder which already
    created a kanban_cards row), it is reused so the graph updates the same card.
    Otherwise a new UUID is generated (standalone /discover call).
    """
    global _discovery_graph

    if _discovery_graph is None:
        await _init_graphs()

    if _discovery_graph is None:
        raise HTTPException(503, "LangGraph not initialized (check Supabase DB connection)")

    if not card_id:
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

    The card must exist in kanban_cards with topic_brief in metadata.
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
        metadata = card.get("metadata", {}) or {}
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                metadata = {}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to fetch card: {e}")

    initial_state = {
        "card_id": card_id,
        "topic_brief": metadata.get("topic_brief", {"title": card.get("title", "Unknown")}),
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


# ─── Preview Before Publish ──────────────────────────────────────────────────

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

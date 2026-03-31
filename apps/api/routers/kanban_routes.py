"""
Kanban task management routes -- Refactored to use PipelineRunner.

These endpoints handle the Kanban board operations for the YouTube Pipeline
dashboard. The Kanban board is a view-only (mostly) representation of the
Pipeline runs stored in Supabase pipeline_runs table.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Path, Body
from pydantic import BaseModel, Field

from apps.api.dependencies import get_pipeline_runner, get_run_store
from apps.api.events import emit_task_created
from packages.core.config import get_settings

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
    """Convert a PipelineRun or run dict to a Kanban-friendly dictionary."""
    if isinstance(run, dict):
        d = run
    else:
        d = run.to_dict() if hasattr(run, "to_dict") else vars(run)
    stage_name = d.get("current_stage", "trend_analysis")

    # Extract title - check 'title' first (normalized field), then 'topic_statement' (raw field)
    # This handles both normalized data (from frontend approval) and raw data (from pipeline storage)
    video_title = "Untitled"
    outputs = d.get("stage_outputs", {})
    approval = outputs.get("human_topic_approval")
    if isinstance(approval, dict):
        video_title = approval.get("title") or approval.get("topic_statement") or "Untitled"
    else:
        trend = outputs.get("trend_analysis")
        if isinstance(trend, list) and trend:
            video_title = trend[0].get("title") or trend[0].get("topic_statement") or "Untitled"

    # Status mapping to Kanban visual states
    # C12 FIX: Accept both "complete" and "completed" for backward compat
    status = d.get("status", "idle")
    if status == "running":
        kanban_status = "thinking"
    elif status == "waiting_human":
        kanban_status = "waiting"
    elif status in ("complete", "completed"):
        kanban_status = "complete"
    elif status == "error":
        kanban_status = "error"
    else:
        kanban_status = "idle"

    # Color mapping (simple palette based on stage)
    colors = ["#1D9E75", "#378ADD", "#BA7517", "#D4A017", "#D1242F", "#0969DA"]
    stage_num = get_kanban_stage(stage_name)
    color = colors[stage_num - 1] if 1 <= stage_num <= 6 else colors[0]

    # Thoughts: Load from centralized Supabase thoughts module
    run_id = d.get("run_id", "")
    thoughts = []
    try:
        from packages.core.thoughts import get_thoughts_for_card
        thoughts = get_thoughts_for_card(str(run_id))
    except Exception as e:
        print(f"Error loading thoughts for {run_id}: {e}")

    # Render artifacts as readable HTML (Task 6 fix)
    research_html = _render_artifact_html(outputs.get("research"), "research")
    script_html = _render_artifact_html(outputs.get("script_writing"), "script")
    visual_html = _render_artifact_html(outputs.get("visual_planning"), "visual")

    return {
        "id": run_id,
        "title": video_title,
        "stage": stage_num,
        "status": kanban_status,
        "color": color,
        "updated_at": d.get("updated_at"),
        "created_at": d.get("created_at"),
        "notion_url": outputs.get("publish", {}).get("notion_url") if isinstance(outputs.get("publish"), dict) else None,
        "research": research_html,
        "script": script_html,
        "visual_cues": visual_html,
        "thoughts": json.dumps(thoughts)  # JSON string for frontend parsing
    }


def _render_artifact_html(data: Any, artifact_type: str) -> str:
    """Render artifact data as readable HTML instead of truncated JSON strings.

    Args:
        data: The artifact data (dict, list, or other)
        artifact_type: Type hint (research, script, visual)

    Returns:
        HTML string for display in the Kanban drawer
    """
    import html as html_module
    
    if not data:
        return ""

    if isinstance(data, str):
        # Special handling for visual plain text output (Option A)
        if artifact_type == "visual":
            # Highlight category labels in visual annotations
            content = html_module.escape(data[:2000])
            labels = ["[B-ROLL]", "[MAP]", "[DATA]", "[ARCHIVAL]", "[GRAPHIC]", "[TRANSITION]", "[SOUND]"]
            for label in labels:
                content = content.replace(
                    html_module.escape(label),
                    f'<span style="color:#1D9E75;font-weight:600;">{html_module.escape(label)}</span>'
                )
            # Preserve line breaks and format nicely
            content = content.replace('\n', '<br>')
            return f'<pre style="margin:0;font-size:12px;white-space:pre-wrap;font-family:inherit;">{content}</pre>'
        return data[:500] if len(data) > 500 else data

    if not isinstance(data, dict):
        # Fallback for non-dict data
        return str(data)[:500]

    # Handle AdaptedScript (script_writing output)
    # C2 FIX: All user/agent data escaped before HTML insertion
    if artifact_type == "script" and "entries" in data:
        entries = data.get("entries", [])
        if not entries:
            return ""

        title = html_module.escape(str(data.get("adapted_title", "Untitled Script")))
        score = data.get("production_readiness_score", 0)

        html_parts = [
            f'<div style="margin-bottom:8px;font-weight:600;">{title}</div>',
            f'<div style="margin-bottom:8px;font-size:11px;color:#888;">Score: {score:.1f}%</div>',
            '<table style="width:100%;border-collapse:collapse;font-size:12px;">',
            '<thead><tr style="background:#1e1e1e;">',
            '<th style="padding:6px;text-align:left;border-bottom:1px solid #333;">Narration</th>',
            '<th style="padding:6px;text-align:left;border-bottom:1px solid #333;">Visual</th>',
            '</tr></thead>',
            '<tbody>'
        ]

        for i, entry in enumerate(entries[:10]):  # Limit to first 10 entries
            bg = "#141414" if i % 2 == 0 else "#1a1a1a"
            prose = html_module.escape(str(entry.get("prose", ""))[:200])
            visual = html_module.escape(str(entry.get("visual_direction", ""))[:100])
            html_parts.append(
                f'<tr style="background:{bg}"><td style="padding:6px;vertical-align:top;border-bottom:1px solid #333;">{prose}</td>'
                f'<td style="padding:6px;vertical-align:top;border-bottom:1px solid #333;color:#888;">{visual}</td></tr>'
            )

        if len(entries) > 10:
            html_parts.append(f'<tr><td colspan="2" style="padding:6px;text-align:center;color:#888;">... and {len(entries) - 10} more entries</td></tr>')

        html_parts.append('</tbody></table>')
        return ''.join(html_parts)

    # Handle Research output
    # C2 FIX: All user/agent data escaped before HTML insertion
    if artifact_type == "research":
        # Check for common research fields
        if "source_video_id" in data:
            # This is an AdaptedScript from research stage
            title = html_module.escape(str(data.get("adapted_title", data.get("source_title", "Research Output"))))
            entries = data.get("entries", [])
            if entries:
                return _render_artifact_html(data, "script")
            return f'<div style="font-weight:600;">{title}</div>'

        # Generic research dict - show key fields
        html_parts = []
        for key in ["topic", "title", "summary", "main_findings", "key_points"]:
            if key in data:
                val = data[key]
                if isinstance(val, list):
                    escaped = html_module.escape("<br>".join(str(v)[:100] for v in val[:5]))
                    html_parts.append(f'<div style="margin-bottom:6px;"><strong>{html_module.escape(key)}:</strong> {escaped}</div>')
                elif isinstance(val, str):
                    escaped = html_module.escape(val[:300])
                    html_parts.append(f'<div style="margin-bottom:6px;"><strong>{html_module.escape(key)}:</strong> {escaped}</div>')

        if html_parts:
            return ''.join(html_parts)

    # Handle Visual Planning output
    # C2 FIX: All user/agent data escaped before HTML insertion
    if artifact_type == "visual" and "section_briefs" in data:
        briefs = data.get("section_briefs", [])
        if not briefs:
            return ""

        html_parts = ['<div style="font-size:12px;">']
        for i, brief in enumerate(briefs[:6]):
            section = html_module.escape(str(brief.get("section_index", i)))
            palette = html_module.escape(str(brief.get("sonic_palette", "N/A"))[:50])
            html_parts.append(
                f'<div style="margin-bottom:4px;padding:4px;background:#1a1a1a;border-radius:4px;">'
                f'<span style="color:#1D9E75;">Section {section}:</span> {palette}</div>'
            )
        if len(briefs) > 6:
            html_parts.append(f'<div style="color:#888;">... and {len(briefs) - 6} more sections</div>')
        html_parts.append('</div>')
        return ''.join(html_parts)

    # C2 FIX: Escape fallback JSON output
    try:
        json_str = json.dumps(data, indent=2, default=str)
        escaped_json = html_module.escape(json_str)
        if len(escaped_json) > 500:
            return f'<pre style="margin:0;font-size:11px;white-space:pre-wrap;">{escaped_json[:500]}...</pre>'
        return f'<pre style="margin:0;font-size:11px;white-space:pre-wrap;">{escaped_json}</pre>'
    except Exception:
        return html_module.escape(str(data)[:500])

# ─── Pydantic Models ────────────────────────────────────────────────────────────

class KanbanTaskUpdate(BaseModel):
    """Request model for updating a Kanban task."""
    stage: Optional[int] = Field(default=None, ge=1, le=6)

class TopicFinderRequest(BaseModel):
    """Request model for triggering Topic Finder."""
    seed_query: str = Field(..., min_length=3, max_length=500)
    genre_id: str = Field(default="default", max_length=50)

class KanbanEventRequest(BaseModel):
    """Request model for Kanban events (thoughts, stage changes, artifacts)."""
    task_id: str = Field(..., description="The run/task ID")
    event_type: str = Field(..., description="Event type: thought, stage_change, artifact, status_change")
    data: Dict[str, Any] = Field(default_factory=dict, description="Event payload")

# ─── API Endpoints ──────────────────────────────────────────────────────────────

KANBAN_MAX_LIST_LIMIT = 200

@router.get("/tasks")
async def list_tasks(limit: int = Query(default=100, ge=1, le=KANBAN_MAX_LIST_LIMIT)) -> dict:
    """List all pipeline runs as Kanban tasks."""
    store = get_run_store()
    if not store:
        return {"tasks": []}

    # 3.7 FIX: Use include_details=True to fetch all columns in one query,
    # avoiding N+1 per-run load() calls
    runs = store.list_runs(limit=limit, include_details=True)
    tasks = []
    for run_data in runs:
        try:
            tasks.append(_run_to_kanban_dict(run_data))
        except Exception as e:
            print(f"Error processing task {run_data.get('run_id')}: {e}")
            continue

    return {"tasks": tasks}

@router.get("/tasks/{task_id}")
async def get_task(task_id: str = Path(..., min_length=1, max_length=100)) -> dict:
    """Get a single PipelineRun as a Kanban task."""
    store = get_run_store()
    if not store:
        raise HTTPException(503, "Store not available")

    run = store.load(task_id)
    if not run:
        raise HTTPException(404, f"Task {task_id} not found")

    return _run_to_kanban_dict(run)

@router.patch("/tasks/{task_id}")
async def update_task(task_id: str = Path(..., min_length=1, max_length=100), data: KanbanTaskUpdate = Body(...), bg: BackgroundTasks = BackgroundTasks()) -> dict:
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
async def delete_task(task_id: str = Path(..., min_length=1, max_length=100)) -> dict:
    """Delete the underlying pipeline run and associated thoughts."""
    store = get_run_store()
    if not store:
        raise HTTPException(503, "Store not available")

    store.delete(task_id)

    # Also delete associated thoughts via centralized module
    try:
        from packages.core.thoughts import delete_thoughts_for_card
        delete_thoughts_for_card(str(task_id))
    except Exception as e:
        print(f"Warning: Could not delete thoughts for {task_id}: {e}")

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

@router.post("/events")
async def record_kanban_event(data: KanbanEventRequest) -> dict:
    """Record a Kanban event (thought, stage change, artifact, etc.).

    This endpoint is called by agents via KanbanCallbackHandler to report
    thoughts, stage changes, artifacts, and status changes.

    Args:
        data: The event request containing task_id, event_type, and data payload

    Returns:
        Success dict with event_type
    """
    if data.event_type == "thought":
        # Write thought directly to Supabase via centralized module
        from packages.core.thoughts import report_thought
        thought_text = data.data.get("content", data.data.get("text", ""))
        report_thought(
            card_id=data.task_id,
            agent_name=data.data.get("agent_name", "unknown"),
            thought_type="thinking",
            content=thought_text,
        )
        return {"success": True, "event_type": data.event_type, "recorded": "thought"}

    # For other event types, we just acknowledge them
    # In the future, we could store stage changes, artifacts, etc.
    return {"success": True, "event_type": data.event_type}


# ─── Card Management Endpoints (for React frontend) ──────────────────────────────

@router.post("/cards/{card_id}/save")
async def save_card(card_id: str = Path(..., min_length=1, max_length=100)) -> dict:
    """Save a suggested topic card by removing the expires_at timestamp.
    
    This prevents the 3-hour auto-delete for Column 2 cards.
    """
    try:
        from packages.core.supabase_client import get_supabase
        sb = get_supabase()
        sb.table("kanban_cards").update({"expires_at": None}).eq("id", card_id).execute()
        return {"status": "saved"}
    except Exception as e:
        raise HTTPException(500, f"Failed to save card: {e}")


class MoveCardRequest(BaseModel):
    """Request model for moving a Kanban card to a different column."""
    column: int = Field(..., ge=1, le=6, description="Target column (1-6)")

@router.put("/cards/{card_id}/move")
async def move_card(card_id: str = Path(..., min_length=1, max_length=100), body: MoveCardRequest = Body(...)) -> dict:
    """Move a card to a different column."""
    try:
        from packages.core.supabase_client import get_supabase
        sb = get_supabase()
        sb.table("kanban_cards").update({
            "column": body.column,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", card_id).execute()
        return {"status": "moved"}
    except Exception as e:
        raise HTTPException(500, f"Failed to move card: {e}")

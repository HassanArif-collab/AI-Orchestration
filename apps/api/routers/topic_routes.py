"""
topic_routes.py — Topic Reservoir Management API.

Endpoints for:
- Viewing topic reservoir
- Approving/rejecting topics
- Submitting custom topics
- Submitting custom scripts

These endpoints integrate with the dashboard to allow users
to interact with the daily topic discovery system.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

# Background task implementations for pipeline integration
from apps.api.background_tasks import (
    start_research_for_topic,
    evaluate_script,
    run_daily_scan,
)

router = APIRouter()


# ─── Topic Reservoir Storage ────────────────────────────────────────────────────

RESERVOIR_FILE = Path(__file__).parent.parent.parent / "packages" / "data" / "topic_reservoir" / "topics.json"


def _ensure_reservoir():
    """Ensure reservoir directory and file exist."""
    RESERVOIR_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not RESERVOIR_FILE.exists():
        RESERVOIR_FILE.write_text("[]")


def _load_topics() -> list[dict]:
    """Load topics from reservoir file."""
    _ensure_reservoir()
    try:
        return json.loads(RESERVOIR_FILE.read_text())
    except Exception:
        return []


def _save_topics(topics: list[dict]):
    """Save topics to reservoir file."""
    _ensure_reservoir()
    RESERVOIR_FILE.write_text(json.dumps(topics, indent=2, ensure_ascii=False))


# ─── Request/Response Models ────────────────────────────────────────────────────

class TopicBrief(BaseModel):
    """Topic brief from reservoir."""
    id: str
    topic_statement: str
    big_question: Optional[str] = None
    genre_id: Optional[str] = None
    gap_type: Optional[str] = None
    mainstream_assumption: Optional[str] = None
    is_tier_1: bool = False
    status: str = "reservoir"
    source: Optional[str] = None
    source_url: Optional[str] = None
    created_at: Optional[str] = None
    local_relevance: Optional[str] = None


class ApproveTopicRequest(BaseModel):
    """Request to approve a topic."""
    topic_id: str
    notes: str = ""


class RejectTopicRequest(BaseModel):
    """Request to reject a topic."""
    topic_id: str
    reason: str = ""


class CustomTopicRequest(BaseModel):
    """Request to submit a custom topic."""
    topic_statement: str
    genre_id: str = "current_situation"
    big_question: str = ""
    notes: str = ""
    start_research: bool = True  # Auto-start research after creation


class CustomScriptRequest(BaseModel):
    """Request to submit a custom script."""
    title: str
    genre_id: str = "current_situation"
    script_content: str
    notes: str = ""
    skip_research: bool = True  # Skip research, go to evaluation


class TopicListResponse(BaseModel):
    """Response for topic list endpoint."""
    topics: list[dict]
    total: int
    by_status: dict[str, int]


# ─── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/reservoir")
async def get_reservoir_topics(
    status: str = "reservoir",
    genre: str = None,
    limit: int = 50,
    include_scores: bool = False
) -> TopicListResponse:
    """
    Get topics from the reservoir.
    
    Args:
        status: Filter by status (reservoir, approved, rejected, processing)
        genre: Filter by genre ID
        limit: Maximum topics to return
        include_scores: Include detailed viability scores
    
    Returns:
        List of topics with metadata
    """
    topics = _load_topics()
    
    # Filter by status
    if status != "all":
        topics = [t for t in topics if t.get("status") == status]
    
    # Filter by genre
    if genre:
        topics = [t for t in topics if t.get("genre_id") == genre]
    
    # Remove detailed scores unless requested
    if not include_scores:
        topics = [
            {k: v for k, v in t.items() if k != "scores"}
            for t in topics
        ]
    
    # Sort by creation date (newest first)
    topics.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    # Count by status
    all_topics = _load_topics()
    by_status = {}
    for t in all_topics:
        s = t.get("status", "unknown")
        by_status[s] = by_status.get(s, 0) + 1
    
    return TopicListResponse(
        topics=topics[:limit],
        total=len(topics),
        by_status=by_status
    )


@router.get("/reservoir/{topic_id}")
async def get_topic(topic_id: str) -> dict:
    """Get a single topic by ID."""
    topics = _load_topics()
    
    for topic in topics:
        if topic.get("id") == topic_id:
            return topic
    
    raise HTTPException(404, f"Topic {topic_id} not found")


@router.post("/approve")
async def approve_topic(
    request: ApproveTopicRequest,
    bg: BackgroundTasks
) -> dict:
    """
    Approve a topic for production.
    
    This will:
    1. Mark topic as approved
    2. Trigger the research phase
    3. Return the topic with updated status
    """
    topics = _load_topics()
    
    for i, topic in enumerate(topics):
        if topic.get("id") == request.topic_id:
            # Update topic
            topic["status"] = "approved"
            topic["approved_at"] = datetime.now(timezone.utc).isoformat()
            topic["user_notes"] = request.notes
            
            # Save updated topics
            topics[i] = topic
            _save_topics(topics)
            
            # Trigger research in background
            bg.add_task(start_research_for_topic, request.topic_id)
            
            return {
                "status": "approved",
                "topic_id": request.topic_id,
                "message": "Topic approved. Research will start automatically."
            }
    
    raise HTTPException(404, f"Topic {request.topic_id} not found")


@router.post("/reject")
async def reject_topic(request: RejectTopicRequest) -> dict:
    """
    Reject a topic.
    
    The topic will be marked as rejected and won't appear
    in the default reservoir view.
    """
    topics = _load_topics()
    
    for i, topic in enumerate(topics):
        if topic.get("id") == request.topic_id:
            topic["status"] = "rejected"
            topic["rejected_at"] = datetime.now(timezone.utc).isoformat()
            topic["rejection_reason"] = request.reason
            
            topics[i] = topic
            _save_topics(topics)
            
            return {
                "status": "rejected",
                "topic_id": request.topic_id
            }
    
    raise HTTPException(404, f"Topic {request.topic_id} not found")


@router.post("/custom")
async def submit_custom_topic(
    request: CustomTopicRequest,
    bg: BackgroundTasks
) -> dict:
    """
    Submit a custom topic provided by the user.
    
    This bypasses the trend scan and creates a topic
    that's immediately ready for research.
    """
    topic_id = f"custom_{uuid.uuid4().hex[:8]}"
    
    topic = {
        "id": topic_id,
        "topic_statement": request.topic_statement,
        "big_question": request.big_question or request.topic_statement,
        "genre_id": request.genre_id,
        "status": "approved",  # Pre-approved since user provided it
        "content_type": "user_provided",
        "user_notes": request.notes,
        "is_tier_1": True,  # Assume user-provided topics are good
        "created_at": datetime.now(timezone.utc).isoformat(),
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "source": "user_input",
    }
    
    topics = _load_topics()
    topics.append(topic)
    _save_topics(topics)
    
    # Trigger research in background
    bg.add_task(start_research_for_topic, topic_id)
    
    return {
        "status": "created",
        "topic_id": topic_id,
        "message": "Custom topic created and approved. Research starting."
    }


@router.post("/custom-script")
async def submit_custom_script(
    request: CustomScriptRequest,
    bg: BackgroundTasks
) -> dict:
    """
    Submit a custom script provided by the user.
    
    This bypasses research and generation phases entirely.
    The script goes directly to evaluation and refinement.
    """
    topic_id = f"script_{uuid.uuid4().hex[:8]}"
    
    # Create a topic entry
    topic = {
        "id": topic_id,
        "topic_statement": request.title,
        "big_question": request.title,
        "genre_id": request.genre_id,
        "status": "script_provided",
        "content_type": "user_script",
        "user_notes": request.notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "user_input",
    }
    
    # Create a script entry
    script_id = f"script_{uuid.uuid4().hex[:8]}"
    script = {
        "id": script_id,
        "topic_id": topic_id,
        "title": request.title,
        "content": request.script_content,
        "status": "pending_evaluation",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "iteration": 0,
        "score": None,
    }
    
    topics = _load_topics()
    topics.append(topic)
    _save_topics(topics)
    
    # Save script
    scripts_file = RESERVOIR_FILE.parent / "scripts.json"
    scripts_file.parent.mkdir(parents=True, exist_ok=True)
    
    scripts = []
    if scripts_file.exists():
        try:
            scripts = json.loads(scripts_file.read_text())
        except Exception:
            pass
    
    scripts.append(script)
    scripts_file.write_text(json.dumps(scripts, indent=2, ensure_ascii=False))
    
    # Trigger evaluation in background
    bg.add_task(evaluate_script, script_id)
    
    return {
        "status": "created",
        "topic_id": topic_id,
        "script_id": script_id,
        "message": "Custom script saved. Starting evaluation."
    }


@router.post("/rescan")
async def trigger_rescan(
    bg: BackgroundTasks,
    genres: str = None
) -> dict:
    """
    Trigger an immediate topic rescan.
    
    This runs the daily_topic_scan logic on demand.
    """
    genre_list = genres.split(",") if genres else None
    
    # Trigger scan in background
    bg.add_task(run_daily_scan, genre_list)
    
    return {
        "status": "started",
        "message": "Topic rescan started in background."
    }


@router.get("/stats")
async def get_topic_stats() -> dict:
    """Get statistics about the topic reservoir."""
    topics = _load_topics()
    
    stats = {
        "total": len(topics),
        "by_status": {},
        "by_genre": {},
        "by_source": {},
        "tier_1_count": 0,
        "approved_today": 0,
        "created_today": 0,
    }
    
    today = datetime.now(timezone.utc).date().isoformat()
    
    for topic in topics:
        # By status
        status = topic.get("status", "unknown")
        stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
        
        # By genre
        genre = topic.get("genre_id", "unknown")
        stats["by_genre"][genre] = stats["by_genre"].get(genre, 0) + 1
        
        # By source
        source = topic.get("source", "unknown")
        stats["by_source"][source] = stats["by_source"].get(source, 0) + 1
        
        # Tier 1
        if topic.get("is_tier_1"):
            stats["tier_1_count"] += 1
        
        # Today's activity
        created = topic.get("created_at", "")
        if created.startswith(today):
            stats["created_today"] += 1
        
        approved = topic.get("approved_at", "")
        if approved.startswith(today):
            stats["approved_today"] += 1
    
    return stats


@router.delete("/reservoir/{topic_id}")
async def delete_topic(topic_id: str) -> dict:
    """Permanently delete a topic from the reservoir."""
    topics = _load_topics()
    
    for i, topic in enumerate(topics):
        if topic.get("id") == topic_id:
            del topics[i]
            _save_topics(topics)
            return {"status": "deleted", "topic_id": topic_id}
    
    raise HTTPException(404, f"Topic {topic_id} not found")

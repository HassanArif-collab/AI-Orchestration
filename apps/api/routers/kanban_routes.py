"""
Kanban task management routes.

These endpoints handle the Kanban board operations for the YouTube Pipeline
dashboard. The Kanban board shows tasks in 6 columns representing different
stages of content production.

Columns:
    1. Topic Finding - Topic finder agents discovering trends
    2. Suggested Topics - Topics discovered, awaiting approval
    3. Researching - Deep research on approved topics
    4. Script - Script writing in progress
    5. Visual - Visual planning and asset creation
    6. Notion - Published to Notion, complete

SSE Events:
    All task changes are broadcast via the EventBus to connected clients.
"""

from __future__ import annotations

import json
import random
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()

# Database path for Kanban tasks
_KANBAN_DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "kanban.db"

# Default colors for tasks
DEFAULT_COLORS = ["#0066cc", "#2da44e", "#8a63d2", "#d4a017", "#d1242f", "#0969da"]


# ─── Database Helpers ───────────────────────────────────────────────────────────

def _get_db_connection() -> sqlite3.Connection:
    """Get a database connection with proper configuration."""
    _KANBAN_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_KANBAN_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_kanban_db() -> None:
    """Initialize the Kanban database schema."""
    with _get_db_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS kanban_tasks (
                id TEXT PRIMARY KEY,
                parent_id TEXT,
                title TEXT NOT NULL,
                stage INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'idle',
                color TEXT NOT NULL,
                content TEXT DEFAULT '',
                research TEXT DEFAULT '',
                script TEXT DEFAULT '',
                visual_cues TEXT DEFAULT '',
                notion_url TEXT DEFAULT '',
                thoughts TEXT DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (parent_id) REFERENCES kanban_tasks(id) ON DELETE SET NULL
            );
            
            CREATE INDEX IF NOT EXISTS idx_kanban_stage ON kanban_tasks(stage);
            CREATE INDEX IF NOT EXISTS idx_kanban_parent ON kanban_tasks(parent_id);
            CREATE INDEX IF NOT EXISTS idx_kanban_status ON kanban_tasks(status);
        """)


# ─── Internal Functions for Direct DB Access ─────────────────────────────────────

async def create_task_internal(title: str, stage: int = 1, task_id: str | None = None) -> str:
    """Create a Kanban task directly in SQLite without HTTP.
    
    Used by pipeline_routes.py to avoid fragile HTTP self-calls.
    
    Args:
        title: Task title
        stage: Kanban column (1-6)
        task_id: Optional specific ID (defaults to UUID)
        
    Returns:
        The task ID
    """
    import uuid as _uuid
    tid = task_id or str(_uuid.uuid4())
    conn = _get_db_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO kanban_tasks (id, title, stage, status, color, created_at, updated_at) VALUES (?,?,?,'idle','#1D9E75',?,?)",
            (tid, title, stage, datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
    finally:
        conn.close()
    return tid


async def update_task_internal(task_id: str, stage: int, status: str = "idle") -> None:
    """Update a Kanban task's stage and status directly in SQLite.
    
    Used by pipeline_routes.py to avoid fragile HTTP self-calls.
    
    Args:
        task_id: The task UUID
        stage: Kanban column (1-6)
        status: Task status (idle, thinking, error, complete, waiting)
    """
    conn = _get_db_connection()
    try:
        conn.execute(
            "UPDATE kanban_tasks SET stage=?, status=?, updated_at=? WHERE id=?",
            (stage, status, datetime.now(timezone.utc).isoformat(), task_id)
        )
        conn.commit()
    finally:
        conn.close()


def _task_to_dict(row: sqlite3.Row) -> dict:
    """Convert a database row to a dictionary."""
    return dict(row)


# ─── Pydantic Models ────────────────────────────────────────────────────────────

class KanbanTaskCreate(BaseModel):
    """Request model for creating a Kanban task."""
    title: str = Field(..., min_length=1, max_length=500)
    stage: int = Field(default=1, ge=1, le=6)
    parent_id: Optional[str] = None
    color: Optional[str] = Field(default=None, pattern=r'^#[0-9a-fA-F]{6}$')


class KanbanTaskUpdate(BaseModel):
    """Request model for updating a Kanban task."""
    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    stage: Optional[int] = Field(default=None, ge=1, le=6)
    status: Optional[str] = Field(default=None, pattern=r'^(idle|thinking|error|complete|waiting)$')
    content: Optional[str] = None
    research: Optional[str] = None
    script: Optional[str] = None
    visual_cues: Optional[str] = None
    notion_url: Optional[str] = None


class KanbanEvent(BaseModel):
    """Request model for posting an event from an agent."""
    task_id: str
    event_type: str = Field(..., pattern=r'^(thought|stage_change|status_change|artifact)$')
    data: Dict[str, Any]


# ─── API Endpoints ──────────────────────────────────────────────────────────────

@router.get("/tasks")
async def list_tasks(
    stage: Optional[int] = None,
    status: Optional[str] = None,
    parent_id: Optional[str] = None,
    limit: int = 100
) -> dict:
    """List all Kanban tasks with optional filtering.
    
    Args:
        stage: Filter by stage number (1-6)
        status: Filter by status (idle, thinking, error, complete, waiting)
        parent_id: Filter by parent task ID
        limit: Maximum number of tasks to return (default: 100)
        
    Returns:
        Dictionary with 'tasks' key containing list of task objects
    """
    try:
        with _get_db_connection() as conn:
            query = "SELECT * FROM kanban_tasks WHERE 1=1"
            params = []
            
            if stage is not None:
                query += " AND stage = ?"
                params.append(stage)
            if status is not None:
                query += " AND status = ?"
                params.append(status)
            if parent_id is not None:
                query += " AND parent_id = ?"
                params.append(parent_id)
            
            query += " ORDER BY updated_at DESC LIMIT ?"
            params.append(limit)
            
            rows = conn.execute(query, params).fetchall()
            return {"tasks": [_task_to_dict(r) for r in rows]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@router.post("/tasks")
async def create_task(data: KanbanTaskCreate) -> dict:
    """Create a new Kanban task.
    
    Creates a task in the specified stage with automatic color assignment.
    If parent_id is provided and color is not, inherits parent's color.
    
    Args:
        data: Task creation parameters
        
    Returns:
        The created task object
    """
    task_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    # Determine color
    color = data.color
    if not color and data.parent_id:
        # Try to inherit color from parent
        try:
            with _get_db_connection() as conn:
                parent = conn.execute(
                    "SELECT color FROM kanban_tasks WHERE id = ?",
                    (data.parent_id,)
                ).fetchone()
                if parent:
                    color = parent["color"]
        except Exception:
            pass
    if not color:
        color = random.choice(DEFAULT_COLORS)
    
    try:
        with _get_db_connection() as conn:
            conn.execute(
                """INSERT INTO kanban_tasks 
                   (id, parent_id, title, stage, status, color, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'idle', ?, ?, ?)""",
                (task_id, data.parent_id, data.title, data.stage, color, now, now)
            )
        
        # Broadcast event
        await _broadcast_event("task_created", {
            "id": task_id,
            "parent_id": data.parent_id,
            "title": data.title,
            "stage": data.stage,
            "color": color,
            "updated_at": now
        })
        
        return {
            "id": task_id,
            "parent_id": data.parent_id,
            "title": data.title,
            "stage": data.stage,
            "status": "idle",
            "color": color,
            "updated_at": now
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create task: {e}")


@router.get("/tasks/{task_id}")
async def get_task(task_id: str) -> dict:
    """Get a single Kanban task by ID.
    
    Args:
        task_id: The UUID of the task
        
    Returns:
        The task object with all fields including thoughts array
    """
    try:
        with _get_db_connection() as conn:
            row = conn.execute(
                "SELECT * FROM kanban_tasks WHERE id = ?",
                (task_id,)
            ).fetchone()
            
            if not row:
                raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
            
            return _task_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@router.patch("/tasks/{task_id}")
async def update_task(task_id: str, data: KanbanTaskUpdate) -> dict:
    """Update a Kanban task.
    
    Only provided fields are updated. Automatically updates updated_at.
    
    Args:
        task_id: The UUID of the task
        data: Fields to update
        
    Returns:
        The updated task object
    """
    updates = data.dict(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    try:
        with _get_db_connection() as conn:
            # Check task exists
            existing = conn.execute(
                "SELECT id FROM kanban_tasks WHERE id = ?",
                (task_id,)
            ).fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
            
            # Build update query
            set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
            values = list(updates.values()) + [task_id]
            
            conn.execute(
                f"UPDATE kanban_tasks SET {set_clause} WHERE id = ?",
                values
            )
            
            # Get updated task
            row = conn.execute(
                "SELECT * FROM kanban_tasks WHERE id = ?",
                (task_id,)
            ).fetchone()
            
            updated_task = _task_to_dict(row)
        
        # Broadcast event
        await _broadcast_event("task_updated", updated_task)
        
        return updated_task
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update task: {e}")


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str) -> dict:
    """Delete a Kanban task.
    
    Also broadcasts a deletion event so connected clients can update.
    
    Args:
        task_id: The UUID of the task
        
    Returns:
        Success confirmation
    """
    try:
        with _get_db_connection() as conn:
            # Check task exists
            existing = conn.execute(
                "SELECT id FROM kanban_tasks WHERE id = ?",
                (task_id,)
            ).fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
            
            conn.execute("DELETE FROM kanban_tasks WHERE id = ?", (task_id,))
        
        # Broadcast event
        await _broadcast_event("task_deleted", {"id": task_id})
        
        return {"success": True, "deleted_id": task_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete task: {e}")


@router.post("/events")
async def report_event(event: KanbanEvent) -> dict:
    """Report an agent event to update a Kanban task.
    
    This is the main endpoint agents use to report progress. It handles:
    - thought: Appends to the thoughts array (agent monologue)
    - stage_change: Moves task to a different column
    - status_change: Updates task status (idle/thinking/error/complete)
    - artifact: Updates an output field (research/script/visual_cues/notion_url)
    
    Args:
        event: The event object with task_id, event_type, and data
        
    Returns:
        Success confirmation
    """
    try:
        with _get_db_connection() as conn:
            # Check task exists
            existing = conn.execute(
                "SELECT id, thoughts FROM kanban_tasks WHERE id = ?",
                (event.task_id,)
            ).fetchone()
            if not existing:
                raise HTTPException(
                    status_code=404, 
                    detail=f"Task {event.task_id} not found"
                )
            
            now = datetime.now(timezone.utc).isoformat()
            
            if event.event_type == "thought":
                # Append to thoughts array
                thoughts = json.loads(existing["thoughts"] or "[]")
                thoughts.append({
                    "timestamp": now,
                    "content": event.data.get("content", "")
                })
                # Keep last 50 thoughts
                thoughts = thoughts[-50:]
                conn.execute(
                    "UPDATE kanban_tasks SET thoughts = ?, updated_at = ? WHERE id = ?",
                    (json.dumps(thoughts), now, event.task_id)
                )
            
            elif event.event_type == "stage_change":
                stage = event.data.get("stage")
                if not isinstance(stage, int) or not 1 <= stage <= 6:
                    raise HTTPException(
                        status_code=400,
                        detail="stage must be an integer between 1 and 6"
                    )
                conn.execute(
                    "UPDATE kanban_tasks SET stage = ?, updated_at = ? WHERE id = ?",
                    (stage, now, event.task_id)
                )
            
            elif event.event_type == "status_change":
                status = event.data.get("status")
                valid_statuses = {"idle", "thinking", "error", "complete", "waiting"}
                if status not in valid_statuses:
                    raise HTTPException(
                        status_code=400,
                        detail=f"status must be one of: {valid_statuses}"
                    )
                conn.execute(
                    "UPDATE kanban_tasks SET status = ?, updated_at = ? WHERE id = ?",
                    (status, now, event.task_id)
                )
            
            elif event.event_type == "artifact":
                key = event.data.get("key")
                value = event.data.get("value")
                valid_keys = {"research", "script", "visual_cues", "notion_url", "content"}
                if key not in valid_keys:
                    raise HTTPException(
                        status_code=400,
                        detail=f"artifact key must be one of: {valid_keys}"
                    )
                conn.execute(
                    f"UPDATE kanban_tasks SET {key} = ?, updated_at = ? WHERE id = ?",
                    (value, now, event.task_id)
                )
        
        # Broadcast event to connected clients
        await _broadcast_event("agent_event", {
            "task_id": event.task_id,
            "event_type": event.event_type,
            "data": event.data,
            "timestamp": now
        })
        
        return {"success": True}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process event: {e}")


@router.get("/stats")
async def get_stats() -> dict:
    """Get statistics about the Kanban board.
    
    Returns counts by stage and status for dashboard overview.
    """
    try:
        with _get_db_connection() as conn:
            # Count by stage
            stage_counts = {}
            for i in range(1, 7):
                count = conn.execute(
                    "SELECT COUNT(*) FROM kanban_tasks WHERE stage = ?",
                    (i,)
                ).fetchone()[0]
                stage_counts[i] = count
            
            # Count by status
            status_counts = {}
            for status in ["idle", "thinking", "error", "complete", "waiting"]:
                count = conn.execute(
                    "SELECT COUNT(*) FROM kanban_tasks WHERE status = ?",
                    (status,)
                ).fetchone()[0]
                status_counts[status] = count
            
            # Total count
            total = conn.execute("SELECT COUNT(*) FROM kanban_tasks").fetchone()[0]
            
            return {
                "total_tasks": total,
                "by_stage": stage_counts,
                "by_status": status_counts
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


# ─── Event Broadcasting ────────────────────────────────────────────────────────

async def _broadcast_event(event_type: str, data: dict) -> None:
    """Broadcast an event to all SSE subscribers.
    
    Uses the main app's EventBus for real-time updates.
    """
    try:
        from apps.api.events import event_bus
        await event_bus.publish(event_type, data)
    except ImportError:
        # EventBus not available (e.g., during testing)
        pass


# ─── Topic Finder Integration ────────────────────────────────────────────────────

class TopicFinderRequest(BaseModel):
    """Request model for triggering Topic Finder."""
    seed_query: str = Field(..., min_length=3, max_length=500)
    genre_id: str = Field(default="default", max_length=50)


@router.post("/topic-finder")
async def trigger_topic_finder(data: TopicFinderRequest) -> dict:
    """Trigger the Topic Finder agent to discover new topics.
    
    This endpoint:
    1. Creates a Kanban task in Stage 1 (Topic Finding)
    2. Launches the TopicFinderAgent in the background
    3. Returns the task ID immediately for SSE tracking
    
    The agent will report progress via the Kanban callback system,
    and any Tier 1 topics found will appear in Stage 2 (Suggested Topics).
    
    Args:
        data: Topic finder parameters (seed_query, genre_id)
        
    Returns:
        The created task ID and status
    """
    from fastapi import BackgroundTasks
    import asyncio
    
    # Create the Kanban task first
    task_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    color = random.choice(DEFAULT_COLORS)
    
    try:
        with _get_db_connection() as conn:
            conn.execute(
                """INSERT INTO kanban_tasks 
                   (id, title, stage, status, color, created_at, updated_at)
                   VALUES (?, ?, 1, 'thinking', ?, ?, ?)""",
                (task_id, f"Finding: {data.seed_query[:50]}...", color, now, now)
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create task: {e}")
    
    # Broadcast task creation
    await _broadcast_event("task_created", {
        "id": task_id,
        "title": f"Finding: {data.seed_query[:50]}...",
        "stage": 1,
        "status": "thinking",
        "color": color,
        "updated_at": now
    })
    
    # Launch the topic finder in background
    async def run_topic_finder():
        """Background task to run the TopicFinderAgent."""
        try:
            from packages.content_factory.topic_finder.finder import TopicFinderAgent
            
            agent = TopicFinderAgent(kanban_task_id=task_id)
            brief = await agent.generate_candidate(data.seed_query, data.genre_id)
            
            if brief:
                # Update task with the found topic
                with _get_db_connection() as conn:
                    conn.execute(
                        """UPDATE kanban_tasks 
                           SET title = ?, status = 'complete', updated_at = ?
                           WHERE id = ?""",
                        (brief.topic_statement[:100], datetime.now(timezone.utc).isoformat(), task_id)
                    )
                
                await _broadcast_event("task_updated", {
                    "id": task_id,
                    "title": brief.topic_statement[:100],
                    "status": "complete"
                })
            else:
                # No topic found
                with _get_db_connection() as conn:
                    conn.execute(
                        """UPDATE kanban_tasks 
                           SET status = 'complete', content = 'No viable topic found'
                           WHERE id = ?""",
                        (task_id,)
                    )
                
                await _broadcast_event("task_updated", {
                    "id": task_id,
                    "status": "complete",
                    "content": "No viable topic found"
                })
                
        except Exception as e:
            # Update task to error state
            try:
                with _get_db_connection() as conn:
                    conn.execute(
                        """UPDATE kanban_tasks 
                           SET status = 'error', content = ?
                           WHERE id = ?""",
                        (str(e)[:500], task_id)
                    )
                
                await _broadcast_event("task_updated", {
                    "id": task_id,
                    "status": "error"
                })
            except Exception:
                pass
    
    # Schedule the background task
    try:
        asyncio.create_task(run_topic_finder())
    except Exception as e:
        # If we can't schedule the background task, still return the task ID
        pass
    
    return {
        "id": task_id,
        "status": "thinking",
        "message": f"Topic finder started for: {data.seed_query}"
    }


# ─── Initialization ─────────────────────────────────────────────────────────────

# Initialize database on module load
init_kanban_db()

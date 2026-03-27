"""
KanbanCallbackHandler - Bridge between agents and Kanban dashboard.

Provides methods for agents to report progress, thoughts, and artifacts
to the Kanban task management system.

Usage:
    async with KanbanCallbackHandler(task_id="abc-123") as callback:
        await callback.on_thought("Analyzing topic viability...")
        await callback.on_stage_change(3)  # Move to Researching
        await callback.on_artifact("research", research_content)
"""

import httpx
import json
from typing import Optional, Any, List, Dict
from packages.core.logger import get_logger

logger = get_logger(__name__)

# Stage mapping: pipeline stage -> kanban column (1-6)
PIPELINE_TO_KANBAN_STAGE = {
    "trend_analysis": 1,        # Topic Finding
    "human_topic_approval": 2,  # Suggested Topics
    "research": 3,              # Researching
    "script_writing": 4,        # Script
    "visual_planning": 5,       # Visual
    "seo": 4,                   # Script (parallel)
    "human_review": 5,          # Visual (review)
    "asset_creation": 6,        # Notion
    "publish": 6,               # Notion (with URL)
}

# Valid Kanban stages
VALID_KANBAN_STAGES = {1, 2, 3, 4, 5, 6}

# Valid status values
VALID_STATUSES = {"idle", "thinking", "error", "complete", "waiting"}

# Valid artifact keys
VALID_ARTIFACT_KEYS = {"research", "script", "visual_cues", "notion_url", "content"}


class KanbanCallbackHandler:
    """Bridge between CrewAI agents and the Kanban dashboard.
    
    This class provides a clean interface for agents to report their
    progress to the Kanban task management system. It handles all
    HTTP communication with the Kanban API and provides proper error
    handling and logging.
    
    Attributes:
        task_id: The UUID of the Kanban task this handler is associated with
        base_url: The base URL of the Kanban API server
        
    Example:
        ```python
        async with KanbanCallbackHandler(task_id="abc-123") as callback:
            await callback.on_thought("Starting research...")
            await callback.on_status_change("thinking")
            
            # ... do work ...
            
            await callback.on_artifact("research", research_content)
            await callback.on_status_change("idle")
        ```
    """
    
    def __init__(
        self, 
        task_id: str,
        base_url: str = "http://localhost:3000"
    ):
        """Initialize the callback handler.
        
        Args:
            task_id: The UUID of the Kanban task
            base_url: The base URL of the API server (default: localhost:3000)
        """
        self.task_id = task_id
        self.base_url = base_url.rstrip('/')
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self) -> "KanbanCallbackHandler":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(timeout=30.0)
        return self
    
    async def __aexit__(self, *args) -> None:
        """Async context manager exit - cleanup client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure we have an HTTP client."""
        if not self._client:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client
    
    async def _post_event(self, event_type: str, data: dict) -> bool:
        """Post an event to the Kanban API.
        
        This is the internal method that handles all HTTP communication.
        It includes proper error handling and logging.
        
        Args:
            event_type: The type of event (thought, stage_change, etc.)
            data: The event data payload
            
        Returns:
            True if the event was posted successfully, False otherwise
        """
        client = self._ensure_client()
        
        try:
            response = await client.post(
                f"{self.base_url}/api/kanban/events",
                json={
                    "task_id": self.task_id,
                    "event_type": event_type,
                    "data": data
                }
            )
            
            if response.status_code == 200:
                logger.debug(f"kanban_event_sent: {event_type} for task {self.task_id[:8]}")
                return True
            else:
                logger.warning(
                    f"kanban_event_failed: {event_type} - "
                    f"status {response.status_code}: {response.text[:100]}"
                )
                return False
                
        except httpx.TimeoutException:
            logger.warning(f"kanban_event_timeout: {event_type}")
            return False
        except Exception as e:
            logger.warning(f"kanban_event_error: {event_type} - {e}")
            return False
    
    async def on_thought(self, thought: str, metadata: Optional[dict] = None) -> bool:
        """Report an agent thought/monologue.
        
        Thoughts appear in the task drawer's "Agent Monologue" section
        in real-time as the agent works.
        
        Args:
            thought: The thought/monologue text to report
            metadata: Optional additional metadata to include
            
        Returns:
            True if the thought was reported successfully
        """
        data = {"content": thought}
        if metadata:
            data.update(metadata)
        return await self._post_event("thought", data)
    
    async def on_stage_change(self, stage: int) -> bool:
        """Report task moving to a new stage.
        
        This will move the task card to a different Kanban column.
        Stages are numbered 1-6:
            1. Topic Finding
            2. Suggested Topics
            3. Researching
            4. Script
            5. Visual
            6. Notion
            
        Args:
            stage: The new stage number (1-6)
            
        Returns:
            True if the stage change was reported successfully
        """
        if stage not in VALID_KANBAN_STAGES:
            logger.warning(f"invalid_kanban_stage: {stage} (must be 1-6)")
            return False
        
        return await self._post_event("stage_change", {"stage": stage})
    
    async def on_status_change(self, status: str) -> bool:
        """Report status change.
        
        Valid statuses:
            - idle: Task is waiting, not actively processing
            - thinking: Agent is actively working on this task
            - error: Task encountered an error
            - complete: Task is finished
            - waiting: Task is waiting for human input
            
        Args:
            status: The new status value
            
        Returns:
            True if the status change was reported successfully
        """
        if status not in VALID_STATUSES:
            logger.warning(f"invalid_kanban_status: {status}")
            return False
        
        return await self._post_event("status_change", {"status": status})
    
    async def on_artifact(self, key: str, value: str) -> bool:
        """Report artifact output.
        
        Artifacts are the outputs produced by agents at each stage.
        Valid keys:
            - research: Research content (stage 3)
            - script: Script content (stage 4)
            - visual_cues: Visual planning notes (stage 5)
            - notion_url: URL to published Notion page (stage 6)
            - content: General content field
            
        Args:
            key: The artifact key (research, script, visual_cues, notion_url, content)
            value: The artifact content/value
            
        Returns:
            True if the artifact was reported successfully
        """
        if key not in VALID_ARTIFACT_KEYS:
            logger.warning(f"invalid_artifact_key: {key}")
            return False
        
        return await self._post_event("artifact", {"key": key, "value": value})
    
    async def create_child_task(
        self, 
        title: str, 
        stage: int = 2,
        color: Optional[str] = None
    ) -> Optional[str]:
        """Create a child task (e.g., suggested topic from topic finder).
        
        Child tasks inherit the parent's color if not specified.
        This is used when TopicFinderAgent discovers new topics.
        
        Args:
            title: The title for the new task
            stage: The stage for the new task (default: 2 for Suggested Topics)
            color: Optional hex color code (e.g., "#0066cc")
            
        Returns:
            The new task ID or None on failure
        """
        client = self._ensure_client()
        
        try:
            response = await client.post(
                f"{self.base_url}/api/kanban/tasks",
                json={
                    "title": title,
                    "stage": stage,
                    "parent_id": self.task_id,
                    "color": color
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                new_id = data.get("id")
                logger.info(f"kanban_child_task_created: {new_id[:8]} -> stage {stage}")
                return new_id
            else:
                logger.warning(f"create_child_task_failed: status {response.status_code}")
                return None
                
        except Exception as e:
            logger.warning(f"create_child_task_error: {e}")
            return None
    
    async def update_title(self, title: str) -> bool:
        """Update the task title.
        
        Args:
            title: The new title for the task
            
        Returns:
            True if successful
        """
        client = self._ensure_client()
        
        try:
            response = await client.patch(
                f"{self.base_url}/api/kanban/tasks/{self.task_id}",
                json={"title": title}
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"update_title_error: {e}")
            return False
    
    async def delete_task(self) -> bool:
        """Delete this task.
        
        Returns:
            True if successful
        """
        client = self._ensure_client()
        
        try:
            response = await client.delete(
                f"{self.base_url}/api/kanban/tasks/{self.task_id}"
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"delete_task_error: {e}")
            return False


async def create_kanban_task(
    title: str,
    stage: int = 1,
    base_url: str = "http://localhost:3000",
    color: Optional[str] = None
) -> Optional[str]:
    """Create a new Kanban task.
    
    This is a convenience function for creating a Kanban task
    without needing to instantiate a handler.
    
    Args:
        title: The task title
        stage: The initial stage (1-6, default: 1 for Topic Finding)
        base_url: The API server URL
        color: Optional hex color code
        
    Returns:
        The new task ID or None on failure
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{base_url.rstrip('/')}/api/kanban/tasks",
                json={
                    "title": title,
                    "stage": stage,
                    "color": color
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                task_id = data.get("id")
                logger.info(f"kanban_task_created: {task_id[:8]} - '{title[:30]}'")
                return task_id
            else:
                logger.warning(f"create_kanban_task_failed: status {response.status_code}")
                return None
                
        except Exception as e:
            logger.warning(f"create_kanban_task_error: {e}")
            return None


def get_kanban_stage(pipeline_stage: str) -> int:
    """Convert a pipeline stage name to Kanban column number.
    
    Args:
        pipeline_stage: The pipeline stage name (e.g., "research")
        
    Returns:
        The corresponding Kanban stage number (1-6), defaults to 1
    """
    return PIPELINE_TO_KANBAN_STAGE.get(pipeline_stage, 1)

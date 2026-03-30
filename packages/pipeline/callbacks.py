"""
Kanban callback handlers for pipeline agents.

Allows agents to report thoughts and stage changes to the Kanban board.
"""

from __future__ import annotations

import httpx
from typing import Any, Dict, Optional

from packages.core.config import get_settings
from packages.core.logger import get_logger

logger = get_logger(__name__)

class KanbanCallbackHandler:
    """Sends pipeline events to the Kanban API."""
    
    def __init__(self, run_id: str):
        self.run_id = run_id
        settings = get_settings()
        # Internal API call to the same process
        self.api_url = f"http://localhost:3000/api/kanban/events"
    
    async def on_thought(self, text: str, stage: Optional[str] = None) -> None:
        """Report an agent thought."""
        payload = {
            "task_id": self.run_id,
            "event_type": "thought",
            "data": {
                "text": text,
                "stage": stage
            }
        }
        await self._send(payload)
    
    async def on_stage_change(self, stage: str, status: str) -> None:
        """Report a stage status change."""
        payload = {
            "task_id": self.run_id,
            "event_type": "stage_change",
            "data": {
                "stage": stage,
                "status": status
            }
        }
        await self._send(payload)

    async def _send(self, payload: Dict[str, Any]) -> None:
        """Send event to the API."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                await client.post(self.api_url, json=payload)
        except Exception as e:
            # Non-blocking failure
            logger.warning(f"kanban_callback_failed: {e}")

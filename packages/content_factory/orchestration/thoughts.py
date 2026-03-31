"""Thought Streaming Infrastructure for LangGraph Pipeline.

This is the UX backbone. Every node reports what it's doing to Supabase.
The React frontend (Phase 5) subscribes to these via WebSocket and renders
them as the live "thinking" drawer.

Key features:
1. report_thought() - Write a thought to Supabase agent_thoughts table
2. update_card_stage() - Move the Kanban card to the correct column
3. @pipeline_node decorator - Automatic thought reporting, error capture, and Kanban updates

CRITICAL: All functions must NEVER crash the pipeline.
If Supabase is down, we log locally and continue.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from functools import wraps
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# Maps stages to Kanban columns so the card moves automatically
STAGE_TO_COLUMN = {
    "discovering": 1,
    "grading": 1,
    "suggested": 2,
    "researching": 3,
    "drafting": 4,
    "scoring": 4,
    "mutating": 4,
    "visuals": 5,
    "review": 5,
    "publishing": 6,
    "complete": 6,
    "completed": 6,  # C12 compat: PipelineRunner uses "completed"
    "error": None,  # Don't move on error
}

# Agent display colors (frontend uses these for rendering)
AGENT_COLORS = {
    "topic_finder": "blue",
    "researcher": "green",
    "script_writer": "purple",
    "scorer": "orange",
    "challenger": "red",
    "visual_annotator": "cyan",
    "system": "gray",
    "notion_publisher": "indigo",
}


async def report_thought(
    card_id: str,
    agent_name: str,
    thought: str,
    thought_type: str = "info",  # "info", "thinking", "error", "success", "milestone"
    metadata: dict = None,
) -> bool:
    """
    Write a thought to Supabase agent_thoughts table.
    
    The React frontend subscribes to INSERTs on this table via WebSocket.
    
    CRITICAL: This function must NEVER crash the pipeline.
    If Supabase is down, we log locally and continue.
    
    Args:
        card_id: The Kanban card ID this thought belongs to
        agent_name: Name of the agent generating the thought
        thought: The thought content (displayed in the drawer)
        thought_type: Category for styling (info, thinking, error, success, milestone)
        metadata: Optional additional data (scores, counts, etc.)
    
    Returns:
        True if successfully written, False otherwise
    """
    try:
        from packages.core.supabase_client import get_supabase
        sb = get_supabase()
        
        sb.table("agent_thoughts").insert({
            "card_id": card_id,
            "agent_name": agent_name,
            "thought_type": thought_type,
            "content": thought,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
        
        logger.debug(f"thought_reported: agent={agent_name} type={thought_type}")
        return True
        
    except Exception as e:
        # NEVER crash the pipeline because of thought streaming
        logger.warning(f"Thought stream failed (non-fatal): {e}")
        return False


async def update_card_stage(card_id: str, stage: str) -> bool:
    """
    Move the Kanban card to the correct column based on pipeline stage.
    Called at the START of each node so the UI updates immediately.
    
    Args:
        card_id: The Kanban card ID
        stage: Current pipeline stage (maps to Kanban column)
    
    Returns:
        True if successfully updated, False otherwise
    """
    column = STAGE_TO_COLUMN.get(stage)
    if column is None:
        logger.debug(f"update_card_stage: No column mapping for stage '{stage}'")
        return False
        
    try:
        from packages.core.supabase_client import get_supabase
        sb = get_supabase()
        
        sb.table("kanban_cards").update({
            "column": column,
            "status": stage,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", card_id).execute()
        
        logger.debug(f"card_stage_updated: card={card_id} stage={stage} column={column}")
        return True
        
    except Exception as e:
        logger.warning(f"Card stage update failed (non-fatal): {e}")
        return False


def pipeline_node(agent_name: str) -> Callable:
    """
    Decorator that wraps every LangGraph node with:
    1. Automatic "starting" thought
    2. Automatic Kanban column update
    3. Exception capture → writes error to state instead of crashing
    4. Automatic "completed" thought
    
    Usage:
        @pipeline_node("researcher")
        async def research_node(state: ProductionState) -> dict:
            # ... do research work ...
            return {"research_dossier": "...", "pipeline_status": "researching"}
    
    The decorator handles all thought reporting and error handling automatically.
    Nodes should focus purely on their logic and return state updates.
    
    Args:
        agent_name: Name of the agent (used for thought reporting and coloring)
    
    Returns:
        Decorated function that wraps the node with thought streaming
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(state: dict) -> dict:
            card_id = state.get("card_id", "unknown")
            stage = state.get("pipeline_status", agent_name)
            
            # Report start
            await report_thought(
                card_id, agent_name, 
                f"Starting {agent_name}...", 
                "thinking"
            )
            await update_card_stage(card_id, stage)
            
            try:
                result = await func(state)
                
                # Ensure result is a dict
                if result is None:
                    result = {}
                
                # Report completion
                await report_thought(
                    card_id, agent_name, 
                    f"✅ {agent_name} complete", 
                    "success"
                )
                return result
                
            except Exception as e:
                error_msg = f"{agent_name} failed: {type(e).__name__}: {str(e)}"
                await report_thought(
                    card_id, agent_name, 
                    f"❌ {error_msg}", 
                    "error"
                )
                # Return error in state — don't raise
                # The conditional edge will route to error_handler
                return {
                    "error": error_msg,
                    "pipeline_status": "error",
                }
                
        return wrapper
    return decorator


async def report_milestone(
    card_id: str,
    agent_name: str,
    message: str,
    metadata: dict = None,
) -> bool:
    """
    Report a milestone achievement (e.g., new best score, iteration complete).
    
    Milestones are highlighted differently in the UI to show progress points.
    
    Args:
        card_id: The Kanban card ID
        agent_name: Agent reporting the milestone
        message: Milestone message
        metadata: Optional data (scores, counts, etc.)
    
    Returns:
        True if successfully written, False otherwise
    """
    return await report_thought(
        card_id, agent_name, message, "milestone", metadata
    )


async def report_error(
    card_id: str,
    agent_name: str,
    error_message: str,
    metadata: dict = None,
) -> bool:
    """
    Report an error condition.
    
    Errors are highlighted in red in the UI.
    
    Args:
        card_id: The Kanban card ID
        agent_name: Agent that encountered the error
        error_message: Error description
        metadata: Optional error details
    
    Returns:
        True if successfully written, False otherwise
    """
    return await report_thought(
        card_id, agent_name, f"❌ {error_message}", "error", metadata
    )

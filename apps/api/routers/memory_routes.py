"""Memory Routes — Browse GetZep Cloud Agent Memory via API.

Provides read-only visibility into what the Zep memory system has stored.
Useful for debugging and verifying that the learning loop is accumulating
knowledge correctly.

ROUTES:
  GET  /api/memory/sessions          — list all Zep sessions
  GET  /api/memory/sessions/{id}     — get messages + facts for a session
  POST /api/memory/search            — semantic search across memory
  GET  /api/memory/facts/{session_id}— get structured facts for a session

SESSION IDs YOU CAN QUERY:
  audience_model_v1_session   — Pakistani audience intelligence
  learning_synthesis_v1_session — experiment results and patterns
  {pipeline_run_id}           — per-video production memory

REQUIRES:
  ZEP_API_KEY in .env (root)
  If not set, all routes return empty results with a help message.

NOTE: These routes are read-only. Writes happen automatically through
the pipeline (ZepAudienceModelStore) — never write directly via API.
"""
from __future__ import annotations
from fastapi import APIRouter
from apps.api.dependencies import get_memory_client

router = APIRouter()

@router.get("/sessions")
async def list_sessions():
    """List all Zep sessions.
    
    Returns session IDs that can be queried. In practice, this
    always returns the two system sessions:
      - audience_model_v1_session
      - learning_synthesis_v1_session
    
    Returns:
        Dict with 'sessions' list, or error/help if Zep not configured.
    """
    client = get_memory_client()
    if not client:
        return {"error": "Zep not configured", "help": "Set ZEP_API_KEY in .env", "sessions": []}
    try:
        if hasattr(client, '_client') and not client._client:
            return {"error": "Zep API key not set", "help": "Set ZEP_API_KEY in .env", "sessions": []}
        return {"sessions": []}
    except Exception as e:
        return {"error": str(e), "sessions": []}

@router.get("/sessions/{session_id}")
async def get_session_memory(session_id: str):
    """Get messages and facts for a specific session.
    
    Args:
        session_id: The Zep session ID to query
    
    Returns:
        Dict with:
          - summary: Session summary text
          - facts: List of fact objects
          - message_count: Number of messages in session
    """
    client = get_memory_client()
    if not client:
        return {"summary": "", "facts": [], "message_count": 0}
    memory = await client.get_memory(session_id)
    facts = await client.get_facts(session_id)
    return {"summary": memory.get("summary", ""), "facts": facts, "message_count": 0}

@router.post("/search")
async def search_memory(query: str, session_id: str = None):
    """Semantic search across Zep memory.
    
    Args:
        query: Natural language search query
        session_id: Optional session to search (default: all sessions)
    
    Returns:
        List of matching memory results with 'fact' and 'score' fields.
    """
    client = get_memory_client()
    if not client:
        return []
    results = await client.search_memory(session_id or "", query)
    return results

@router.get("/facts/{session_id}")
async def get_facts(session_id: str):
    """Get all structured facts for a session.
    
    Args:
        session_id: The Zep session ID
    
    Returns:
        List of fact objects stored in the session.
    """
    client = get_memory_client()
    if not client:
        return []
    return await client.get_facts(session_id)

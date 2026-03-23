"""memory_routes.py — Browse GetZep Cloud agent memory."""
from __future__ import annotations
from fastapi import APIRouter
from apps.api.dependencies import get_memory_client

router = APIRouter()

@router.get("/sessions")
async def list_sessions():
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
    client = get_memory_client()
    if not client:
        return {"summary": "", "facts": [], "message_count": 0}
    memory = await client.get_memory(session_id)
    facts = await client.get_facts(session_id)
    return {"summary": memory.get("summary", ""), "facts": facts, "message_count": 0}

@router.post("/search")
async def search_memory(query: str, session_id: str = None):
    client = get_memory_client()
    if not client:
        return []
    results = await client.search_memory(session_id or "", query)
    return results

@router.get("/facts/{session_id}")
async def get_facts(session_id: str):
    client = get_memory_client()
    if not client:
        return []
    return await client.get_facts(session_id)

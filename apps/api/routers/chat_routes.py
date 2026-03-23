"""
chat_routes.py — Chat and conversation management using freerouter internals.

Uses freerouter.router (Router class) and freerouter.storage directly.
No HTTP proxy to :8080 needed. The Router still calls :4000 for LLM calls,
but that's handled internally by get_router().

Streaming: Router.stream() is an async generator — we wrap it in
StreamingResponse exactly as FreeRouter's web/app.py does.
"""

from __future__ import annotations
import json
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter()


class ChatRequest(BaseModel):
    model: str = "auto"
    messages: list[dict[str, Any]]
    temperature: float = 0.7
    max_tokens: int = 4096
    provider: Optional[str] = None


@router.post("/stream")
async def chat_stream(data: ChatRequest):
    """
    Streaming chat using FreeRouter's Router directly.
    Returns SSE stream of OpenAI-compatible chunks + meta chunk with provider info.
    """
    try:
        from freerouter.router import get_router, RouterError
        rtr = get_router()

        async def generate():
            try:
                async for chunk in rtr.stream(
                    messages=data.messages,
                    model=data.model,
                    temperature=data.temperature,
                    max_tokens=data.max_tokens,
                    provider=data.provider,
                ):
                    yield chunk
            except RouterError as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': f'Internal error: {e}'})}\n\n"
                yield "data: [DONE]\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except ImportError:
        async def err():
            yield f"data: {json.dumps({'error': 'FreeRouter not available'})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(err(), media_type="text/event-stream")


@router.get("/models")
async def get_models():
    """List available models from all configured providers."""
    try:
        from freerouter.router import get_router
        models = await get_router().list_models()
        return {"models": models}
    except Exception as e:
        return {"models": [], "error": str(e)}


@router.get("/conversations")
async def list_conversations():
    """List all conversations from FreeRouter's SQLite storage."""
    try:
        from freerouter.storage import list_conversations as _list
        return {"conversations": _list()}
    except Exception as e:
        return {"conversations": [], "error": str(e)}


@router.post("/conversations")
async def create_conversation(data: dict = {}):
    """Create a new conversation."""
    try:
        from freerouter.storage import create_conversation as _create
        conv = _create(
            title=data.get("title", "New Chat"),
            model=data.get("model", ""),
        )
        return {"id": conv["id"]}
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@router.get("/conversations/{cid}")
async def get_conversation(cid: str):
    """Get a conversation with all its messages."""
    try:
        from freerouter.storage import get_conversation as _get
        conv = _get(cid)
        if not conv:
            raise HTTPException(404, "Conversation not found")
        return conv
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@router.delete("/conversations/{cid}")
async def delete_conversation(cid: str):
    """Delete a conversation."""
    try:
        from freerouter.storage import delete_conversation as _del
        ok = _del(cid)
        if not ok:
            raise HTTPException(404, "Conversation not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@router.post("/conversations/{cid}/messages")
async def add_message(cid: str, data: dict):
    """Add a message to a conversation."""
    try:
        from freerouter.storage import add_message as _add
        msg = _add(
            cid=cid,
            role=data.get("role", "user"),
            content=data.get("content", ""),
            provider=data.get("provider", ""),
            model=data.get("model", ""),
        )
        if not msg:
            raise HTTPException(404, "Conversation not found")
        return {"success": True, "message": msg}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=str(e))

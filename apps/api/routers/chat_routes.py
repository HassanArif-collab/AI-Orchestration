"""
chat_routes.py — Chat and conversation management with LangGraph ReAct agent.

This replaces the old FreeRouter-direct chat with a tool-calling agent
that can query the pipeline, search memory, look up YouTube data, etc.

The agent uses LangGraph's prebuilt ReAct pattern with:
- Streaming response via SSE
- Conversation history via LangGraph checkpointer
- Tool call visibility in the UI
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

# Module-level agent — initialized at startup
_chat_agent = None


async def init_chat_agent():
    """Initialize the chat agent at app startup."""
    global _chat_agent
    try:
        from packages.content_factory.chat.agent import build_chat_agent
        _chat_agent = await build_chat_agent()
        if _chat_agent:
            logger.info("chat_agent_initialized")
        else:
            logger.warning("chat_agent_unavailable")
    except Exception as e:
        logger.error(f"chat_agent_init_failed: {e}")
        _chat_agent = None


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None  # Reuse for conversation continuity


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    tools_used: list[str]


@router.post("/message", response_model=ChatResponse)
async def chat_message(body: ChatRequest):
    """
    Send a message to the chat agent and get a response.

    The agent will:
    1. Analyze the question
    2. Decide which tools to call (if any)
    3. Execute tools and gather data
    4. Formulate a response

    Conversation history is preserved per session_id via LangGraph checkpointer.
    """
    if _chat_agent is None:
        raise HTTPException(503, "Chat agent not initialized yet")

    session_id = body.session_id or str(uuid4())
    config = {"configurable": {"thread_id": session_id}}

    try:
        result = await _chat_agent.ainvoke(
            {"messages": [{"role": "user", "content": body.message}]},
            config=config,
        )

        # Extract the final response
        messages = result.get("messages", [])
        reply = ""
        tools_used = []

        for msg in messages:
            if hasattr(msg, 'type'):
                if msg.type == "ai" and msg.content:
                    reply = msg.content
                elif msg.type == "tool":
                    tools_used.append(msg.name)
            elif isinstance(msg, dict):
                if msg.get("role") == "assistant" and msg.get("content"):
                    reply = msg["content"]

        return ChatResponse(
            reply=reply or "I processed your request but have no text response.",
            session_id=session_id,
            tools_used=list(set(tools_used)),
        )
    except Exception as e:
        logger.error(f"chat_message_error: {e}")
        raise HTTPException(500, f"Chat agent error: {str(e)}")


@router.post("/stream")
async def chat_stream(body: ChatRequest):
    """
    Stream the chat response token-by-token for real-time UX.
    Uses Server-Sent Events (SSE) so the frontend gets partial responses.

    The frontend calls this with EventSource or fetch + ReadableStream.
    """
    if _chat_agent is None:
        raise HTTPException(503, "Chat agent not initialized yet")

    session_id = body.session_id or str(uuid4())
    config = {"configurable": {"thread_id": session_id}}

    async def event_generator():
        try:
            async for event in _chat_agent.astream_events(
                {"messages": [{"role": "user", "content": body.message}]},
                config=config,
                version="v2",
            ):
                kind = event.get("event", "")

                # Stream tool calls as they happen
                if kind == "on_tool_start":
                    tool_name = event.get("name", "unknown")
                    yield f"data: {json.dumps({'type': 'tool_start', 'tool': tool_name})}\n\n"

                elif kind == "on_tool_end":
                    tool_name = event.get("name", "unknown")
                    yield f"data: {json.dumps({'type': 'tool_end', 'tool': tool_name})}\n\n"

                # Stream AI response tokens
                elif kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        yield f"data: {json.dumps({'type': 'token', 'content': chunk.content})}\n\n"

            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"
        except Exception as e:
            logger.error(f"chat_stream_error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/history/{session_id}")
async def get_chat_history(session_id: str):
    """
    Retrieve the conversation history for a session.
    Reads from the LangGraph checkpointer.
    """
    if _chat_agent is None:
        raise HTTPException(503, "Chat agent not initialized yet")

    config = {"configurable": {"thread_id": session_id}}

    try:
        state = await _chat_agent.aget_state(config)
        messages = state.values.get("messages", [])

        history = []
        for msg in messages:
            if hasattr(msg, 'type') and hasattr(msg, 'content'):
                if msg.type in ("human", "ai") and msg.content:
                    history.append({
                        "role": "user" if msg.type == "human" else "assistant",
                        "content": msg.content,
                    })

        return {"session_id": session_id, "messages": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models")
async def get_models():
    """List available models from FreeRouter ROUTES config."""
    try:
        from freerouter.config import ROUTES
        models = [
            {
                "id": task_name,
                "object": "model",
                "owned_by": route["model"].split("/")[0],
                "primary": route["model"],
                "fallback": route["fallback"],
            }
            for task_name, route in ROUTES.items()
        ]
        return {"object": "list", "data": models}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations")
async def list_conversations():
    """List all conversations.

    NOTE: Conversation storage moved to apps/api layer.
    SQLite storage removed from freerouter (it was app-level concern).
    """
    return {"conversations": []}

"""
web/app.py — FreeRouter Web Dashboard (FastAPI).

Context: Provides the browser-based management UI and chat interface.
Unlike the old version, this app calls providers DIRECTLY via the Router —
no LiteLLM proxy, no separate process, no port 4000 dependency.
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from freerouter.providers import (
    KNOWN_PROVIDERS, get_configured_providers,
    save_api_key, check_provider_health, get_all_usage,
    reset_provider, load_env,
)
from freerouter.router import get_router, RouterError
from freerouter.storage import (
    init_db, create_conversation, list_conversations,
    get_conversation, delete_conversation, add_message,
    get_db_stats, get_db_path,
    create_pipeline_task, list_pipeline_tasks, get_pipeline_task,
    update_pipeline_task, delete_pipeline_task, add_task_thought,
)

logger = logging.getLogger("freerouter.web")


# ─── Pydantic Models ──────────────────────────────────────────────────────────

class SaveKeyRequest(BaseModel):
    api_key: str


class ChatRequest(BaseModel):
    model: str = "auto"
    messages: list[dict[str, Any]]
    temperature: float = 0.7
    max_tokens: int = 4096
    provider: Optional[str] = None


class PipelineTaskCreate(BaseModel):
    title: str
    stage: int = 1
    parent_id: Optional[str] = None
    color: Optional[str] = None


class PipelineTaskUpdate(BaseModel):
    title: Optional[str] = None
    stage: Optional[int] = None
    status: Optional[str] = None
    content: Optional[str] = None
    research: Optional[str] = None
    script: Optional[str] = None
    visual_cues: Optional[str] = None
    notion_url: Optional[str] = None


class PipelineEvent(BaseModel):
    task_id: str
    event_type: str  # 'thought', 'stage_change', 'status_change', 'artifact'
    data: Dict[str, Any]


# ─── Real-time Events ────────────────────────────────────────────────────────

# Global set of active SSE queues
pipeline_subscribers: List[asyncio.Queue] = []

async def broadcast_pipeline_event(event: dict):
    """Broadcast a pipeline event to all connected SSE clients."""
    disconnected = []
    for queue in pipeline_subscribers:
        try:
            await queue.put(event)
        except Exception:
            disconnected.append(queue)
    
    for queue in disconnected:
        if queue in pipeline_subscribers:
            pipeline_subscribers.remove(queue)


# ─── App Factory ──────────────────────────────────────────────────────────────

def create_web_app() -> FastAPI:
    app = FastAPI(
        title="FreeRouter Dashboard",
        description="AI Provider Management & Chat",
        version="2.0.0",
    )

    # Init database on startup
    @app.on_event("startup")
    async def startup():
        init_db()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Static files
    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # ─── Dashboard ────────────────────────────────────────────────────────────

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        html_path = static_dir / "index.html"
        if html_path.exists():
            return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
        return HTMLResponse(content="<h1>FreeRouter - index.html not found</h1>")

    # ─── Pipeline API ─────────────────────────────────────────────────────────

    @app.get("/api/pipeline/tasks")
    async def get_tasks():
        return {"tasks": list_pipeline_tasks()}

    @app.post("/api/pipeline/tasks")
    async def create_task(data: PipelineTaskCreate):
        task = create_pipeline_task(
            title=data.title,
            stage=data.stage,
            parent_id=data.parent_id,
            color=data.color
        )
        await broadcast_pipeline_event({"type": "task_created", "task": task})
        return task

    @app.patch("/api/pipeline/tasks/{tid}")
    async def update_task(tid: str, data: PipelineTaskUpdate):
        updates = data.dict(exclude_unset=True)
        if update_pipeline_task(tid, updates):
            task = get_pipeline_task(tid)
            await broadcast_pipeline_event({"type": "task_updated", "task": task})
            return task
        raise HTTPException(status_code=404, detail="Task not found")

    @app.delete("/api/pipeline/tasks/{tid}")
    async def delete_task(tid: str):
        if delete_pipeline_task(tid):
            await broadcast_pipeline_event({"type": "task_deleted", "task_id": tid})
            return {"success": True}
        raise HTTPException(status_code=404, detail="Task not found")

    @app.post("/api/pipeline/events")
    async def report_event(event: PipelineEvent):
        """Endpoint for agents to report their progress."""
        if event.event_type == "thought":
            add_task_thought(event.task_id, event.data)
        elif event.event_type == "stage_change":
            update_pipeline_task(event.task_id, {"stage": event.data.get("stage")})
        elif event.event_type == "status_change":
            update_pipeline_task(event.task_id, {"status": event.data.get("status")})
        elif event.event_type == "artifact":
            update_pipeline_task(event.task_id, {event.data.get("key"): event.data.get("value")})
        
        # Broadcast the raw event to the UI
        await broadcast_pipeline_event({
            "type": "agent_event",
            "task_id": event.task_id,
            "event_type": event.event_type,
            "data": event.data
        })
        return {"success": True}

    @app.get("/api/pipeline/stream")
    async def pipeline_stream(request: Request):
        """SSE stream for real-time pipeline updates."""
        queue = asyncio.Queue()
        pipeline_subscribers.append(queue)

        async def event_generator():
            try:
                while True:
                    # Check if client closed connection
                    if await request.is_disconnected():
                        break
                    
                    event = await queue.get()
                    yield f"data: {json.dumps(event)}\n\n"
            except asyncio.CancelledError:
                pass
            finally:
                if queue in pipeline_subscribers:
                    pipeline_subscribers.remove(queue)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )

    # ─── Providers API ────────────────────────────────────────────────────────

    @app.get("/api/providers")
    async def list_providers():
        load_env()
        result = []
        for defn, is_configured in get_configured_providers():
            result.append({
                "name": defn.name,
                "display_name": defn.display_name,
                "provider_type": defn.provider_type.value,
                "requires_auth": defn.requires_auth,
                "is_configured": is_configured,
                "signup_url": defn.signup_url,
                "priority": defn.priority,
            })
        return {"providers": result}

    @app.post("/api/providers/{name}/key")
    async def save_provider_key(name: str, data: SaveKeyRequest):
        try:
            save_api_key(name, data.api_key)
            return {"success": True, "message": f"API key saved for {name}"}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/providers/{name}/test")
    async def test_provider(name: str):
        ok, msg = await check_provider_health(name)
        return {"ok": ok, "message": msg}

    @app.post("/api/providers/{name}/reset")
    async def reset_provider_limits(name: str):
        from freerouter.providers import reset_provider
        reset_provider(name)
        return {"success": True, "message": f"Rate limits cleared for {name}"}

    @app.get("/api/providers/status")
    async def providers_status():
        results = []
        for defn, is_configured in get_configured_providers():
            if is_configured:
                ok, msg = await check_provider_health(defn.name)
            else:
                ok, msg = False, "Not configured"
            results.append({
                "name": defn.name,
                "display_name": defn.display_name,
                "is_configured": is_configured,
                "healthy": ok,
                "message": msg,
            })
        return {"providers": results}

    # ─── Models API ───────────────────────────────────────────────────────────

    @app.get("/api/models")
    async def list_models():
        router = get_router()
        models = await router.list_models()
        return {"models": models}

    # ─── Chat API — The Core Feature ─────────────────────────────────────────

    @app.post("/api/chat/stream")
    async def chat_stream(data: ChatRequest):
        router = get_router()

        async def generate():
            try:
                async for chunk in router.stream(
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
                logger.exception("Unexpected error in chat_stream")
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

    @app.post("/api/chat/complete")
    async def chat_complete(data: ChatRequest):
        router = get_router()
        try:
            result = await router.complete(
                messages=data.messages,
                model=data.model,
                temperature=data.temperature,
                max_tokens=data.max_tokens,
                provider=data.provider,
            )
            return result
        except RouterError as e:
            raise HTTPException(status_code=503, detail=str(e))

    # ─── Usage API ────────────────────────────────────────────────────────────

    @app.get("/api/usage")
    async def get_usage():
        from freerouter.providers import KNOWN_PROVIDERS, get_provider_key, DEFAULT_MODELS
        import time
        all_u = get_all_usage()
        result = {}

        for defn in sorted(KNOWN_PROVIDERS, key=lambda x: x.priority):
            name = defn.name
            has_key = (not defn.requires_auth) or bool(get_provider_key(name))
            if not has_key:
                continue

            u = all_u.get(name)
            pct = round((u.requests_used_pct or 0) * 100, 1) if u else 0
            last = u.last_updated if u else None
            ago = None
            if last:
                secs = int(time.time() - last)
                if secs < 60: ago = f"{secs}s ago"
                elif secs < 3600: ago = f"{secs//60}m ago"
                else: ago = f"{secs//3600}h ago"

            result[name] = {
                "display_name": defn.display_name,
                "provider_type": defn.provider_type.value,
                "default_model": DEFAULT_MODELS.get(name, ""),
                "requests_limit": u.requests_limit if u else 0,
                "requests_remaining": u.requests_remaining if u else -1,
                "tokens_limit": u.tokens_limit if u else 0,
                "tokens_remaining": u.tokens_remaining if u else -1,
                "used_pct": pct,
                "is_soft_limited": u.is_soft_limited if u else False,
                "is_hard_limited": u.is_hard_limited if u else False,
                "last_updated": last,
                "last_updated_ago": ago,
                "has_data": u is not None,
                "signup_url": defn.signup_url,
                "priority": defn.priority,
            }

        return {"usage": result, "source": "response_headers"}

    # ─── Conversations API ────────────────────────────────────────────────────

    @app.get("/api/conversations")
    async def list_convs():
        return {"conversations": list_conversations()}

    @app.post("/api/conversations")
    async def create_conv(data: dict = {}):
        conv = create_conversation(
            title=data.get("title", "New Chat"),
            model=data.get("model", ""),
        )
        return {"id": conv["id"]}

    @app.get("/api/conversations/{cid}")
    async def get_conv(cid: str):
        conv = get_conversation(cid)
        if not conv:
            raise HTTPException(status_code=404, detail="Not found")
        return conv

    @app.delete("/api/conversations/{cid}")
    async def delete_conv(cid: str):
        if delete_conversation(cid):
            return {"success": True}
        raise HTTPException(status_code=404, detail="Not found")

    @app.post("/api/conversations/{cid}/messages")
    async def add_msg(cid: str, data: dict):
        msg = add_message(
            cid=cid,
            role=data.get("role", "user"),
            content=data.get("content", ""),
            provider=data.get("provider", ""),
            model=data.get("model", ""),
        )
        if not msg:
            raise HTTPException(status_code=404, detail="Not found")
        return {"success": True, "message": msg}

    # ─── Health ───────────────────────────────────────────────────────────────

    @app.get("/api/storage")
    async def storage_info():
        return get_db_stats()

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "version": "2.0.0"}

    return app

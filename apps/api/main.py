"""
main.py — YouTube Pipeline Dashboard entry point.

Runs on port 3000. Single process — replaces both the old FreeRouter
web dashboard (:8080) and the new dashboard. FreeRouter proxy (:4000)
still runs separately for external tools (Claude Code, Cursor).

ROUTES (all prefixed with their router):
  /api/pipeline/*      — start, approve, status, list pipeline runs
  /api/providers/*     — FreeRouter provider management (proxied to :4000)
  /api/chat/*          — direct chat with FreeRouter (proxied to :4000)
  /api/memory/*        — browse Zep Cloud agent memory
  /api/analytics/*     — YouTube analytics and health monitor dashboard
  /api/visual/*        — visual asset manifest management
  /api/settings/*      — environment and configuration management
  /events              — SSE stream for real-time pipeline updates

STATIC DASHBOARD:
  apps/api/static/index.html — the web UI
  JavaScript files in apps/api/static/js/ correspond to each route:
    pipeline.js, providers.js, chat.js, memory.js, analytics.js,
    visual.js, settings.js

FREEROUTER PROXY:
  Provider and chat routes proxy requests to FreeRouter at :4000.
  FreeRouter MUST be running before these routes work.
  Check: make freerouter (in a separate terminal)

PORT:
  Runs on 3000 by default (not 8000 — intentional to avoid conflicts).
  Start: python -m apps.api.main
"""

from __future__ import annotations
import sys
import os
from pathlib import Path

# Make freerouter importable without installing it separately
_fr_src = Path(__file__).parent.parent.parent / "freerouter" / "src"
if str(_fr_src) not in sys.path:
    sys.path.insert(0, str(_fr_src))

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from apps.api.dependencies import close_all
from apps.api.events import sse_endpoint
from apps.api.middleware.auth import AuthMiddleware
from apps.api.routers import (
    pipeline_routes,
    provider_routes,
    chat_routes,
    memory_routes,
    analytics_routes,
    visual_routes,
    settings_routes,
    topic_routes,
    health_routes,
    kanban_routes,
)
from packages.core.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler.
    
    Initializes databases on startup and cleans up on shutdown.
    """
    try:
        from freerouter.storage import init_db
        init_db()
    except Exception:
        pass
    
    # Initialize Kanban database
    try:
        from apps.api.routers.kanban_routes import init_kanban_db
        init_kanban_db()
    except Exception as e:
        print(f"Warning: Could not init Kanban DB: {e}")
    
    print("\nFreeRouter Dashboard - http://localhost:3000")
    print("   LLM proxy: python -m freerouter proxy  (port 4000)\n")
    yield
    await close_all()


app = FastAPI(
    title="YouTube Pipeline Dashboard",
    description="Unified control panel for the YouTube automation pipeline",
    version="1.0.0",
    lifespan=lifespan,
)

# Get settings for CORS configuration
settings = get_settings()

# Add AuthMiddleware BEFORE CORSMiddleware (order matters!)
app.add_middleware(AuthMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint (no auth required)
app.include_router(health_routes, tags=["health"])

# API routes
app.include_router(pipeline_routes, prefix="/api/pipeline",  tags=["pipeline"])
app.include_router(provider_routes, prefix="/api/providers", tags=["providers"])
app.include_router(chat_routes,     prefix="/api/chat",      tags=["chat"])
app.include_router(memory_routes,   prefix="/api/memory",    tags=["memory"])
app.include_router(analytics_routes,prefix="/api/analytics", tags=["analytics"])
app.include_router(visual_routes,   prefix="/api/visual",    tags=["visual"])
app.include_router(settings_routes, prefix="/api/settings",  tags=["settings"])
app.include_router(topic_routes,    prefix="/api/topics",    tags=["topics"])
app.include_router(kanban_routes, prefix="/api/kanban", tags=["kanban"])

# SSE endpoint
app.add_api_route("/api/events", sse_endpoint, methods=["GET"])

# Static frontend — MUST be last
import os
_static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")


if __name__ == "__main__":
    uvicorn.run("apps.api.main:app", host="0.0.0.0", port=3000, reload=True)

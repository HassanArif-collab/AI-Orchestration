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

import os

# ── MUST run before any litellm import (triggered by crewai) ────────────
# Prevents LiteLLM from blocking startup with a remote HTTP fetch
# to GitHub for model pricing data. Uses bundled local copy instead.
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

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
    dlq_routes,
)
from packages.core.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler.
    
    Initializes databases on startup and cleans up on shutdown.
    """

    # NOTE: bootstrap_agents() removed in Phase 3 — packages.agents.bootstrap deleted
    # (CrewAI agents were dead code; LangGraph nodes handle content creation)

    # NOTE: start_scheduler() removed in Phase 3 — MasterOrchestrator deprecated
    # (LangGraph pipeline handles topic discovery and production natively)

    # Start the expired card cleanup task
    try:
        from apps.api.background_tasks import start_cleanup_task
        if not start_cleanup_task():
            print("Warning: Cleanup task startup failed (non-fatal)")
    except Exception as e:
        print(f"Warning: Cleanup task startup failed (non-fatal): {e}")
    
    # Initialize the chat agent (Phase 6)
    try:
        from apps.api.routers.chat_routes import init_chat_agent
        await init_chat_agent()
    except Exception as e:
        print(f"Warning: Chat agent startup failed (non-fatal): {e}")
    
    # Startup health validation — check all services and log warnings
    try:
        from packages.core.config import get_settings as _get_settings
        _settings = _get_settings()
        service_status = _settings.get_service_status()
        unavailable = [svc for svc, status in service_status.items() if status != "available"]
        if unavailable:
            print(f"Warning: {len(unavailable)} service(s) not available at startup: {', '.join(unavailable)}")
            for svc in unavailable:
                print(f"  - {svc}: {service_status[svc]}")
        # Store initial health status for dashboard consumption
        app.state.initial_health = service_status

        # ── Configuration completeness validation (Issue 18) ──
        # Check critical vs optional config keys and log warnings for missing optional ones
        critical_keys = {
            "FREEROUTER_URL": _settings.FREEROUTER_URL,
        }
        optional_keys = {
            "NOTION_API_KEY": _settings.NOTION_API_KEY,
            "ZEP_API_KEY": _settings.ZEP_API_KEY,
            "EXA_API_KEY": _settings.EXA_API_KEY,
            "SUPABASE_URL": _settings.SUPABASE_URL,
            "YOUTUBE_API_KEY": _settings.YOUTUBE_API_KEY,
        }

        missing_critical = [k for k, v in critical_keys.items() if not v]
        missing_optional = [k for k, v in optional_keys.items() if not v]

        if missing_critical:
            print(f"ERROR: {len(missing_critical)} critical config key(s) missing: {', '.join(missing_critical)}")
        if missing_optional:
            print(f"Info: {len(missing_optional)} optional service(s) not configured: {', '.join(missing_optional)}")
            print("  These services will operate in degraded mode. Set the corresponding env vars to enable them.")

        # Store config status for the /api/health/config endpoint
        app.state.config_status = {
            "critical": {k: bool(v) for k, v in critical_keys.items()},
            "optional": {k: bool(v) for k, v in optional_keys.items()},
            "missing_critical": missing_critical,
            "missing_optional": missing_optional,
        }
    except Exception as e:
        print(f"Warning: Startup health validation failed (non-fatal): {e}")
        app.state.initial_health = {}
        app.state.config_status = {}

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
app.include_router(dlq_routes, tags=["dlq"])

# SSE endpoint
app.add_api_route("/api/events", sse_endpoint, methods=["GET"])

# Static frontend — MUST be last
import os
_static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")


if __name__ == "__main__":
    uvicorn.run("apps.api.main:app", host="0.0.0.0", port=3000, reload=True)

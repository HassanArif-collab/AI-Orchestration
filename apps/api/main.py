"""
main.py — YouTube Pipeline Dashboard entry point.

Runs on port 3000. Single process — replaces both the old FreeRouter
web dashboard (:8080) and the new dashboard. FreeRouter proxy (:4000)
still runs separately for external tools (Claude Code, Cursor).

Start with: python -m apps.api.main
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
from apps.api.routers import (
    pipeline_routes,
    provider_routes,
    chat_routes,
    memory_routes,
    analytics_routes,
    visual_routes,
    settings_routes,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        from freerouter.storage import init_db
        init_db()
    except Exception:
        pass
    print("\n⚡ FreeRouter Dashboard — http://localhost:3000")
    print("   LLM proxy: python -m freerouter proxy  (port 4000)\n")
    yield
    await close_all()


app = FastAPI(
    title="YouTube Pipeline Dashboard",
    description="Unified control panel for the YouTube automation pipeline",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(pipeline_routes.router, prefix="/api/pipeline",  tags=["pipeline"])
app.include_router(provider_routes.router, prefix="/api/providers", tags=["providers"])
app.include_router(chat_routes.router,     prefix="/api/chat",      tags=["chat"])
app.include_router(memory_routes.router,   prefix="/api/memory",    tags=["memory"])
app.include_router(analytics_routes.router,prefix="/api/analytics", tags=["analytics"])
app.include_router(visual_routes.router,   prefix="/api/visual",    tags=["visual"])
app.include_router(settings_routes.router, prefix="/api/settings",  tags=["settings"])

# SSE endpoint
app.add_api_route("/api/events", sse_endpoint, methods=["GET"])

# Static frontend — MUST be last
import os
_static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")


if __name__ == "__main__":
    uvicorn.run("apps.api.main:app", host="0.0.0.0", port=3000, reload=True)

"""
dependencies.py — Shared HTTP clients and package imports.

_proxy_client → http://localhost:4000  (FreeRouter LLM proxy, still separate)

FreeRouter web (:8080) is gone — chat and providers now use freerouter
internals directly.

REMOVED (Phase 3 dead code cleanup):
    get_pipeline_runner() — PipelineRunner is deprecated, use LangGraph endpoints.
"""

from __future__ import annotations
import httpx

_proxy_client: httpx.AsyncClient | None = None


async def get_proxy_client() -> httpx.AsyncClient:
    """HTTP client for FreeRouter LLM proxy at :4000."""
    global _proxy_client
    if _proxy_client is None:
        _proxy_client = httpx.AsyncClient(
            base_url="http://localhost:4000",
            timeout=60.0,
        )
    return _proxy_client


def get_run_store():
    try:
        from packages.pipeline.state import RunStore
        return RunStore()
    except ImportError:
        return None


def get_memory_client():
    try:
        from packages.memory.client import AsyncZepMemoryClient
        return AsyncZepMemoryClient()
    except ImportError:
        return None


def get_youtube_client():
    try:
        from packages.integrations.youtube.client import YouTubeClient
        return YouTubeClient()
    except ImportError:
        return None


def get_radiant_manager():
    try:
        from packages.visual.radiant.manager import RadiantManager
        return RadiantManager()
    except ImportError:
        return None


async def close_all() -> None:
    if _proxy_client:
        await _proxy_client.aclose()

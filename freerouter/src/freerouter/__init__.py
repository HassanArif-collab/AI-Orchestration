"""
FreeRouter — Smart AI proxy that routes to the best free provider automatically.

Direct provider routing (no LiteLLM). Supports Ollama (local), Groq, OpenRouter,
Together AI, DeepInfra, OpenAI, and Anthropic with automatic fallback.

Key modules:
  providers.py  — provider definitions, API keys, health checks, rate-limit tracking
  router.py     — routes requests to providers, handles streaming and fallback
  web/app.py    — FastAPI web dashboard + chat UI
  proxy_server.py — OpenAI-compatible /v1/chat/completions endpoint (for Cursor, etc.)
"""

__version__ = "2.0.0"
__author__ = "FreeRouter"

from freerouter.providers import (
    KNOWN_PROVIDERS, PROVIDER_MAP,
    get_configured_providers, save_api_key,
    update_usage_from_headers, mark_hard_limited,
    should_skip_provider, get_all_usage,
)
from freerouter.router import Router, get_router

__all__ = [
    "KNOWN_PROVIDERS",
    "PROVIDER_MAP",
    "get_configured_providers",
    "save_api_key",
    "update_usage_from_headers",
    "mark_hard_limited",
    "should_skip_provider",
    "get_all_usage",
    "Router",
    "get_router",
    "__version__",
]

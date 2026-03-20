"""
proxy_server.py — OpenAI-compatible API proxy server.

Context: Exposes FreeRouter as a drop-in OpenAI replacement.
Point any tool (Cursor, Continue, VS Code, scripts) at this server and
it will route your requests through the best available free provider.

Usage:
    python -m freerouter proxy          # starts on port 4000
    python -m freerouter proxy --port 4001

Then in your tool set:
    base_url = "http://localhost:4000/v1"
    api_key  = "any-value"             # key is not checked by default

Endpoints:
    GET  /health                     → status check
    GET  /v1/models                  → list available models
    POST /v1/chat/completions        → streaming + non-streaming chat

Imports: router.py, providers.py
Imported by: cli.py (proxy command)
"""

import json
import logging
import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from freerouter.router import get_router, RouterError
from freerouter.providers import get_configured_providers, DEFAULT_MODELS

logger = logging.getLogger("freerouter.proxy_server")


def create_proxy_app(api_key: Optional[str] = None) -> FastAPI:
    """
    Create the OpenAI-compatible proxy FastAPI app.
    api_key: if set, all requests must include 'Authorization: Bearer <key>'
    """
    app = FastAPI(
        title="FreeRouter Proxy",
        description="OpenAI-compatible proxy — routes to free providers automatically",
        version="2.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _api_key = api_key or os.getenv("FREEROUTER_API_KEY")

    def _check_auth(request: Request):
        if not _api_key:
            return  # No auth required
        auth = request.headers.get("Authorization", "")
        key = auth.removeprefix("Bearer ").strip()
        if key != _api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")

    # ─── Health ───────────────────────────────────────────────────────────────

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": "2.0.0"}

    # ─── Models ───────────────────────────────────────────────────────────────

    @app.get("/v1/models")
    async def list_models(request: Request):
        _check_auth(request)
        router = get_router()
        models = await router.list_models()
        return {
            "object": "list",
            "data": [
                {
                    "id": m["id"],
                    "object": "model",
                    "owned_by": m["provider"],
                }
                for m in models
            ],
        }

    # ─── Chat completions ─────────────────────────────────────────────────────

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request):
        """
        OpenAI-compatible chat completions endpoint.
        Supports streaming (stream=true) and non-streaming.
        Model can be:
          - "auto"              → best available provider
          - "groq/llama-3.3-70b-versatile" → specific provider+model
          - any OpenAI model name → routed to best available provider
        """
        _check_auth(request)
        body = await request.json()

        model = body.get("model", "auto")
        messages = body.get("messages", [])
        temperature = body.get("temperature", 0.7)
        max_tokens = body.get("max_tokens", 4096)
        stream = body.get("stream", False)

        # Detect if a specific provider is requested via "provider/model" syntax
        provider = None
        if "/" in model and not model.startswith("gpt-") and not model.startswith("claude-"):
            parts = model.split("/", 1)
            from freerouter.providers import PROVIDER_MAP
            if parts[0] in PROVIDER_MAP:
                provider = parts[0]

        router = get_router()

        if stream:
            async def generate():
                try:
                    async for chunk in router.stream(
                        messages=messages,
                        model=model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        provider=provider,
                    ):
                        yield chunk
                except RouterError as e:
                    yield f"data: {json.dumps({'error': {'message': str(e), 'type': 'router_error'}})}\n\n"
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
        else:
            try:
                result = await router.complete(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    provider=provider,
                )
                return result
            except RouterError as e:
                raise HTTPException(status_code=503, detail=str(e))

    return app

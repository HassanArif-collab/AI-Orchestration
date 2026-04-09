"""
server.py — LiteLLM-backed proxy with multi-provider fallback chains.

v4.0 changes:
  - 4 providers: Zhipu AI (primary), Google AI Studio, Ollama Cloud, OpenRouter
  - Deep fallback chains (6 levels per route)
  - Auto-retry on rate limits (429) with exponential backoff

Accepts POST /v1/chat/completions with model= set to either:
  - A task name:  "researcher", "scorer", "auto", etc.
  - A direct LiteLLM string: "openai/glm-4-plus"

Run:  python -m freerouter
"""

import json
import logging
import os
import asyncio
from typing import AsyncIterator

import litellm
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from .config import ROUTES, ZHIPU_API_BASE

# ── Setup ─────────────────────────────────────────────────────────────────────

_env_candidates = [
    os.path.join(os.path.dirname(__file__), "..", "..", ".env"),
    os.path.join(os.path.dirname(__file__), ".env"),
]
for _env_path in _env_candidates:
    _env_path = os.path.normpath(_env_path)
    if os.path.exists(_env_path):
        load_dotenv(_env_path)
        break

litellm.drop_params = True
litellm.set_verbose = False

log = logging.getLogger("freerouter")
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")

app = FastAPI(title="FreeRouter", version="4.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Provider config ───────────────────────────────────────────────────────────

OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "https://ollama.com")
OLLAMA_API_KEY  = os.getenv("OLLAMA_API_KEY", "")
GOOGLE_API_KEY  = os.getenv("GOOGLE_API_KEY", "")
ZHIPU_API_KEY   = os.getenv("ZHIPU_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")


# ── Routing helpers ───────────────────────────────────────────────────────────

def _resolve(model: str) -> list[str]:
    """Return ordered list of LiteLLM model strings to try."""
    route = ROUTES.get(model)
    if route:
        models = []
        for key in ("model", "fallback", "fallback2", "fallback3", "fallback4", "fallback5"):
            val = route.get(key)
            if val:
                models.append(val)
        return models
    return [model, ROUTES["auto"]["model"]]


def _provider(model_str: str) -> str:
    """Extract provider name from litellm model string."""
    prefix = model_str.split("/")[0]
    if prefix.startswith("ollama"):
        return "ollama"
    if prefix == "gemini":
        return "google_ai_studio"
    if prefix == "openrouter":
        return "openrouter"
    # Zhipu models use "openai/glm-4-*" with custom api_base
    if "glm" in model_str:
        return "zhipu"
    return prefix


def _build_call_kwargs(model_str: str) -> dict:
    """Build extra kwargs for litellm.acompletion based on provider."""
    kwargs = {}
    if model_str.startswith("ollama"):
        kwargs["api_base"] = OLLAMA_API_BASE
        if OLLAMA_API_KEY:
            kwargs["api_key"] = OLLAMA_API_KEY
    elif model_str.startswith("gemini"):
        if GOOGLE_API_KEY:
            kwargs["api_key"] = GOOGLE_API_KEY
    elif model_str.startswith("openrouter"):
        if OPENROUTER_API_KEY:
            kwargs["api_key"] = OPENROUTER_API_KEY
    elif "glm" in model_str:
        # Zhipu AI uses OpenAI-compatible endpoint
        kwargs["api_base"] = ZHIPU_API_BASE
        if ZHIPU_API_KEY:
            kwargs["api_key"] = ZHIPU_API_KEY
    return kwargs


# ── Core call (non-streaming) ─────────────────────────────────────────────────

async def _complete(model_chain: list[str], messages: list, params: dict):
    """Try each model in the chain until one succeeds."""
    last_error = None
    for i, model in enumerate(model_chain):
        try:
            extra = _build_call_kwargs(model)
            resp = await litellm.acompletion(model=model, messages=messages, **params, **extra)
            resp._used_model = model
            return resp
        except Exception as exc:
            last_error = exc
            remaining = len(model_chain) - i - 1
            error_str = str(exc)

            if "429" in error_str or "rate" in error_str.lower():
                wait = min(2 ** i, 8)
                log.warning(
                    "rate_limited model=%s error=%s waiting_%ss remaining=%d",
                    model, exc, wait, remaining,
                )
                await asyncio.sleep(wait)
            else:
                log.warning(
                    "model_failed model=%s error=%s remaining=%d",
                    model, exc, remaining,
                )

    raise HTTPException(
        status_code=503,
        detail=f"All models failed: {model_chain}. Last error: {last_error}",
    )


# ── Core call (streaming) ─────────────────────────────────────────────────────

async def _stream(model_chain: list[str], messages: list, params: dict) -> AsyncIterator[str]:
    """Try each model in the chain for streaming."""
    for model in model_chain:
        try:
            extra = _build_call_kwargs(model)
            resp = await litellm.acompletion(
                model=model, messages=messages, stream=True, **params, **extra,
            )
            async for chunk in resp:
                yield f"data: {chunk.model_dump_json()}\n\n"
            yield "data: [DONE]\n\n"
            return
        except Exception as exc:
            log.warning("stream_failed model=%s error=%s", model, exc)

    yield f"data: {json.dumps({'error': 'all models failed'})}\n\n"
    yield "data: [DONE]\n\n"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    model_chain = _resolve(body.get("model", "auto"))

    messages = body["messages"]
    params = {k: v for k, v in body.items() if k not in ("model", "messages")}

    primary = model_chain[0]
    log.info("request task=%s → primary=%s chain_len=%d", body.get("model", "auto"), primary, len(model_chain))

    if params.pop("stream", False):
        return StreamingResponse(
            _stream(model_chain, messages, params),
            media_type="text/event-stream",
            headers={
                "x-freerouter-model":    primary,
                "x-freerouter-provider": _provider(primary),
            },
        )

    resp = await _complete(model_chain, messages, params)
    used = getattr(resp, "_used_model", primary)

    # Normalize response for reasoning models
    data = resp.model_dump()
    for choice in data.get("choices", []):
        msg = choice.get("message", {})
        if not msg.get("content") and msg.get("reasoning_content"):
            msg["content"] = msg["reasoning_content"]
            log.info("reasoning_model_content_fix model=%s", used)

    return JSONResponse(
        content=data,
        headers={
            "x-freerouter-model":    used,
            "x-freerouter-provider": _provider(used),
        },
    )


@app.get("/v1/models")
async def list_models():
    """Return available models from ROUTES config with full chain info."""
    models = []
    for task_name, route in ROUTES.items():
        chain = []
        for key in ("model", "fallback", "fallback2", "fallback3", "fallback4", "fallback5"):
            val = route.get(key)
            if val:
                chain.append(val)
        models.append({
            "id": task_name,
            "object": "model",
            "owned_by": _provider(route["model"]),
            "primary": route["model"],
            "chain": chain,
        })
    return {"object": "list", "data": models}


@app.get("/health")
async def health():
    """Health check endpoint — shows all provider statuses."""
    return {
        "status": "ok",
        "version": "4.0.0",
        "providers": {
            "zhipu": bool(ZHIPU_API_KEY),
            "google_ai_studio": bool(GOOGLE_API_KEY),
            "ollama": bool(OLLAMA_API_KEY),
            "openrouter": bool(OPENROUTER_API_KEY),
        },
        "tasks": list(ROUTES.keys()),
    }

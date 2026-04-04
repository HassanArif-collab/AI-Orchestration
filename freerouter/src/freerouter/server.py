"""
server.py — Minimal LiteLLM-backed proxy.

Accepts POST /v1/chat/completions with model= set to either:
  - A task name:  "researcher", "scorer", "auto", etc.
  - A direct LiteLLM string: "groq/llama-3.3-70b-versatile" (passed through)

Returns standard OpenAI-compatible JSON + two headers:
  x-freerouter-model     — actual model used
  x-freerouter-provider  — provider (groq / openrouter / ollama)

Run:  python -m freerouter

v3 FIXES applied:
  - GAP 1: HTTPException(503) instead of RuntimeError (critical for RouterClient retry)
  - GAP 2: .env path resolves to freerouter/.env correctly
  - Added /v1/models endpoint (was missing from v2)
  - Added version "3.0.0" to health response
"""

import json
import logging
import os
from typing import AsyncIterator

import litellm
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from .config import ROUTES

# ── Setup ─────────────────────────────────────────────────────────────────────

# GAP FIX 2: Load from freerouter/.env
# __file__ = freerouter/src/freerouter/server.py
# Go up two levels to reach freerouter/.env
_env_candidates = [
    os.path.join(os.path.dirname(__file__), "..", "..", ".env"),  # freerouter/.env
    os.path.join(os.path.dirname(__file__), ".env"),               # freerouter/src/freerouter/.env
]
for _env_path in _env_candidates:
    _env_path = os.path.normpath(_env_path)
    if os.path.exists(_env_path):
        load_dotenv(_env_path)
        break

litellm.drop_params = True          # ignore params unsupported by a model silently
litellm.set_verbose = False

log = logging.getLogger("freerouter")
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")

app = FastAPI(title="FreeRouter", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ── Routing helpers ───────────────────────────────────────────────────────────

def _resolve(model: str) -> tuple[str, str]:
    """Return (primary, fallback) LiteLLM model strings for a task name or pass-through."""
    route = ROUTES.get(model)
    if route:
        return route["model"], route["fallback"]
    # Already a litellm string like "groq/llama-3.3-70b-versatile" — pass through
    return model, ROUTES["auto"]["fallback"]


def _provider(model_str: str) -> str:
    return model_str.split("/")[0]


# ── Core call (non-streaming) ─────────────────────────────────────────────────

async def _complete(primary: str, fallback: str, messages: list, params: dict):
    for model in [primary, fallback]:
        try:
            resp = await litellm.acompletion(model=model, messages=messages, **params)
            resp._used_model = model
            return resp
        except Exception as exc:
            log.warning("model_failed model=%s error=%s trying_fallback=%s", model, exc, fallback)

    # GAP FIX 1: Return 503 so RouterClient retries with "auto"
    # RouterClient only retries on 503 — returning 500 would break fallback logic
    raise HTTPException(status_code=503, detail=f"Both {primary!r} and {fallback!r} failed")


# ── Core call (streaming) ─────────────────────────────────────────────────────

async def _stream(primary: str, fallback: str, messages: list, params: dict) -> AsyncIterator[str]:
    for model in [primary, fallback]:
        try:
            resp = await litellm.acompletion(
                model=model, messages=messages, stream=True, **params
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
    primary, fallback = _resolve(body.get("model", "auto"))

    messages = body["messages"]
    params = {k: v for k, v in body.items() if k not in ("model", "messages")}

    log.info("request task=%s → model=%s", body.get("model", "auto"), primary)

    if params.pop("stream", False):
        return StreamingResponse(
            _stream(primary, fallback, messages, params),
            media_type="text/event-stream",
            headers={
                "x-freerouter-model":    primary,
                "x-freerouter-provider": _provider(primary),
            },
        )

    resp = await _complete(primary, fallback, messages, params)
    used = getattr(resp, "_used_model", primary)

    return JSONResponse(
        content=resp.model_dump(),
        headers={
            "x-freerouter-model":    used,
            "x-freerouter-provider": _provider(used),
        },
    )


@app.get("/v1/models")
async def list_models():
    """Return available models from ROUTES config."""
    models = []
    for task_name, route in ROUTES.items():
        models.append({
            "id": task_name,
            "object": "model",
            "owned_by": _provider(route["model"]),
            "primary": route["model"],
            "fallback": route["fallback"],
        })
    return {"object": "list", "data": models}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": "3.0.0",
        "tasks": list(ROUTES.keys()),
    }

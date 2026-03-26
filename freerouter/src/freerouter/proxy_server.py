"""
proxy_server.py — Multi-format AI proxy server.

Context: Exposes FreeRouter as a drop-in replacement for both:
  - OpenAI API    (POST /v1/chat/completions) — Cursor, Continue, scripts
  - Anthropic API (POST /v1/messages)         — Claude Code, Claude SDKs

Both formats route through Router → best available free provider with
automatic fallback. The actual provider/model used is returned in response
headers so you can always see what ran.

Response headers added:
  x-freerouter-provider  — which provider handled it (e.g. "groq")
  x-freerouter-model     — actual model used (e.g. "llama-3.3-70b-versatile")

Imports: router.py, providers.py
Imported by: cli.py
"""

import json
import logging
import os
import uuid
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from freerouter.router import get_router
from freerouter.exceptions import RouterError
from freerouter.providers import PROVIDER_MAP, reset_provider

logger = logging.getLogger("freerouter.proxy_server")


# ─── Format converters ────────────────────────────────────────────────────────

def _anthropic_to_openai_messages(anthropic_messages: list, system: str = None) -> list:
    """Convert Anthropic messages format to OpenAI format."""
    openai_messages = []
    if system:
        openai_messages.append({"role": "system", "content": system})
    for msg in anthropic_messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            content = "\n".join(text_parts)
        openai_messages.append({"role": role, "content": content})
    return openai_messages


def _openai_to_anthropic_response(openai_resp: dict, model: str) -> dict:
    """Convert OpenAI response to Anthropic format."""
    choice = openai_resp.get("choices", [{}])[0]
    content = choice.get("message", {}).get("content", "")
    usage = openai_resp.get("usage", {})
    return {
        "id": openai_resp.get("id", f"msg_{uuid.uuid4().hex[:24]}"),
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": content}],
        "model": model,
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        },
    }


def _anthropic_sse(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def _extract_provider_from_stream(raw_chunk: str) -> tuple[str, str]:
    """Extract _provider and _model from the meta chunk the router sends."""
    for line in raw_chunk.split("\n"):
        if line.startswith("data: "):
            try:
                parsed = json.loads(line[6:])
                meta = parsed.get("meta", {})
                if meta:
                    return meta.get("_provider", ""), meta.get("_model", "")
            except Exception:
                pass
    return "", ""


# ─── App factory ──────────────────────────────────────────────────────────────

def create_proxy_app(api_key: Optional[str] = None) -> FastAPI:
    app = FastAPI(
        title="FreeRouter Proxy",
        description="OpenAI + Anthropic compatible proxy — auto-routes to free providers",
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
            return
        auth = request.headers.get("Authorization", "")
        key = auth.removeprefix("Bearer ").strip()
        if key != _api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")

    def _detect_provider(model: str) -> Optional[str]:
        """If model is 'groq/llama-xxx', extract 'groq' as the forced provider."""
        if "/" in model and not model.startswith(("gpt-", "claude-", "o1", "o3")):
            prefix = model.split("/")[0]
            if prefix in PROVIDER_MAP:
                return prefix
        return None

    # ─── Health ───────────────────────────────────────────────────────────────

    @app.get("/health")
    @app.get("/v1/health")
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
            "data": [{"id": m["id"], "object": "model", "owned_by": m["provider"]} for m in models],
        }

    # ─── Provider reset (useful when stuck on rate limit) ─────────────────────

    @app.post("/v1/providers/{name}/reset")
    async def reset_provider_limits(name: str, request: Request):
        _check_auth(request)
        reset_provider(name)
        return {"success": True, "message": f"Rate limits cleared for {name}"}

    # ─── OpenAI: POST /v1/chat/completions ────────────────────────────────────

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request):
        _check_auth(request)
        body = await request.json()

        model = body.get("model", "auto")
        messages = body.get("messages", [])
        temperature = body.get("temperature", 0.7)
        max_tokens = body.get("max_tokens", 4096)
        stream = body.get("stream", False)
        provider = _detect_provider(model)
        router = get_router()

        if stream:
            actual_provider = ["unknown"]
            actual_model = [model]

            async def generate():
                first = True
                async for chunk in router.stream(
                    messages=messages, model=model,
                    temperature=temperature, max_tokens=max_tokens,
                    provider=provider,
                ):
                    # Grab provider info from first (meta) chunk
                    if first:
                        p, m = _extract_provider_from_stream(chunk)
                        if p:
                            actual_provider[0] = p
                            actual_model[0] = m
                        first = False
                    yield chunk

            return StreamingResponse(
                generate(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                    "x-freerouter-provider": actual_provider[0],
                    "x-freerouter-model": actual_model[0],
                },
            )
        else:
            try:
                result = await router.complete(
                    messages=messages, model=model,
                    temperature=temperature, max_tokens=max_tokens,
                    provider=provider,
                )
                actual_p = result.pop("_provider", "unknown")
                actual_m = result.pop("_model", model)
                # Return actual model name in response so tools can see it
                result["model"] = f"{actual_p}/{actual_m}"
                logger.info(f"Served by {actual_p} / {actual_m}")
                return Response(
                    content=json.dumps(result),
                    media_type="application/json",
                    headers={
                        "x-freerouter-provider": actual_p,
                        "x-freerouter-model": actual_m,
                    },
                )
            except RouterError as e:
                raise HTTPException(status_code=503, detail=str(e))

    # ─── Anthropic: POST /v1/messages ─────────────────────────────────────────

    @app.post("/v1/messages")
    async def anthropic_messages(request: Request):
        _check_auth(request)
        body = await request.json()

        model = body.get("model", "auto")
        system = body.get("system", None)
        anthropic_msgs = body.get("messages", [])
        temperature = body.get("temperature", 0.7)
        max_tokens = body.get("max_tokens", 4096)
        stream = body.get("stream", False)

        messages = _anthropic_to_openai_messages(anthropic_msgs, system)
        provider = _detect_provider(model)
        router = get_router()
        msg_id = f"msg_{uuid.uuid4().hex[:24]}"

        if stream:
            actual_provider = ["unknown"]
            actual_model = [model]

            async def generate_anthropic():
                first = True
                try:
                    yield _anthropic_sse("message_start", {
                        "type": "message_start",
                        "message": {
                            "id": msg_id, "type": "message", "role": "assistant",
                            "content": [], "model": model, "stop_reason": None,
                            "stop_sequence": None, "usage": {"input_tokens": 0, "output_tokens": 0},
                        },
                    })
                    yield _anthropic_sse("content_block_start", {
                        "type": "content_block_start", "index": 0,
                        "content_block": {"type": "text", "text": ""},
                    })

                    async for raw_chunk in router.stream(
                        messages=messages, model=model,
                        temperature=temperature, max_tokens=max_tokens,
                        provider=provider,
                    ):
                        # Extract provider info from meta chunk
                        if first:
                            p, m = _extract_provider_from_stream(raw_chunk)
                            if p:
                                actual_provider[0] = p
                                actual_model[0] = m
                                logger.info(f"Claude Code served by {p} / {m}")
                            first = False

                        for line in raw_chunk.split("\n"):
                            line = line.strip()
                            if not line.startswith("data: "):
                                continue
                            payload = line[6:]
                            if payload in ("[DONE]", ""):
                                continue
                            try:
                                parsed = json.loads(payload)
                                if parsed.get("error"):
                                    err = parsed["error"]
                                    err_text = err if isinstance(err, str) else err.get("message", "Error")
                                    yield _anthropic_sse("content_block_delta", {
                                        "type": "content_block_delta", "index": 0,
                                        "delta": {"type": "text_delta", "text": f"\n\n[FreeRouter Error: {err_text}]"},
                                    })
                                    continue
                                delta = parsed.get("choices", [{}])[0].get("delta", {}).get("content")
                                if delta:
                                    yield _anthropic_sse("content_block_delta", {
                                        "type": "content_block_delta", "index": 0,
                                        "delta": {"type": "text_delta", "text": delta},
                                    })
                            except (json.JSONDecodeError, KeyError):
                                continue

                    yield _anthropic_sse("content_block_stop", {"type": "content_block_stop", "index": 0})
                    yield _anthropic_sse("message_delta", {
                        "type": "message_delta",
                        "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                        "usage": {"output_tokens": 0},
                    })
                    yield _anthropic_sse("message_stop", {"type": "message_stop"})

                except RouterError as e:
                    yield _anthropic_sse("content_block_delta", {
                        "type": "content_block_delta", "index": 0,
                        "delta": {"type": "text_delta", "text": f"\n\n[FreeRouter Error: {str(e)}]"},
                    })
                    yield _anthropic_sse("content_block_stop", {"type": "content_block_stop", "index": 0})
                    yield _anthropic_sse("message_stop", {"type": "message_stop"})

            return StreamingResponse(
                generate_anthropic(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                    "x-freerouter-provider": actual_provider[0],
                    "x-freerouter-model": actual_model[0],
                },
            )

        else:
            try:
                openai_result = await router.complete(
                    messages=messages, model=model,
                    temperature=temperature, max_tokens=max_tokens,
                    provider=provider,
                )
                actual_p = openai_result.pop("_provider", "unknown")
                actual_m = openai_result.pop("_model", model)
                logger.info(f"Claude Code served by {actual_p} / {actual_m}")
                anthropic_resp = _openai_to_anthropic_response(openai_result, f"{actual_p}/{actual_m}")
                return Response(
                    content=json.dumps(anthropic_resp),
                    media_type="application/json",
                    headers={
                        "x-freerouter-provider": actual_p,
                        "x-freerouter-model": actual_m,
                    },
                )
            except RouterError as e:
                raise HTTPException(status_code=503, detail=str(e))

    return app

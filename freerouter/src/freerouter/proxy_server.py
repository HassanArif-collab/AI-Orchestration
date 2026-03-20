"""
proxy_server.py — Multi-format AI proxy server.

Context: Exposes FreeRouter as a drop-in replacement for both:
  - OpenAI API   (POST /v1/chat/completions) — for Cursor, Continue, scripts
  - Anthropic API (POST /v1/messages)        — for Claude Code, Claude SDKs

Both formats route through the same Router → best free provider.

Usage:
    python -m freerouter proxy   # starts on port 4000

Tool config:
    OpenAI-style:    base_url=http://localhost:4000/v1  api_key=any
    Anthropic-style: ANTHROPIC_BASE_URL=http://localhost:4000
                     ANTHROPIC_API_KEY=any

Imports: router.py, providers.py
Imported by: cli.py
"""

import json
import logging
import os
import time
import uuid
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from freerouter.router import get_router, RouterError
from freerouter.providers import PROVIDER_MAP

logger = logging.getLogger("freerouter.proxy_server")


# ─── Format converters ────────────────────────────────────────────────────────

def _anthropic_to_openai_messages(anthropic_messages: list, system: str = None) -> list:
    """Convert Anthropic messages format to OpenAI format."""
    openai_messages = []

    # Anthropic puts system prompt separately; OpenAI puts it as first message
    if system:
        openai_messages.append({"role": "system", "content": system})

    for msg in anthropic_messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        # Anthropic content can be a list of blocks
        if isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            content = "\n".join(text_parts)

        openai_messages.append({"role": role, "content": content})

    return openai_messages


def _openai_response_to_anthropic(openai_resp: dict, model: str) -> dict:
    """Convert OpenAI response format to Anthropic format."""
    choice = openai_resp.get("choices", [{}])[0]
    message = choice.get("message", {})
    content = message.get("content", "")
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


def _make_anthropic_stream_chunk(text: str, msg_id: str, model: str, event_type: str = "content_block_delta") -> str:
    """Format a text chunk as an Anthropic SSE event."""
    if event_type == "message_start":
        data = {
            "type": "message_start",
            "message": {
                "id": msg_id,
                "type": "message",
                "role": "assistant",
                "content": [],
                "model": model,
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {"input_tokens": 0, "output_tokens": 0},
            },
        }
    elif event_type == "content_block_start":
        data = {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}
    elif event_type == "content_block_delta":
        data = {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": text}}
    elif event_type == "content_block_stop":
        data = {"type": "content_block_stop", "index": 0}
    elif event_type == "message_delta":
        data = {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None}, "usage": {"output_tokens": 0}}
    elif event_type == "message_stop":
        data = {"type": "message_stop"}
    else:
        data = {"type": event_type}

    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


# ─── App factory ──────────────────────────────────────────────────────────────

def create_proxy_app(api_key: Optional[str] = None) -> FastAPI:
    app = FastAPI(
        title="FreeRouter Proxy",
        description="OpenAI + Anthropic compatible proxy — routes to free providers",
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
        if "/" in model and not model.startswith(("gpt-", "claude-", "o1", "o3")):
            prefix = model.split("/", 1)[0]
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

    # ─── OpenAI format: POST /v1/chat/completions ─────────────────────────────

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
            async def generate():
                try:
                    async for chunk in router.stream(
                        messages=messages, model=model,
                        temperature=temperature, max_tokens=max_tokens,
                        provider=provider,
                    ):
                        yield chunk
                except RouterError as e:
                    yield f"data: {json.dumps({'error': {'message': str(e)}})}\n\n"
                    yield "data: [DONE]\n\n"

            return StreamingResponse(generate(), media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})
        else:
            try:
                return await router.complete(
                    messages=messages, model=model,
                    temperature=temperature, max_tokens=max_tokens,
                    provider=provider,
                )
            except RouterError as e:
                raise HTTPException(status_code=503, detail=str(e))

    # ─── Anthropic format: POST /v1/messages ──────────────────────────────────
    # Claude Code, Claude SDKs, and anything using ANTHROPIC_BASE_URL hit this.

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

        # Convert Anthropic → OpenAI message format
        messages = _anthropic_to_openai_messages(anthropic_msgs, system)
        provider = _detect_provider(model)
        router = get_router()
        msg_id = f"msg_{uuid.uuid4().hex[:24]}"

        if stream:
            async def generate_anthropic_stream():
                try:
                    # Send Anthropic stream preamble
                    yield _make_anthropic_stream_chunk("", msg_id, model, "message_start")
                    yield _make_anthropic_stream_chunk("", msg_id, model, "content_block_start")

                    # Stream content from provider (OpenAI SSE format)
                    async for raw_chunk in router.stream(
                        messages=messages, model=model,
                        temperature=temperature, max_tokens=max_tokens,
                        provider=provider,
                    ):
                        # raw_chunk is "data: {...}\n\n" or "data: [DONE]\n\n"
                        for line in raw_chunk.split("\n"):
                            line = line.strip()
                            if not line.startswith("data: "):
                                continue
                            payload = line[6:]
                            if payload == "[DONE]" or not payload:
                                continue
                            try:
                                parsed = json.loads(payload)
                                if parsed.get("error"):
                                    err_text = parsed["error"] if isinstance(parsed["error"], str) else parsed["error"].get("message", "Error")
                                    yield _make_anthropic_stream_chunk(f"\n\nError: {err_text}", msg_id, model, "content_block_delta")
                                    continue
                                delta = parsed.get("choices", [{}])[0].get("delta", {}).get("content")
                                if delta:
                                    yield _make_anthropic_stream_chunk(delta, msg_id, model, "content_block_delta")
                            except (json.JSONDecodeError, KeyError):
                                continue

                    # Send Anthropic stream closing events
                    yield _make_anthropic_stream_chunk("", msg_id, model, "content_block_stop")
                    yield _make_anthropic_stream_chunk("", msg_id, model, "message_delta")
                    yield _make_anthropic_stream_chunk("", msg_id, model, "message_stop")

                except RouterError as e:
                    yield _make_anthropic_stream_chunk(f"\n\nError: {str(e)}", msg_id, model, "content_block_delta")
                    yield _make_anthropic_stream_chunk("", msg_id, model, "content_block_stop")
                    yield _make_anthropic_stream_chunk("", msg_id, model, "message_stop")

            return StreamingResponse(
                generate_anthropic_stream(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
            )

        else:
            try:
                openai_result = await router.complete(
                    messages=messages, model=model,
                    temperature=temperature, max_tokens=max_tokens,
                    provider=provider,
                )
                return _openai_response_to_anthropic(openai_result, model)
            except RouterError as e:
                raise HTTPException(status_code=503, detail=str(e))

    return app

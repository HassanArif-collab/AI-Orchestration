"""
router.py — Direct provider routing without LiteLLM.

Context: This is the core of FreeRouter. Picks the best available provider
and streams/completes requests directly using their OpenAI-compatible APIs.
Auto-falls back to next provider if one fails or is rate-limited.

Routing priority (configured in providers.py):
  1. Ollama (local)   — priority 10, no rate limits
  2. Groq             — priority 20, fast free tier
  3. OpenRouter       — priority 30, many free models
  4. Together/DeepInfra — priority 40-50
  5. OpenAI/Anthropic — priority 60-70, paid fallbacks

Imports: providers.py
Imported by: web/app.py, proxy_server.py
"""

import json
import logging
import os
from typing import Any, AsyncIterator, Optional

import httpx

from .providers import (
    KNOWN_PROVIDERS, PROVIDER_MAP, DEFAULT_MODELS,
    get_provider_key, should_skip_provider,
    mark_hard_limited, update_usage_from_headers,
    get_configured_providers, fetch_ollama_models,
    load_env,
)

# Import custom adapters for non-OpenAI-compatible providers
from .adapters.apifreellm import APIFreeLLMAdapter

logger = logging.getLogger("freerouter.router")


class RouterError(Exception):
    pass


class Router:
    """Routes requests to the best available provider with automatic fallback."""

    def __init__(self):
        load_env()
        self._adapters: dict = {}  # Cache for custom adapters

    def _get_adapter(self, provider_name: str):
        """Get or create a custom adapter for providers that need one."""
        defn = PROVIDER_MAP.get(provider_name)
        if not defn or not defn.requires_custom_adapter:
            return None
        
        if provider_name in self._adapters:
            return self._adapters[provider_name]
        
        key = get_provider_key(provider_name)
        if not key:
            return None
        
        if provider_name == "apifreellm":
            adapter = APIFreeLLMAdapter(api_key=key)
            self._adapters[provider_name] = adapter
            return adapter
        
        return None
    
    def _needs_custom_adapter(self, provider_name: str) -> bool:
        """Check if a provider requires a custom adapter."""
        defn = PROVIDER_MAP.get(provider_name)
        return defn.requires_custom_adapter if defn else False

    def _get_provider_base_url(self, name: str) -> str:
        defn = PROVIDER_MAP[name]
        if name == "ollama":
            return os.getenv("OLLAMA_BASE_URL", defn.base_url).rstrip("/")
        return defn.base_url

    def _get_auth_headers(self, name: str) -> dict[str, str]:
        defn = PROVIDER_MAP[name]
        headers = {"Content-Type": "application/json"}
        if defn.requires_auth:
            key = get_provider_key(name)
            if key:
                headers["Authorization"] = f"Bearer {key}"
        if name == "openrouter":
            headers["HTTP-Referer"] = "https://freerouter.local"
            headers["X-Title"] = "FreeRouter"
        return headers

    def _resolve_model(self, provider_name: str, model: str) -> str:
        """
        Resolve the correct model string for a specific provider.

        Rules:
          "auto"              → provider's default model
          "ollama/llama3.2"  → if provider=ollama: "llama3.2"
                             → if provider=groq:   groq's default (don't send ollama name)
          "groq/llama-3.3"   → if provider=groq:   "llama-3.3"
          bare name          → pass through for ollama, use default for others if wrong
        """
        # Auto → always use provider default
        if model == "auto" or model.startswith("free-router/"):
            return DEFAULT_MODELS.get(provider_name, "llama-3.3-70b-versatile")

        # Has a provider prefix
        if "/" in model:
            prefix = model.split("/")[0]
            if prefix == provider_name:
                # Correct provider — strip prefix and use the rest
                return model.split("/", 1)[1]
            if prefix in PROVIDER_MAP:
                # Wrong provider's model — use this provider's default
                return DEFAULT_MODELS.get(provider_name, "llama-3.3-70b-versatile")

        # Bare model name — Ollama accepts anything, cloud providers use as-is
        if provider_name == "ollama":
            return model

        return model

    def _get_ordered_providers(self) -> list[str]:
        """Return configured providers in priority order, skipping rate-limited ones."""
        load_env()
        providers = []
        for defn in sorted(KNOWN_PROVIDERS, key=lambda x: x.priority):
            name = defn.name
            if should_skip_provider(name):
                logger.info(f"Skipping {name}: rate limited (will auto-reset)")
                continue
            if defn.requires_auth and not get_provider_key(name):
                continue
            providers.append(name)
        return providers

    # ─── Non-streaming ────────────────────────────────────────────────────────

    async def complete(
        self,
        messages: list[dict],
        model: str = "auto",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        provider: Optional[str] = None,
    ) -> dict[str, Any]:
        providers = [provider] if provider else self._get_ordered_providers()
        last_error = "No providers available. Add an API key in the Providers tab."

        for pname in providers:
            try:
                return await self._complete_with_provider(pname, messages, model, temperature, max_tokens)
            except RouterError as e:
                last_error = str(e)
                logger.warning(f"Provider {pname} failed: {e}, trying next")

        raise RouterError(f"All providers failed. Last error: {last_error}")

    async def _complete_with_provider(
        self, provider_name: str, messages: list[dict],
        model: str, temperature: float, max_tokens: int,
    ) -> dict[str, Any]:
        # Check if this provider needs a custom adapter
        if self._needs_custom_adapter(provider_name):
            adapter = self._get_adapter(provider_name)
            if adapter:
                try:
                    return await adapter.complete(
                        messages=messages,
                        model=model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                except Exception as e:
                    raise RouterError(str(e))
            else:
                raise RouterError(f"No API key for {provider_name}")
        
        # Standard OpenAI-compatible providers
        base_url = self._get_provider_base_url(provider_name)
        headers = self._get_auth_headers(provider_name)
        resolved_model = self._resolve_model(provider_name, model)

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json={"model": resolved_model, "messages": messages,
                          "temperature": temperature, "max_tokens": max_tokens, "stream": False},
                )
                update_usage_from_headers(provider_name, dict(resp.headers))

                if resp.status_code == 429:
                    mark_hard_limited(provider_name)
                    raise RouterError(f"Rate limited by {provider_name}")
                if resp.status_code != 200:
                    raise RouterError(f"HTTP {resp.status_code}: {resp.text[:300]}")

                data = resp.json()
                data["_provider"] = provider_name
                data["_model"] = resolved_model
                return data

        except httpx.ConnectError:
            raise RouterError(f"Cannot connect to {provider_name}")
        except httpx.TimeoutException:
            raise RouterError(f"Timeout from {provider_name}")
        except RouterError:
            raise
        except Exception as e:
            raise RouterError(f"Unexpected error from {provider_name}: {e}")

    # ─── Streaming ────────────────────────────────────────────────────────────

    async def stream(
        self,
        messages: list[dict],
        model: str = "auto",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        provider: Optional[str] = None,
    ) -> AsyncIterator[str]:
        providers = [provider] if provider else self._get_ordered_providers()

        if not providers:
            yield f"data: {json.dumps({'error': 'No providers configured. Add an API key in the Providers tab.'})}\n\n"
            yield "data: [DONE]\n\n"
            return

        last_error = "No providers available"

        for pname in providers:
            try:
                got_real_content = False
                async for chunk in self._stream_with_provider(pname, messages, model, temperature, max_tokens):
                    # Only count actual content chunks, not the meta header chunk
                    if '"content"' in chunk and '"delta"' in chunk:
                        got_real_content = True
                    yield chunk

                # If we streamed without raising RouterError, it worked
                return

            except RouterError as e:
                last_error = str(e)
                logger.warning(f"Provider {pname} stream failed: {e}, trying next")
                continue

        yield f"data: {json.dumps({'error': f'All providers failed: {last_error}'})}\n\n"
        yield "data: [DONE]\n\n"

    async def _stream_with_provider(
        self, provider_name: str, messages: list[dict],
        model: str, temperature: float, max_tokens: int,
    ) -> AsyncIterator[str]:
        # Check if this provider needs a custom adapter
        if self._needs_custom_adapter(provider_name):
            adapter = self._get_adapter(provider_name)
            if adapter:
                async for chunk in adapter.stream(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ):
                    yield chunk
                return
            else:
                raise RouterError(f"No API key for {provider_name}")
        
        # Standard OpenAI-compatible providers
        base_url = self._get_provider_base_url(provider_name)
        headers = self._get_auth_headers(provider_name)
        resolved_model = self._resolve_model(provider_name, model)

        logger.info(f"Routing to {provider_name} with model {resolved_model}")

        # Send meta chunk so the UI knows which provider is being used
        meta = {"_provider": provider_name, "_model": resolved_model}
        yield f"data: {json.dumps({'choices': [{'delta': {'role': 'assistant'}, 'index': 0}], 'meta': meta})}\n\n"

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
                async with client.stream(
                    "POST",
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json={"model": resolved_model, "messages": messages,
                          "temperature": temperature, "max_tokens": max_tokens, "stream": True},
                ) as resp:
                    update_usage_from_headers(provider_name, dict(resp.headers))

                    if resp.status_code == 429:
                        mark_hard_limited(provider_name)
                        raise RouterError(f"Rate limited by {provider_name}")

                    if resp.status_code != 200:
                        body = await resp.aread()
                        raise RouterError(f"HTTP {resp.status_code}: {body[:300].decode()}")

                    async for line in resp.aiter_lines():
                        if line:
                            yield line + "\n\n"

        except httpx.ConnectError:
            raise RouterError(f"Cannot connect to {provider_name}")
        except httpx.TimeoutException:
            raise RouterError(f"Timeout from {provider_name}")
        except RouterError:
            raise
        except Exception as e:
            raise RouterError(f"Unexpected error from {provider_name}: {e}")

    # ─── Model listing ────────────────────────────────────────────────────────

    async def list_models(self) -> list[dict]:
        """List available models — Ollama shows actual installed models, others show defaults."""
        models = []
        for defn, is_configured in get_configured_providers():
            if not is_configured:
                continue
            if defn.name == "ollama":
                ollama_models = await fetch_ollama_models()
                for m in ollama_models:
                    models.append({
                        "id": f"ollama/{m}",
                        "provider": "ollama",
                        "display": f"ollama / {m}",
                    })
            else:
                default = DEFAULT_MODELS.get(defn.name, "")
                if default:
                    models.append({
                        "id": f"{defn.name}/{default}",
                        "provider": defn.name,
                        "display": f"{defn.name} / {default}",
                    })

        models.insert(0, {"id": "auto", "provider": "auto", "display": "⚡ Auto (best available)"})
        return models


_router: Optional[Router] = None


def get_router() -> Router:
    global _router
    if _router is None:
        _router = Router()
    return _router

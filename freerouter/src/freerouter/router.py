"""
router.py — Direct provider routing without LiteLLM.

Context: This is the core of FreeRouter. It picks the best available provider
and streams/completes requests directly using their OpenAI-compatible APIs.

Routing strategy (priority order):
  1. Ollama (local) — fastest, no rate limits, private
  2. Groq — very fast, generous free tier
  3. OpenRouter — many free models
  4. Together / DeepInfra — cheap alternatives
  5. OpenAI / Anthropic — paid fallbacks

If a provider is rate-limited or down, it automatically tries the next one.

Usage:
    router = Router()
    async for chunk in router.stream(messages, model="auto"):
        yield chunk
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

logger = logging.getLogger("freerouter.router")


class RouterError(Exception):
    """Raised when no provider could handle the request."""
    pass


class Router:
    """
    Picks the best available provider and routes requests directly.
    No LiteLLM. No separate proxy process needed.
    """

    def __init__(self):
        load_env()

    def _get_provider_base_url(self, name: str) -> str:
        """Get effective base URL for a provider (respects env overrides)."""
        defn = PROVIDER_MAP[name]
        if name == "ollama":
            return os.getenv("OLLAMA_BASE_URL", defn.base_url).rstrip("/")
        return defn.base_url

    def _get_auth_headers(self, name: str) -> dict[str, str]:
        """Build auth headers for a provider."""
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
        Resolve the model string for a specific provider.
        If model is "auto" or a freerouter alias, use the provider's default.
        """
        if model.startswith("auto") or model.startswith("free-router/"):
            return DEFAULT_MODELS.get(provider_name, DEFAULT_MODELS.get("groq", "llama-3.3-70b-versatile"))

        # If model explicitly names a provider (e.g. "groq/llama-3.3-70b-versatile")
        # and this is that provider, strip the prefix
        if "/" in model and model.split("/")[0] == provider_name:
            return model.split("/", 1)[1]

        # For Ollama, pass model as-is (user might specify "llama3.2" etc.)
        if provider_name == "ollama":
            return model

        # For OpenRouter, models need the full path (e.g. "meta-llama/...")
        # If user passes just a model name, use the default
        return model

    def _get_ordered_providers(self) -> list[str]:
        """Return provider names in priority order, skipping unconfigured/limited ones."""
        load_env()
        providers = []
        for defn in sorted(KNOWN_PROVIDERS, key=lambda x: x.priority):
            name = defn.name
            # Skip if rate limited
            if should_skip_provider(name):
                logger.info(f"Skipping {name}: rate limited")
                continue
            # Skip cloud providers without API keys
            if defn.requires_auth and not get_provider_key(name):
                continue
            providers.append(name)
        return providers

    async def complete(
        self,
        messages: list[dict],
        model: str = "auto",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        provider: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Non-streaming completion. Tries providers in priority order.
        Returns OpenAI-compatible response dict.
        """
        providers = [provider] if provider else self._get_ordered_providers()
        last_error = "No providers available"

        for pname in providers:
            try:
                result = await self._complete_with_provider(
                    pname, messages, model, temperature, max_tokens
                )
                return result
            except RouterError as e:
                last_error = str(e)
                logger.warning(f"Provider {pname} failed: {e}, trying next")
                continue

        raise RouterError(f"All providers failed. Last error: {last_error}")

    async def _complete_with_provider(
        self,
        provider_name: str,
        messages: list[dict],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        base_url = self._get_provider_base_url(provider_name)
        headers = self._get_auth_headers(provider_name)
        resolved_model = self._resolve_model(provider_name, model)

        payload = {
            "model": resolved_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                update_usage_from_headers(provider_name, dict(resp.headers))

                if resp.status_code == 429:
                    mark_hard_limited(provider_name)
                    raise RouterError(f"Rate limited by {provider_name}")

                if resp.status_code != 200:
                    raise RouterError(f"HTTP {resp.status_code}: {resp.text[:200]}")

                data = resp.json()
                # Tag the response with which provider was used
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

    async def stream(
        self,
        messages: list[dict],
        model: str = "auto",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        provider: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """
        Streaming completion. Yields SSE-formatted chunks.
        Automatically falls back to next provider on failure.
        """
        providers = [provider] if provider else self._get_ordered_providers()

        if not providers:
            yield f"data: {json.dumps({'error': 'No providers configured. Add an API key in the Providers tab.'})}\n\n"
            yield "data: [DONE]\n\n"
            return

        last_error = "No providers available"

        for pname in providers:
            try:
                found_content = False
                async for chunk in self._stream_with_provider(pname, messages, model, temperature, max_tokens):
                    found_content = True
                    yield chunk
                if found_content:
                    return  # Success, stop trying providers
            except RouterError as e:
                last_error = str(e)
                logger.warning(f"Provider {pname} stream failed: {e}, trying next")
                continue

        # All providers failed
        error_msg = f"All providers failed: {last_error}"
        yield f"data: {json.dumps({'error': error_msg})}\n\n"
        yield "data: [DONE]\n\n"

    async def _stream_with_provider(
        self,
        provider_name: str,
        messages: list[dict],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[str]:
        base_url = self._get_provider_base_url(provider_name)
        headers = self._get_auth_headers(provider_name)
        resolved_model = self._resolve_model(provider_name, model)

        payload = {
            "model": resolved_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        # Send a "which provider" header chunk first
        meta = {"_provider": provider_name, "_model": resolved_model}
        yield f"data: {json.dumps({'choices': [{'delta': {'role': 'assistant'}, 'index': 0}], 'meta': meta})}\n\n"

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
                async with client.stream(
                    "POST",
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                ) as resp:
                    update_usage_from_headers(provider_name, dict(resp.headers))

                    if resp.status_code == 429:
                        mark_hard_limited(provider_name)
                        raise RouterError(f"Rate limited by {provider_name}")

                    if resp.status_code != 200:
                        body = await resp.aread()
                        raise RouterError(f"HTTP {resp.status_code}: {body[:200].decode()}")

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

    async def list_models(self) -> list[dict]:
        """List all available models from configured providers."""
        models = []
        for defn, is_configured in get_configured_providers():
            if not is_configured:
                continue
            if defn.name == "ollama":
                ollama_models = await fetch_ollama_models()
                for m in ollama_models:
                    models.append({
                        "id": m,
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

        # Always add the "auto" option
        models.insert(0, {
            "id": "auto",
            "provider": "auto",
            "display": "⚡ Auto (best available)",
        })

        return models


# Singleton instance
_router: Optional[Router] = None


def get_router() -> Router:
    global _router
    if _router is None:
        _router = Router()
    return _router

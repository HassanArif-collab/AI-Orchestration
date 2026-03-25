"""
router/client.py — HTTP client that calls FreeRouter proxy at localhost:4000.

Context: This is the ONLY way pipeline code should call LLMs.
FreeRouter is a separate running process — this file calls it over HTTP.
Never import from freerouter/. Never call provider APIs directly.

FreeRouter handles:
  - Picking the best free provider (Ollama → Groq → OpenRouter → ...)
  - Automatic fallback if a provider is rate-limited
  - Rate limit tracking and auto-reset after 60s

This client handles:
  - Connection errors (FreeRouter not running)
  - 503 from specific model → retry with "auto"
  - Structured output via instructor + openai client
  - Startup health check with clear error messages

Usage:
    from packages.router.client import RouterClient

    async with RouterClient() as client:
        text = await client.complete_text("Summarise this topic: ...")
        idea = await client.complete_structured(msgs, VideoIdea)

Imports: httpx, requests, instructor, openai, packages.core
Imported by: packages/pipeline/, packages/agents/
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Type, TypeVar

import httpx
import requests

from packages.core.config import get_settings
from packages.core.errors import LLMClientError, RateLimitError
from packages.core.logger import get_logger

log = get_logger(__name__)
T = TypeVar("T")


class RouterClient:
    """
    Async HTTP client for FreeRouter proxy.
    Use as an async context manager or call close() when done.

    Features:
        - Startup health check to ensure FreeRouter is running
        - Async health_check() method for monitoring
        - Automatic retry with exponential backoff
        - Fallback to "auto" model on 503 errors
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 90.0,
        startup_check: bool = True,
    ) -> None:
        """
        Initialize the RouterClient.

        Args:
            base_url: FreeRouter URL (defaults to config FREEROUTER_URL)
            timeout: HTTP timeout in seconds (default: 90.0)
            startup_check: If True, perform sync health check on init (default: True)

        Raises:
            LLMClientError: If startup_check=True and FreeRouter is not running
        """
        settings = get_settings()
        self.base_url = (base_url or settings.FREEROUTER_URL).rstrip("/")
        self.timeout = timeout
        self._healthy: bool | None = None

        # Determine if startup check should run
        should_check = startup_check and settings.FREEROUTER_STARTUP_CHECK
        if should_check:
            self._startup_health_check()

        self._http = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

    def _startup_health_check(self) -> None:
        """
        Synchronous health check at initialization.

        Raises:
            LLMClientError: If FreeRouter is not accessible
        """
        try:
            response = requests.get(
                f"{self.base_url}/health",
                timeout=5.0,
            )
            if response.status_code == 200:
                self._healthy = True
                log.info("freerouter_startup_check_passed", url=self.base_url)
                return
        except requests.exceptions.ConnectionError:
            pass
        except requests.exceptions.Timeout:
            pass
        except Exception as e:
            log.warning(f"freerouter_startup_check_exception: {e}")

        raise LLMClientError(
            f"FreeRouter is not running at {self.base_url}. "
            f"Please start it with: cd freerouter && python -m freerouter"
        )

    async def health_check(self) -> dict:
        """
        Async health check for monitoring.

        Returns:
            Dict with keys:
                - healthy (bool): Whether FreeRouter is responding
                - latency_ms (float | None): Response latency in milliseconds
        """
        start = datetime.now(timezone.utc)
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                if response.status_code == 200:
                    latency = (datetime.now(timezone.utc) - start).total_seconds() * 1000
                    self._healthy = True
                    return {"healthy": True, "latency_ms": latency}
        except Exception as e:
            log.debug(f"health_check_failed: {e}")

        self._healthy = False
        return {"healthy": False, "latency_ms": None}

    @property
    def is_healthy(self) -> bool:
        """Return whether the last health check passed."""
        return self._healthy or False

    async def __aenter__(self) -> RouterClient:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the HTTP client connection."""
        await self._http.aclose()

    async def complete(
        self,
        messages: list[dict],
        model: str = "auto",
        max_tokens: int = 2000,
        temperature: float = 0.7,
        retries: int = 3,
    ) -> dict:
        """
        Call FreeRouter and return parsed response with exponential backoff retries.

        Returns dict with keys:
            content  (str)  — the model's reply
            model    (str)  — actual model used (from x-freerouter-model header)
            provider (str)  — actual provider (from x-freerouter-provider header)
            usage    (dict) — prompt_tokens, completion_tokens

        If a specific model returns 503, automatically retries with model="auto"
        so FreeRouter's fallback chain kicks in.
        """
        body = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        last_error = None
        for attempt in range(retries):
            try:
                resp = await self._http.post("/v1/chat/completions", json=body)

                # Specific provider unavailable → let FreeRouter pick
                if resp.status_code == 503 and body["model"] != "auto":
                    log.warning("provider_unavailable", model=body["model"], retrying_with="auto")
                    body["model"] = "auto"
                    resp = await self._http.post("/v1/chat/completions", json=body)

                if resp.status_code == 429:
                    wait_time = (2**attempt) + 1
                    log.warning(f"rate_limit_hit_waiting_{wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue

                resp.raise_for_status()
                data = resp.json()

                result = {
                    "content": data["choices"][0]["message"]["content"],
                    "model": resp.headers.get("x-freerouter-model", body["model"]),
                    "provider": resp.headers.get("x-freerouter-provider", "unknown"),
                    "usage": data.get("usage", {}),
                }
                log.info(
                    "llm_call_ok",
                    provider=result["provider"],
                    model=result["model"],
                    tokens=result["usage"].get("total_tokens", 0),
                )
                return result

            except httpx.HTTPStatusError as e:
                last_error = e
                if attempt < retries - 1:
                    wait_time = (2**attempt) + 1
                    log.warning(f"http_error_{e.response.status_code}_retrying_in_{wait_time}s")
                    await asyncio.sleep(wait_time)
                continue
            except httpx.ConnectError as e:
                raise LLMClientError(
                    f"Cannot connect to FreeRouter at {self.base_url}. "
                    "Start it with: python -m freerouter proxy"
                ) from e
            except Exception as e:
                last_error = e
                if attempt < retries - 1:
                    await asyncio.sleep(1)
                continue

        raise LLMClientError(f"LLM call failed after {retries} attempts: {last_error}")

    async def complete_text(
        self,
        prompt: str,
        model: str = "auto",
        system: str = "",
        **kwargs: Any,
    ) -> str:
        """Convenience wrapper: single prompt string in, text string out."""
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        result = await self.complete(messages, model=model, **kwargs)
        return result["content"]

    async def complete_structured(
        self,
        messages: list[dict],
        response_model: Type[T],
        model: str = "auto",
        **kwargs: Any,
    ) -> T:
        """
        Get a structured response parsed into a Pydantic model.
        Uses instructor library which talks to FreeRouter as an OpenAI client.
        """
        try:
            import instructor
            from openai import AsyncOpenAI

            openai_client = AsyncOpenAI(
                base_url=f"{self.base_url}/v1",
                api_key="not-needed",
            )
            client = instructor.from_openai(openai_client)
            return await client.chat.completions.create(
                model=model,
                messages=messages,
                response_model=response_model,
                **kwargs,
            )
        except Exception as e:
            raise LLMClientError(f"Structured completion failed: {e}") from e

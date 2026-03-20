"""
FastAPI wrapper for task classification middleware.

This module provides additional endpoints and middleware for
intelligent task-based model routing with web search interception.
Also tracks rate-limit response headers to enable proactive
soft-limit switching (at 80-90% usage) before a hard 429 is hit.
"""

import asyncio
import json
import os
import logging
import hashlib
import time
from typing import Any, Optional, Dict, List
from functools import lru_cache

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from freerouter.classifier import TaskClassifier, TaskCategory
from freerouter.websearch import WebSearchInterceptor, SearchProvider, check_for_web_search_intent
from freerouter.health import ModelHealthChecker, get_health_checker
from freerouter.providers import (
    update_usage_from_headers, mark_hard_limited, should_skip_provider,
    get_all_usage, PROVIDER_MAP,
)
from freerouter.config import load_config

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("freerouter.proxy")


class ChatMessage(BaseModel):
    """Chat message model."""

    role: str
    content: str | list[Any]


class ChatCompletionRequest(BaseModel):
    """Chat completion request model."""

    model: str
    messages: list[ChatMessage]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False


class FreeRouterProxy:
    """FastAPI wrapper for task-based routing with web search support."""

    def __init__(
        self,
        litellm_base: str = "http://localhost:4000",
        classifier_model: str = "ollama/qwen2.5:3b",
        ollama_base: str = "http://localhost:11434",
        use_classification: bool = True,
        enable_web_search: bool = True,
        search_provider: SearchProvider = SearchProvider.DUCKDUCKGO,
        searxng_url: Optional[str] = None,
        config_path: Optional[str] = None,
        api_key: Optional[str] = None,
        state_dir: Optional[str] = None,
    ):
        """Initialize the proxy.

        Args:
            litellm_base: Base URL for LiteLLM proxy
            classifier_model: Model to use for classification
            ollama_base: Base URL for Ollama API
            use_classification: Whether to use AI-based classification
            enable_web_search: Whether to intercept web search tool calls
            search_provider: Search provider to use
            searxng_url: URL for SearXNG instance (if using SearXNG)
            config_path: Optional path to config file
            api_key: Optional API key for proxy authentication
            state_dir: Directory for shared state files (multi-worker)
        """
        self.litellm_base = litellm_base
        self.classifier = TaskClassifier(
            classifier_model=classifier_model,
            api_base=ollama_base,
            use_fast_classifier=use_classification,
        )

        # Web search interceptor
        self.web_search_enabled = enable_web_search
        self.web_search = WebSearchInterceptor(
            provider=search_provider,
            searxng_url=searxng_url,
            enabled=enable_web_search,
        )

        # Health checker
        self.health_checker = get_health_checker()
        self.config = load_config() if not config_path else self._load_config_from_path(config_path)
        
        # Fallback cache with TTL and shared state support
        self._state_dir = state_dir or os.path.join(os.path.dirname(__file__), "..", "..", "state")
        os.makedirs(self._state_dir, exist_ok=True)
        self._fallback_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 30  # seconds
        self._last_cache_load = 0

        # Circuit Breaker state
        self._consecutive_failures: Dict[str, int] = {}
        self._failure_threshold = 3
        
        # Classification cache
        self._classification_cache: Dict[str, Any] = {}
        
        # API key authentication
        self._api_key = api_key or os.getenv("FREEROUTER_API_KEY")
        
        # Create FastAPI app
        self.app = FastAPI(
            title="FreeRouter",
            description="Smart LLM Proxy that always prefers free models",
            version="1.0.0",
        )

        # Add CORS middleware (restricted by ALLOWED_ORIGINS env var)
        allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "*")
        allowed_origins = [o.strip() for o in allowed_origins_raw.split(",") if o.strip()]
        
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Add authentication middleware if API key is set
        if self._api_key:
            self.app.add_middleware(AuthMiddleware, api_key=self._api_key)

        # Add routes
        self._setup_routes()

        # Startup/shutdown events
        self.app.on_event("startup")(self._on_startup)
        self.app.on_event("shutdown")(self._on_shutdown)

    def _load_config_from_path(self, path: str) -> dict:
        """Load config from specific path."""
        import yaml
        with open(path, "r") as f:
            return yaml.safe_load(f)

    async def _on_startup(self) -> None:
        """Initialize on startup."""
        # Run initial health check
        await self._run_health_check()
        # Start periodic health checks
        api_keys = {
            "openrouter": os.getenv("OPENROUTER_API_KEY"),
            "groq": os.getenv("GROQ_API_KEY"),
            "openai": os.getenv("OPENAI_API_KEY"),
            "anthropic": os.getenv("ANTHROPIC_API_KEY"),
        }
        api_keys = {k: v for k, v in api_keys.items() if v}
        asyncio.create_task(
            self.health_checker.start_periodic_checks(
                self.config.get("model_list", []),
                api_keys
            )
        )

    async def _on_shutdown(self) -> None:
        """Cleanup on shutdown."""
        self.health_checker.stop()

    async def _run_health_check(self) -> None:
        """Run a health check on all providers."""
        api_keys = {
            "openrouter": os.getenv("OPENROUTER_API_KEY"),
            "groq": os.getenv("GROQ_API_KEY"),
            "openai": os.getenv("OPENAI_API_KEY"),
            "anthropic": os.getenv("ANTHROPIC_API_KEY"),
        }
        # Remove None values
        api_keys = {k: v for k, v in api_keys.items() if v}

        # Check providers
        providers = ["ollama", "groq", "openrouter"]
        for provider in providers:
            api_key = api_keys.get(provider)
            health = await self.health_checker.check_provider(provider, api_key)
            self.health_checker.provider_health[provider] = health
        
        logger.info(f"Health check completed: {self.health_checker.get_status_report()}")
        
        # Invalidate shared fallback cache after health update
        self._invalidate_shared_cache()

    def _setup_routes(self) -> None:
        """Set up API routes."""

        @self.app.get("/health")
        async def health() -> dict:
            """Health check endpoint."""
            return {
                "status": "healthy",
                "version": "1.0.0",
                "providers": self.health_checker.get_status_report(),
            }

        @self.app.get("/status")
        async def status() -> dict:
            """Get detailed status of all providers."""
            return {
                "version": "1.0.0",
                "providers": self.health_checker.get_status_report(),
                "web_search_enabled": self.web_search_enabled,
            }

        @self.app.get("/v1/usage")
        async def usage() -> dict:
            """Show rate-limit usage per provider."""
            all_u = get_all_usage()
            result: Dict[str, Any] = {}
            for name, u in all_u.items():
                pct = u.requests_used_pct
                result[name] = {
                    "requests_remaining": u.requests_remaining,
                    "requests_limit": u.requests_limit,
                    "tokens_remaining": u.tokens_remaining,
                    "tokens_limit": u.tokens_limit,
                    "used_pct": round(pct * 100, 1) if pct is not None else None,
                    "soft_limited": u.is_soft_limited,
                    "hard_limited": u.is_hard_limited,
                    "last_updated": u.last_updated,
                }
            return result

        @self.app.post("/v1/chat/completions")
        async def chat_completions(request: Request) -> Response:
            """Handle chat completions with intelligent routing and web search."""
            body = await request.json()

            # Get the model from request
            model = body.get("model", "free-router/balanced")

            # If using auto-routing, classify the task
            if model == "free-router/auto":
                model = await self._classify_and_route(body)
                logger.debug(f"Auto-routing to model: {model}")

            # Check for web search tool calls and intercept
            if self.web_search_enabled:
                body = await self._handle_web_search(body)

            # Forward to LiteLLM
            return await self._forward_to_litellm(request, model, body)

        @self.app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
        async def proxy(request: Request, path: str) -> Response:
            """Proxy all other requests to LiteLLM."""
            return await self._forward_to_litellm(request, None)

    async def _classify_and_route(self, body: Dict[str, Any]) -> str:
        """Classify the task and return the best model alias with health-aware fallbacks.

        Args:
            body: The request body

        Returns:
            The recommended model alias
        """
        messages = body.get("messages", [])
        if not isinstance(messages, list):
            messages = []
        
        content_parts: List[str] = []
        has_images = False

        # Extract text content from messages
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            
            msg_content = msg.get("content", "")
            if isinstance(msg_content, str):
                content_parts.append(msg_content)
            elif isinstance(msg_content, list):
                for item in msg_content:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            text = item.get("text", "")
                            if isinstance(text, str):
                                content_parts.append(text)
                        elif item.get("type") == "image_url":
                            has_images = True

        content = "\n".join(content_parts).strip()

        # Check for vision content
        if has_images:
            return "free-router/vision"

        # Classify the task with caching
        if content:
            result = await self._classify_with_cache(content)
            primary_model = result.recommended_model
            
            # Get health-adjusted fallback chain
            fallback_chain = self._get_healthy_fallback_chain(primary_model)
            logger.debug(f"Selected model: {primary_model}, healthy fallbacks: {fallback_chain}")
            
            return primary_model
        
        # Default to balanced if no content
        return "free-router/balanced"

    def _get_healthy_fallback_chain(self, model_alias: str) -> List[str]:
        """Get fallback chain excluding unhealthy providers.
        
        Uses cache and shared state to avoid recomputing on every request.
        Invalidates cache when health status changes.
        
        Args:
            model_alias: Primary model alias
            
        Returns:
            List of healthy model aliases (primary first)
        """
        # Try to load from shared cache first
        cached = self._load_shared_cache()
        if model_alias in cached:
            logger.debug(f"Using cached fallback chain for {model_alias}")
            return cached[model_alias]
        
        # Build healthy fallback chain
        fallbacks_config = self.config.get("fallbacks", [])
        healthy_chain = []
        
        for fb_config in fallbacks_config:
            if fb_config.get("model") == model_alias:
                # Include primary model if healthy
                primary_provider = self._provider_from_model(model_alias)
                if primary_provider and should_skip_provider(primary_provider):
                    logger.warning(f"Primary model {model_alias} provider {primary_provider} is unhealthy, skipping")
                else:
                    healthy_chain.append(model_alias)
                
                # Add healthy fallbacks
                for fb_model in fb_config.get("fallbacks", []):
                    fb_provider = self._provider_from_model(fb_model)
                    if fb_provider and should_skip_provider(fb_provider):
                        logger.warning(f"Skipping unhealthy fallback {fb_model} (provider: {fb_provider})")
                        continue
                    healthy_chain.append(fb_model)
                
                break
        
        # If no fallback config found, just return primary if healthy
        if not healthy_chain:
            healthy_chain = [model_alias]
        
        # Cache the result locally and share to disk
        self._fallback_cache[model_alias] = healthy_chain
        self._save_shared_cache({model_alias: healthy_chain})
        
        return healthy_chain

    def _load_shared_cache(self) -> Dict[str, List[str]]:
        """Load fallback cache from shared file."""
        cache_file = os.path.join(self._state_dir, "fallback_cache.json")
        now = time.time()
        
        # Reload from disk if cache is stale
        if now - self._last_cache_load > self._cache_ttl:
            try:
                if os.path.exists(cache_file):
                    with open(cache_file, "r") as f:
                        data = json.load(f)
                        # Check TTL per entry
                        fresh_data = {}
                        for model, entry in data.items():
                            timestamp = entry.get("_ts", 0)
                            if now - timestamp < self._cache_ttl:
                                fresh_data[model] = entry["chain"]
                        self._fallback_cache.update(fresh_data)
                        self._last_cache_load = now
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to load shared cache: {e}")
        
        return self._fallback_cache

    def _save_shared_cache(self, update: Dict[str, List[str]]) -> None:
        """Update shared cache file atomically."""
        cache_file = os.path.join(self._state_dir, "fallback_cache.json")
        now = time.time()
        
        # Load existing cache
        cache_data = {}
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r") as f:
                    cache_data = json.load(f)
            except json.JSONDecodeError:
                pass
        
        # Update with new entries
        for model, chain in update.items():
            cache_data[model] = {
                "chain": chain,
                "_ts": now,
            }
        
        # Clean old entries
        cache_data = {
            k: v for k, v in cache_data.items()
            if now - v.get("_ts", 0) < self._cache_ttl * 10  # Keep for 5 minutes
        }
        
        # Write atomically
        temp_file = cache_file + ".tmp"
        try:
            with open(temp_file, "w") as f:
                json.dump(cache_data, f, indent=2)
            os.replace(temp_file, cache_file)
        except Exception as e:
            logger.error(f"Failed to save shared cache: {e}")

    def _invalidate_shared_cache(self) -> None:
        """Invalidate shared cache when health changes."""
        self._fallback_cache.clear()
        cache_file = os.path.join(self._state_dir, "fallback_cache.json")
        try:
            if os.path.exists(cache_file):
                os.remove(cache_file)
        except Exception as e:
            logger.warning(f"Failed to invalidate cache: {e}")

    async def _classify_with_cache(self, content: str) -> Any:
        """Classify with simple in-memory cache to reduce latency.
        
        Args:
            content: The text content to classify
            
        Returns:
            ClassificationResult
        """
        # Simple string matching for exact repeats
        if content in self._classification_cache:
            logger.debug("Using cached classification result")
            return self._classification_cache[content]
        
        result = await self.classifier.classify(content)
        
        # Cache the result (limit cache size to 100 entries)
        if len(self._classification_cache) >= 100:
            # Simple FIFO eviction
            first_key = next(iter(self._classification_cache))
            self._classification_cache.pop(first_key)
            
        self._classification_cache[content] = result
        return result

    async def _handle_web_search(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """Handle web search tool calls in request.

        Checks if the last message contains tool calls for web search
        and executes them, adding results as tool messages.

        Args:
            body: The request body

        Returns:
            Modified request body with search results
        """
        messages = body.get("messages", [])
        if not isinstance(messages, list) or not messages:
            return body

        # Check for web search intent in any message
        for msg in messages:
            if isinstance(msg, dict):
                content = msg.get("content", "")
                if isinstance(content, str) and check_for_web_search_intent(content):
                    # Auto-inject web search results
                    search_response = await self.web_search.execute_search(content[:500])
                    if search_response.results:
                        # Add search results as context
                        search_context = self.web_search.format_results_as_message(search_response)
                        # Prepend to system or first message
                        if messages and messages[0].get("role") == "system":
                            system_msg = messages[0].copy()
                            if isinstance(system_msg.get("content"), str):
                                system_msg["content"] += "\n\n" + search_context
                                messages[0] = system_msg
                        else:
                            system_msg = {
                                "role": "system",
                                "content": search_context
                            }
                            messages.insert(0, system_msg)
                        body["messages"] = messages
                    return body

        # Check for explicit tool calls in the last message
        last_message = messages[-1]
        if not isinstance(last_message, dict):
            return body
            
        tool_calls = last_message.get("tool_calls", [])
        if not isinstance(tool_calls, list) or not tool_calls:
            return body

        # Process tool calls for web search
        new_messages = messages.copy()
        modified = False
        
        for tool_call in tool_calls:
            if not isinstance(tool_call, dict):
                continue
                
            if self.web_search.is_search_tool(tool_call):
                query = self.web_search.extract_search_query(tool_call)
                if query:
                    # Execute search
                    response = await self.web_search.execute_search(query)
                    # Create tool result message
                    tool_result = self.web_search.create_tool_result(
                        tool_call.get("id", "unknown"),
                        response
                    )
                    new_messages.append(tool_result)
                    modified = True

        if modified:
            body["messages"] = new_messages
        
        return body

    async def _forward_to_litellm(
        self,
        request: Request,
        override_model: Optional[str] = None,
        body: Optional[Dict[str, Any]] = None,
    ) -> Response:
        """Forward request to LiteLLM proxy.

        Args:
            request: The incoming request
            override_model: Optional model to override in request
            body: Optional pre-parsed body (to avoid re-parsing)

        Returns:
            The response from LiteLLM
        """
        if body is None:
            body = await request.json()

        # Ensure body is a dict
        if not isinstance(body, dict):
            body = {}

        # Override model if specified
        if override_model:
            body["model"] = override_model

        # Check if streaming is requested
        stream = body.get("stream", False)

        # Get headers to forward
        headers = dict(request.headers)
        headers.pop("host", None)
        headers.pop("content-length", None)

        # Forward request
        timeout = httpx.Timeout(300.0, connect=60.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                if stream:
                    # Handle streaming response
                    resp = await self._forward_streaming(client, body, headers)
                    # Note: For streaming, we record success/failure inside the generator
                    return resp
                else:
                    response = await client.post(
                        f"{self.litellm_base}/v1/chat/completions",
                        json=body,
                        headers=headers,
                    )
                    
                    # ── Circuit Breaker & Rate-Limit Tracking ────────────────
                    resp_model = body.get("model", "")
                    provider_name = self._provider_from_model(resp_model) if isinstance(resp_model, str) else None
                    
                    if 200 <= response.status_code < 300:
                        if provider_name:
                            self._record_success(provider_name)
                            update_usage_from_headers(provider_name, dict(response.headers))
                    elif response.status_code >= 500 or response.status_code == 429:
                        if provider_name:
                            self._record_failure(provider_name)
                            if response.status_code == 429:
                                mark_hard_limited(provider_name)
                    # ────────────────────────────────────────────────────────
                    
                    return Response(
                        content=response.content,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                    )
            except (httpx.HTTPError, Exception) as e:
                resp_model = body.get("model", "")
                provider_name = self._provider_from_model(resp_model) if isinstance(resp_model, str) else None
                if provider_name:
                    self._record_failure(provider_name)
                
                logger.error(f"LiteLLM forwarding error: {e}")
                raise HTTPException(
                    status_code=502,
                    detail=f"LiteLLM forwarding failed: {str(e)}",
                )

    async def _forward_streaming(
        self,
        client: httpx.AsyncClient,
        body: Dict[str, Any],
        headers: Dict[str, str],
    ) -> StreamingResponse:
        """Forward streaming request with rate-limit tracking."""
        model = body.get("model", "")
        provider_name = self._provider_from_model(model) if isinstance(model, str) else None
        
        async def stream_generator():
            try:
                async with client.stream(
                    "POST",
                    f"{self.litellm_base}/v1/chat/completions",
                    json=body,
                    headers=headers,
                ) as response:
                    # Track rate limits
                    if response.status_code == 429 and provider_name:
                        mark_hard_limited(provider_name)
                    elif provider_name:
                        update_usage_from_headers(provider_name, dict(response.headers))
                    
                    yield f"event: message\ndata: {json.dumps({'choices': [{'delta': {'content': ''}}]})}\n\n"
                    
                    async for chunk in response.aiter_bytes():
                        yield chunk
                    
                    # If we got here without error, record success
                    if 200 <= response.status_code < 300 and provider_name:
                        self._record_success(provider_name)
                        
            except httpx.HTTPError as e:
                logger.error(f"Streaming error: {e}")
                if provider_name:
                    self._record_failure(provider_name)
                    mark_hard_limited(provider_name)
                # Return error as SSE
                error_data = json.dumps({"error": {"message": str(e), "type": "stream_error"}})
                yield f"event: error\ndata: {error_data}\n\n"
            except Exception as e:
                logger.error(f"Streaming error: {e}")
                if provider_name:
                    self._record_failure(provider_name)
                error_data = json.dumps({"error": {"message": str(e), "type": "stream_error"}})
                yield f"event: error\ndata: {error_data}\n\n"

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    def _record_success(self, provider_name: str):
        """Record a successful request for a provider."""
        self._consecutive_failures[provider_name] = 0

    def _record_success(self, provider_name: str):
        """Record a successful request for a provider."""
        self._consecutive_failures[provider_name] = 0

    def _record_failure(self, provider_name: str):
        """Record a failed request for a provider and trigger circuit breaker if needed."""
        count = self._consecutive_failures.get(provider_name, 0) + 1
        self._consecutive_failures[provider_name] = count
        if count >= self._failure_threshold:
            logger.warning(f"Circuit breaker triggered for {provider_name} ({count} failures)")
            mark_hard_limited(provider_name)

    @staticmethod
    def _provider_from_model(model_alias: Optional[str]) -> Optional[str]:
        """
        Infer the upstream provider name from a model alias or backend model string.
        Used to route soft-limit updates to the right ProviderUsage tracker.
        """
        if not model_alias:
            return None
            
        alias_lower = model_alias.lower()
        # Explicit backend model prefixes (e.g. "groq/llama-3.3-70b")
        for name, defn in PROVIDER_MAP.items():
            if defn.litellm_prefix and alias_lower.startswith(defn.litellm_prefix):
                return name
        # Alias-based hints (e.g. "free-router/fast-groq")
        for name in PROVIDER_MAP:
            if name in alias_lower:
                return name
        return None


class AuthMiddleware(BaseHTTPMiddleware):
    """Simple API key authentication middleware."""

    def __init__(self, app, api_key: str):
        """Initialize middleware.

        Args:
            app: FastAPI app
            api_key: Expected API key
        """
        super().__init__(app)
        self.api_key = api_key

    async def dispatch(self, request: Request, call_next):
        """Process request."""
        # Skip auth for health and status endpoints
        if request.url.path in ["/health", "/status", "/docs", "/openapi.json"]:
            return await call_next(request)

        # Check for API key in Authorization header or query param
        auth_header = request.headers.get("Authorization", "")
        api_key = ""
        
        if auth_header.startswith("Bearer "):
            api_key = auth_header[7:]
        else:
            api_key = request.query_params.get("api_key", "")
        
        if not api_key or api_key != self.api_key:
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid or missing API key"},
            )
        
        return await call_next(request)


def create_app() -> FastAPI:
    """Create and return the FastAPI application."""
    proxy = FreeRouterProxy()
    return proxy.app


# For running with uvicorn
app = create_app()
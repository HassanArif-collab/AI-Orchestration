"""
Model availability health checker for FreeRouter.

Periodically checks if configured models are available and
adjusts fallback chains based on availability.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

import httpx


class ModelStatus(Enum):
    """Status of a model."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ModelHealth:
    """Health status of a model."""
    name: str
    status: ModelStatus = ModelStatus.UNKNOWN
    last_check: float = 0.0
    latency_ms: float = 0.0
    error_count: int = 0
    success_count: int = 0
    last_error: Optional[str] = None


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    healthy_count: int = 0
    degraded_count: int = 0
    unhealthy_count: int = 0
    models: dict[str, ModelHealth] = field(default_factory=dict)

    @property
    def total_checked(self) -> int:
        return self.healthy_count + self.degraded_count + self.unhealthy_count


class ModelHealthChecker:
    """Checks and tracks model availability."""

    # Provider-specific health endpoints
    HEALTH_ENDPOINTS = {
        "ollama": {
            "url": "http://localhost:11434/api/tags",
            "method": "GET",
        },
        "groq": {
            "url": "https://api.groq.com/openai/v1/models",
            "method": "GET",
            "requires_auth": True,
        },
        "openrouter": {
            "url": "https://openrouter.ai/api/v1/models",
            "method": "GET",
            "requires_auth": True,
        },
        "openai": {
            "url": "https://api.openai.com/v1/models",
            "method": "GET",
            "requires_auth": True,
        },
        "anthropic": {
            "url": "https://api.anthropic.com/v1/models",
            "method": "GET",
            "requires_auth": True,
        },
    }

    def __init__(
        self,
        check_interval: int = 300,  # 5 minutes
        degraded_threshold: int = 3,  # Errors before degraded
        unhealthy_threshold: int = 5,  # Errors before unhealthy
        recovery_threshold: int = 2,  # Successes before recovery
        timeout: float = 10.0,
    ):
        """Initialize health checker.

        Args:
            check_interval: Seconds between health checks
            degraded_threshold: Consecutive errors before marking degraded
            unhealthy_threshold: Consecutive errors before marking unhealthy
            recovery_threshold: Consecutive successes for recovery
            timeout: Request timeout in seconds
        """
        self.check_interval = check_interval
        self.degraded_threshold = degraded_threshold
        self.unhealthy_threshold = unhealthy_threshold
        self.recovery_threshold = recovery_threshold
        self.timeout = timeout

        self.model_health: dict[str, ModelHealth] = {}
        self.provider_health: dict[str, ModelHealth] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def get_provider_from_model(self, model: str) -> str:
        """Extract provider name from model string.

        Args:
            model: Model name (e.g., "ollama/qwen2.5:7b")

        Returns:
            Provider name
        """
        if model.startswith("ollama/"):
            return "ollama"
        elif model.startswith("groq/"):
            return "groq"
        elif model.startswith("openrouter/"):
            return "openrouter"
        elif model.startswith("openai/"):
            return "openai"
        elif model.startswith("anthropic/"):
            return "anthropic"
        return "unknown"

    async def check_provider(self, provider: str, api_key: Optional[str] = None) -> ModelHealth:
        """Check health of a provider.

        Args:
            provider: Provider name
            api_key: Optional API key for auth

        Returns:
            ModelHealth status
        """
        health = ModelHealth(name=provider)
        start_time = time.time()

        endpoint_config = self.HEALTH_ENDPOINTS.get(provider)
        if not endpoint_config:
            health.status = ModelStatus.UNKNOWN
            health.last_error = "Unknown provider"
            return health

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                headers = {}
                if endpoint_config.get("requires_auth") and api_key:
                    headers["Authorization"] = f"Bearer {api_key}"

                response = await client.get(
                    endpoint_config["url"],
                    headers=headers,
                )

                health.latency_ms = (time.time() - start_time) * 1000

                if response.status_code == 200:
                    health.status = ModelStatus.HEALTHY
                    health.success_count = 1
                elif response.status_code in (401, 403):
                    # Auth issue, but provider is reachable
                    health.status = ModelStatus.DEGRADED
                    health.last_error = "Authentication issue"
                elif response.status_code == 429:
                    # Rate limited
                    health.status = ModelStatus.DEGRADED
                    health.last_error = "Rate limited"
                else:
                    health.status = ModelStatus.UNHEALTHY
                    health.error_count = 1
                    health.last_error = f"Status {response.status_code}"

        except httpx.TimeoutException:
            health.status = ModelStatus.UNHEALTHY
            health.error_count = 1
            health.last_error = "Timeout"
        except httpx.ConnectError:
            health.status = ModelStatus.UNHEALTHY
            health.error_count = 1
            health.last_error = "Connection refused"
        except Exception as e:
            health.status = ModelStatus.UNKNOWN
            health.last_error = str(e)

        health.last_check = time.time()
        return health

    async def check_model_list(
        self,
        models: list[dict],
        api_keys: Optional[dict] = None,
    ) -> HealthCheckResult:
        """Check health of all models by provider.

        Args:
            models: List of model configurations
            api_keys: Dict of provider -> API key

        Returns:
            HealthCheckResult with status for each provider
        """
        api_keys = api_keys or {}
        providers = set()

        for model_config in models:
            model_name = model_config.get("model", "")
            provider = self.get_provider_from_model(model_name)
            if provider != "unknown":
                providers.add(provider)

        # Check all providers in parallel
        tasks = []
        for provider in providers:
            api_key = api_keys.get(provider)
            tasks.append(self.check_provider(provider, api_key))

        results = await asyncio.gather(*tasks)

        result = HealthCheckResult()
        for health in results:
            self.provider_health[health.name] = health
            result.models[health.name] = health

            if health.status == ModelStatus.HEALTHY:
                result.healthy_count += 1
            elif health.status == ModelStatus.DEGRADED:
                result.degraded_count += 1
            elif health.status == ModelStatus.UNHEALTHY:
                result.unhealthy_count += 1

        return result

    def get_available_models(
        self,
        model_list: list[dict],
        include_degraded: bool = True,
    ) -> list[str]:
        """Get list of available models based on health status.

        Args:
            model_list: List of model configurations
            include_degraded: Include degraded models

        Returns:
            List of available model names
        """
        available = []

        for model_config in model_list:
            model_alias = model_config.get("model_name", "")
            backend_model = model_config.get("litellm_params", {}).get("model", "")
            provider = self.get_provider_from_model(backend_model)

            health = self.provider_health.get(provider)
            if not health:
                # Unknown status, include it
                available.append(model_alias)
                continue

            if health.status == ModelStatus.HEALTHY:
                available.append(model_alias)
            elif health.status == ModelStatus.DEGRADED and include_degraded:
                available.append(model_alias)
            # Skip UNHEALTHY models

        return available

    def adjust_fallbacks(
        self,
        fallbacks: list[dict],
        exclude_unhealthy: bool = True,
    ) -> list[dict]:
        """Adjust fallback chains based on model health.

        Args:
            fallbacks: Original fallback configuration
            exclude_unhealthy: Whether to exclude unhealthy models

        Returns:
            Adjusted fallback configuration
        """
        adjusted = []

        for fallback_config in fallbacks:
            model = fallback_config.get("model")
            fallback_list = fallback_config.get("fallbacks", [])

            # Filter out unhealthy models from fallbacks
            new_fallbacks = []
            for fb_model in fallback_list:
                # Get provider for this fallback model
                # This requires model_list lookup, simplified here
                provider = self._get_provider_for_alias(fb_model)
                health = self.provider_health.get(provider)

                if not health:
                    # Unknown, keep it
                    new_fallbacks.append(fb_model)
                elif health.status == ModelStatus.HEALTHY:
                    new_fallbacks.append(fb_model)
                elif health.status == ModelStatus.DEGRADED:
                    new_fallbacks.append(fb_model)
                # Skip UNHEALTHY

            adjusted.append({
                "model": model,
                "fallbacks": new_fallbacks,
            })

        return adjusted

    def _get_provider_for_alias(self, alias: str) -> str:
        """Get provider for a model alias.

        Args:
            alias: Model alias (e.g., "free-router/fast")

        Returns:
            Provider name
        """
        # Simple mapping based on alias naming
        if "ollama" in alias:
            return "ollama"
        elif "groq" in alias:
            return "groq"
        elif "openrouter" in alias:
            return "openrouter"

        # Default based on category
        # These are typically local-first
        if alias in ["free-router/fast", "free-router/smart", "free-router/balanced"]:
            return "ollama"
        elif alias in ["free-router/fast-groq", "free-router/coder-groq", "free-router/smart-groq"]:
            return "groq"
        else:
            return "openrouter"

    def get_status_report(self) -> dict:
        """Get a status report of all providers.

        Returns:
            Dict with provider status information
        """
        report = {}

        for provider, health in self.provider_health.items():
            report[provider] = {
                "status": health.status.value,
                "latency_ms": round(health.latency_ms, 2),
                "last_check": health.last_check,
                "error_count": health.error_count,
                "last_error": health.last_error,
            }

        return report

    async def start_periodic_checks(
        self,
        models: list[dict],
        api_keys: Optional[dict] = None,
    ) -> None:
        """Start periodic health checks.

        Args:
            models: List of model configurations
            api_keys: Dict of provider -> API key
        """
        self._running = True

        while self._running:
            try:
                await self.check_model_list(models, api_keys)
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Health check error: {e}")
                await asyncio.sleep(60)  # Wait before retry

    def stop(self) -> None:
        """Stop periodic health checks."""
        self._running = False
        if self._task:
            self._task.cancel()


# Singleton instance for app state
_health_checker: Optional[ModelHealthChecker] = None


def get_health_checker() -> ModelHealthChecker:
    """Get the global health checker instance."""
    global _health_checker
    if _health_checker is None:
        _health_checker = ModelHealthChecker()
    return _health_checker
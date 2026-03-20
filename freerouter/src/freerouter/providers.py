"""
Provider management for FreeRouter.

Handles adding, listing, and tracking usage for all AI model providers
(both cloud-based and local like Ollama).
"""

import os
import json
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv, set_key, dotenv_values


# ─── Provider Definitions ────────────────────────────────────────────────────

class ProviderType(str, Enum):
    CLOUD = "cloud"
    LOCAL = "local"


@dataclass
class ProviderDefinition:
    """Static definition of a supported provider."""
    name: str           # Internal key e.g. "openrouter"
    display_name: str   # Human label e.g. "OpenRouter"
    provider_type: ProviderType
    env_key: str        # .env variable name for existence/base e.g. "OPENROUTER_API_KEY"
    signup_url: str     # Where to get a key
    health_url: str     # API endpoint to ping
    requires_auth: bool = True
    auth_env_key: Optional[str] = None  # Optional secondary key for auth (e.g. OLLAMA_API_KEY)
    # LiteLLM prefix used in model strings
    litellm_prefix: str = ""
    # Groq/OpenRouter specific: rate-limit header name
    remaining_header: str = "x-ratelimit-remaining-requests"
    limit_header: str = "x-ratelimit-limit-requests"
    # Soft-limit threshold: switch when usage > this fraction
    soft_limit_threshold: float = 0.90


KNOWN_PROVIDERS: list[ProviderDefinition] = [
    ProviderDefinition(
        name="openrouter",
        display_name="OpenRouter (Free Cloud Models)",
        provider_type=ProviderType.CLOUD,
        env_key="OPENROUTER_API_KEY",
        signup_url="https://openrouter.ai/keys",
        health_url="https://openrouter.ai/api/v1/models",
        litellm_prefix="openrouter/",
        remaining_header="x-ratelimit-remaining-requests",
        limit_header="x-ratelimit-limit-requests",
    ),
    ProviderDefinition(
        name="groq",
        display_name="Groq (Very Fast Free Inference)",
        provider_type=ProviderType.CLOUD,
        env_key="GROQ_API_KEY",
        signup_url="https://console.groq.com/keys",
        health_url="https://api.groq.com/openai/v1/models",
        litellm_prefix="groq/",
        remaining_header="x-ratelimit-remaining-requests",
        limit_header="x-ratelimit-limit-requests",
    ),
    ProviderDefinition(
        name="anthropic",
        display_name="Anthropic (Claude models)",
        provider_type=ProviderType.CLOUD,
        env_key="ANTHROPIC_API_KEY",
        signup_url="https://console.anthropic.com/account/keys",
        health_url="https://api.anthropic.com/v1/models",
        litellm_prefix="anthropic/",
    ),
    ProviderDefinition(
        name="openai",
        display_name="OpenAI (GPT models)",
        provider_type=ProviderType.CLOUD,
        env_key="OPENAI_API_KEY",
        signup_url="https://platform.openai.com/api-keys",
        health_url="https://api.openai.com/v1/models",
        litellm_prefix="openai/",
    ),
    ProviderDefinition(
        name="together",
        display_name="Together AI (Free Tier Available)",
        provider_type=ProviderType.CLOUD,
        env_key="TOGETHER_API_KEY",
        signup_url="https://api.together.ai/settings/api-keys",
        health_url="https://api.together.xyz/v1/models",
        litellm_prefix="together_ai/",
    ),
    ProviderDefinition(
        name="deepinfra",
        display_name="DeepInfra (Very Cheap Models)",
        provider_type=ProviderType.CLOUD,
        env_key="DEEPINFRA_API_KEY",
        signup_url="https://deepinfra.com/dash?ref=gh",
        health_url="https://api.deepinfra.com/v1/openai/models",
        litellm_prefix="deepinfra/",
    ),
    ProviderDefinition(
        name="ollama",
        display_name="Ollama (Local Models on Your PC)",
        provider_type=ProviderType.LOCAL,
        env_key="OLLAMA_BASE_URL",
        signup_url="https://ollama.ai",
        health_url="http://localhost:11434/api/tags",
        requires_auth=False,
        auth_env_key="OLLAMA_API_KEY",
        litellm_prefix="ollama/",
    ),
]

# Map name → definition for quick lookups
PROVIDER_MAP: dict[str, ProviderDefinition] = {p.name: p for p in KNOWN_PROVIDERS}


# ─── Live Usage Tracking ─────────────────────────────────────────────────────

@dataclass
class ProviderUsage:
    """Tracks real-time rate-limit usage for a single provider."""
    name: str
    requests_limit: int = 0       # Total allowed per period
    requests_remaining: int = -1  # -1 = unknown
    tokens_limit: int = 0
    tokens_remaining: int = -1
    last_updated: float = field(default_factory=time.time)
    is_soft_limited: bool = False  # True when > threshold
    is_hard_limited: bool = False  # True after 429

    @property
    def requests_used_pct(self) -> Optional[float]:
        """Percentage of request budget consumed (0.0–1.0)."""
        if self.requests_limit > 0 and self.requests_remaining >= 0:
            return 1.0 - (self.requests_remaining / self.requests_limit)
        return None


_usage_state: dict[str, ProviderUsage] = {}


def get_usage(provider_name: str) -> ProviderUsage:
    """Get or create a ProviderUsage tracker."""
    if provider_name not in _usage_state:
        _usage_state[provider_name] = ProviderUsage(name=provider_name)
    return _usage_state[provider_name]


def update_usage_from_headers(provider_name: str, headers: dict) -> ProviderUsage:
    """
    Parse rate-limit headers from a provider response and update usage state.
    This enables proactive soft-limit switching before hitting a hard 429.
    """
    definition = PROVIDER_MAP.get(provider_name)
    usage = get_usage(provider_name)

    def _try_int(headers: dict, key: str) -> Optional[int]:
        # Headers can come in as case-insensitive dicts or plain dicts
        for k, v in headers.items():
            if k.lower() == key.lower():
                try:
                    return int(v)
                except (ValueError, TypeError):
                    pass
        return None

    if definition:
        remaining = _try_int(headers, definition.remaining_header)
        limit = _try_int(headers, definition.limit_header)
    else:
        remaining = _try_int(headers, "x-ratelimit-remaining-requests")
        limit = _try_int(headers, "x-ratelimit-limit-requests")

    if remaining is not None:
        usage.requests_remaining = remaining
    if limit is not None:
        usage.requests_limit = limit

    # Also try token headers
    tok_rem = _try_int(headers, "x-ratelimit-remaining-tokens")
    tok_lim = _try_int(headers, "x-ratelimit-limit-tokens")
    if tok_rem is not None:
        usage.tokens_remaining = tok_rem
    if tok_lim is not None:
        usage.tokens_limit = tok_lim

    usage.last_updated = time.time()

    # Evaluate soft-limit threshold
    threshold = definition.soft_limit_threshold if definition else 0.90
    pct = usage.requests_used_pct
    if pct is not None:
        usage.is_soft_limited = pct >= threshold
    else:
        usage.is_soft_limited = False

    _usage_state[provider_name] = usage
    return usage


def mark_hard_limited(provider_name: str) -> None:
    """Mark a provider as hard-limited (got a 429 response)."""
    usage = get_usage(provider_name)
    usage.is_hard_limited = True
    usage.requests_remaining = 0
    _usage_state[provider_name] = usage


def reset_limits(provider_name: str) -> None:
    """Reset usage state (e.g. after rate-limit window resets)."""
    _usage_state.pop(provider_name, None)


def get_all_usage() -> dict[str, ProviderUsage]:
    """Return a snapshot of all tracked usage."""
    return dict(_usage_state)


def should_skip_provider(provider_name: str) -> bool:
    """Return True if a provider should be skipped due to soft or hard limit."""
    usage = _usage_state.get(provider_name)
    if not usage:
        return False
    return usage.is_hard_limited or usage.is_soft_limited


# ─── Provider Health Check ────────────────────────────────────────────────────

async def check_provider_reachable(name: str, timeout: float = 5.0) -> tuple[bool, str]:
    """
    Asynchronously ping a provider to see if it is reachable.

    Returns:
        (True, "OK") or (False, "Error reason")
    """
    definition = PROVIDER_MAP.get(name)
    if not definition:
        return False, "Unknown provider"

    api_key = os.getenv(definition.env_key, "")
    # Try secondary auth key if primary is empty (useful for Ollama/Local)
    if not api_key and definition.auth_env_key:
        api_key = os.getenv(definition.auth_env_key, "")

    headers = {}
    if (definition.requires_auth or (definition.auth_env_key and api_key)) and api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(definition.health_url, headers=headers)
            if response.status_code == 200:
                return True, "OK"
            elif response.status_code in (401, 403):
                return False, "Invalid API Key"
            elif response.status_code == 429:
                return False, "Rate Limited"
            else:
                return False, f"HTTP {response.status_code}"
    except httpx.ConnectError:
        return False, "Connection refused (not running?)"
    except httpx.TimeoutException:
        return False, "Timed out"
    except Exception as e:
        return False, str(e)


# ─── .env File Management ─────────────────────────────────────────────────────

def get_env_path() -> Path:
    """Get the .env file path (project root)."""
    return Path(__file__).parent.parent.parent / ".env"


def save_api_key(provider_name: str, api_key: str) -> None:
    """Persist an API key to the .env file."""
    definition = PROVIDER_MAP.get(provider_name)
    if not definition:
        raise ValueError(f"Unknown provider: {provider_name}")

    env_path = get_env_path()
    if not env_path.exists():
        env_path.touch()

    set_key(str(env_path), definition.env_key, api_key)
    # Also set in the current process
    os.environ[definition.env_key] = api_key


def get_linked_providers() -> list[tuple[ProviderDefinition, bool]]:
    """
    Return all known providers with a flag indicating whether their API key is set.
    
    Returns:
        List of (ProviderDefinition, is_configured) tuples
    """
    load_dotenv(get_env_path(), override=True)
    result = []
    for p in KNOWN_PROVIDERS:
        value = os.getenv(p.env_key, "")
        is_configured = bool(value and value.strip())
        result.append((p, is_configured))
    return result

"""
providers.py — Provider definitions, API key management, and health checks.

Context: Defines all supported AI providers (cloud + local).
Manages API keys, checks provider health, and tracks rate-limit usage
to enable automatic fallback before hitting hard limits.

All cloud providers use OpenAI-compatible APIs, so we call them directly
with httpx — no LiteLLM proxy needed.
"""

import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv, set_key


# ─── Provider Definitions ─────────────────────────────────────────────────────

class ProviderType(str, Enum):
    CLOUD = "cloud"
    LOCAL = "local"


@dataclass
class ProviderDefinition:
    name: str               # Internal key
    display_name: str
    provider_type: ProviderType
    env_key: str            # .env variable for API key / base URL
    base_url: str           # OpenAI-compatible API base
    health_url: str
    signup_url: str
    requires_auth: bool = True
    priority: int = 100     # Lower = preferred (Ollama=10, Groq=20 …)
    soft_limit_threshold: float = 0.90


KNOWN_PROVIDERS: list[ProviderDefinition] = [
    ProviderDefinition(
        name="ollama",
        display_name="Ollama (Local Models)",
        provider_type=ProviderType.LOCAL,
        env_key="OLLAMA_BASE_URL",
        base_url="http://localhost:11434/v1",
        health_url="http://localhost:11434/api/tags",
        signup_url="https://ollama.ai",
        requires_auth=False,
        priority=10,
    ),
    ProviderDefinition(
        name="groq",
        display_name="Groq (Fast Free Inference)",
        provider_type=ProviderType.CLOUD,
        env_key="GROQ_API_KEY",
        base_url="https://api.groq.com/openai/v1",
        health_url="https://api.groq.com/openai/v1/models",
        signup_url="https://console.groq.com/keys",
        priority=20,
    ),
    ProviderDefinition(
        name="openrouter",
        display_name="OpenRouter (Free Cloud Models)",
        provider_type=ProviderType.CLOUD,
        env_key="OPENROUTER_API_KEY",
        base_url="https://openrouter.ai/api/v1",
        health_url="https://openrouter.ai/api/v1/models",
        signup_url="https://openrouter.ai/keys",
        priority=30,
    ),
    ProviderDefinition(
        name="together",
        display_name="Together AI (Free Tier)",
        provider_type=ProviderType.CLOUD,
        env_key="TOGETHER_API_KEY",
        base_url="https://api.together.xyz/v1",
        health_url="https://api.together.xyz/v1/models",
        signup_url="https://api.together.ai/settings/api-keys",
        priority=40,
    ),
    ProviderDefinition(
        name="deepinfra",
        display_name="DeepInfra (Cheap Models)",
        provider_type=ProviderType.CLOUD,
        env_key="DEEPINFRA_API_KEY",
        base_url="https://api.deepinfra.com/v1/openai",
        health_url="https://api.deepinfra.com/v1/openai/models",
        signup_url="https://deepinfra.com/dash",
        priority=50,
    ),
    ProviderDefinition(
        name="openai",
        display_name="OpenAI (GPT Models)",
        provider_type=ProviderType.CLOUD,
        env_key="OPENAI_API_KEY",
        base_url="https://api.openai.com/v1",
        health_url="https://api.openai.com/v1/models",
        signup_url="https://platform.openai.com/api-keys",
        priority=60,
    ),
    ProviderDefinition(
        name="anthropic",
        display_name="Anthropic (Claude Models)",
        provider_type=ProviderType.CLOUD,
        env_key="ANTHROPIC_API_KEY",
        base_url="https://api.anthropic.com/v1",
        health_url="https://api.anthropic.com/v1/models",
        signup_url="https://console.anthropic.com/account/keys",
        priority=70,
    ),
]

PROVIDER_MAP: dict[str, ProviderDefinition] = {p.name: p for p in KNOWN_PROVIDERS}

# Default model to use per provider
DEFAULT_MODELS: dict[str, str] = {
    "ollama": "llama3.2",
    "groq": "llama-3.3-70b-versatile",
    "openrouter": "meta-llama/llama-3.3-70b-instruct:free",
    "together": "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
    "deepinfra": "meta-llama/Meta-Llama-3.1-70B-Instruct",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-haiku-20240307",
}


# ─── Rate Limit Tracking ──────────────────────────────────────────────────────

@dataclass
class ProviderUsage:
    name: str
    requests_limit: int = 0
    requests_remaining: int = -1
    tokens_limit: int = 0
    tokens_remaining: int = -1
    last_updated: float = field(default_factory=time.time)
    is_soft_limited: bool = False
    is_hard_limited: bool = False

    @property
    def requests_used_pct(self) -> Optional[float]:
        if self.requests_limit > 0 and self.requests_remaining >= 0:
            return 1.0 - (self.requests_remaining / self.requests_limit)
        return None


_usage: dict[str, ProviderUsage] = {}


def get_usage(name: str) -> ProviderUsage:
    if name not in _usage:
        _usage[name] = ProviderUsage(name=name)
    return _usage[name]


def get_all_usage() -> dict[str, ProviderUsage]:
    return dict(_usage)


def update_usage_from_headers(name: str, headers: dict) -> None:
    usage = get_usage(name)

    def _get_int(key: str) -> Optional[int]:
        for k, v in headers.items():
            if k.lower() == key.lower():
                try:
                    return int(v)
                except (ValueError, TypeError):
                    pass
        return None

    rem = _get_int("x-ratelimit-remaining-requests")
    lim = _get_int("x-ratelimit-limit-requests")
    if rem is not None:
        usage.requests_remaining = rem
    if lim is not None:
        usage.requests_limit = lim
    tok_rem = _get_int("x-ratelimit-remaining-tokens")
    tok_lim = _get_int("x-ratelimit-limit-tokens")
    if tok_rem is not None:
        usage.tokens_remaining = tok_rem
    if tok_lim is not None:
        usage.tokens_limit = tok_lim

    usage.last_updated = time.time()
    defn = PROVIDER_MAP.get(name)
    threshold = defn.soft_limit_threshold if defn else 0.90
    pct = usage.requests_used_pct
    usage.is_soft_limited = (pct is not None and pct >= threshold)


def mark_hard_limited(name: str) -> None:
    usage = get_usage(name)
    usage.is_hard_limited = True
    usage.requests_remaining = 0


def should_skip_provider(name: str) -> bool:
    u = _usage.get(name)
    return bool(u and (u.is_hard_limited or u.is_soft_limited))


# ─── API Key / Config Management ─────────────────────────────────────────────

def _env_path() -> Path:
    return Path(__file__).parent.parent.parent / ".env"


def load_env() -> None:
    load_dotenv(_env_path(), override=True)


def save_api_key(provider_name: str, api_key: str) -> None:
    defn = PROVIDER_MAP.get(provider_name)
    if not defn:
        raise ValueError(f"Unknown provider: {provider_name}")
    env_path = _env_path()
    if not env_path.exists():
        env_path.touch()
    set_key(str(env_path), defn.env_key, api_key)
    os.environ[defn.env_key] = api_key


def get_provider_key(name: str) -> Optional[str]:
    load_env()
    defn = PROVIDER_MAP.get(name)
    if not defn:
        return None
    return os.getenv(defn.env_key, "").strip() or None


def get_configured_providers() -> list[tuple[ProviderDefinition, bool]]:
    """Return all providers sorted by priority with is_configured flag."""
    load_env()
    result = []
    for p in sorted(KNOWN_PROVIDERS, key=lambda x: x.priority):
        if p.requires_auth:
            is_configured = bool(get_provider_key(p.name))
        else:
            is_configured = True  # Ollama: assume configured, health check verifies
        result.append((p, is_configured))
    return result


# ─── Health Checks ────────────────────────────────────────────────────────────

async def check_provider_health(name: str, timeout: float = 5.0) -> tuple[bool, str]:
    defn = PROVIDER_MAP.get(name)
    if not defn:
        return False, "Unknown provider"

    headers = {}
    if defn.requires_auth:
        key = get_provider_key(name)
        if not key:
            return False, "No API key configured"
        headers["Authorization"] = f"Bearer {key}"

    health_url = defn.health_url
    if name == "ollama":
        base = os.getenv("OLLAMA_BASE_URL", "").strip()
        if base:
            health_url = base.rstrip("/").replace("/v1", "") + "/api/tags"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(health_url, headers=headers)
            if resp.status_code == 200:
                return True, "OK"
            elif resp.status_code in (401, 403):
                return False, "Invalid API key"
            elif resp.status_code == 429:
                return False, "Rate limited"
            else:
                return False, f"HTTP {resp.status_code}"
    except httpx.ConnectError:
        return False, "Connection refused"
    except httpx.TimeoutException:
        return False, "Timed out"
    except Exception as e:
        return False, str(e)


async def fetch_ollama_models(base_url: Optional[str] = None) -> list[str]:
    url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
    url = url.replace("/v1", "")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{url}/api/tags")
            if resp.status_code == 200:
                return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        pass
    return []

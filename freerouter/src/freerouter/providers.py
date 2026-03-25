"""
providers.py — Provider definitions, API key management, and health checks.

Context: Defines all supported AI providers (cloud + local).
Manages API keys, checks provider health, and tracks rate-limit usage
to enable automatic fallback before hitting hard limits.

All cloud providers use OpenAI-compatible APIs, so we call them directly
with httpx — no LiteLLM proxy needed.

Imports: nothing internal
Imported by: router.py, web/app.py, proxy_server.py
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
    name: str
    display_name: str
    provider_type: ProviderType
    env_key: str
    base_url: str
    health_url: str
    signup_url: str
    requires_auth: bool = True
    priority: int = 100
    soft_limit_threshold: float = 0.90
    requires_custom_adapter: bool = False  # Flag for non-OpenAI APIs like APIFreeLLM
    rate_limit_reset_seconds: int = 60  # Provider-specific rate limit reset time


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
    # ─── NEW PROVIDERS ─────────────────────────────────────────────────────
    ProviderDefinition(
        name="mistral",
        display_name="Mistral AI",
        provider_type=ProviderType.CLOUD,
        env_key="MISTRAL_API_KEY",
        base_url="https://api.mistral.ai/v1",
        health_url="https://api.mistral.ai/v1/models",
        signup_url="https://console.mistral.ai/",
        priority=35,
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
        name="sambanova",
        display_name="SambaNova Cloud",
        provider_type=ProviderType.CLOUD,
        env_key="SAMBANOVA_API_KEY",
        base_url="https://api.sambanova.ai/v1",
        health_url="https://api.sambanova.ai/v1/models",
        signup_url="https://cloud.sambanova.ai/",
        priority=45,
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
        name="cerebras",
        display_name="Cerebras AI",
        provider_type=ProviderType.CLOUD,
        env_key="CEREBRAS_API_KEY",
        base_url="https://api.cerebras.ai/v1",
        health_url="https://api.cerebras.ai/v1/models",
        signup_url="https://cloud.cerebras.ai/",
        priority=55,
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
        name="github",
        display_name="GitHub Models",
        provider_type=ProviderType.CLOUD,
        env_key="GITHUB_TOKEN",
        base_url="https://models.inference.ai.azure.com",
        health_url="https://models.inference.ai.azure.com/models",
        signup_url="https://github.com/settings/tokens",
        priority=65,
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
    # ─── NON-STANDARD API PROVIDERS (require custom adapter) ─────────────────
    ProviderDefinition(
        name="apifreellm",
        display_name="APIFreeLLM (Free Tier)",
        provider_type=ProviderType.CLOUD,
        env_key="APIFREELLM_API_KEY",
        base_url="https://apifreellm.com/api/v1",
        health_url="https://apifreellm.com/api/v1/status",
        signup_url="https://apifreellm.com/en/api-access",
        priority=75,
        requires_custom_adapter=True,
        rate_limit_reset_seconds=25,  # APIFreeLLM requires 25 second wait on 429
    ),
    ProviderDefinition(
        name="zai",
        display_name="Z.AI (GLM Models)",
        provider_type=ProviderType.CLOUD,
        env_key="ZAI_API_KEY",
        base_url="https://api.z.ai/v1",
        health_url="https://api.z.ai/v1/models",
        signup_url="https://docs.z.ai/",
        priority=80,
    ),
]

PROVIDER_MAP: dict[str, ProviderDefinition] = {p.name: p for p in KNOWN_PROVIDERS}

# ─── Default Models ───────────────────────────────────────────────────────────
# These are used when model="auto" or when a wrong-provider model is received.
# Change these to set your preferred model per provider.

DEFAULT_MODELS: dict[str, str] = {
    "ollama": "llama3.2",                                        # whatever you have locally
    "groq": "llama-3.3-70b-versatile",                          # fast, generous free tier
    "openrouter": "stepfun/step-3.5-flash:free",                # as requested
    "mistral": "mistral-small-latest",                          # free tier model
    "together": "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
    "sambanova": "Meta-Llama-3.1-8B-Instruct",                  # free tier model
    "deepinfra": "meta-llama/Meta-Llama-3.1-70B-Instruct",
    "cerebras": "llama-3.3-70b",                                # fast inference
    "openai": "gpt-4o-mini",
    "github": "gpt-4o-mini",                                    # GitHub Models free tier
    "anthropic": "claude-3-haiku-20240307",
    "apifreellm": "apifreellm",                                 # only model available
    "zai": "glm-4-flash",                                       # Z.AI GLM model
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
    # Track when hard limit was set so we can auto-reset after a window
    hard_limited_at: float = 0.0

    @property
    def requests_used_pct(self) -> Optional[float]:
        if self.requests_limit > 0 and self.requests_remaining >= 0:
            return 1.0 - (self.requests_remaining / self.requests_limit)
        return None


_usage: dict[str, ProviderUsage] = {}

# Auto-reset hard limits after this many seconds (1 minute)
# OpenRouter rate limits reset per minute
HARD_LIMIT_RESET_SECONDS = 60


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

    # If we got a successful response, clear any hard limit
    if rem is not None and rem > 0:
        usage.is_hard_limited = False
        usage.hard_limited_at = 0.0


def mark_hard_limited(name: str) -> None:
    usage = get_usage(name)
    usage.is_hard_limited = True
    usage.requests_remaining = 0
    usage.hard_limited_at = time.time()


def should_skip_provider(name: str) -> bool:
    u = _usage.get(name)
    if not u:
        return False
    # Auto-reset hard limits after the window expires
    if u.is_hard_limited and u.hard_limited_at > 0:
        if time.time() - u.hard_limited_at > HARD_LIMIT_RESET_SECONDS:
            u.is_hard_limited = False
            u.hard_limited_at = 0.0
            return False
    return u.is_hard_limited or u.is_soft_limited


def reset_provider(name: str) -> None:
    """Manually reset a provider's rate limit state."""
    if name in _usage:
        _usage[name].is_hard_limited = False
        _usage[name].is_soft_limited = False
        _usage[name].hard_limited_at = 0.0
        _usage[name].requests_remaining = -1


# ─── API Key Management ───────────────────────────────────────────────────────

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
            is_configured = True
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
                # Clear any stale rate limit on successful health check
                reset_provider(name)
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

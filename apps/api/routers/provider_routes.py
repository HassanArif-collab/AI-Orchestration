"""
provider_routes.py — LLM provider management using .env and ROUTES directly.

After FreeRouter v3 migration, freerouter.providers is removed.
This module reads provider config from freerouter/.env and
task-to-model mapping from freerouter.config.ROUTES.
FreeRouter proxy (:4000) still needed separately for LLM calls.
"""

from __future__ import annotations
import glob, os
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

ENV_PATH = Path(__file__).resolve().parents[3] / "freerouter" / ".env"

# Known providers: env key → display metadata
KNOWN_PROVIDERS: list[dict] = [
    {"name": "groq",        "display_name": "Groq",        "env_key": "GROQ_API_KEY",       "requires_auth": True,  "signup_url": "https://console.groq.com",   "priority": 1},
    {"name": "openrouter",  "display_name": "OpenRouter",  "env_key": "OPENROUTER_API_KEY", "requires_auth": True,  "signup_url": "https://openrouter.ai",      "priority": 2},
    {"name": "mistral",     "display_name": "Mistral",     "env_key": "MISTRAL_API_KEY",    "requires_auth": True,  "signup_url": "https://console.mistral.ai", "priority": 3},
    {"name": "sambanova",   "display_name": "SambaNova",   "env_key": "SAMBANOVA_API_KEY",  "requires_auth": True,  "signup_url": "https://sambanova.ai",       "priority": 4},
    {"name": "cerebras",    "display_name": "Cerebras",    "env_key": "CEREBRAS_API_KEY",   "requires_auth": True,  "signup_url": "https://cloud.cerebras.ai",  "priority": 5},
    {"name": "together",    "display_name": "Together AI", "env_key": "TOGETHER_API_KEY",   "requires_auth": True,  "signup_url": "https://api.together.ai",    "priority": 6},
    {"name": "ollama",      "display_name": "Ollama",      "env_key": "OLLAMA_BASE_URL",    "requires_auth": False, "signup_url": "",                          "priority": 7},
]


def _read_env() -> dict[str, str]:
    """Read freerouter/.env into a dict (without loading into os.environ)."""
    env = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                env[key.strip()] = val.strip()
    return env


def _save_env(env: dict[str, str]) -> None:
    """Write env dict back to freerouter/.env, preserving comments."""
    if not ENV_PATH.exists():
        ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
        ENV_PATH.write_text("# FreeRouter Environment Configuration\n")
    lines = ENV_PATH.read_text().splitlines()
    updated_keys = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key, _, _ = stripped.partition("=")
            key = key.strip()
            if key in env:
                new_lines.append(f"{key}={env[key]}")
                updated_keys.add(key)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
    # Append any new keys not already in the file
    for key, val in env.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={val}")
    ENV_PATH.write_text("\n".join(new_lines) + "\n")


def _get_configured_providers() -> list[tuple[dict, bool]]:
    """Return list of (provider_info, is_configured) tuples based on .env."""
    env = _read_env()
    result = []
    for prov in KNOWN_PROVIDERS:
        val = env.get(prov["env_key"], "")
        is_configured = bool(val.strip()) if prov["requires_auth"] else bool(val.strip())
        result.append((prov, is_configured))
    return result


class SaveKeyRequest(BaseModel):
    api_key: str


@router.get("/")
async def list_providers():
    try:
        result = []
        for prov, is_configured in _get_configured_providers():
            result.append({
                "name": prov["name"],
                "display_name": prov["display_name"],
                "requires_auth": prov["requires_auth"],
                "is_configured": is_configured,
                "has_key": is_configured,
                "signup_url": prov["signup_url"],
                "priority": prov["priority"],
                "default_model": "",
            })
        return {"providers": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{name}/key")
async def save_key(name: str, data: SaveKeyRequest):
    """Save an API key to freerouter/.env."""
    try:
        providers_by_name = {p["name"]: p for p in KNOWN_PROVIDERS}
        if name not in providers_by_name:
            raise ValueError(f"Unknown provider: {name}")
        env = _read_env()
        env[providers_by_name[name]["env_key"]] = data.api_key
        _save_env(env)
        return {"success": True}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{name}/test")
async def test_provider(name: str):
    try:
        providers_by_name = {p["name"]: p for p in KNOWN_PROVIDERS}
        if name not in providers_by_name:
            return {"ok": False, "message": f"Unknown provider: {name}"}
        env = _read_env()
        key = env.get(providers_by_name[name]["env_key"], "")
        if not key.strip() and providers_by_name[name]["requires_auth"]:
            return {"ok": False, "message": f"No API key set for {name}"}
        return {"ok": True, "message": f"Provider {name} is configured"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{name}/reset")
async def reset_provider_limit(name: str):
    try:
        from packages.router.tracker import UsageTracker
        tracker = UsageTracker()
        tracker.is_near_limit.cache_clear() if hasattr(tracker.is_near_limit, "cache_clear") else None
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/usage")
async def get_usage():
    try:
        pipeline = {}
        try:
            from packages.router.tracker import UsageTracker
            for row in UsageTracker().get_all_usage_today():
                pipeline[row["provider"]] = row
        except Exception:
            pass
        return {"freerouter": {}, "pipeline": pipeline}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models")
async def list_models():
    try:
        from freerouter.config import ROUTES
        models = []
        for task_name, route in ROUTES.items():
            models.append({"task": task_name, "model": route["model"], "fallback": route["fallback"]})
        return {"models": models}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    health: dict = {}

    # FreeRouter proxy (:4000)
    try:
        from apps.api.dependencies import get_proxy_client
        proxy = await get_proxy_client()
        await proxy.get("/v1/models", timeout=3.0)
        health["freerouter_proxy"] = {"status": "online", "url": "http://localhost:4000"}
    except Exception:
        health["freerouter_proxy"] = {
            "status": "offline", "url": "http://localhost:4000",
            "fix": "python -m freerouter proxy",
        }

    # Configured providers from .env
    try:
        configured = [p["name"] for p, c in _get_configured_providers() if c]
        health["providers"] = {"status": "ok" if configured else "no_keys",
                               "configured_count": len(configured)}
    except Exception:
        health["providers"] = {"status": "error", "configured_count": 0}

    # DBs
    for key, path in [("pipeline_db", "packages/data/pipeline.db"),
                       ("chat_db",     "freerouter/data/conversations.db"),
                       ("usage_db",    "packages/data/usage_tracker.db")]:
        health[key] = {"status": "ok" if os.path.exists(path) else "missing", "path": path}

    # Optional services
    try:
        from packages.core.config import get_settings
        s = get_settings()
        health["zep"]         = {"status": "configured" if s.ZEP_API_KEY else "not_configured"}
        health["youtube_api"] = {"status": "configured" if s.YOUTUBE_API_KEY else "not_configured"}
    except Exception:
        health["zep"] = health["youtube_api"] = {"status": "not_configured"}

    shaders = glob.glob("data/radiant-shaders/static/*.html")
    health["radiant_shaders"] = {"status": "ok" if shaders else "not_cloned", "count": len(shaders)}
    health["remotion_project"] = {"status": "ok" if os.path.exists("visual-engine") else "not_scaffolded"}

    proxy_ok = health["freerouter_proxy"]["status"] == "online"
    n_keys   = health["providers"].get("configured_count", 0)
    health["overall"] = "healthy" if (proxy_ok and n_keys > 0) else \
                        "degraded" if n_keys > 0 else "offline"
    return health


@router.get("/quota")
async def get_live_quota():
    """
    Returns the most recent RPM/TPM remaining values
    for each provider from the tracker DB.
    """
    try:
        from packages.router.tracker import UsageTracker
        tracker = UsageTracker()
        rows = tracker.get_latest_limits()
        return {
            "providers": [
                {
                    "name": row["provider"],
                    "rpm_remaining": row["live_rpm_remaining"],
                    "tpm_remaining": row["live_tpm_remaining"],
                    "last_updated": row["timestamp"]
                }
                for row in rows
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

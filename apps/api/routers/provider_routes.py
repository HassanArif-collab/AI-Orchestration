"""
provider_routes.py — LLM provider management using freerouter internals directly.

No HTTP proxy to :8080 needed. Imports freerouter package directly.
FreeRouter proxy (:4000) still needed separately for LLM calls.
"""

from __future__ import annotations
import glob, os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


def _fr():
    from freerouter.providers import (
        KNOWN_PROVIDERS, get_configured_providers, save_api_key,
        check_provider_health, get_all_usage, reset_provider, load_env,
    )
    return locals()


class SaveKeyRequest(BaseModel):
    api_key: str


@router.get("/")
async def list_providers():
    try:
        f = _fr()
        f["load_env"]()
        result = []
        for defn, is_configured in f["get_configured_providers"]():
            result.append({
                "name": defn.name,
                "display_name": defn.display_name,
                "requires_auth": defn.requires_auth,
                "is_configured": is_configured,
                "has_key": is_configured,
                "signup_url": getattr(defn, "signup_url", ""),
                "priority": defn.priority,
                "default_model": getattr(defn, "default_model", ""),
            })
        return {"providers": result}
    except Exception as e:
        return {"error": str(e), "providers": []}


@router.post("/{name}/key")
async def save_key(name: str, data: SaveKeyRequest):
    try:
        _fr()["save_api_key"](name, data.api_key)
        return {"success": True}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@router.post("/{name}/test")
async def test_provider(name: str):
    try:
        ok, msg = await _fr()["check_provider_health"](name)
        return {"ok": ok, "message": msg}
    except Exception as e:
        return {"ok": False, "message": str(e)}


@router.post("/{name}/reset")
async def reset_provider_limit(name: str):
    try:
        _fr()["reset_provider"](name)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/usage")
async def get_usage():
    try:
        all_u = _fr()["get_all_usage"]()
        result = {}
        for name, u in all_u.items():
            result[name] = {
                "requests": getattr(u, "requests_today", 0),
                "tokens_in": getattr(u, "tokens_in_today", 0),
                "tokens_out": getattr(u, "tokens_out_today", 0),
                "requests_used_pct": round((getattr(u, "requests_used_pct", 0) or 0) * 100, 1),
                "rate_limited": getattr(u, "is_hard_limited", False),
            }
        pipeline = {}
        try:
            from packages.router.tracker import UsageTracker
            for row in UsageTracker().get_all_usage_today():
                pipeline[row["provider"]] = row
        except Exception:
            pass
        return {"freerouter": result, "pipeline": pipeline}
    except Exception as e:
        return {"error": str(e), "freerouter": {}, "pipeline": {}}


@router.get("/models")
async def list_models():
    try:
        from freerouter.router import get_router
        models = await get_router().list_models()
        return {"models": models}
    except Exception as e:
        return {"error": str(e), "models": []}


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

    # Configured providers
    try:
        f = _fr()
        f["load_env"]()
        configured = [d.name for d, c in f["get_configured_providers"]() if c]
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

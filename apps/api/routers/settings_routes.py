"""settings_routes.py — System configuration and health status."""
from __future__ import annotations
import os
from fastapi import APIRouter
from apps.api.routers.provider_routes import health_check as _health

router = APIRouter()

@router.get("/")
async def get_settings():
    """Return current config with secrets masked."""
    result = {
        "freerouter_proxy": "http://localhost:4000",
        "dashboard_port": 3000,
        "pipeline_db": "packages/data/pipeline.db",
        "chat_db": "freerouter/data/conversations.db",
        "data_dir": "packages/data",
        "log_level": "INFO",
        "zep_configured": False,
        "youtube_configured": False,
        "notion_configured": False,
    }
    try:
        from packages.core.config import get_settings as _s
        s = _s()
        result["zep_configured"]     = bool(s.ZEP_API_KEY)
        result["youtube_configured"] = bool(s.YOUTUBE_API_KEY)
        result["notion_configured"]  = bool(s.NOTION_API_KEY)
        result["log_level"]          = s.LOG_LEVEL
    except Exception:
        pass
    return result

@router.get("/status")
async def system_status():
    health = await _health()
    components = {k: v for k, v in health.items() if k != "overall"}
    components["dashboard"] = {"status": "online", "port": 3000}
    return {"overall": health.get("overall", "unknown"), "components": components}

@router.get("/commands")
async def get_startup_commands():
    return {
        "dashboard":      "python -m apps.api.main",
        "freerouter_proxy": "python -m freerouter proxy",
        "radiant_setup":  "python -c \"from packages.visual.radiant.manager import RadiantManager; RadiantManager().setup()\"",
        "remotion_setup": "python -c \"from packages.visual.remotion.setup import scaffold_project; scaffold_project()\"",
        "pipeline_cli":   "python apps/worker/main.py start",
    }

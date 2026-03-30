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


@router.get("/services/status")
async def get_service_status():
    """Get configuration status of all services.
    
    Returns a dict mapping service names to their status values:
    - available: Service is properly configured
    - not_configured: Required API key/URL is not set
    - misconfigured: Configuration exists but is invalid
    """
    from packages.core.config import get_settings
    settings = get_settings()
    return settings.get_service_status()


@router.post("/services/validate")
async def validate_configuration():
    """Validate all service configurations.
    
    Returns validation results with any issues found.
    Issues include services that are not configured or misconfigured.
    """
    from packages.core.config import get_settings, ServiceStatus
    settings = get_settings()
    issues = []
    recommendations = []
    
    for service in ["zep", "youtube", "notion", "freerouter"]:
        status = settings.validate_service(service)
        if status != ServiceStatus.AVAILABLE:
            issue = {"service": service, "status": status.value}
            issues.append(issue)
            
            # Add recommendations based on status
            if status == ServiceStatus.NOT_CONFIGURED:
                if service == "zep":
                    recommendations.append("Set ZEP_API_KEY environment variable for memory features")
                elif service == "youtube":
                    recommendations.append("Set YOUTUBE_API_KEY for YouTube analytics integration")
                elif service == "notion":
                    recommendations.append("Set NOTION_API_KEY for Notion publishing")
                elif service == "freerouter":
                    recommendations.append("Ensure FREEROUTER_URL is set (default: http://localhost:4000)")
            elif status == ServiceStatus.MISCONFIGURED:
                if service == "youtube":
                    recommendations.append("YOUTUBE_API_KEY appears invalid (too short)")
                elif service == "notion":
                    recommendations.append("NOTION_API_KEY should start with 'secret_'")
    
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "recommendations": recommendations
    }


@router.get("/commands")
async def get_startup_commands():
    return {
        "dashboard":      "python -m apps.api.main",
        "freerouter_proxy": "python -m freerouter proxy",
        "radiant_setup":  "python -c \"from packages.visual.radiant.manager import RadiantManager; RadiantManager().setup()\"",
        "remotion_setup": "python -c \"from packages.visual.remotion.setup import scaffold_project; scaffold_project()\"",
        "pipeline_cli":   "python apps/worker/main.py start",
    }


@router.get("/skills")
async def get_skills():
    """Return all data/skills/*.md files for the read-only viewer.
    
    This endpoint serves the skill prompt files to the React frontend
    for display in the System tab of the sidebar.
    """
    import os
    from pathlib import Path
    
    # Find the data/skills directory relative to this file
    skills_dir = Path(__file__).parent.parent.parent.parent / "data" / "skills"
    files = []
    
    if skills_dir.is_dir():
        for fname in sorted(skills_dir.iterdir()):
            if fname.suffix == '.md':
                try:
                    content = fname.read_text(encoding='utf-8')
                    files.append({
                        "name": fname.name,
                        "content": content
                    })
                except Exception as e:
                    print(f"Warning: Could not read skill file {fname}: {e}")
    
    return {"files": files}

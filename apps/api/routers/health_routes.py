"""
health_routes.py — Health check endpoints.

Provides endpoints for monitoring application health and status.
These endpoints are publicly accessible without authentication.

Endpoints:
    GET /health       - Basic health check
    GET /api/health   - Detailed health status
    GET /api/health/services       - Comprehensive service health check
    GET /api/health/circuit-breakers - Circuit breaker statuses
    GET /api/health/config          - Configuration completeness check
"""

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check endpoint.
    
    Returns a simple status indicating the service is running.
    This endpoint is public and requires no authentication.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "youtube-pipeline-dashboard"
    }


@router.get("/api/health")
async def api_health_check():
    """Detailed health check endpoint.
    
    Returns detailed health information including service status.
    This endpoint is public and requires no authentication.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "youtube-pipeline-dashboard",
        "version": "1.0.0",
        "components": {
            "api": "operational",
            "dashboard": "operational"
        }
    }


@router.get("/api/health/freerouter")
async def freerouter_health():
    """Check if FreeRouter LLM proxy is running.
    
    Returns health status of the FreeRouter proxy service.
    This endpoint is public and requires no authentication.
    """
    import httpx
    from packages.core.config import get_settings
    
    settings = get_settings()
    url = settings.FREEROUTER_URL
    
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{url}/health")
            if response.status_code == 200:
                return {"healthy": True, "url": url}
    except Exception as e:
        logger.warning(f"health_check_failed for {url}: {e}")
    
    return {"healthy": False, "url": url}


@router.get("/api/health/services")
async def service_health_check():
    """Comprehensive health check for all external services.

    Checks configuration availability and, where possible, performs
    lightweight connectivity tests for each service.

    Returns:
        Dict with service names as keys, each containing:
        - name: Service display name
        - config_status: "available" | "not_configured" | "misconfigured"
        - operational_status: "operational" | "degraded" | "unavailable" | "unknown"
        - message: Human-readable status description
        - last_checked: ISO timestamp
    """
    from packages.core.config import get_settings, ServiceStatus

    settings = get_settings()
    now = datetime.now(timezone.utc).isoformat()
    services = {}

    # ─── Zep Memory ───────────────────────────────────────────────────────
    config_status = settings.validate_service("zep")
    zep_info = {
        "name": "Zep Memory",
        "config_status": config_status.value,
        "operational_status": "unknown",
        "message": "",
        "last_checked": now,
    }

    if config_status == ServiceStatus.NOT_CONFIGURED:
        zep_info["operational_status"] = "unavailable"
        zep_info["message"] = "ZEP_API_KEY not set. Memory features operate in degraded mode."
    elif config_status == ServiceStatus.AVAILABLE:
        # Attempt a quick connectivity test
        try:
            client = AsyncZepMemoryClient()
            # Just checking if the client initialized successfully
            if client._client is not None:
                zep_info["operational_status"] = "operational"
                zep_info["message"] = "Zep client initialized successfully."
            else:
                zep_info["operational_status"] = "degraded"
                zep_info["message"] = "Zep API key configured but client failed to initialize."
        except Exception as e:
            zep_info["operational_status"] = "degraded"
            zep_info["message"] = f"Zep initialization error: {e}"

    services["zep"] = zep_info

    # ─── Notion ───────────────────────────────────────────────────────────
    config_status = settings.validate_service("notion")
    notion_info = {
        "name": "Notion",
        "config_status": config_status.value,
        "operational_status": "unknown",
        "message": "",
        "last_checked": now,
    }

    if config_status == ServiceStatus.NOT_CONFIGURED:
        notion_info["operational_status"] = "unavailable"
        notion_info["message"] = "NOTION_API_KEY not set. Publishing features are unavailable."
    elif config_status == ServiceStatus.MISCONFIGURED:
        notion_info["operational_status"] = "degraded"
        notion_info["message"] = "NOTION_API_KEY format invalid (expected 'secret_...' prefix)."
    elif config_status == ServiceStatus.AVAILABLE:
        # Check if client can be initialized
        try:
            from packages.integrations.notion.client import NotionScriptClient
            client = NotionScriptClient()
            if client._client is not None:
                notion_info["operational_status"] = "operational"
                notion_info["message"] = "Notion client initialized successfully."
                if not client.database_id:
                    notion_info["operational_status"] = "degraded"
                    notion_info["message"] = "Notion API key valid but NOTION_DATABASE_ID not set."
            else:
                notion_info["operational_status"] = "degraded"
                notion_info["message"] = "Notion API key configured but client failed to initialize."
        except Exception as e:
            notion_info["operational_status"] = "degraded"
            notion_info["message"] = f"Notion initialization error: {e}"

    services["notion"] = notion_info

    # ─── FreeRouter ───────────────────────────────────────────────────────
    config_status = settings.validate_service("freerouter")
    freerouter_info = {
        "name": "FreeRouter",
        "config_status": config_status.value,
        "operational_status": "unknown",
        "message": "",
        "last_checked": now,
    }

    if config_status == ServiceStatus.NOT_CONFIGURED:
        freerouter_info["operational_status"] = "unavailable"
        freerouter_info["message"] = "FREEROUTER_URL not configured."
    elif config_status == ServiceStatus.AVAILABLE:
        # Reuse existing health check logic
        try:
            import httpx
            async with httpx.AsyncClient(timeout=3.0) as http_client:
                response = await http_client.get(f"{settings.FREEROUTER_URL}/health")
                if response.status_code == 200:
                    freerouter_info["operational_status"] = "operational"
                    freerouter_info["message"] = "FreeRouter proxy is running."
                else:
                    freerouter_info["operational_status"] = "degraded"
                    freerouter_info["message"] = f"FreeRouter returned HTTP {response.status_code}."
        except Exception as e:
            freerouter_info["operational_status"] = "unavailable"
            freerouter_info["message"] = f"FreeRouter not reachable: {e}"

    services["freerouter"] = freerouter_info

    # ─── Supabase ─────────────────────────────────────────────────────────
    config_status = settings.validate_service("supabase")
    supabase_info = {
        "name": "Supabase",
        "config_status": config_status.value,
        "operational_status": "unknown",
        "message": "",
        "last_checked": now,
    }

    if config_status == ServiceStatus.NOT_CONFIGURED:
        supabase_info["operational_status"] = "unavailable"
        supabase_info["message"] = "Supabase credentials not configured."
    elif config_status == ServiceStatus.MISCONFIGURED:
        supabase_info["operational_status"] = "degraded"
        supabase_info["message"] = "Supabase URL or key format invalid."
    elif config_status == ServiceStatus.AVAILABLE:
        supabase_info["operational_status"] = "operational"
        supabase_info["message"] = "Supabase configured. Connectivity check skipped (config-only)."

    services["supabase"] = supabase_info

    # ─── Exa ──────────────────────────────────────────────────────────────
    config_status = settings.validate_service("exa")
    exa_info = {
        "name": "Exa Search",
        "config_status": config_status.value,
        "operational_status": "unknown",
        "message": "",
        "last_checked": now,
    }

    if config_status == ServiceStatus.NOT_CONFIGURED:
        exa_info["operational_status"] = "unavailable"
        exa_info["message"] = "EXA_API_KEY not set. Topic discovery uses fallback mode."
    elif config_status == ServiceStatus.MISCONFIGURED:
        exa_info["operational_status"] = "degraded"
        exa_info["message"] = "EXA_API_KEY appears too short (may be invalid)."
    elif config_status == ServiceStatus.AVAILABLE:
        exa_info["operational_status"] = "operational"
        exa_info["message"] = "Exa configured. Connectivity check skipped (config-only)."

    services["exa"] = exa_info

    # ─── YouTube ──────────────────────────────────────────────────────────
    config_status = settings.validate_service("youtube")
    youtube_info = {
        "name": "YouTube",
        "config_status": config_status.value,
        "operational_status": "unknown",
        "message": "",
        "last_checked": now,
    }

    if config_status == ServiceStatus.NOT_CONFIGURED:
        youtube_info["operational_status"] = "unavailable"
        youtube_info["message"] = "YouTube API key not configured."
    elif config_status == ServiceStatus.MISCONFIGURED:
        youtube_info["operational_status"] = "degraded"
        youtube_info["message"] = "YouTube API key appears invalid (too short)."
    elif config_status == ServiceStatus.AVAILABLE:
        youtube_info["operational_status"] = "operational"
        youtube_info["message"] = "YouTube configured. Connectivity check skipped (config-only)."

    services["youtube"] = youtube_info

    return {
        "timestamp": now,
        "services": services,
        "summary": {
            "total": len(services),
            "operational": sum(1 for s in services.values() if s["operational_status"] == "operational"),
            "degraded": sum(1 for s in services.values() if s["operational_status"] == "degraded"),
            "unavailable": sum(1 for s in services.values() if s["operational_status"] == "unavailable"),
        },
    }


@router.get("/api/health/circuit-breakers")
async def circuit_breaker_status():
    """Get status of all registered circuit breakers.

    Returns:
        Dict with circuit breaker names as keys, each containing:
        - name: Circuit breaker identifier
        - state: "closed" | "open" | "half_open"
        - failure_count: Current consecutive failure count
        - failure_threshold: Failures before opening
        - recovery_timeout: Seconds before transitioning to half_open
        - last_failure_time: ISO timestamp of last failure (if any)
    """
    try:
        from packages.core.circuit_breaker import get_all_circuit_breaker_statuses
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "circuit_breakers": get_all_circuit_breaker_statuses(),
        }
    except ImportError:
        # Graceful fallback if get_all_circuit_breaker_statuses is not yet available
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "circuit_breakers": {},
            "message": "Circuit breaker status module not yet available.",
        }


@router.get("/api/health/config")
async def config_health_check(request: Request):
    """Check which optional services are configured vs missing.

    Returns configuration completeness status, showing which critical
    and optional config keys are set. Useful for setup wizards and
    configuration dashboards.

    Returns:
        Dict with:
        - timestamp: ISO timestamp
        - critical: Dict mapping critical key names to configured (bool)
        - optional: Dict mapping optional key names to configured (bool)
        - missing_critical: List of missing critical keys
        - missing_optional: List of missing optional keys
        - summary: Dict with configured/missing counts
    """
    # Try to get pre-computed config status from app.state
    try:
        config_status = getattr(request.app.state, "config_status", None)
        if config_status:
            critical = config_status.get("critical", {})
            optional = config_status.get("optional", {})
            missing_critical = config_status.get("missing_critical", [])
            missing_optional = config_status.get("missing_optional", [])
        else:
            # Compute on-the-fly if not pre-computed
            from packages.core.config import get_settings as _get_settings
            _settings = _get_settings()
            critical = {
                "FREEROUTER_URL": bool(_settings.FREEROUTER_URL),
            }
            optional = {
                "NOTION_API_KEY": bool(_settings.NOTION_API_KEY),
                "ZEP_API_KEY": bool(_settings.ZEP_API_KEY),
                "EXA_API_KEY": bool(_settings.EXA_API_KEY),
                "SUPABASE_URL": bool(_settings.SUPABASE_URL),
                "YOUTUBE_API_KEY": bool(_settings.YOUTUBE_API_KEY),
            }
            missing_critical = [k for k, v in critical.items() if not v]
            missing_optional = [k for k, v in optional.items() if not v]
    except Exception:
        critical = {}
        optional = {}
        missing_critical = []
        missing_optional = []

    total = len(critical) + len(optional)
    configured_count = sum(1 for v in critical.values() if v) + sum(1 for v in optional.values() if v)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "critical": critical,
        "optional": optional,
        "missing_critical": missing_critical,
        "missing_optional": missing_optional,
        "summary": {
            "total_keys": total,
            "configured": configured_count,
            "missing": total - configured_count,
            "all_critical_configured": len(missing_critical) == 0,
        },
    }


# ─── Helper: Lazy import for Zep connectivity test ────────────────────────

def AsyncZepMemoryClient():
    """Lazy helper to import AsyncZepMemoryClient for health checks."""
    from packages.memory.client import AsyncZepMemoryClient as _AZMC
    return _AZMC()

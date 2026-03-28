"""
health_routes.py — Health check endpoints.

Provides endpoints for monitoring application health and status.
These endpoints are publicly accessible without authentication.

Endpoints:
    GET /health       - Basic health check
    GET /api/health   - Detailed health status
"""

from datetime import datetime
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check endpoint.
    
    Returns a simple status indicating the service is running.
    This endpoint is public and requires no authentication.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
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
        "timestamp": datetime.utcnow().isoformat(),
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
    except Exception:
        pass
    
    return {"healthy": False, "url": url}

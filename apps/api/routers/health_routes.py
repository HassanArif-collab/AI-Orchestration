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

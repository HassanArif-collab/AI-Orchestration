"""
API Routers Package

Exports all API routers for the FastAPI application.
"""

from apps.api.routers.pipeline_routes import router as pipeline_router
from apps.api.routers.pipeline_routes import router as pipeline_routes
from apps.api.routers.provider_routes import router as provider_routes
from apps.api.routers.chat_routes import router as chat_routes
from apps.api.routers.memory_routes import router as memory_routes
from apps.api.routers.analytics_routes import router as analytics_routes
from apps.api.routers.visual_routes import router as visual_routes
from apps.api.routers.settings_routes import router as settings_routes
from apps.api.routers.topic_routes import router as topic_routes
from apps.api.routers.health_routes import router as health_routes
from apps.api.routers.kanban_routes import router as kanban_routes

__all__ = [
    "pipeline_router",
    "pipeline_routes",
    "provider_routes",
    "chat_routes",
    "memory_routes",
    "analytics_routes",
    "visual_routes",
    "settings_routes",
    "topic_routes",
    "health_routes",
    "kanban_routes",
]

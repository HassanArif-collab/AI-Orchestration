"""
Middleware package for the API server.
"""

from apps.api.middleware.auth import AuthMiddleware

__all__ = ["AuthMiddleware"]

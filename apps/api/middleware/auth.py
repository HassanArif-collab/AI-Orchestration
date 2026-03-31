"""
auth.py — API Authentication Middleware.

Provides API key-based authentication for protected API endpoints.
Public paths are exempt from authentication requirements.

Usage:
    The middleware is automatically applied to all requests.
    Protected endpoints require X-API-Key header with a valid key.

Configuration:
    API_KEYS: Comma-separated list of valid API keys (env variable)
    API_KEY_HEADER: Header name for API key (default: X-API-Key)
    API_AUTH_ENABLED: Enable/disable auth (default: True)
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from packages.core.config import get_settings


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware for API key-based authentication.
    
    Public paths are accessible without authentication.
    All other paths require a valid API key in the specified header.
    """
    
    # Paths that don't require authentication
    PUBLIC_PATHS = {"/health", "/api/health", "/", "/favicon.ico", "/api/events"}
    
    # Path prefixes that don't require authentication
    PUBLIC_PREFIXES = ["/static/"]
    
    async def dispatch(self, request: Request, call_next):
        """Process the request and validate API key if required.
        
        Args:
            request: The incoming HTTP request
            call_next: The next middleware or route handler
            
        Returns:
            Response from next handler or authentication error
        """
        settings = get_settings()
        
        # Check if path is public
        path = request.url.path
        if path in self.PUBLIC_PATHS:
            return await call_next(request)
        for prefix in self.PUBLIC_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)
        
        # Skip if auth not configured
        if not settings.is_auth_enabled():
            return await call_next(request)
        
        # Validate API key
        api_key = request.headers.get(settings.API_KEY_HEADER)
        if not api_key:
            return JSONResponse(
                status_code=401,
                content={
                    "error": "Unauthorized",
                    "message": f"Missing {settings.API_KEY_HEADER} header"
                }
            )
        if api_key not in settings.valid_api_keys:
            return JSONResponse(
                status_code=403,
                content={
                    "error": "Forbidden",
                    "message": "Invalid API key"
                }
            )
        
        return await call_next(request)

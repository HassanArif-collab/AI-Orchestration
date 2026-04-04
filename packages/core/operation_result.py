"""
operation_result.py — Typed result wrapper for all external service operations.

Instead of returning None on failure (silent), all service methods return
OperationResult with explicit success/failure, user-friendly error messages,
severity for display routing, and retry metadata.

UX Pattern: Severity-based error routing (NN/g, Adobe Spectrum)
  - critical → modal dialog (blocks workflow)
  - warning  → persistent banner (service degradation)
  - info     → toast notification (non-blocking)
  - low      → inline message (form field level)

Imports: pydantic, datetime, enum, typing
Imported by: packages/integrations/, apps/api/
"""

from __future__ import annotations
from enum import Enum
from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone


class ErrorSeverity(str, Enum):
    """Error severity levels for display routing."""
    CRITICAL = "critical"  # Blocks workflow → modal dialog
    WARNING = "warning"    # Service degradation → persistent banner
    INFO = "info"          # Non-blocking → toast notification
    LOW = "low"            # Form/validation → inline message


T = TypeVar("T")


class OperationResult(BaseModel, Generic[T]):
    """Typed result wrapper with rich error context for UX display.

    Every external service operation should return this instead of
    returning None/empty on failure. The frontend uses severity to
    route errors to the appropriate display channel.

    Usage:
        result = await notion_client.create_script_page(...)
        if not result.success:
            # result.severity → determines display channel
            # result.user_message → shown to user
            # result.error_code → for programmatic handling
            # result.retryable → whether to show retry button
    """
    success: bool
    data: Optional[T] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    user_message: Optional[str] = None
    severity: ErrorSeverity = ErrorSeverity.INFO
    retryable: bool = False
    retry_after_seconds: Optional[int] = None
    error_details: dict[str, Any] = {}

    @classmethod
    def ok(cls, data: T, message: str = "") -> "OperationResult[T]":
        """Create a successful result."""
        return cls(success=True, data=data, user_message=message or "Success")

    @classmethod
    def fail(
        cls,
        message: str,
        code: str = "",
        severity: ErrorSeverity = ErrorSeverity.INFO,
        user_message: str = "",
        retryable: bool = False,
        retry_after: int = None,
        details: dict = None,
    ) -> "OperationResult[T]":
        """Create a failure result with full UX context."""
        return cls(
            success=False,
            error_message=message,
            error_code=code,
            user_message=user_message or message,
            severity=severity,
            retryable=retryable,
            retry_after_seconds=retry_after,
            error_details=details or {},
        )

    def to_api_response(self) -> dict:
        """Convert to API response dict."""
        if self.success:
            return {
                "success": True,
                "data": self.data,
                "message": self.user_message,
            }
        return {
            "success": False,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "user_message": self.user_message,
            "severity": self.severity.value,
            "retryable": self.retryable,
            "retry_after_seconds": self.retry_after_seconds,
        }


# Required for Pydantic V2 Generic model resolution
OperationResult.model_rebuild()

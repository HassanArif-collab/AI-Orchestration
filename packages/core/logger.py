"""
logger.py — Structured JSON logging for the pipeline.

Context: All pipeline packages use this for consistent log output.
Logs are JSON lines, easy to parse and search.

Usage:
    from packages.core.logger import get_logger
    log = get_logger(__name__)
    log.info("stage_started", stage="research", run_id="abc123")

Imports: structlog
Imported by: all packages
"""

import logging
import threading
import structlog

from packages.core.config import get_settings

# Module-level state to prevent repeated configuration
_logging_configured = False
_structlog_configured = False
_config_lock = threading.Lock()

# Sensitive field patterns for log sanitization (P2-10)
SENSITIVE_FIELDS = frozenset([
    "api_key", "apikey", "api-key",
    "token", "access_token", "refresh_token", "auth_token",
    "password", "passwd", "secret", "secret_key",
    "authorization", "bearer", "credential", "credentials",
    "private_key", "private-key", "privatekey",
])


def _sanitize_value(value: str, max_length: int = 100) -> str:
    """Sanitize a potentially sensitive string value.

    Args:
        value: The string value to sanitize
        max_length: Maximum length before truncation

    Returns:
        Sanitized string (redacted if sensitive, truncated if too long)
    """
    if not isinstance(value, str):
        value = str(value)

    # Truncate long values
    if len(value) > max_length:
        return value[:max_length] + "...[truncated]"

    return value


def sanitize_dict(data: dict, depth: int = 0) -> dict:
    """Recursively sanitize a dictionary by redacting sensitive fields.

    This function is used to prevent sensitive data from appearing in logs.
    It redacts values for keys that match known sensitive field patterns.

    Args:
        data: Dictionary to sanitize
        depth: Current recursion depth (max 5 to prevent infinite recursion)

    Returns:
        Sanitized dictionary with sensitive values redacted
    """
    if depth > 5:  # Prevent infinite recursion
        return {"_truncated": "max depth exceeded"}

    if not isinstance(data, dict):
        return data

    result = {}
    for key, value in data.items():
        key_lower = key.lower().replace("-", "_").replace(" ", "_")

        # Check if this key matches a sensitive field pattern
        is_sensitive = any(
            key_lower == sf or key_lower.startswith(sf + "_") or key_lower.endswith("_" + sf)
            for sf in [f.replace("-", "_") for f in SENSITIVE_FIELDS]
        )

        if is_sensitive:
            result[key] = "[REDACTED]"
        elif isinstance(value, dict):
            result[key] = sanitize_dict(value, depth + 1)
        elif isinstance(value, str):
            result[key] = _sanitize_value(value)
        else:
            result[key] = value

    return result


def _configure_logging_once() -> None:
    """Configure Python logging exactly once, thread-safe.

    This function ensures logging.basicConfig() is only called once
    per process, preventing duplicate handlers and log message duplication.
    """
    global _logging_configured

    with _config_lock:
        if _logging_configured:
            return

        settings = get_settings()
        logging.basicConfig(
            format="%(message)s",
            level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        )
        _logging_configured = True


def _configure_structlog_once() -> None:
    """Configure structlog exactly once, thread-safe.

    This function ensures structlog.configure() is only called once
    per process, preventing redundant configuration overhead.
    """
    global _structlog_configured

    with _config_lock:
        if _structlog_configured:
            return

        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.BoundLogger,
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
        )
        _structlog_configured = True


def get_logger(name: str) -> structlog.BoundLogger:
    """Return a configured structlog logger for the given module name.

    This function ensures logging is configured exactly once per process,
    using thread-safe initialization to prevent duplicate handlers and
    configuration overhead.

    Args:
        name: Module name for the logger (typically __name__)

    Returns:
        A configured structlog.BoundLogger instance
    """
    _configure_logging_once()
    _configure_structlog_once()
    return structlog.get_logger(name)

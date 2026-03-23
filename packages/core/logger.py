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
import structlog

from packages.core.config import get_settings


def get_logger(name: str) -> structlog.BoundLogger:
    """Return a configured structlog logger for the given module name."""
    settings = get_settings()

    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    )

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

    return structlog.get_logger(name)

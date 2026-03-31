"""
escalation.py — Escalation service for quality gate failures and critical errors.

Context: Provides a centralized escalation service for notifying operators
when quality gate failures occur or other critical issues need attention.
Supports multiple channels: logging, webhooks, and extensible for more.

Configuration (via Settings):
    ESCALATION_ENABLED: Enable/disable escalation (default: True)
    ESCALATION_WEBHOOK_URL: Webhook URL for external notifications
    ESCALATION_MIN_SCORE: Minimum score to trigger escalation (default: 50.0)

Imports: core.config, core.logger, core.errors
Imported by: evaluation/loop.py
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Callable
import asyncio
import logging

# These will be imported from the packages when the module is used
# For now, we'll use standard logging to avoid circular imports
logger = logging.getLogger(__name__)


class EscalationLevel(str, Enum):
    """Severity level for escalation events."""
    INFO = "info"          # Informational, no action required
    WARNING = "warning"    # Potential issue, monitoring recommended
    ERROR = "error"        # Issue detected, action may be required
    CRITICAL = "critical"  # Critical issue, immediate action required


class EscalationChannel(str, Enum):
    """Available escalation channels."""
    LOG = "log"            # Standard logging
    WEBHOOK = "webhook"    # HTTP webhook POST
    SLACK = "slack"        # Slack webhook (specialized format)
    DISCORD = "discord"    # Discord webhook (specialized format)


@dataclass
class EscalationEvent:
    """Represents an escalation event."""
    event_type: str
    message: str
    level: EscalationLevel = EscalationLevel.WARNING
    source: str = "pipeline"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "event_type": self.event_type,
            "message": self.message,
            "level": self.level.value,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class EscalationHandler:
    """Base class for escalation handlers."""

    async def handle(self, event: EscalationEvent) -> bool:
        """Handle an escalation event.

        Args:
            event: The escalation event to handle

        Returns:
            True if handled successfully, False otherwise
        """
        raise NotImplementedError


class LogHandler(EscalationHandler):
    """Handler that logs escalation events."""

    def __init__(self, log_level: int = logging.WARNING):
        """Initialize the log handler.

        Args:
            log_level: The logging level to use (default: WARNING)
        """
        self.log_level = log_level

    async def handle(self, event: EscalationEvent) -> bool:
        """Log the escalation event."""
        log_msg = f"[ESCALATION:{event.level.value.upper()}] {event.event_type}: {event.message}"
        if event.metadata:
            log_msg += f" | metadata={event.metadata}"

        if event.level == EscalationLevel.CRITICAL:
            logger.critical(log_msg)
        elif event.level == EscalationLevel.ERROR:
            logger.error(log_msg)
        elif event.level == EscalationLevel.WARNING:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

        return True


class WebhookHandler(EscalationHandler):
    """Handler that sends escalation events to a webhook."""

    def __init__(
        self,
        webhook_url: str,
        timeout: float = 10.0,
        headers: Optional[dict] = None,
    ):
        """Initialize the webhook handler.

        Args:
            webhook_url: URL to POST escalation events to
            timeout: Request timeout in seconds (default: 10.0)
            headers: Additional headers to include in the request
        """
        self.webhook_url = webhook_url
        self.timeout = timeout
        self.headers = headers or {"Content-Type": "application/json"}

    async def handle(self, event: EscalationEvent) -> bool:
        """Send the event to the webhook."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.webhook_url,
                    content=event.to_json(),
                    headers=self.headers,
                )
                if response.status_code >= 400:
                    logger.warning(
                        f"webhook_escalation_failed: status={response.status_code} "
                        f"url={self.webhook_url}"
                    )
                    return False
                return True
        except Exception as e:
            logger.warning(f"webhook_escalation_error: {e}")
            return False


class SlackHandler(WebhookHandler):
    """Handler that sends escalation events to Slack."""

    async def handle(self, event: EscalationEvent) -> bool:
        """Send the event to Slack with proper formatting."""
        # Format message for Slack
        color = {
            EscalationLevel.INFO: "#36a64f",      # green
            EscalationLevel.WARNING: "#ff9900",   # orange
            EscalationLevel.ERROR: "#ff0000",     # red
            EscalationLevel.CRITICAL: "#990000",  # dark red
        }.get(event.level, "#808080")

        slack_payload = {
            "attachments": [
                {
                    "color": color,
                    "title": f"[{event.level.value.upper()}] {event.event_type}",
                    "text": event.message,
                    "fields": [
                        {"title": "Source", "value": event.source, "short": True},
                        {"title": "Timestamp", "value": event.timestamp.isoformat(), "short": True},
                    ],
                    "footer": "AI Orchestration Pipeline",
                }
            ]
        }

        # Add metadata as fields if present
        if event.metadata:
            for key, value in event.metadata.items():
                slack_payload["attachments"][0]["fields"].append({
                    "title": key,
                    "value": str(value),
                    "short": len(str(value)) < 50,
                })

        try:
            import httpx
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.webhook_url,
                    json=slack_payload,
                    headers={"Content-Type": "application/json"},
                )
                return response.status_code < 400
        except Exception as e:
            logger.warning(f"slack_escalation_error: {e}")
            return False


class EscalationService:
    """Centralized service for handling escalations.

    Provides a unified interface for escalating issues to operators
    through multiple channels. Supports configurable rules and handlers.

    Example:
        service = EscalationService()
        service.add_handler(LogHandler())

        # Escalate a quality gate failure
        await service.escalate(
            event_type="quality_gate_failure",
            message="Script quality score 45% below floor 60%",
            level=EscalationLevel.ERROR,
            metadata={"score": 45, "floor": 60, "script_id": "abc123"}
        )
    """

    def __init__(
        self,
        enabled: bool = True,
        min_score_for_escalation: float = 50.0,
    ):
        """Initialize the escalation service.

        Args:
            enabled: Whether escalation is enabled (default: True)
            min_score_for_escalation: Minimum score to trigger escalation (default: 50.0)
        """
        self.enabled = enabled
        self.min_score_for_escalation = min_score_for_escalation
        self._handlers: list[EscalationHandler] = []
        self._escalation_count = 0

    def add_handler(self, handler: EscalationHandler) -> None:
        """Add an escalation handler.

        Args:
            handler: The handler to add
        """
        self._handlers.append(handler)

    def remove_handler(self, handler: EscalationHandler) -> None:
        """Remove an escalation handler.

        Args:
            handler: The handler to remove
        """
        if handler in self._handlers:
            self._handlers.remove(handler)

    async def escalate(
        self,
        event_type: str,
        message: str,
        level: EscalationLevel = EscalationLevel.WARNING,
        source: str = "pipeline",
        metadata: Optional[dict] = None,
    ) -> bool:
        """Escalate an event through all configured handlers.

        Args:
            event_type: Type of event (e.g., "quality_gate_failure")
            message: Human-readable message describing the issue
            level: Severity level (default: WARNING)
            source: Source of the escalation (default: "pipeline")
            metadata: Additional context data

        Returns:
            True if at least one handler succeeded, False otherwise
        """
        if not self.enabled:
            logger.debug(f"escalation_disabled: event_type={event_type}")
            return True

        event = EscalationEvent(
            event_type=event_type,
            message=message,
            level=level,
            source=source,
            metadata=metadata or {},
        )

        self._escalation_count += 1
        success = False

        for handler in self._handlers:
            try:
                if await handler.handle(event):
                    success = True
            except Exception as e:
                logger.warning(f"escalation_handler_error: {e}")

        if not success:
            logger.warning(f"escalation_all_handlers_failed: event_type={event_type}")

        return success

    async def escalate_quality_gate_failure(
        self,
        score: float,
        floor: float,
        script_id: Optional[str] = None,
        video_id: Optional[str] = None,
        iteration_count: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """Escalate a quality gate failure.

        Convenience method for the most common escalation scenario.

        Args:
            score: The actual quality score achieved
            floor: The minimum acceptable floor score
            script_id: ID of the failed script
            video_id: ID of the associated video
            iteration_count: Number of iterations attempted
            error_message: Original error message if any

        Returns:
            True if escalation succeeded
        """
        metadata = {
            "score": score,
            "floor": floor,
            "gap": floor - score,
        }
        if script_id:
            metadata["script_id"] = script_id
        if video_id:
            metadata["video_id"] = video_id
        if iteration_count is not None:
            metadata["iteration_count"] = iteration_count
        if error_message:
            metadata["error_message"] = error_message

        # Determine level based on how far below floor
        if score < floor * 0.5:  # Less than half the floor
            level = EscalationLevel.CRITICAL
        elif score < floor * 0.75:  # Less than 3/4 the floor
            level = EscalationLevel.ERROR
        else:
            level = EscalationLevel.WARNING

        return await self.escalate(
            event_type="quality_gate_failure",
            message=f"Script quality score {score:.1f}% is below minimum floor {floor:.1f}%",
            level=level,
            source="quality_gate",
            metadata=metadata,
        )

    async def escalate_pipeline_error(
        self,
        stage: str,
        error: str,
        run_id: Optional[str] = None,
        recoverable: bool = True,
    ) -> bool:
        """Escalate a pipeline stage error.

        Args:
            stage: The pipeline stage that failed
            error: The error message
            run_id: ID of the pipeline run
            recoverable: Whether the error is potentially recoverable

        Returns:
            True if escalation succeeded
        """
        metadata = {
            "stage": stage,
            "error": error,
            "recoverable": recoverable,
        }
        if run_id:
            metadata["run_id"] = run_id

        level = EscalationLevel.WARNING if recoverable else EscalationLevel.ERROR

        return await self.escalate(
            event_type="pipeline_error",
            message=f"Pipeline stage '{stage}' failed: {error}",
            level=level,
            source="pipeline",
            metadata=metadata,
        )

    def get_stats(self) -> dict:
        """Get escalation statistics.

        Returns:
            Dict with escalation count and handler count
        """
        return {
            "enabled": self.enabled,
            "total_escalations": self._escalation_count,
            "handler_count": len(self._handlers),
        }


# Global escalation service singleton
_service: Optional[EscalationService] = None


def get_escalation_service() -> EscalationService:
    """Get the global escalation service instance.

    The service is configured based on environment variables:
        ESCALATION_ENABLED: Enable/disable escalation (default: True)
        ESCALATION_WEBHOOK_URL: Webhook URL for external notifications
        ESCALATION_WEBHOOK_TYPE: Type of webhook (default, slack, discord)
        ESCALATION_MIN_SCORE: Minimum score to trigger escalation (default: 50.0)
        CIRCUIT_BREAKER_FAILURE_THRESHOLD: Used for critical escalation threshold

    Returns:
        EscalationService singleton
    """
    global _service
    if _service is not None:
        return _service

    # Read configuration from environment
    from packages.core.config import get_settings

    settings = get_settings()

    enabled = settings.ESCALATION_ENABLED
    min_score = settings.ESCALATION_MIN_SCORE
    webhook_url = settings.ESCALATION_WEBHOOK_URL.strip()
    webhook_type = settings.ESCALATION_WEBHOOK_TYPE.lower()

    service = EscalationService(
        enabled=enabled,
        min_score_for_escalation=min_score,
    )

    # Always add log handler
    service.add_handler(LogHandler())

    # Add webhook handler if configured
    if webhook_url:
        if webhook_type == "slack":
            service.add_handler(SlackHandler(webhook_url))
        else:
            service.add_handler(WebhookHandler(webhook_url))

        logger.info(f"escalation_webhook_configured: type={webhook_type}")

    logger.info(
        f"escalation_service_initialized: enabled={enabled} "
        f"handlers={len(service._handlers)}"
    )

    # Atomic assignment — if another thread beat us, discard ours
    if _service is not None:
        return _service
    _service = service
    return _service


def reset_escalation_service() -> None:
    """Reset the global escalation service (for testing)."""
    global _service
    _service = None

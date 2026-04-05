"""
progress.py — Progress tracking for long-running operations.

UX Pattern: Duration-based indicator selection (NN/g)
  < 1s:    No indicator needed
  1-5s:    Spinner or skeleton screen
  5-10s:   Indeterminate progress bar
  > 10s:   Determinate progress bar with named stages

Provides:
  - ProgressTracker: Context manager for tracking multi-stage operations
  - ProgressEvent: Structured progress data emitted via SSE
  - Stage-based milestone reporting with elapsed times
  - Backward-progress prevention (progress bars never decrease)
  - emit_progress: Standalone function for ad-hoc progress emission

Imports: time, datetime, enum, typing, pydantic
Imported by: packages/content_factory/, apps/api/
"""

from __future__ import annotations
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Any

from pydantic import BaseModel, Field


class ProgressStage(str, Enum):
    """Operation stage types for progress display.

    Core stages (Issue 4 spec):
      starting, in_progress, completed, failed

    Extended domain stages for fine-grained pipeline tracking:
      searching, generating, scoring, saving, researching, drafting,
      mutating, evaluating, publishing
    """
    STARTING = "starting"
    IN_PROGRESS = "in_progress"
    SEARCHING = "searching"
    GENERATING = "generating"
    SCORING = "scoring"
    SAVING = "saving"
    RESEARCHING = "researching"
    DRAFTING = "drafting"
    MUTATING = "mutating"
    EVALUATING = "evaluating"
    PUBLISHING = "publishing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProgressEvent(BaseModel):
    """Structured progress event for SSE broadcasting.

    Frontend uses this to render:
    - Stage-based progress bar with named milestones
    - Elapsed time per completed stage
    - Connection status indicator
    """
    operation_id: str
    operation_type: str  # e.g., "topic_generation", "script_writing", "pipeline_run"
    stage: ProgressStage = ProgressStage.STARTING
    stage_label: str = ""  # Human-readable stage name
    progress_percent: Optional[int] = None  # 0-100, None for indeterminate
    message: str = ""
    elapsed_seconds: float = 0.0
    estimated_remaining_seconds: Optional[float] = None
    total_stages: int = 1
    current_stage_index: int = 0
    metadata: dict[str, Any] = {}
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Required for Pydantic V2 forward reference resolution
ProgressEvent.model_rebuild()


class ProgressTracker:
    """Tracks progress through a multi-stage operation.

    Supports two APIs:
    1. High-level: start_stage() / complete_stage() / finish() / fail()
       For multi-stage pipelines with named stages.
    2. Simple: report() / complete() / fail()
       For single-pass or step-based tracking with total_steps.

    Usage (high-level):
        tracker = ProgressTracker("run-123", "topic_generation",
                                   stages=["searching", "generating", "scoring", "saving"])
        tracker.start_stage("searching", "Searching the web for trending topics...")
        # ... do searching ...
        tracker.complete_stage()
        tracker.finish("Topic generation complete!")

    Usage (simple):
        tracker = ProgressTracker("run-123", "script_writing", total_steps=5)
        tracker.report(ProgressStage.IN_PROGRESS, "Generating section 1...", percent=20)
        tracker.complete("Script generation complete!")

    The tracker emits ProgressEvents via SSE and prevents backward progress.
    """

    def __init__(
        self,
        operation_id: str,
        operation_type: str,
        stages: list[str] | None = None,
        total_steps: int | None = None,
    ):
        self.operation_id = operation_id
        self.operation_type = operation_type
        self.stages = stages or ["processing"]
        self.total_steps = total_steps or len(self.stages)
        self.total_stages = len(self.stages)
        self.current_stage_index = 0
        self._stage_start_time: float = 0.0
        self._operation_start_time: float = time.monotonic()
        self._last_percent: int = -1  # For backward-progress prevention
        self._last_event: Optional[ProgressEvent] = None

    def report(
        self,
        stage: ProgressStage | str,
        message: str = "",
        percent: int | None = None,
        metadata: dict[str, Any] | None = None,
        estimated_remaining: float | None = None,
    ) -> ProgressEvent:
        """Report progress with a simple, direct API.

        This is the primary method for the Issue 4 spec — allows callers
        to report stage, message, percent, and optional metadata in one call.

        Args:
            stage: The current ProgressStage (or string value).
            message: Human-readable progress message.
            percent: Progress percentage 0-100. None for indeterminate.
            metadata: Optional key-value metadata dict.
            estimated_remaining: Estimated seconds until completion.

        Returns:
            The ProgressEvent that was emitted.
        """
        if isinstance(stage, str):
            try:
                stage = ProgressStage(stage.lower())
            except ValueError:
                stage = ProgressStage.STARTING

        if percent is not None:
            percent = max(percent, self._last_percent)
            self._last_percent = percent
        else:
            percent = self._last_percent

        elapsed = time.monotonic() - self._operation_start_time

        if estimated_remaining is None:
            estimated_remaining = self._estimate_remaining(elapsed, percent)

        event = ProgressEvent(
            operation_id=self.operation_id,
            operation_type=self.operation_type,
            stage=stage,
            stage_label=stage.value,
            progress_percent=percent,
            message=message,
            elapsed_seconds=round(elapsed, 1),
            estimated_remaining_seconds=estimated_remaining,
            total_stages=self.total_steps,
            current_stage_index=self.current_stage_index,
            metadata=metadata or {},
        )

        self._last_event = event
        self._emit_event(event)
        return event

    def complete(self, message: str = "Operation complete!") -> ProgressEvent:
        """Mark the entire operation as successfully completed.

        Convenience method for the simple report()-based API.
        Progress is set to 100% and stage to COMPLETED.

        Args:
            message: Success message to display.

        Returns:
            The final ProgressEvent.
        """
        return self.finish(message)

    def start_stage(self, stage_name: str, message: str = "", metadata: dict | None = None) -> ProgressEvent:
        """Begin a new stage with progress tracking."""
        self._stage_start_time = time.monotonic()

        # Find stage index
        try:
            stage_enum = ProgressStage(stage_name.lower())
        except ValueError:
            stage_enum = ProgressStage.STARTING

        try:
            idx = self.stages.index(stage_name)
        except ValueError:
            idx = min(self.current_stage_index, self.total_stages - 1)
        self.current_stage_index = idx

        # Calculate progress (prevent going backward)
        percent = int((idx / max(self.total_stages, 1)) * 100)
        percent = max(percent, self._last_percent)
        self._last_percent = percent

        elapsed = time.monotonic() - self._operation_start_time

        event = ProgressEvent(
            operation_id=self.operation_id,
            operation_type=self.operation_type,
            stage=stage_enum,
            stage_label=stage_name,
            progress_percent=percent,
            message=message or f"Stage {idx + 1}/{self.total_stages}: {stage_name}",
            elapsed_seconds=round(elapsed, 1),
            estimated_remaining_seconds=self._estimate_remaining(elapsed, percent),
            total_stages=self.total_stages,
            current_stage_index=idx,
            metadata=metadata or {},
        )

        self._last_event = event
        self._emit_event(event)
        return event

    def update_stage(self, message: str, percent: int = None, metadata: dict | None = None) -> ProgressEvent:
        """Update progress within the current stage."""
        if percent is not None:
            # Blend stage-internal percent with overall progress
            base = int((self.current_stage_index / max(self.total_stages, 1)) * 100)
            stage_portion = int((1 / max(self.total_stages, 1)) * (percent / 100))
            overall = min(base + stage_portion, 99)
            overall = max(overall, self._last_percent)  # Prevent backward
            self._last_percent = overall
        else:
            overall = self._last_percent

        elapsed = time.monotonic() - self._operation_start_time

        event = ProgressEvent(
            operation_id=self.operation_id,
            operation_type=self.operation_type,
            stage=self._last_event.stage if self._last_event else ProgressStage.STARTING,
            stage_label=self._last_event.stage_label if self._last_event else "",
            progress_percent=overall,
            message=message,
            elapsed_seconds=round(elapsed, 1),
            estimated_remaining_seconds=self._estimate_remaining(elapsed, overall),
            total_stages=self.total_stages,
            current_stage_index=self.current_stage_index,
            metadata=metadata or {},
        )

        self._last_event = event
        self._emit_event(event)
        return event

    def complete_stage(self, message: str = "") -> ProgressEvent:
        """Mark current stage as completed and move to next."""
        if message:
            stage_message = message
        else:
            stage_name = (
                self.stages[self.current_stage_index]
                if self.current_stage_index < len(self.stages)
                else "Unknown"
            )
            stage_message = f"Completed: {stage_name}"

        # Ensure at least this stage's progress is shown
        next_index = min(self.current_stage_index + 1, self.total_stages)
        percent = int((next_index / max(self.total_stages, 1)) * 100)
        percent = max(percent, self._last_percent)
        self._last_percent = percent

        elapsed = time.monotonic() - self._operation_start_time

        event = ProgressEvent(
            operation_id=self.operation_id,
            operation_type=self.operation_type,
            stage=ProgressStage.COMPLETED,
            stage_label=self._last_event.stage_label if self._last_event else "",
            progress_percent=percent,
            message=stage_message,
            elapsed_seconds=round(elapsed, 1),
            total_stages=self.total_stages,
            current_stage_index=self.current_stage_index,
        )

        self._last_event = event
        self._emit_event(event)
        return event

    def fail(self, message: str, error_details: dict | None = None) -> ProgressEvent:
        """Mark the operation as failed with explanation."""
        elapsed = time.monotonic() - self._operation_start_time

        event = ProgressEvent(
            operation_id=self.operation_id,
            operation_type=self.operation_type,
            stage=ProgressStage.FAILED,
            stage_label=self._last_event.stage_label if self._last_event else "",
            progress_percent=self._last_percent,
            message=message,
            elapsed_seconds=round(elapsed, 1),
            total_stages=self.total_stages,
            current_stage_index=self.current_stage_index,
            metadata=error_details or {},
        )

        self._last_event = event
        self._emit_event(event)
        return event

    def finish(self, message: str = "Operation complete!") -> ProgressEvent:
        """Mark the entire operation as finished."""
        elapsed = time.monotonic() - self._operation_start_time

        event = ProgressEvent(
            operation_id=self.operation_id,
            operation_type=self.operation_type,
            stage=ProgressStage.COMPLETED,
            stage_label="",
            progress_percent=100,
            message=message,
            elapsed_seconds=round(elapsed, 1),
            total_stages=self.total_stages,
            current_stage_index=self.total_stages,
        )

        self._last_event = event
        self._emit_event(event)
        return event

    def _estimate_remaining(self, elapsed: float, percent: int) -> Optional[float]:
        """Estimate remaining time based on progress so far."""
        if percent <= 0 or percent >= 100:
            return None
        rate = elapsed / percent  # seconds per percent
        remaining = rate * (100 - percent)
        return round(remaining, 1)

    def _emit_event(self, event: ProgressEvent) -> None:
        """Emit progress event via SSE event bus."""
        try:
            import asyncio
            from apps.api.events import event_bus

            # Try to get running loop, emit if available
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(
                    event_bus.publish("progress", event.model_dump())
                )
            except RuntimeError:
                # No running loop — emit synchronously is fine during sync code
                pass
        except ImportError:
            # events module not available (e.g., during testing)
            pass


def emit_progress(event_type: str, data: dict) -> None:
    """Emit a progress event to the global SSE event bus.

    Standalone function for ad-hoc progress emission without needing a
    ProgressTracker instance. Integrates with the existing EventBus
    from apps/api/events.py.

    Args:
        event_type: The SSE event type string (e.g., "progress", "stage_complete").
        data: The event data dict to publish. Will be serialized to JSON.

    Usage:
        from packages.core.progress import emit_progress
        emit_progress("progress", {
            "operation_id": "run-123",
            "stage": "generating",
            "progress_percent": 50,
            "message": "Generating topics..."
        })
    """
    try:
        import asyncio
        from apps.api.events import event_bus

        # Add timestamp if not already present
        if "timestamp" not in data:
            data["timestamp"] = datetime.now(timezone.utc).isoformat()

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(event_bus.publish(event_type, data))
        except RuntimeError:
            # No running loop — cannot emit asynchronously from sync context.
            # This is acceptable; the caller should use ProgressTracker for
            # proper async emission.
            pass
    except ImportError:
        # events module not available (e.g., during testing)
        pass

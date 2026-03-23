"""Event hooks for pipeline execution.

Allows other packages to register custom behavior for pipeline events.
"""

from abc import ABC
from typing import TYPE_CHECKING, Any

from packages.core.logger import get_logger

if TYPE_CHECKING:
    from packages.pipeline.stages import Stage


class PipelineHooks:
    """Event hooks for pipeline lifecycle.

    Subclass to add custom behavior. Default implementation logs events.
    """

    async def on_stage_start(self, run_id: str, stage: "Stage") -> None:
        """Called when a stage starts executing.

        Args:
            run_id: Pipeline run identifier
            stage: Stage that started
        """
        logger = get_logger("pipeline.hooks")
        logger.info(f"Stage started: {stage.value} for run {run_id}")

    async def on_stage_complete(
        self, run_id: str, stage: "Stage", output: Any
    ) -> None:
        """Called when a stage completes.

        Args:
            run_id: Pipeline run identifier
            stage: Stage that completed
            output: Stage output
        """
        logger = get_logger("pipeline.hooks")
        logger.info(f"Stage completed: {stage.value} for run {run_id}")

    async def on_stage_error(
        self, run_id: str, stage: "Stage", error: Exception
    ) -> None:
        """Called when a stage fails.

        Args:
            run_id: Pipeline run identifier
            stage: Stage that failed
            error: The exception that occurred
        """
        logger = get_logger("pipeline.hooks")
        logger.error(f"Stage error: {stage.value} for run {run_id}: {error}")

    async def on_human_gate(self, run_id: str, stage: "Stage") -> None:
        """Called when pipeline pauses at a human gate.

        Args:
            run_id: Pipeline run identifier
            stage: Human gate stage
        """
        logger = get_logger("pipeline.hooks")
        logger.info(f"Human gate reached: {stage.value} for run {run_id}")

    async def on_pipeline_complete(self, run_id: str) -> None:
        """Called when pipeline completes all stages.

        Args:
            run_id: Pipeline run identifier
        """
        logger = get_logger("pipeline.hooks")
        logger.info(f"Pipeline completed: {run_id}")


class DefaultPipelineHooks(PipelineHooks):
    """Default implementation that logs all events."""

    pass

"""Pipeline Event Hooks — Extensibility Layer for the PipelineRunner.

Allows external code to react to pipeline lifecycle events without
modifying PipelineRunner itself (open/closed principle).

DEFAULT BEHAVIOR:
  PipelineRunner uses DefaultPipelineHooks which just logs each event.
  This is the safe default — events are visible in logs but nothing else happens.

HOW TO ADD CUSTOM BEHAVIOR:
  Subclass PipelineHooks and override the events you care about:

  class NotifySlackHooks(PipelineHooks):
      async def on_stage_complete(self, run_id, stage, output):
          await slack.send(f"Stage {stage.value} complete for {run_id}")

  runner = PipelineRunner(hooks=NotifySlackHooks())

AVAILABLE EVENTS:
  on_stage_start(run_id, stage)           — stage is about to execute
  on_stage_complete(run_id, stage, output) — stage finished with output
  on_stage_error(run_id, stage, error)     — stage raised an exception
  on_human_gate(run_id, stage)             — pipeline paused, waiting for approval
  on_pipeline_complete(run_id)             — all stages done, pipeline finished

CURRENT USAGE:
  apps/api/routers/pipeline_routes.py uses DefaultPipelineHooks.
  The API emits SSE events (server-sent events) via apps/api/events.py
  which could be wired into hooks for real-time frontend updates.
"""

from abc import ABC
from typing import TYPE_CHECKING, Any

from packages.core.logger import get_logger

if TYPE_CHECKING:
    from packages.pipeline.stages import Stage


class PipelineHooks:
    """Event hooks for pipeline lifecycle.

    Subclass to add custom behavior. Default implementation logs events.
    
    EXTENSIBILITY PATTERN:
      This class uses the Template Method pattern. The PipelineRunner
      calls these hook methods at specific lifecycle points. Subclasses
      can override any or all methods without modifying the runner.
    
    THREAD SAFETY:
      Hooks are called from the pipeline's async context. If your hook
      performs blocking operations, use asyncio.to_thread() or similar.
    
    EXAMPLE:
      class MetricsHooks(PipelineHooks):
          async def on_stage_complete(self, run_id, stage, output):
              metrics.stage_completed(stage.value, run_id)
              
          async def on_pipeline_complete(self, run_id):
              metrics.pipeline_finished(run_id)
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
            output: Stage output (varies by stage)
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

        Human gates are stages that require human approval:
          - HUMAN_TOPIC_APPROVAL — user must pick a topic
          - HUMAN_REVIEW — user must review script

        Args:
            run_id: Pipeline run identifier
            stage: Human gate stage
        """
        logger = get_logger("pipeline.hooks")
        logger.info(f"Human gate reached: {stage.value} for run {run_id}")

    async def on_pipeline_complete(self, run_id: str) -> None:
        """Called when pipeline completes all stages.

        This is called whether the pipeline succeeded or failed.
        Check the run status to determine the outcome.

        Args:
            run_id: Pipeline run identifier
        """
        logger = get_logger("pipeline.hooks")
        logger.info(f"Pipeline completed: {run_id}")


class DefaultPipelineHooks(PipelineHooks):
    """Default implementation that logs all events.
    
    This is what PipelineRunner uses by default. It provides
    visibility into pipeline progress without any side effects.
    """

    pass

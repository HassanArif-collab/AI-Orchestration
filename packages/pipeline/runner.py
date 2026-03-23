"""Pipeline orchestration runner.

Executes stages in dependency order with human gate support.
"""

import asyncio
from typing import TYPE_CHECKING, Any, Optional

from packages.core.errors import PipelineError
from packages.core.logger import get_logger
from packages.pipeline.handlers import STAGE_HANDLERS
from packages.pipeline.hooks import PipelineHooks
from packages.pipeline.state import PipelineRun, RunStore
from packages.pipeline.stages import Stage, is_human_gate

if TYPE_CHECKING:
    pass


class PipelineRunner:
    """Orchestrates pipeline execution.

    Handles stage execution, dependency management, and human gates.
    """

    def __init__(self, store: Optional[RunStore] = None, hooks: Optional[PipelineHooks] = None):
        """Initialize the pipeline runner.

        Args:
            store: RunStore instance (creates new if None)
            hooks: PipelineHooks instance for events (uses default if None)
        """
        self.store = store or RunStore()
        self.hooks = hooks or PipelineHooks()
        self.logger = get_logger(__name__)

    async def create_run(self) -> PipelineRun:
        """Create a new pipeline run.

        Returns:
            New PipelineRun instance, saved to store
        """
        run = PipelineRun.new()
        self.store.save(run)
        return run

    async def execute_stage(
        self, run: PipelineRun, stage: Stage, context: dict = None
    ) -> Any:
        """Execute a single stage.

        Args:
            run: Current pipeline run
            stage: Stage to execute
            context: Additional context for the handler

        Returns:
            Stage output, or None if paused at human gate

        Raises:
            PipelineError: If stage cannot start or has no handler
        """
        context = context or {}

        # Check dependencies
        if not run.can_start(stage):
            raise PipelineError(
                f"Cannot start {stage.value}: dependencies not met",
                stage=stage.value,
            )

        # Check if human gate - pause instead of executing
        if is_human_gate(stage):
            run.status = "waiting_human"
            run.current_stage = stage
            run.stage_status[stage.value] = "waiting_human"
            self.store.save(run)
            if self.hooks:
                await self.hooks.on_human_gate(run.run_id, stage)
            return None

        # Get handler
        handler = STAGE_HANDLERS.get(stage.value)
        if not handler:
            raise PipelineError(
                f"No handler for stage: {stage.value}",
                stage=stage.value,
            )

        # Execute stage
        run.stage_status[stage.value] = "running"
        run.current_stage = stage
        self.store.save(run)

        if self.hooks:
            await self.hooks.on_stage_start(run.run_id, stage)

        try:
            output = await handler(run, context)
            run.set_output(stage, output)
            self.store.save(run)

            if self.hooks:
                await self.hooks.on_stage_complete(run.run_id, stage, output)

            return output

        except Exception as e:
            run.stage_status[stage.value] = "error"
            run.error_message = str(e)
            run.status = "error"
            self.store.save(run)

            if self.hooks:
                await self.hooks.on_stage_error(run.run_id, stage, e)

            raise

    async def approve_gate(
        self,
        run: PipelineRun,
        stage: Stage,
        approved: bool,
        selection: Any = None,
    ) -> None:
        """Approve a human gate and continue.

        Args:
            run: Current pipeline run
            stage: Human gate stage being approved
            approved: Whether the gate is approved
            selection: Selection data (e.g., chosen video idea)
        """
        if not is_human_gate(stage):
            raise PipelineError(f"Stage {stage.value} is not a human gate")

        # Store human decision as stage output
        run.set_output(
            stage,
            selection if selection is not None else approved,
        )
        run.status = "running"
        self.store.save(run)

    async def run_until_gate(self, run: PipelineRun) -> Optional[Stage]:
        """Execute stages until hitting a human gate or completion.

        Args:
            run: Current pipeline run

        Returns:
            The gate Stage if paused, or None if pipeline is complete
        """
        while True:
            runnable = run.get_runnable_stages()

            if not runnable:
                # Check for human gates
                for stage in Stage:
                    if (
                        run.stage_status.get(stage.value) == "pending"
                        and is_human_gate(stage)
                        and run.can_start(stage)
                    ):
                        await self.execute_stage(run, stage)
                        return stage

                # Nothing runnable and no gates -> pipeline complete
                run.status = "complete"
                self.store.save(run)
                if self.hooks:
                    await self.hooks.on_pipeline_complete(run.run_id)
                return None

            # Run parallel stages concurrently (e.g., SEO + VISUAL_PLANNING)
            if len(runnable) > 1:
                await asyncio.gather(
                    *[self.execute_stage(run, s) for s in runnable]
                )
            else:
                await self.execute_stage(run, runnable[0])

    async def request_feedback(
        self,
        run: PipelineRun,
        from_stage: Stage,
        to_stage: Stage,
        feedback: str,
    ) -> None:
        """Request feedback and re-run stages.

        Args:
            run: Current pipeline run
            from_stage: Stage requesting feedback
            to_stage: Stage to re-run with feedback
            feedback: Feedback text
        """
        from packages.pipeline.stages import can_feedback_to

        if not can_feedback_to(from_stage, to_stage):
            raise PipelineError(
                f"Feedback from {from_stage.value} to {to_stage.value} is not allowed"
            )

        # Reset to_stage status to pending
        run.stage_status[to_stage.value] = "pending"

        # Re-run to_stage with feedback in context
        await self.execute_stage(run, to_stage, context={"feedback": feedback})

        # Re-run from_stage with new output
        run.stage_status[from_stage.value] = "pending"
        await self.execute_stage(run, from_stage)

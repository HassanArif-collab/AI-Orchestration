"""
⚠️  DEPRECATED — This file is no longer used.
     Pipeline orchestration has moved to LangGraph.
     See: packages/content_factory/orchestration/graphs.py
     
     This file is kept for reference only. Do not import from it.
     Will be deleted after Phase 5 frontend is confirmed working.
"""
import warnings
warnings.warn(
    "This module is deprecated. Use orchestration.graphs instead.",
    DeprecationWarning,
    stacklevel=2
)

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
    Thread-safe for parallel stage execution via asyncio.Lock.
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
        # Lock for thread-safe state modifications during parallel execution
        self._state_lock = asyncio.Lock()

    async def create_run(self) -> PipelineRun:
        """Create a new pipeline run.

        Returns:
            New PipelineRun instance, saved to store
        """
        run = PipelineRun.new()
        self.store.save(run)
        return run

    async def _update_stage_status_atomic(
        self, run: PipelineRun, stage: Stage, status: str
    ) -> None:
        """Thread-safe wrapper for updating stage status.

        Acquires lock before modifying stage_status dictionary to prevent
        race conditions during parallel stage execution.

        Args:
            run: PipelineRun to update
            stage: Stage whose status is being updated
            status: New status value
        """
        async with self._state_lock:
            run.stage_status[stage.value] = status
            self.store.save(run)

    async def _update_run_state_atomic(
        self, run: PipelineRun, **kwargs
    ) -> None:
        """Thread-safe wrapper for updating run state.

        Acquires lock before modifying run attributes to prevent
        race conditions during parallel stage execution.

        Args:
            run: PipelineRun to update
            **kwargs: Attributes to update (e.g., status, current_stage, error_message)
        """
        async with self._state_lock:
            for key, value in kwargs.items():
                if hasattr(run, key):
                    setattr(run, key, value)
            self.store.save(run)

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

        # Check dependencies (read-only, no lock needed)
        if not run.can_start(stage):
            raise PipelineError(
                f"Cannot start {stage.value}: dependencies not met",
                stage=stage.value,
            )

        # Check if human gate - pause instead of executing
        if is_human_gate(stage):
            await self._update_run_state_atomic(
                run,
                status="waiting_human",
                current_stage=stage,
            )
            await self._update_stage_status_atomic(run, stage, "waiting_human")
            if self.hooks:
                await self.hooks.on_human_gate(run.run_id, stage)
            return None

        # Get handler (read-only, no lock needed)
        handler = STAGE_HANDLERS.get(stage.value)
        if not handler:
            raise PipelineError(
                f"No handler for stage: {stage.value}",
                stage=stage.value,
            )

        # Mark stage as running (atomic update)
        await self._update_stage_status_atomic(run, stage, "running")
        await self._update_run_state_atomic(run, current_stage=stage)

        if self.hooks:
            await self.hooks.on_stage_start(run.run_id, stage)

        try:
            output = await handler(run, context)
            # Atomic update for stage output
            async with self._state_lock:
                run.set_output(stage, output)
                self.store.save(run)

            if self.hooks:
                await self.hooks.on_stage_complete(run.run_id, stage, output)

            return output

        except Exception as e:
            # Atomic update for error state
            async with self._state_lock:
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
            # Each stage uses atomic state updates via _state_lock to prevent races
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

    async def resume_run(self, run_id: str) -> Optional[Stage]:
        """Resume a crashed or paused pipeline run.

        Recovers a pipeline run from error state or waiting_human state.
        For error states, resets the failed stage and attempts to continue.
        For waiting_human states, returns the gate stage for approval.

        Args:
            run_id: ID of the run to resume

        Returns:
            Stage where execution stopped (gate or recovered), or None if:
            - Run not found
            - Run already completed
            - Run cannot be resumed
        """
        run = self.store.load(run_id)
        if not run:
            self.logger.warning(f"resume_run_not_found: run_id={run_id}")
            return None

        # Already completed - nothing to resume
        if run.status == "completed":
            self.logger.info(f"resume_run_already_completed: run_id={run_id}")
            return None

        # Waiting at human gate - return the gate stage
        if run.status == "waiting_human":
            self.logger.info(f"resume_run_waiting_gate: run_id={run_id}")
            return run.current_stage

        # Error state - attempt recovery
        if run.status == "error":
            self.logger.info(f"resume_run_recovering: run_id={run_id}")
            failed_stage = run.current_stage
            if failed_stage:
                # Reset the failed stage to pending
                run.stage_status[failed_stage.value] = "pending"
                run.error_message = ""
            run.status = "running"

            # Save and verify no concurrent resume happened
            self.store.save(run)
            reloaded = self.store.load(run_id)
            if reloaded and reloaded.status != "running":
                self.logger.warning(
                    f"resume_run_race_condition: run_id={run_id} "
                    f"status changed to {reloaded.status} during resume"
                )
                return None

            # Continue execution
            return await self.run_until_gate(run)

        # Running state - just continue from where it left off
        if run.status == "running":
            self.logger.info(f"resume_run_continuing: run_id={run_id}")
            return await self.run_until_gate(run)

        self.logger.warning(f"resume_run_unknown_status: run_id={run_id} status={run.status}")
        return None

    def list_resumable_runs(self) -> list[dict]:
        """List all runs that can be resumed.

        Scans all pipeline runs and returns those in error or waiting_human states.
        These are runs that can be recovered via resume_run().

        Returns:
            List of dictionaries, each containing:
            - run_id: The run identifier
            - status: Current status ("error" or "waiting_human")
            - current_stage: The stage where the run stopped
            - error_message: Error message (if status is "error")
            - created_at: When the run was created
            - updated_at: When the run was last updated
        """
        # 3.7 FIX: Pre-filter by status from summary to avoid loading non-resumable runs.
        # Summary already contains run_id, current_stage, status, updated_at.
        # Only load full run data for status-matching runs (which need error_message, created_at).
        runs = self.store.list_runs(limit=100)
        resumable = []

        for run_summary in runs:
            run_id = run_summary.get("run_id")
            if not run_id:
                continue

            # 3.7 FIX: Filter by summary status to skip N load() calls for non-resumable runs
            status = run_summary.get("status")
            if status not in ("error", "waiting_human"):
                continue

            run = self.store.load(run_id)
            if not run:
                continue

            resumable.append({
                "run_id": run.run_id,
                "status": run.status,
                "current_stage": run.current_stage.value if run.current_stage else None,
                "error_message": run.error_message,
                "created_at": run.created_at.isoformat() if run.created_at else None,
                "updated_at": run.updated_at.isoformat() if run.updated_at else None,
            })

        return resumable

    async def recover_all_failed(self) -> list[dict]:
        """Attempt to recover all failed pipeline runs.

        Finds all runs in error state and attempts to resume them.
        Useful after system restart or transient failure resolution.

        Returns:
            List of recovery results, each containing:
            - run_id: The run that was recovered
            - success: Whether recovery was attempted
            - current_stage: Where the run resumed to (if successful)
        """
        resumable = self.list_resumable_runs()
        results = []

        for run_info in resumable:
            if run_info["status"] == "error":
                try:
                    result = await self.resume_run(run_info["run_id"])
                    results.append({
                        "run_id": run_info["run_id"],
                        "success": result is not None,
                        "current_stage": result.value if result else None,
                    })
                except Exception as e:
                    self.logger.error(
                        f"recover_all_failed_error: run_id={run_info['run_id']} error={e}"
                    )
                    results.append({
                        "run_id": run_info["run_id"],
                        "success": False,
                        "error": str(e),
                    })

        return results

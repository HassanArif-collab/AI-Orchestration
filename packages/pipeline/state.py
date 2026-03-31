"""Pipeline state management and persistence.

Handles PipelineRun state and Supabase persistence.
"""

import uuid
from datetime import datetime
from typing import Any

from packages.pipeline.stages import Stage, STAGE_DEPENDENCIES


class PipelineRun:
    """Runtime state of a single pipeline execution.

    NOT to be confused with packages.core.types.PipelineState which is
    a Pydantic model for API serialization. PipelineRun is the live
    mutable state object that PipelineRunner works with.

    LIFECYCLE:
      PipelineRun.new() -> created with all stages "pending"
      runner.execute_stage() -> stage moves pending -> running -> complete/error
      runner.run_until_gate() -> runs until HUMAN_TOPIC_APPROVAL or HUMAN_REVIEW
      runner.approve_gate() -> human approves, status returns to "running"
      run.status == "complete" -> all stages done

    PERSISTENCE:
      Saved to Supabase pipeline_runs table after every
      stage transition. If the process crashes, state is recovered on restart.

    RUN ID vs CYCLE ID:
      run_id: UUID from PipelineRunner -- the pipeline execution identifier
      cycle_id: UUID from MasterOrchestrator -- the production cycle identifier
      They are linked in OrchestrationDB.production_registry.pipeline_run_id

    STAGE OUTPUTS:
      stage_outputs: dict mapping Stage.value -> handler return value
      Access via: run.get_output(Stage.RESEARCH) -> AdaptedScript dict
      Set via:    run.set_output(Stage.RESEARCH, script_data)
    """

    def __init__(
        self,
        run_id: str,
        current_stage: Stage,
        stage_outputs: dict[str, Any],
        stage_status: dict[str, str],
        status: str,
        created_at: datetime,
        updated_at: datetime,
        error_message: str = "",
    ):
        """Initialize a pipeline run.

        Args:
            run_id: Unique identifier
            current_stage: Current executing stage
            stage_outputs: Stage value -> output data mapping
            stage_status: Stage value -> status mapping
            status: Overall status
            created_at: Creation timestamp
            updated_at: Last update timestamp
            error_message: Error message if status is 'error'
        """
        self.run_id = run_id
        self.current_stage = current_stage
        self.stage_outputs = stage_outputs
        self.stage_status = stage_status
        self.status = status
        self.created_at = created_at
        self.updated_at = updated_at
        self.error_message = error_message

    @classmethod
    def new(cls) -> "PipelineRun":
        """Create a new pipeline run with default values.

        All stages start as "pending". The first stage is TREND_ANALYSIS.

        Returns:
            New PipelineRun instance
        """
        now = datetime.utcnow()
        stage_status = {stage.value: "pending" for stage in Stage}
        return cls(
            run_id=str(uuid.uuid4()),
            current_stage=Stage.TREND_ANALYSIS,
            stage_outputs={},
            stage_status=stage_status,
            status="running",
            created_at=now,
            updated_at=now,
            error_message="",
        )

    def is_stage_complete(self, stage: Stage) -> bool:
        """Check if a stage has completed.

        Args:
            stage: The stage to check

        Returns:
            True if stage status is 'complete'
        """
        return self.stage_status.get(stage.value) == "complete"

    def can_start(self, stage: Stage) -> bool:
        """Check if a stage can start (all dependencies met).

        Uses STAGE_DEPENDENCIES from stages.py to determine prerequisites.
        For example, SCRIPT_WRITING depends on RESEARCH completing first.

        Args:
            stage: The stage to check

        Returns:
            True if all dependencies are complete
        """
        dependencies = STAGE_DEPENDENCIES.get(stage, [])
        return all(self.is_stage_complete(dep) for dep in dependencies)

    def set_output(self, stage: Stage, output: Any) -> None:
        """Store output and mark stage as complete.

        Args:
            stage: The stage that completed
            output: The stage output data
        """
        self.stage_outputs[stage.value] = output
        self.stage_status[stage.value] = "complete"
        self.updated_at = datetime.utcnow()

    def get_output(self, stage: Stage) -> Any | None:
        """Get output from a completed stage.

        Args:
            stage: The stage to get output for

        Returns:
            Stage output or None if not found
        """
        return self.stage_outputs.get(stage.value)

    def get_runnable_stages(self) -> list[Stage]:
        """Get all stages that can run now.

        Returns:
            List of stages where dependencies are met and status is 'pending'
        """
        runnable = []
        for stage in Stage:
            if self.stage_status.get(stage.value) == "pending" and self.can_start(stage):
                # Exclude human gates (handled separately)
                from packages.pipeline.stages import is_human_gate

                if not is_human_gate(stage):
                    runnable.append(stage)
        return runnable

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dictionary.

        Returns:
            Serializable state dictionary
        """
        return {
            "run_id": self.run_id,
            "current_stage": self.current_stage.value,
            "stage_outputs": _serialize_datetimes(self.stage_outputs),
            "stage_status": self.stage_status,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PipelineRun":
        """Create PipelineRun from dictionary.

        Args:
            data: Dictionary from to_dict()

        Returns:
            PipelineRun instance
        """
        try:
            current_stage = Stage(data["current_stage"])
        except (ValueError, KeyError):
            # Handle renamed or unknown stages gracefully
            current_stage = Stage.TREND_ANALYSIS
            import logging
            logging.getLogger(__name__).warning(
                f"from_dict_unknown_stage: {data['current_stage']} "
                f"defaulting to TREND_ANALYSIS"
            )

        return cls(
            run_id=data["run_id"],
            current_stage=current_stage,
            stage_outputs=data["stage_outputs"],
            stage_status=data["stage_status"],
            status=data["status"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            error_message=data.get("error_message", ""),
        )


def _serialize_datetimes(obj: Any) -> Any:
    """Recursively serialize datetime objects to ISO strings.

    Args:
        obj: Object to serialize (dict, list, datetime, or primitive)

    Returns:
        JSON-serializable version of the object
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: _serialize_datetimes(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_serialize_datetimes(item) for item in obj]
    else:
        return obj


class RunStore:
    """Supabase persistence for PipelineRun objects.

    Stores runs in the pipeline_runs table.

    TABLE SCHEMA:
      pipeline_runs
        run_id (PK)         -- UUID
        current_stage       -- TEXT
        stage_outputs       -- JSONB
        stage_status        -- JSONB
        status              -- TEXT
        error_message       -- TEXT
        created_at          -- TIMESTAMPTZ
        updated_at          -- TIMESTAMPTZ

    CRASH RECOVERY:
      After any crash, PipelineRunner.load_run(run_id) can recover
      the exact state and resume from the last completed stage.
    """

    def __init__(self):
        pass  # Supabase tables are pre-created via migration SQL

    def _db(self):
        from packages.core.supabase_client import get_supabase
        return get_supabase().table("pipeline_runs")

    def save(self, run: PipelineRun) -> None:
        """Save a pipeline run to Supabase (upsert on run_id).

        Args:
            run: The pipeline run to save
        """
        data = {
            "run_id": run.run_id,
            "current_stage": run.current_stage.value if hasattr(run.current_stage, "value") else str(run.current_stage),
            "stage_outputs": run.to_dict()["stage_outputs"],
            "stage_status": run.stage_status,
            "status": run.status,
            "error_message": run.error_message,
            "created_at": run.created_at.isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        self._db().upsert(data, on_conflict="run_id").execute()

    def load(self, run_id: str) -> PipelineRun | None:
        """Load a pipeline run from Supabase.

        Args:
            run_id: The run ID to load

        Returns:
            PipelineRun instance or None if not found
        """
        result = self._db().select("*").eq("run_id", run_id).maybe_single().execute()
        if not result.data:
            return None
        row = result.data
        return PipelineRun(
            run_id=row["run_id"],
            current_stage=Stage(row["current_stage"]),
            stage_outputs=row["stage_outputs"] or {},
            stage_status=row["stage_status"] or {},
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            error_message=row.get("error_message", ""),
        )

    def list_runs(self, limit: int = 20, include_details: bool = False) -> list[dict]:
        """List recent pipeline runs.

        Args:
            limit: Maximum number of runs to return
            include_details: If True, select all columns (for detail views).
                Defaults to summary-only (run_id, current_stage, status, updated_at)
                to avoid expensive full-row fetches in list endpoints.

        Returns:
            List of run summaries or full run records
        """
        if include_details:
            result = (
                self._db()
                .select("*")
                .order("updated_at", desc=True)
                .limit(limit)
                .execute()
            )
        else:
            result = (
                self._db()
                .select("run_id, current_stage, status, updated_at")
                .order("updated_at", desc=True)
                .limit(limit)
                .execute()
            )
        return result.data or []

    def delete(self, run_id: str) -> None:
        """Delete a pipeline run.

        Args:
            run_id: The run ID to delete
        """
        self._db().delete().eq("run_id", run_id).execute()

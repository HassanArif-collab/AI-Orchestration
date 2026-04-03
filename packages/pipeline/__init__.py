"""
Pipeline package — 9-stage state machine runner.

Drives the full video production pipeline from topic → published output.
State is persisted in packages/data/pipeline.db so runs survive crashes.
Stages with human gates pause and wait for approval before continuing.

    from packages.pipeline import PipelineRunner, Stage

"""

from packages.pipeline.stages import Stage, is_human_gate, get_dependencies, can_feedback_to
from packages.pipeline.state import PipelineRun, RunStore
from packages.pipeline.runner import PipelineRunner
from packages.pipeline.handlers import STAGE_HANDLERS
from packages.pipeline.hooks import PipelineHooks, DefaultPipelineHooks

__all__ = [
    "Stage",
    "is_human_gate",
    "get_dependencies",
    "can_feedback_to",
    "PipelineRun",
    "RunStore",
    "PipelineRunner",
    "STAGE_HANDLERS",
    "PipelineHooks",
    "DefaultPipelineHooks",
]

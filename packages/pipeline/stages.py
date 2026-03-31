"""Pipeline stage definitions and dependency management.

Defines all stages, their dependencies, and utility functions.
"""

from enum import Enum
from typing import Callable


class Stage(str, Enum):
    """All pipeline stages."""

    TREND_ANALYSIS = "trend_analysis"
    HUMAN_TOPIC_APPROVAL = "human_topic_approval"
    RESEARCH = "research"
    SCRIPT_WRITING = "script_writing"
    VISUAL_PLANNING = "visual_planning"
    HUMAN_REVIEW = "human_review"
    ASSET_CREATION = "asset_creation"
    SEO = "seo"
    PUBLISH = "publish"


# Human gate stages that require manual approval
HUMAN_GATES: set[Stage] = {
    Stage.HUMAN_TOPIC_APPROVAL,
    Stage.HUMAN_REVIEW,
}

# What must complete before each stage can start
STAGE_DEPENDENCIES: dict[Stage, list[Stage]] = {
    Stage.TREND_ANALYSIS: [],
    Stage.HUMAN_TOPIC_APPROVAL: [Stage.TREND_ANALYSIS],
    Stage.RESEARCH: [Stage.HUMAN_TOPIC_APPROVAL],
    Stage.SCRIPT_WRITING: [Stage.RESEARCH],
    Stage.VISUAL_PLANNING: [Stage.SCRIPT_WRITING],
    Stage.HUMAN_REVIEW: [Stage.VISUAL_PLANNING, Stage.SEO],
    Stage.ASSET_CREATION: [Stage.HUMAN_REVIEW],
    Stage.SEO: [Stage.SCRIPT_WRITING],
    Stage.PUBLISH: [Stage.ASSET_CREATION],
}

# Stages that can request re-execution of earlier stages
FEEDBACK_LOOPS: dict[Stage, list[Stage]] = {
    Stage.SCRIPT_WRITING: [Stage.RESEARCH],
    Stage.VISUAL_PLANNING: [Stage.SCRIPT_WRITING],
}


def is_human_gate(stage: Stage) -> bool:
    """Check if a stage is a human gate.

    Args:
        stage: The stage to check

    Returns:
        True if stage requires human approval
    """
    return stage in HUMAN_GATES


def get_dependencies(stage: Stage) -> list[Stage]:
    """Get the dependencies for a stage.

    Args:
        stage: The stage to get dependencies for

    Returns:
        List of stages that must complete before this stage
    """
    return STAGE_DEPENDENCIES.get(stage, [])


def can_feedback_to(from_stage: Stage, to_stage: Stage) -> bool:
    """Check if a feedback loop is allowed.

    Args:
        from_stage: The stage requesting feedback
        to_stage: The target stage for feedback

    Returns:
        True if the feedback loop is allowed
    """
    return to_stage in FEEDBACK_LOOPS.get(from_stage, [])

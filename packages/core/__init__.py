"""Core package — shared types, config, errors, logging."""

from packages.core.types import (
    VideoIdea, ResearchOutput, Script, ScriptSection,
    VisualDecision, VisualPlan, SEOPackage, PipelineState,
    SessionType, AgentRole, MessageRole,
    VideoMetadata, ChannelMetadata, AnalyticsMetadata,
    ChannelStats, MemoryFact,
)
from packages.core.config import Settings, get_settings
from packages.core.errors import (
    PipelineError, LLMClientError, RateLimitError,
    ZepMemoryError, IntegrationError,
)
from packages.core.logger import get_logger

__all__ = [
    "VideoIdea", "ResearchOutput", "Script", "ScriptSection",
    "VisualDecision", "VisualPlan", "SEOPackage", "PipelineState",
    "SessionType", "AgentRole", "MessageRole",
    "VideoMetadata", "ChannelMetadata", "AnalyticsMetadata",
    "ChannelStats", "MemoryFact",
    "Settings", "get_settings",
    "PipelineError", "LLMClientError", "RateLimitError",
    "ZepMemoryError", "IntegrationError",
    "get_logger",
]

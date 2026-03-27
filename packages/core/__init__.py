"""
Core package — shared infrastructure foundation.

Provides: config (loads all .env vars), logger, typed errors, shared types.
Import from here — never from individual submodules directly.

    from packages.core import get_settings, get_logger, PipelineError
"""

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
from packages.core.cache import FileCache

__all__ = [
    "VideoIdea", "ResearchOutput", "Script", "ScriptSection",
    "VisualDecision", "VisualPlan", "SEOPackage", "PipelineState",
    "SessionType", "AgentRole", "MessageRole",
    "VideoMetadata", "ChannelMetadata", "AnalyticsMetadata",
    "ChannelStats", "MemoryFact",
    "Settings", "get_settings",
    "PipelineError", "LLMClientError", "RateLimitError",
    "ZepMemoryError", "IntegrationError",
    "get_logger", "FileCache",
]

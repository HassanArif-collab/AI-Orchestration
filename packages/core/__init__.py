"""
Core package — shared infrastructure foundation.

Provides: config (loads all .env vars), logger, typed errors, shared types,
operation results, error codes, progress tracking, circuit breakers.

Import from here — never from individual submodules directly.

    from packages.core import get_settings, get_logger, PipelineError
    from packages.core import OperationResult, ErrorSeverity
    from packages.core import get_user_friendly_error, get_error_response
    from packages.core import ProgressTracker, emit_progress
"""

from packages.core.types import (
    PipelineState,
    SessionType, AgentRole, MessageRole,
    VideoMetadata, ChannelMetadata, AnalyticsMetadata,
    ChannelStats, MemoryFact,
)
from packages.core.config import Settings, get_settings
from packages.core.errors import (
    PipelineError, LLMClientError, RateLimitError,
    ZepMemoryError, IntegrationError, QualityGateError,
    PipelineException,
)
from packages.core.logger import get_logger
from packages.core.cache import FileCache
from packages.core.operation_result import OperationResult, ErrorSeverity
from packages.core.error_codes import (
    get_user_friendly_error, get_error_response,
    ERROR_REGISTRY, get_error_detail,
)
from packages.core.progress import ProgressTracker, ProgressStage, emit_progress

__all__ = [
    # Types
    "PipelineState",
    "SessionType", "AgentRole", "MessageRole",
    "VideoMetadata", "ChannelMetadata", "AnalyticsMetadata",
    "ChannelStats", "MemoryFact",
    # Config & logging
    "Settings", "get_settings",
    "get_logger", "FileCache",
    # Errors
    "PipelineException",
    "PipelineError", "LLMClientError", "RateLimitError",
    "ZepMemoryError", "IntegrationError", "QualityGateError",
    # Operation results
    "OperationResult", "ErrorSeverity",
    # Error codes
    "ERROR_REGISTRY", "get_error_detail",
    "get_user_friendly_error", "get_error_response",
    # Progress tracking
    "ProgressTracker", "ProgressStage", "emit_progress",
]

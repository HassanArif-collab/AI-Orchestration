"""
error_codes.py — Maps technical exceptions to user-friendly messages and actions.

UX Pattern: Three-Element Error Message Structure (NN/g)
  1. What happened (plain English)  → user_message
  2. Why it happened                 → cause
  3. What to do next (actionable)     → solution

Each error code includes:
  - user_message: Shown directly to users
  - cause: Explanation of why (shown in error detail panel)
  - solution: What the user should do to resolve
  - action_button: Dict with 'text' and 'link' for a call-to-action button
  - severity: For display routing (critical/warning/info/low)
  - icon: Icon identifier for the error display
  - documentation_url: Link to relevant documentation
  - retryable: Whether the system should auto-retry
  - recovery_time_seconds: Estimated time before retry can succeed

Imports: dataclasses, typing
Imported by: packages/core/operation_result.py, apps/api/routers/
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ErrorDetail:
    """Structured error information for UX display."""
    user_message: str
    cause: str = ""
    solution: str = ""
    action_button: dict[str, str] = field(default_factory=dict)  # {"text": "...", "link": "..."}
    severity: str = "info"  # critical, warning, info, low
    icon: str = "info-circle"  # Icon identifier
    documentation_url: str = ""
    retryable: bool = False
    recovery_time_seconds: Optional[int] = None

    # Backward-compatible aliases
    @property
    def suggested_action(self) -> str:
        return self.solution

    @property
    def action_link(self) -> Optional[str]:
        return self.action_button.get("link")


ERROR_REGISTRY: dict[str, ErrorDetail] = {
    # ─── Notion Errors ───
    "NOTION_AUTH_FAILED": ErrorDetail(
        user_message="Could not connect to your Notion workspace.",
        cause="Your Notion API key may be invalid or expired.",
        solution="Go to Settings and verify your Notion API key is correct.",
        action_button={"text": "Open Settings", "link": "/settings"},
        severity="critical",
        icon="shield",
        documentation_url="https://developers.notion.com/docs/authorization",
    ),
    "NOTION_RATE_LIMIT": ErrorDetail(
        user_message="Notion is temporarily rate-limited. Will retry automatically.",
        cause="Too many requests were sent to Notion's API in a short period.",
        solution="No action needed. The system will retry automatically.",
        severity="warning",
        icon="clock",
        recovery_time_seconds=60,
        retryable=True,
        documentation_url="https://developers.notion.com/reference/request-limits",
    ),
    "NOTION_NOT_CONFIGURED": ErrorDetail(
        user_message="Notion is not configured. Publishing features are disabled.",
        cause="No NOTION_API_KEY was found in environment variables.",
        solution="Add your Notion API key in Settings to enable publishing to Notion.",
        action_button={"text": "Configure Notion", "link": "/settings"},
        severity="info",
        icon="settings",
    ),
    "NOTION_NOT_FOUND": ErrorDetail(
        user_message="Could not find the specified page or database in Notion.",
        cause="The Notion database ID may be incorrect or the database was deleted.",
        solution="Check your Notion database ID in Settings.",
        action_button={"text": "Open Settings", "link": "/settings"},
        severity="warning",
        icon="search",
    ),
    "NOTION_CONNECTION_ERROR": ErrorDetail(
        user_message="Could not reach Notion's servers. Your internet connection may be unstable.",
        cause="Network connectivity issue or Notion service outage.",
        solution="Check your internet connection and try again in a moment.",
        severity="warning",
        icon="wifi-off",
        retryable=True,
        recovery_time_seconds=30,
    ),
    "NOTION_PUBLISH_FAILED": ErrorDetail(
        user_message="Failed to save script to Notion after multiple attempts.",
        cause="The operation was attempted 3 times but consistently failed. "
              "The operation has been queued for automatic retry.",
        solution="The operation will be retried automatically. "
                 "You can also check the Failed Operations panel.",
        action_button={"text": "View Failed Ops", "link": "/dlq"},
        severity="critical",
        icon="alert-triangle",
    ),

    # ─── Zep Memory Errors ───
    "ZEP_UNAVAILABLE": ErrorDetail(
        user_message="Memory service is unavailable. Learning features are disabled.",
        cause="Zep Cloud service cannot be reached. The system will produce "
              "lower quality outputs without historical context.",
        solution="The pipeline will continue without memory features. "
                 "Check ZEP_API_KEY in settings.",
        action_button={"text": "Open Settings", "link": "/settings"},
        severity="warning",
        icon="brain",
    ),
    "ZEP_NOT_CONFIGURED": ErrorDetail(
        user_message="Memory service is not configured. Learning features are disabled.",
        cause="No ZEP_API_KEY was found in environment variables.",
        solution="Add your Zep API key in Settings to enable learning features.",
        action_button={"text": "Configure Zep", "link": "/settings"},
        severity="info",
        icon="settings",
    ),
    "ZEP_RATE_LIMIT": ErrorDetail(
        user_message="Memory service is busy. Retrying automatically...",
        cause="Zep API rate limit reached. The system will retry shortly.",
        solution="No action needed. The operation will continue automatically.",
        severity="warning",
        icon="clock",
        recovery_time_seconds=15,
        retryable=True,
    ),

    # ─── LLM / Router Errors ───
    "LLM_UNAVAILABLE": ErrorDetail(
        user_message="AI service is unavailable. Please start FreeRouter or check your configuration.",
        cause="The FreeRouter LLM proxy at localhost:4000 is not responding.",
        solution="Start FreeRouter: open a terminal and run "
                 "'python -m freerouter proxy' in the freerouter directory.",
        action_button={"text": "Open Settings", "link": "/settings"},
        severity="critical",
        icon="cpu",
    ),
    "LLM_RATE_LIMIT": ErrorDetail(
        user_message="AI service is temporarily busy. Retrying automatically...",
        cause="All configured LLM providers are rate-limited. "
              "FreeRouter auto-resets limits after 60 seconds.",
        solution="No action needed. The system will retry when the rate limit resets.",
        severity="warning",
        icon="clock",
        recovery_time_seconds=60,
        retryable=True,
    ),
    "LLM_SERVICE_DOWN": ErrorDetail(
        user_message="AI service is unavailable. Please start FreeRouter or check your configuration.",
        cause="The FreeRouter LLM proxy at localhost:4000 is not responding.",
        solution="Start FreeRouter: open a terminal and run "
                 "'python -m freerouter proxy' in the freerouter directory.",
        action_button={"text": "Open Settings", "link": "/settings"},
        severity="critical",
        icon="cpu",
    ),
    "LLM_ALL_PROVIDERS_FAILED": ErrorDetail(
        user_message="All AI providers failed. The pipeline cannot continue.",
        cause="Every configured LLM provider returned an error. This may be a "
              "configuration issue or widespread provider outage.",
        solution="Check your provider API keys and verify FreeRouter is running.",
        action_button={"text": "Open Settings", "link": "/settings"},
        severity="critical",
        icon="alert-octagon",
    ),
    "LLM_RESPONSE_PARSE_ERROR": ErrorDetail(
        user_message="AI returned an unexpected response format. Retrying with adjusted parameters...",
        cause="The LLM response could not be parsed into the expected structure.",
        solution="The system will retry automatically with modified parameters.",
        severity="warning",
        icon="refresh-cw",
        retryable=True,
    ),

    # ─── Exa Search Errors ───
    "EXA_NOT_CONFIGURED": ErrorDetail(
        user_message="Web search is not configured. Topic discovery will use AI-only mode.",
        cause="No EXA_API_KEY was found in environment variables.",
        solution="Add your Exa API key in Settings to enable web-enhanced topic discovery.",
        action_button={"text": "Configure Exa", "link": "/settings"},
        severity="info",
        icon="search",
    ),
    "EXA_SEARCH_FAILED": ErrorDetail(
        user_message="Web search failed. Falling back to AI-only discovery mode.",
        cause="The Exa search API returned an error or no results.",
        solution="The pipeline will continue with AI-generated topics. You can retry later.",
        severity="info",
        icon="search",
        retryable=True,
    ),
    "EXA_RATE_LIMIT": ErrorDetail(
        user_message="Web search rate limit reached. Slowing down search requests.",
        cause="Too many search requests to Exa. The free tier allows 1000 searches/month.",
        solution="Consider upgrading your Exa plan or reducing topic scan frequency.",
        severity="warning",
        icon="clock",
    ),

    # ─── Pipeline Errors ───
    "PIPELINE_STAGE_FAILED": ErrorDetail(
        user_message="A pipeline stage failed. The pipeline has been paused.",
        cause="An error occurred during pipeline execution. The system has saved "
              "all progress up to the failure point.",
        solution="You can resume the pipeline from where it left off, "
                 "or check the error details for more information.",
        action_button={"text": "View Pipeline", "link": "/pipeline"},
        severity="critical",
        icon="alert-triangle",
        retryable=True,
    ),
    "PIPELINE_QUALITY_FLOOR": ErrorDetail(
        user_message="Script quality is below the minimum threshold after all iterations.",
        cause="The script scored below the quality floor and could not be improved "
              "further within the iteration budget.",
        solution="Try a different topic or adjust your quality settings. "
                 "You can also manually approve the current draft.",
        severity="warning",
        icon="trending-down",
    ),
    "PIPELINE_INVALID_STATE": ErrorDetail(
        user_message="Pipeline is in an unexpected state and cannot proceed.",
        cause="The pipeline run's internal state is inconsistent. "
              "This may happen after a system restart.",
        solution="Try resuming the pipeline. If the issue persists, "
                 "delete the run and start a new one.",
        severity="warning",
        icon="alert-circle",
        retryable=True,
    ),

    # ─── Input Validation Errors ───
    "INPUT_VALIDATION_FAILED": ErrorDetail(
        user_message="The input you provided is not valid.",
        cause="One or more fields failed validation checks.",
        solution="Please review the highlighted fields and correct the errors.",
        severity="low",
        icon="edit",
    ),
    "VALIDATION_TOPIC_TOO_SHORT": ErrorDetail(
        user_message="Please provide a more specific topic (at least 5 characters).",
        cause="The topic field is too short to generate meaningful content.",
        solution="Try a more descriptive topic like "
                 "'How AI is Transforming Healthcare in Pakistan'.",
        severity="low",
        icon="type",
    ),
    "VALIDATION_TOPIC_TOO_LONG": ErrorDetail(
        user_message="Topic is too long. Please keep it under 200 characters.",
        cause="Topics longer than 200 characters can cause issues with content generation.",
        solution="Shorten your topic while keeping the key idea.",
        severity="low",
        icon="type",
    ),
    "VALIDATION_EMPTY_FIELD": ErrorDetail(
        user_message="This field cannot be empty.",
        cause="A required field was left blank.",
        solution="Please fill in this field to continue.",
        severity="low",
        icon="edit",
    ),

    # ─── Dead Letter Queue Errors ───
    "DLQ_RETRY_FAILED": ErrorDetail(
        user_message="An operation failed repeatedly and could not be recovered.",
        cause="A previously failed operation was retried from the Dead Letter Queue "
              "but failed again. It has been moved back to the queue.",
        solution="The operation will be retried again later automatically. "
                 "You can manually retry it from the Failed Operations panel.",
        action_button={"text": "View Failed Ops", "link": "/dlq"},
        severity="warning",
        icon="refresh-cw",
        retryable=True,
        recovery_time_seconds=300,
    ),

    # ─── Circuit Breaker Errors ───
    "CIRCUIT_BREAKER_OPEN": ErrorDetail(
        user_message="A service is temporarily unavailable due to repeated failures.",
        cause="Too many consecutive failures were detected. The circuit breaker "
              "has opened to prevent cascading failures.",
        solution="The service will be automatically retried after a cooldown period. "
                 "No action is needed unless the issue persists.",
        action_button={"text": "View Service Health", "link": "/health"},
        severity="warning",
        icon="zap-off",
        retryable=True,
    ),

    # ─── Supabase Errors ───
    "SUPABASE_CONNECTION_FAILED": ErrorDetail(
        user_message="Database connection failed. Some features may be unavailable.",
        cause="Could not connect to the Supabase database. Check your network and credentials.",
        solution="Verify SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in Settings.",
        action_button={"text": "Open Settings", "link": "/settings"},
        severity="critical",
        icon="database",
    ),
    "SUPABASE_NOT_CONFIGURED": ErrorDetail(
        user_message="Database is not configured. Pipeline storage features are disabled.",
        cause="No Supabase credentials were found.",
        solution="Add your Supabase credentials in Settings to enable full pipeline features.",
        action_button={"text": "Configure Database", "link": "/settings"},
        severity="warning",
        icon="database",
    ),

    # ─── YouTube Errors ───
    "YOUTUBE_AUTH_FAILED": ErrorDetail(
        user_message="Could not connect to YouTube. Check your API credentials.",
        cause="YouTube API key or OAuth credentials are invalid or expired.",
        solution="Update your YouTube credentials in Settings.",
        action_button={"text": "Open Settings", "link": "/settings"},
        severity="critical",
        icon="youtube",
    ),

    # ─── Integration Errors ───
    "INTEGRATION_FAILED": ErrorDetail(
        user_message="An external service call failed.",
        cause="An integration with an external service returned an error.",
        solution="Check the service status and your configuration, then try again.",
        action_button={"text": "Open Settings", "link": "/settings"},
        severity="warning",
        icon="plug",
        retryable=True,
    ),

    # ─── Quality Gate Errors ───
    "QUALITY_GATE_FAILED": ErrorDetail(
        user_message="Content quality check failed.",
        cause="The generated content did not meet the required quality standards.",
        solution="The system will automatically attempt to improve the content. "
                 "You can also adjust quality settings or manually edit the result.",
        severity="warning",
        icon="trending-down",
    ),

    # ─── Unknown ───
    "UNKNOWN_ERROR": ErrorDetail(
        user_message="An unexpected error occurred.",
        cause="An unhandled error was encountered.",
        solution="Try again. If the problem persists, check the logs or contact support.",
        severity="warning",
        icon="alert-circle",
        retryable=True,
    ),
}


def get_error_detail(error_code: str) -> ErrorDetail | None:
    """Look up error details by error code."""
    return ERROR_REGISTRY.get(error_code)


def get_error_response(error_code: str) -> dict:
    """Return the full error info dict for an error code.

    Converts an ErrorDetail dataclass into a plain dict suitable for
    JSON API responses. Returns UNKNOWN_ERROR details if code not found.

    Args:
        error_code: The error code to look up.

    Returns:
        Dict with keys: error_code, user_message, cause, solution,
        action_button, severity, icon, documentation_url, retryable,
        recovery_time_seconds.
    """
    detail = get_error_detail(error_code)
    if detail is None:
        detail = ERROR_REGISTRY["UNKNOWN_ERROR"]
        # Override the error_code in the response to the original code
        # so the caller knows which code was not found
        return {
            "error_code": error_code,
            "user_message": detail.user_message,
            "cause": detail.cause,
            "solution": detail.solution,
            "action_button": detail.action_button,
            "severity": detail.severity,
            "icon": detail.icon,
            "documentation_url": detail.documentation_url,
            "retryable": detail.retryable,
            "recovery_time_seconds": detail.recovery_time_seconds,
        }
    return {
        "error_code": error_code,
        "user_message": detail.user_message,
        "cause": detail.cause,
        "solution": detail.solution,
        "action_button": detail.action_button,
        "severity": detail.severity,
        "icon": detail.icon,
        "documentation_url": detail.documentation_url,
        "retryable": detail.retryable,
        "recovery_time_seconds": detail.recovery_time_seconds,
    }


def get_user_friendly_error(exception: Exception) -> dict:
    """Convert a Python exception to a user-friendly error dict.

    Maps exception types and messages to error codes, then looks up
    the corresponding ErrorDetail. Falls back to a generic message.

    Supports:
    - Custom PipelineException subclasses with .error_code attribute
    - Notion APIResponseError
    - Built-in ConnectionError, TimeoutError

    Args:
        exception: Any Python exception instance.

    Returns:
        Dict with keys: error_code, user_message, cause, solution,
        action_button, severity, icon, documentation_url, retryable,
        recovery_time_seconds, technical_message.
    """
    error_code = _map_exception_to_code(exception)
    return {
        "error_code": error_code,
        **get_error_response(error_code),
        "technical_message": str(exception),
    }


def _map_exception_to_code(exception: Exception) -> str:
    """Map a Python exception to an error code string.

    Priority order:
    1. Instance .error_code attribute (from PipelineException)
    2. Class .error_code attribute (from PipelineException default)
    3. Heuristic mapping by exception name/message patterns
    4. Fallback: UNKNOWN_ERROR
    """
    exc_name = type(exception).__name__
    exc_msg = str(exception).lower()

    # 1. Check if the exception has an error_code attribute (PipelineException)
    if hasattr(exception, "error_code") and getattr(exception, "error_code"):
        code = getattr(exception, "error_code")
        # Validate it exists in registry; if not, fall through to heuristic
        if code in ERROR_REGISTRY:
            return code

    # 2. Import and check custom exception types
    try:
        from packages.core.errors import (
            LLMClientError, RateLimitError, ZepMemoryError,
            PipelineError, IntegrationError, QualityGateError,
        )

        if isinstance(exception, RateLimitError):
            if "zep" in exc_msg:
                return "ZEP_RATE_LIMIT"
            return "LLM_RATE_LIMIT"

        if isinstance(exception, ZepMemoryError):
            if "api_key" in exc_msg or "not configured" in exc_msg:
                return "ZEP_NOT_CONFIGURED"
            return "ZEP_UNAVAILABLE"

        if isinstance(exception, QualityGateError):
            return "QUALITY_GATE_FAILED"

        if isinstance(exception, PipelineError):
            return "PIPELINE_STAGE_FAILED"

        if isinstance(exception, IntegrationError):
            if "notion" in exc_msg:
                return "NOTION_PUBLISH_FAILED"
            if "youtube" in exc_msg:
                return "YOUTUBE_AUTH_FAILED"
            return "INTEGRATION_FAILED"

        if isinstance(exception, LLMClientError):
            if "not running" in exc_msg or "freerouter" in exc_msg:
                return "LLM_UNAVAILABLE"
            return "LLM_SERVICE_DOWN"

    except ImportError:
        pass

    # 3. Map by exception name patterns (Notion SDK)
    if "APIResponseError" in exc_name or "HTTPResponseError" in exc_name:
        if "rate" in exc_msg or "429" in exc_msg:
            return "NOTION_RATE_LIMIT"
        if "auth" in exc_msg or "unauthorized" in exc_msg:
            return "NOTION_AUTH_FAILED"
        if "not_found" in exc_msg or "404" in exc_msg:
            return "NOTION_NOT_FOUND"
        return "NOTION_CONNECTION_ERROR"

    # Map by exception name (built-in)
    if "Connection" in exc_name or "Timeout" in exc_name or "Connect" in exc_name:
        if "notion" in exc_msg:
            return "NOTION_CONNECTION_ERROR"
        return "LLM_UNAVAILABLE"

    # 4. Map by message content
    if "EXA_API_KEY" in exc_msg or "exa" in exc_msg:
        return "EXA_NOT_CONFIGURED"
    if "ZEP_API_KEY" in exc_msg or "zep" in exc_msg:
        return "ZEP_NOT_CONFIGURED"
    if "NOTION_API_KEY" in exc_msg or "notion" in exc_msg:
        return "NOTION_AUTH_FAILED"
    if "circuit" in exc_msg or "breaker" in exc_msg:
        return "CIRCUIT_BREAKER_OPEN"

    return "UNKNOWN_ERROR"

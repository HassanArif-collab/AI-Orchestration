"""
errors.py — Custom exceptions for the YouTube pipeline.

Context: All pipeline packages raise these exceptions.
Callers catch them to decide whether to retry, fallback, or abort.

NAMING RULES ENFORCED HERE:
  - NOT named "RouterError"  → freerouter/router.py already defines RouterError.
    Ours is LLMClientError to avoid silent shadowing.
  - NOT named "MemoryError"  → Python built-in. Ours is ZepMemoryError.

UX Pattern: Error codes on exceptions enable automatic mapping to user-friendly
messages via packages/core/error_codes.py. Each exception carries an error_code
that the frontend can use to display structured error information.

Imports: nothing
Imported by: all packages
"""


class PipelineException(Exception):
    """Base exception for all pipeline errors.

    Provides an error_code attribute that maps to user-friendly messages
    in the error registry (packages/core/error_codes.py).

    Attributes:
        error_code: Machine-readable error code for UX display routing.
    """

    error_code: str = ""

    def __init__(self, message: str = "", *, error_code: str | None = None):
        super().__init__(message)
        if error_code is not None:
            self.error_code = error_code

    def get_error_code(self) -> str:
        """Return the error code for this exception.

        Instance-level error_code takes precedence over class-level default.
        """
        return self.error_code or "UNKNOWN_ERROR"


class PipelineError(PipelineException):
    """A pipeline stage failed. Check PipelineState.error_message for detail."""
    error_code: str = "PIPELINE_STAGE_FAILED"


class LLMClientError(PipelineException):
    """Failed to get a response from FreeRouter proxy at localhost:4000.

    Could mean FreeRouter isn't running or all providers failed.
    Fix: run 'python -m freerouter proxy' in a separate terminal.
    """
    error_code: str = "LLM_UNAVAILABLE"


class RateLimitError(LLMClientError):
    """FreeRouter returned 429 — all configured providers are rate-limited.

    FreeRouter auto-resets limits after 60 seconds. Retry then.
    """
    error_code: str = "LLM_RATE_LIMIT"


class ZepMemoryError(PipelineException):
    """Failed to read or write agent memory in GetZep Cloud.

    Check ZEP_API_KEY in .env and ZEP_BASE_URL.
    """
    error_code: str = "ZEP_UNAVAILABLE"


class IntegrationError(PipelineException):
    """Failed to call an external API (YouTube, Notion).

    The integration name and endpoint should be in the message.
    """
    error_code: str = "INTEGRATION_FAILED"


class QualityGateError(PipelineException):
    """Raised when script quality is below minimum threshold.

    This error indicates that a script failed to meet the minimum
    quality floor after all evolution iterations are exhausted.

    Attributes:
        score: The actual quality score achieved
        floor: The minimum acceptable quality floor
    """
    error_code: str = "QUALITY_GATE_FAILED"

    def __init__(
        self,
        message: str = "",
        score: float | None = None,
        floor: float | None = None,
        *,
        error_code: str | None = None,
    ):
        super().__init__(message, error_code=error_code)
        self.score = score
        self.floor = floor

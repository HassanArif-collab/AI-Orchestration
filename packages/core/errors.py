"""
errors.py — Custom exceptions for the YouTube pipeline.

Context: All pipeline packages raise these exceptions.
Callers catch them to decide whether to retry, fallback, or abort.

NAMING RULES ENFORCED HERE:
  - NOT named "RouterError"  → freerouter/router.py already defines RouterError.
    Ours is LLMClientError to avoid silent shadowing.
  - NOT named "MemoryError"  → Python built-in. Ours is ZepMemoryError.

Imports: nothing
Imported by: all packages
"""


class LLMClientError(Exception):
    """
    Failed to get a response from FreeRouter proxy at localhost:4000.
    Could mean FreeRouter isn't running or all providers failed.
    Fix: run 'python -m freerouter proxy' in a separate terminal.
    """


class RateLimitError(LLMClientError):
    """
    FreeRouter returned 429 — all configured providers are rate-limited.
    FreeRouter auto-resets limits after 60 seconds. Retry then.
    """


class ZepMemoryError(Exception):
    """
    Failed to read or write agent memory in GetZep Cloud.
    Check ZEP_API_KEY in .env and ZEP_BASE_URL.
    """


class PipelineError(Exception):
    """
    A pipeline stage failed. Check PipelineState.error_message for detail.
    """


class IntegrationError(Exception):
    """
    Failed to call an external API (YouTube, Notion).
    The integration name and endpoint should be in the message.
    """


class QualityGateError(Exception):
    """Raised when script quality is below minimum threshold.
    
    This error indicates that a script failed to meet the minimum
    quality floor after all evolution iterations are exhausted.
    
    Attributes:
        score: The actual quality score achieved
        floor: The minimum acceptable quality floor
    """
    
    def __init__(self, message: str, score: float = None, floor: float = None):
        super().__init__(message)
        self.score = score
        self.floor = floor

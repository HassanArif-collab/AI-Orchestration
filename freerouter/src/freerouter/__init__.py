"""
FreeRouter - Smart LLM Proxy that always prefers free models.

A LiteLLM-based proxy that automatically selects the best free model
based on the task type, with intelligent fallbacks and web search support.
"""

__version__ = "1.0.0"
__author__ = "FreeRouter Team"

from freerouter.classifier import TaskClassifier, TaskCategory
from freerouter.config import get_config_path, load_config, validate_environment
from freerouter.websearch import WebSearchInterceptor, SearchProvider
from freerouter.health import ModelHealthChecker, get_health_checker
from freerouter.providers import (
    KNOWN_PROVIDERS, PROVIDER_MAP,
    get_linked_providers, save_api_key,
    update_usage_from_headers, mark_hard_limited,
    should_skip_provider, get_all_usage,
)

__all__ = [
    "TaskClassifier",
    "TaskCategory",
    "get_config_path",
    "load_config",
    "validate_environment",
    "WebSearchInterceptor",
    "SearchProvider",
    "ModelHealthChecker",
    "get_health_checker",
    "KNOWN_PROVIDERS",
    "PROVIDER_MAP",
    "get_linked_providers",
    "save_api_key",
    "update_usage_from_headers",
    "mark_hard_limited",
    "should_skip_provider",
    "get_all_usage",
    "__version__",
]
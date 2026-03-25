"""
Adapters for non-standard API providers.

Some providers don't use OpenAI-compatible APIs. These adapters
convert between OpenAI format and the provider's native format.
"""

from .apifreellm import APIFreeLLMAdapter

__all__ = ["APIFreeLLMAdapter"]

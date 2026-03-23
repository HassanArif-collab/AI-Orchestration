"""
Memory package — Zep Cloud agent memory client.

Handles long-term memory and conversation history for pipeline agents.
Requires ZEP_API_KEY in root .env. Gracefully skips if key is not set.

    from packages.memory import ZepMemoryClient
"""

from packages.memory.client import ZepMemoryClient

__all__ = ["ZepMemoryClient"]

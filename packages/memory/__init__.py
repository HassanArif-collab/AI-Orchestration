"""
Memory package — Zep Cloud agent memory client.

Handles long-term memory and conversation history for pipeline agents.
Requires ZEP_API_KEY in root .env. Gracefully skips if key is not set.

    from packages.memory import AsyncZepMemoryClient
"""

from packages.memory.client import AsyncZepMemoryClient, get_async_zep_client

__all__ = ["AsyncZepMemoryClient", "get_async_zep_client"]

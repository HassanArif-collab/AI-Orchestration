"""
Router package — HTTP client for the FreeRouter LLM proxy.

ALL LLM calls in this project go through this package → FreeRouter at :4000.
FreeRouter then picks the best free provider (Groq → OpenRouter → Ollama).
Never call LLM APIs directly — always use RouterClient here.

    from packages.router import RouterClient
    async with RouterClient() as client:
        text = await client.complete_text("Your prompt")

WEB SEARCH:
    from packages.router import WebSearchClient
    async with WebSearchClient() as client:
        results = await client.search("query")
"""

from packages.router.client import RouterClient
from packages.router.capabilities import get_model_for_capability
from packages.router.tracker import UsageTracker
from packages.router.web_search import WebSearchClient, SearchResult

__all__ = [
    "RouterClient",
    "get_model_for_capability",
    "UsageTracker",
    "WebSearchClient",
    "SearchResult",
]

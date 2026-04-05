"""
router/web_search.py — Web search client using z-ai-web-dev-sdk.

Context: This module provides web search capabilities for the research pipeline.
Uses the z-ai-web-dev-sdk which is already installed in the environment.

FIXES APPLIED:
1. Removed fake URL fallback - returns empty list instead of hallucinated URLs
2. Added rate limiting for parallel searches to prevent API bans

Usage:
    from packages.router.web_search import WebSearchClient

    async with WebSearchClient() as client:
        results = await client.search("Pakistan economy 2026", num_results=10)
        for result in results:
            print(result["title"], result["url"])

Imports: z-ai-web-dev-sdk
Imported by: packages/content_factory/production/deep_research.py
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from packages.core.logger import get_logger

log = get_logger(__name__)


@dataclass
class SearchResult:
    """Single web search result."""
    url: str
    title: str
    snippet: str
    host_name: str
    rank: int
    date: str = ""
    favicon: str = ""

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "title": self.title,
            "snippet": self.snippet,
            "host_name": self.host_name,
            "rank": self.rank,
            "date": self.date,
            "favicon": self.favicon,
        }


class WebSearchClient:
    """
    Async web search client wrapping z-ai-web-dev-sdk.

    Provides structured search results that can be used by the research engine.

    Rate Limiting:
        - Configurable rate limit (default: 2 searches/second)
        - Semaphore-based throttling for parallel searches
        - Automatic delay between searches in multi_search()

    Fallback Behavior:
        - Returns empty list if web search is unavailable
        - Does NOT generate fake URLs (removed hallucination fallback)
    """

    def __init__(
        self,
        rate_limit_per_second: float = 2.0,
    ) -> None:
        """
        Initialize the web search client.

        Args:
            rate_limit_per_second: Maximum searches per second (default: 2.0)
        """
        self._zai = None
        self._rate_limit_per_second = rate_limit_per_second
        self._semaphore = asyncio.Semaphore(int(rate_limit_per_second * 2))
        self._last_search_time: float = 0.0
        self._min_interval = 1.0 / rate_limit_per_second if rate_limit_per_second > 0 else 0

    async def __aenter__(self) -> "WebSearchClient":
        await self._init_client()
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass

    async def _init_client(self) -> None:
        """Initialize the z-ai-web-dev-sdk client."""
        try:
            # Lazy import to avoid errors if SDK not installed.
            # Use importlib because the package name contains hyphens
            # which __import__ handles unreliably across Python versions.
            import importlib
            sdk = importlib.import_module("z-ai-web-dev-sdk")
            self._zai = await sdk.ZAI.create()
            log.debug("web_search_client_initialized")
        except Exception as e:
            log.warning(f"web_search_sdk_init_failed: {e}")
            self._zai = None

    async def _acquire_rate_limit(self) -> None:
        """Wait until rate limit allows next search."""
        async with self._semaphore:
            now = time.time()
            elapsed = now - self._last_search_time
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_search_time = time.time()

    async def search(
        self,
        query: str,
        num_results: int = 10,
    ) -> list[SearchResult]:
        """
        Perform a web search and return structured results.

        Args:
            query: The search query string
            num_results: Maximum number of results to return

        Returns:
            List of SearchResult objects (empty list if search unavailable)
        """
        # Apply rate limiting
        await self._acquire_rate_limit()

        if self._zai is None:
            log.warning(f"web_search_unavailable_returning_empty: query='{query[:50]}'")
            return []

        try:
            # Use z-ai-web-dev-sdk web_search function
            raw_results = await self._zai.functions.invoke(
                "web_search",
                query=query,
                num=num_results,
            )

            results = []
            if isinstance(raw_results, list):
                for i, item in enumerate(raw_results):
                    if isinstance(item, dict):
                        results.append(SearchResult(
                            url=item.get("url", ""),
                            title=item.get("name", item.get("title", "")),
                            snippet=item.get("snippet", ""),
                            host_name=item.get("host_name", ""),
                            rank=item.get("rank", i + 1),
                            date=item.get("date", ""),
                            favicon=item.get("favicon", ""),
                        ))

            log.info(f"web_search_complete: query='{query[:50]}...' results={len(results)}")
            return results

        except Exception as e:
            log.error(f"web_search_failed: {e}")
            return []

    async def multi_search(
        self,
        queries: list[str],
        num_per_query: int = 5,
        delay_between: float = 0.5,
    ) -> dict[str, list[SearchResult]]:
        """
        Perform multiple searches with rate limiting.

        Searches are executed sequentially with configurable delays
        to prevent rate limit bans from the search provider.

        Args:
            queries: List of search queries
            num_per_query: Results per query
            delay_between: Delay in seconds between searches (default: 0.5s)

        Returns:
            Dict mapping query -> list of results
        """
        output: dict[str, list[SearchResult]] = {}

        for i, query in enumerate(queries):
            # Add delay between searches (not before first one)
            if i > 0 and delay_between > 0:
                await asyncio.sleep(delay_between)

            try:
                results = await self.search(query, num_per_query)
                output[query] = results
            except Exception as e:
                log.warning(f"multi_search_query_failed: {query} -> {e}")
                output[query] = []

        return output

    async def multi_search_parallel(
        self,
        queries: list[str],
        num_per_query: int = 5,
    ) -> dict[str, list[SearchResult]]:
        """
        Perform multiple searches in parallel with rate limiting.

        Uses semaphore-based rate limiting to allow controlled parallelism.

        Args:
            queries: List of search queries
            num_per_query: Results per query

        Returns:
            Dict mapping query -> list of results
        """
        tasks = [self.search(q, num_per_query) for q in queries]
        results_lists = await asyncio.gather(*tasks, return_exceptions=True)

        output = {}
        for query, results in zip(queries, results_lists):
            if isinstance(results, Exception):
                log.warning(f"multi_search_query_failed: {query} -> {results}")
                output[query] = []
            else:
                output[query] = results

        return output

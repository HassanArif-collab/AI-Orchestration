"""
router/web_search.py — Web search client using Exa.ai.

Context: This module provides web search capabilities for the research pipeline.
Uses Exa.ai (exa_py) — a proper Python package that returns semantic search
results with actual article text content.

PREVIOUS BUG: z-ai-web-dev-sdk is a Node.js/Bun package — it CANNOT be imported
in Python. All searches silently failed and returned empty results, causing the
entire research pipeline to produce lifeless scripts with no real data.

FIX: Replaced with Exa.ai (exa_py) which is a native Python package already
used in the discovery pipeline and proven to work.

Rate Limits:
    Exa free tier: 1000 searches/month
    Rate limited to ~2 searches/second to avoid API bans

Usage:
    from packages.router.web_search import WebSearchClient

    async with WebSearchClient() as client:
        results = await client.search("Pakistan economy 2026", num_results=10)
        for result in results:
            print(result.title, result.url)

Imports: exa_py, packages.core
Imported by: packages/content_factory/production/deep_research.py
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional
from urllib.parse import urlparse

from packages.core.config import get_settings
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
    Async web search client using Exa.ai (exa_py).

    Provides structured search results with actual article content
    that can be used by the research engine.

    Uses Exa's `search_and_contents` with `text=True` to get actual
    article text (not just meta descriptions), which gives the
    DeepResearchEngine real data to extract facts from.

    Rate Limiting:
        - Configurable rate limit (default: 2 searches/second)
        - Semaphore-based throttling for parallel searches
        - Automatic delay between searches in multi_search()

    Fallback Behavior:
        - Returns empty list if Exa is unavailable
        - Does NOT generate fake URLs (no hallucination fallback)
    """

    def __init__(
        self,
        rate_limit_per_second: float = 2.0,
        days_back: int = 30,
        text_length: int = 1000,
    ) -> None:
        """
        Initialize the web search client.

        Args:
            rate_limit_per_second: Maximum searches per second (default: 2.0)
            days_back: Only include content from last N days (default: 30)
            text_length: Max characters of article text per result (default: 1000)
        """
        self._exa_client = None
        self._rate_limit_per_second = rate_limit_per_second
        self._days_back = days_back
        self._text_length = text_length
        self._semaphore = asyncio.Semaphore(int(rate_limit_per_second * 2))
        self._last_search_time: float = 0.0
        self._min_interval = 1.0 / rate_limit_per_second if rate_limit_per_second > 0 else 0

    async def __aenter__(self) -> "WebSearchClient":
        self._init_client()
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass

    def _init_client(self) -> None:
        """Initialize the Exa client."""
        try:
            from exa_py import Exa
            settings = get_settings()
            api_key = settings.EXA_API_KEY
            if not api_key:
                log.warning("exa_web_search_not_configured: EXA_API_KEY is not set")
                self._exa_client = None
                return
            self._exa_client = Exa(api_key=api_key)
            log.debug("exa_web_search_client_initialized")
        except ImportError:
            log.warning("exa_py_not_installed: pip install exa_py")
            self._exa_client = None
        except Exception as e:
            log.warning(f"exa_web_search_init_failed: {e}")
            self._exa_client = None

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
        Perform a web search and return structured results with article text.

        Args:
            query: The search query string
            num_results: Maximum number of results to return

        Returns:
            List of SearchResult objects (empty list if search unavailable)
        """
        # Apply rate limiting
        await self._acquire_rate_limit()

        if self._exa_client is None:
            log.warning(f"exa_web_search_unavailable_returning_empty: query='{query[:50]}'")
            return []

        try:
            start_date = (datetime.now() - timedelta(days=self._days_back)).strftime("%Y-%m-%d")

            # Use Exa's search_and_contents with text=True to get actual article content
            response = self._exa_client.search_and_contents(
                query=query,
                type="neural",
                num_results=min(num_results, 10),
                text={"max_characters": self._text_length},
                start_published_date=start_date,
            )

            results = []
            for i, item in enumerate(response.results):
                # Extract full article text (not just meta description)
                text = (item.text or "").strip()
                if not text:
                    text = (item.highlight or "").strip()

                # Extract host from URL
                host = ""
                try:
                    host = urlparse(item.url or "").netloc or ""
                except Exception:
                    pass

                # Extract published date
                date = ""
                try:
                    if hasattr(item, "published_date") and item.published_date:
                        date = str(item.published_date)
                except Exception:
                    pass

                if text:  # Only include results that have actual content
                    results.append(SearchResult(
                        url=item.url or "",
                        title=item.title or "Untitled",
                        snippet=text,
                        host_name=host,
                        rank=item.rank if hasattr(item, "rank") else i + 1,
                        date=date,
                    ))

            log.info(f"exa_web_search_complete: query='{query[:50]}...' results={len(results)}")
            return results

        except Exception as e:
            log.error(f"exa_web_search_failed: {e}")
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
        to prevent rate limit bans from Exa.

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
                log.warning(f"exa_multi_search_query_failed: {query} -> {e}")
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
                log.warning(f"exa_multi_search_query_failed: {query} -> {results}")
                output[query] = []
            else:
                output[query] = results

        return output

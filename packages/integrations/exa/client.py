"""Exa.ai semantic search client for topic discovery.

Exa.ai is an AI-native search engine that returns semantically relevant
web results. It replaces the deleted MiroFish integration as the
TopicFinderAgent's source of real-world trending signals.

Usage:
    from packages.integrations.exa.client import ExaResearchClient

    client = ExaResearchClient()
    results = client.search_trending("Pakistan AI regulation", num_results=5)
    # results is a list of dicts: [{"title": ..., "url": ..., "snippet": ..., "date": ...}]

    context_str = client.build_discovery_context("Pakistan economic crisis")
    # context_str is a formatted string ready to inject into an LLM prompt

Rate Limits:
    Exa free tier: 1000 searches/month
    Each call to search_trending uses 1 search
    build_discovery_context uses 3 searches (different query angles)
"""

from typing import Optional
from packages.core.config import get_settings
from packages.core.logger import get_logger

logger = get_logger(__name__)


class ExaResearchClient:
    """Semantic web search client using Exa.ai.

    Provides methods for discovering trending Pakistani topics
    by searching across news, social media, and web content.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.EXA_API_KEY
        self._client = None

    def _get_client(self):
        """Lazy-initialize the Exa client."""
        if self._client is None:
            if not self._api_key:
                raise RuntimeError(
                    "EXA_API_KEY is not set. Add it to your .env file. "
                    "Get a free key from https://dashboard.exa.ai/api-keys"
                )
            from exa_py import Exa
            self._client = Exa(api_key=self._api_key)
        return self._client

    def search_trending(
        self,
        query: str,
        num_results: int = 5,
        days_back: int = 7,
    ) -> list[dict]:
        """Search for recent web content matching query.

        Args:
            query: Natural language search query
            num_results: Max results to return (1-10)
            days_back: Only include content from last N days

        Returns:
            List of dicts with keys: title, url, snippet, published_date
            Returns empty list on any failure (never crashes pipeline)
        """
        try:
            from datetime import datetime, timedelta
            start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

            client = self._get_client()
            response = client.search_and_contents(
                query=query,
                type="neural",
                num_results=min(num_results, 10),
                text=True,
                start_published_date=start_date,
            )

            results = []
            for item in response.results:
                # Truncate text to first 500 chars for context efficiency
                snippet = (item.text or "")[:500].strip()
                if snippet:
                    results.append({
                        "title": item.title or "Untitled",
                        "url": item.url or "",
                        "snippet": snippet,
                        "published_date": getattr(item, "published_date", None),
                    })

            logger.info(f"exa_search_completed: query='{query[:50]}', results={len(results)}")
            return results

        except Exception as e:
            logger.warning(f"exa_search_failed_non_blocking: {e}")
            return []

    def build_discovery_context(
        self,
        seed_query: str,
        card_id: Optional[str] = None,
    ) -> tuple[str, list[dict]]:
        """Run multiple Exa searches from different angles and combine results.

        Searches three angles:
        1. Direct topic search (news/articles)
        2. Pakistani public frustration search (social sentiment)
        3. Economic/policy impact search (data-driven)

        Args:
            seed_query: Base topic from user
            card_id: Optional Kanban card ID for thought reporting

        Returns:
            Tuple of (formatted_context_string, all_raw_results)
            The context string is ready to inject into an LLM prompt.
            Returns ("", []) if all searches fail.
        """
        from packages.core.thoughts import report_thought

        # Define three search angles for comprehensive coverage
        search_queries = [
            f"{seed_query} Pakistan news analysis 2024",
            f"Pakistani public frustration about {seed_query}",
            f"{seed_query} economic impact Pakistan policy data",
        ]

        all_results = []
        for i, query in enumerate(search_queries, 1):
            if card_id:
                report_thought(
                    card_id=card_id,
                    agent_name="topic_finder",
                    thought_type="search",
                    content=f"🔍 Exa search [{i}/3]: \"{query[:60]}\"...",
                )

            results = self.search_trending(query, num_results=5, days_back=14)

            if card_id and results:
                titles = [r["title"][:50] for r in results[:3]]
                report_thought(
                    card_id=card_id,
                    agent_name="topic_finder",
                    thought_type="search",
                    content=f"Found {len(results)} results. Top: {', '.join(titles)}",
                )

            all_results.extend(results)

        if not all_results:
            if card_id:
                report_thought(
                    card_id=card_id,
                    agent_name="topic_finder",
                    thought_type="error",
                    content="⚠️ Exa returned no results. Falling back to LLM-only discovery.",
                )
            return "", []

        # Deduplicate by URL
        seen_urls = set()
        unique_results = []
        for r in all_results:
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                unique_results.append(r)

        # Format into prompt-injectable context
        context_parts = ["REAL-TIME WEB INTELLIGENCE (from Exa.ai search):"]
        for i, r in enumerate(unique_results[:10], 1):  # Cap at 10 to save tokens
            date_str = f" ({r['published_date']})" if r.get("published_date") else ""
            context_parts.append(
                f"\n[Source {i}] {r['title']}{date_str}\n"
                f"URL: {r['url']}\n"
                f"Key Info: {r['snippet'][:300]}"
            )

        context_str = "\n".join(context_parts)

        if card_id:
            report_thought(
                card_id=card_id,
                agent_name="topic_finder",
                thought_type="output",
                content=f"✅ Exa discovery complete: {len(unique_results)} unique sources compiled into research context.",
            )

        return context_str, unique_results

"""
Web search interception and execution for FreeRouter.

Intercepts tool calls for web search and executes them,
injecting results back into the conversation.
"""

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any, Optional
from enum import Enum

import logging
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class SearchProvider(str, Enum):
    """Available search providers."""
    DUCKDUCKGO = "duckduckgo"
    SEARXNG = "searxng"
    CUSTOM = "custom"


@dataclass
class SearchResult:
    """A single search result."""
    title: str
    url: str
    snippet: str
    source: str = "web"


@dataclass
class WebSearchResponse:
    """Response from a web search."""
    query: str
    results: list[SearchResult]
    error: Optional[str] = None


# Tool definitions for common search patterns
SEARCH_TOOL_DEFINITIONS = {
    "web_search": {
        "name": "web_search",
        "description": "Search the web for information",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to return",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    },
    "search": {
        "name": "search",
        "description": "Search for information",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "q": {"type": "string"}
            },
            "required": []
        }
    },
    "google_search": {
        "name": "google_search",
        "description": "Search Google for information",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"}
            },
            "required": ["query"]
        }
    },
    "browser_search": {
        "name": "browser_search",
        "description": "Search the web using browser",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"}
            },
            "required": ["query"]
        }
    }
}


class WebSearchInterceptor:
    """Intercepts and executes web search tool calls."""

    def __init__(
        self,
        provider: SearchProvider = SearchProvider.DUCKDUCKGO,
        searxng_url: Optional[str] = None,
        custom_search_url: Optional[str] = None,
        custom_api_key: Optional[str] = None,
        enabled: bool = True,
        max_results: int = 5,
    ):
        """Initialize the web search interceptor.

        Args:
            provider: Search provider to use
            searxng_url: URL for SearXNG instance (if using SearXNG)
            custom_search_url: Custom search API URL
            custom_api_key: API key for custom search
            enabled: Whether web search is enabled
            max_results: Maximum results to return
        """
        self.provider = provider
        self.searxng_url = searxng_url
        self.custom_search_url = custom_search_url
        self.custom_api_key = custom_api_key
        self.enabled = enabled
        self.max_results = max_results

    def is_search_tool(self, tool_call: dict) -> bool:
        """Check if a tool call is a web search.

        Args:
            tool_call: The tool call to check

        Returns:
            True if this is a web search tool call
        """
        tool_name = tool_call.get("function", {}).get("name", "")
        return tool_name in SEARCH_TOOL_DEFINITIONS

    def extract_search_query(self, tool_call: dict) -> Optional[str]:
        """Extract search query from tool call.

        Args:
            tool_call: The tool call to extract from

        Returns:
            The search query or None if not found
        """
        try:
            args = json.loads(tool_call.get("function", {}).get("arguments", "{}"))
            # Try common parameter names
            for key in ["query", "q", "search_query", "search"]:
                if key in args and args[key]:
                    return args[key]
        except json.JSONDecodeError:
            pass
        return None

    async def execute_search(self, query: str, num_results: Optional[int] = None) -> WebSearchResponse:
        """Execute a web search.

        Args:
            query: The search query
            num_results: Number of results (default: self.max_results)

        Returns:
            WebSearchResponse with results
        """
        if not self.enabled:
            return WebSearchResponse(
                query=query,
                results=[],
                error="Web search is disabled"
            )

        if not query or not query.strip():
            return WebSearchResponse(query=query, results=[], error="Empty search query")

        num_results = num_results or self.max_results

        if self.provider == SearchProvider.DUCKDUCKGO:
            return await self._search_duckduckgo(query, num_results)
        elif self.provider == SearchProvider.SEARXNG:
            return await self._search_searxng(query, num_results)
        elif self.provider == SearchProvider.CUSTOM:
            return await self._search_custom(query, num_results)

        return WebSearchResponse(query=query, results=[], error="Unknown provider")

    async def _search_duckduckgo(self, query: str, num_results: int) -> WebSearchResponse:
        """Search using DuckDuckGo with BeautifulSoup parsing.

        Args:
            query: Search query
            num_results: Number of results

        Returns:
            WebSearchResponse
        """
        results = []
        error = None

        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                    headers={
                        "User-Agent": "Mozilla/5.0 (compatible; FreeRouter/1.0)"
                    }
                )

                if response.status_code == 200:
                    results = self._parse_duckduckgo_html(response.text, num_results)
                else:
                    error = f"Search failed with status {response.status_code}"

        except httpx.TimeoutException:
            error = "Search timed out"
        except Exception as e:
            error = str(e)

        return WebSearchResponse(query=query, results=results, error=error)

    def _parse_duckduckgo_html(self, html: str, max_results: int) -> list[SearchResult]:
        """Parse DuckDuckGo HTML response using BeautifulSoup.

        Args:
            html: HTML response
            max_results: Maximum results to extract

        Returns:
            List of SearchResult
        """
        results = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            
            # DuckDuckGo result blocks - try multiple possible selectors
            # The 'result' class is the classic one for the HTML version
            result_divs = soup.find_all("div", class_="result")
            if not result_divs:
                # Alternative selectors if "result" class changes or for different versions
                result_divs = soup.find_all("div", class_="links_main") or \
                              soup.find_all("div", class_="web-result") or \
                              soup.find_all("article", class_="result") or \
                              soup.select(".results .result")
            
            for div in result_divs[:max_results]:
                # Extract title and URL - try multiple classes
                title_elem = div.find("a", class_="result__a") or \
                             div.find("a", class_="result__title") or \
                             div.find("a", class_="result_title") or \
                             (div.find("h2").find("a") if div.find("h2") else None)
                
                if not title_elem:
                    continue
                    
                title = title_elem.get_text(strip=True)
                url = title_elem.get("href", "")
                
                # Handle DuckDuckGo redirect URLs (they often look like /l/?kh=-1&uddg=...)
                if url.startswith("/l/?"):
                    from urllib.parse import urlparse, parse_qs
                    params = parse_qs(urlparse(url).query)
                    if "uddg" in params:
                        url = params["uddg"][0]
                elif url.startswith("//"):
                    url = "https:" + url
                elif url.startswith("/"):
                    url = "https://duckduckgo.com" + url
                
                # Extract snippet - try multiple classes
                snippet_elem = div.find("a", class_="result__snippet") or \
                               div.find("div", class_="result__snippet") or \
                               div.find("div", class_="snippet") or \
                               div.find("p") or \
                               div.find("div", class_="result__body")
                
                snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                
                # Basic cleaning
                if url and title:
                    results.append(SearchResult(
                        title=title, 
                        url=url, 
                        snippet=snippet,
                        source="duckduckgo"
                    ))
            
            if not results:
                logger.warning("No search results found - DuckDuckGo layout might have changed.")
                
        except Exception as e:
            logger.error(f"Error parsing DuckDuckGo HTML: {e}")

        return results

    async def _search_searxng(self, query: str, num_results: int) -> WebSearchResponse:
        """Search using SearXNG instance.

        Args:
            query: Search query
            num_results: Number of results

        Returns:
            WebSearchResponse
        """
        results = []
        error = None

        if not self.searxng_url:
            return WebSearchResponse(query=query, results=[], error="SearXNG URL not configured")

        try:
            base_url = self.searxng_url.rstrip('/') if self.searxng_url else ""
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{base_url}/search",
                    params={
                        "q": query,
                        "format": "json",
                        "engines": "google,bing,duckduckgo"
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    for result in data.get("results", [])[:num_results]:
                        results.append(SearchResult(
                            title=result.get("title", ""),
                            url=result.get("url", ""),
                            snippet=result.get("content", ""),
                            source="searxng"
                        ))
                else:
                    error = f"Search failed with status {response.status_code}"

        except httpx.TimeoutException:
            error = "Search timed out"
        except Exception as e:
            error = str(e)

        return WebSearchResponse(query=query, results=results, error=error)

    async def _search_custom(self, query: str, num_results: int) -> WebSearchResponse:
        """Search using custom API.

        Args:
            query: Search query
            num_results: Number of results

        Returns:
            WebSearchResponse
        """
        if not self.custom_search_url:
            return WebSearchResponse(query=query, results=[], error="Custom search URL not configured")

        results = []
        error = None

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                headers = {}
                if self.custom_api_key:
                    headers["Authorization"] = f"Bearer {self.custom_api_key}"

                response = await client.get(
                    self.custom_search_url,
                    params={"q": query, "num": num_results},
                    headers=headers
                )

                if response.status_code == 200:
                    # Assume standard JSON format
                    data = response.json()
                    for item in data.get("results", data.get("items", []))[:num_results]:
                        results.append(SearchResult(
                            title=item.get("title", ""),
                            url=item.get("url", item.get("link", "")),
                            snippet=item.get("snippet", item.get("description", "")),
                            source="custom"
                        ))
                else:
                    error = f"Search failed with status {response.status_code}"

        except httpx.TimeoutException:
            error = "Search timed out"
        except Exception as e:
            error = str(e)

        return WebSearchResponse(query=query, results=results, error=error)

    def format_results_as_message(self, response: WebSearchResponse) -> str:
        """Format search results as a message to inject into conversation.

        Args:
            response: The search response

        Returns:
            Formatted message string
        """
        if response.error:
            return f"Web search error: {response.error}"

        if not response.results:
            return f"No results found for: {response.query}"

        lines = [f"Web search results for '{response.query}':\n"]

        for i, result in enumerate(response.results, 1):
            lines.append(f"{i}. **{result.title}**")
            lines.append(f"   URL: {result.url}")
            lines.append(f"   {result.snippet}")
            lines.append("")

        return "\n".join(lines)

    def create_tool_result(self, tool_call_id: str, response: WebSearchResponse) -> dict:
        """Create a tool result message.

        Args:
            tool_call_id: The ID of the tool call
            response: The search response

        Returns:
            Tool result message dict
        """
        content = self.format_results_as_message(response)

        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content
        }


def check_for_web_search_intent(content: str) -> bool:
    """Check if content suggests web search intent.

    Args:
        content: The content to check

    Returns:
        True if web search seems needed
    """
    patterns = [
        r"\b(what is|who is|when did|where is|how to|why did)\b.*\?",
        r"\b(latest|recent|current|news|today)\b",
        r"\b(search|google|look up|find information)\b",
        r"\b(what's new|what happened|recent developments)\b",
    ]

    content_lower = content.lower()
    matches = sum(1 for pattern in patterns if re.search(pattern, content_lower))

    return matches >= 1
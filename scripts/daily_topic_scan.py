#!/usr/bin/env python3
"""
scripts/daily_topic_scan.py — Daily Topic Discovery Scanner

This script runs automatically (via cron or scheduler) to:
1. Scan trending sources (YouTube, Google)
2. Score topic viability (17 criteria)
3. Store Tier 1 topics in the Topic Reservoir
4. Notify the dashboard of new topics

Usage:
    # Run daily scan
    python scripts/daily_topic_scan.py

    # Run with specific genres
    python scripts/daily_topic_scan.py --genres current_situation,history,economics

Cron Example:
    # Run every day at 9 AM
    0 9 * * * cd /path/to/AI-Orchestration && python scripts/daily_topic_scan.py
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from packages.core.config import get_settings
from packages.core.logger import get_logger

log = get_logger(__name__)


# ─── Trend Analysis ─────────────────────────────────────────────────────────────

class TrendScanner:
    """
    Scans multiple sources for trending topics in Pakistan.
    """
    
    def __init__(self):
        self.youtube_api_key = get_settings().YOUTUBE_API_KEY
    
    async def scan_youtube_trends(self, region: str = "PK") -> list[dict]:
        """
        Fetch trending videos from YouTube Data API v3.
        
        Args:
            region: Region code (default: PK for Pakistan)
            
        Returns:
            List of trending video data
        """
        if not self.youtube_api_key:
            log.warning("youtube_api_key_not_configured: skipping YouTube trends")
            return []
        
        try:
            from googleapiclient.discovery import build
            
            youtube = build('youtube', 'v3', developerKey=self.youtube_api_key)
            
            # Get most popular videos
            request = youtube.videos().list(
                part="snippet,statistics",
                chart="mostPopular",
                regionCode=region,
                maxResults=50
            )
            response = request.execute()
            
            trends = []
            for item in response.get("items", []):
                snippet = item.get("snippet", {})
                stats = item.get("statistics", {})
                
                trends.append({
                    "title": snippet.get("title", ""),
                    "description": snippet.get("description", ""),
                    "category_id": snippet.get("categoryId", ""),
                    "views": int(stats.get("viewCount", 0)),
                    "likes": int(stats.get("likeCount", 0)),
                    "source": "youtube_trending",
                    "source_url": f"https://youtube.com/watch?v={item.get('id', '')}",
                    "scanned_at": datetime.now(timezone.utc).isoformat()
                })
            
            log.info(f"youtube_trends_fetched: {len(trends)} videos")
            return trends
            
        except Exception as e:
            log.error(f"youtube_trends_error: {e}")
            return []
    
    async def scan_google_trends(self, queries: list[str] = None) -> list[dict]:
        """
        Search Google for trending topics in Pakistan.
        
        Uses web search to find what's trending.
        
        Args:
            queries: List of search queries
            
        Returns:
            List of trending topics
        """
        from packages.router.web_search import WebSearchClient
        
        if not queries:
            queries = [
                "what is trending in Pakistan today 2025",
                "Pakistan trending topics",
                "Pakistan viral news",
                "Pakistan hot topics this week"
            ]
        
        trends = []
        
        async with WebSearchClient() as client:
            for query in queries:
                try:
                    results = await client.search(query, num_results=10)
                    
                    for result in results:
                        trends.append({
                            "title": result.get("name", ""),
                            "description": result.get("snippet", ""),
                            "source": "google_search",
                            "source_url": result.get("url", ""),
                            "query": query,
                            "scanned_at": datetime.now(timezone.utc).isoformat()
                        })
                    
                    log.info(f"google_trends_fetched: {len(results)} results for '{query}'")
                    
                except Exception as e:
                    log.warning(f"google_trends_query_failed: {query} - {e}")
        
        return trends
    
    async def aggregate_trends(self) -> list[dict]:
        """
        Aggregate trends from all sources.
        
        Returns:
            Combined and deduplicated trends
        """
        all_trends = []
        
        # YouTube trends (higher priority)
        yt_trends = await self.scan_youtube_trends()
        all_trends.extend(yt_trends)
        
        # Google trends (supplementary)
        google_trends = await self.scan_google_trends()
        all_trends.extend(google_trends)
        
        # Deduplicate by title similarity
        unique_trends = self._deduplicate_trends(all_trends)
        
        log.info(f"trends_aggregated: {len(unique_trends)} unique topics")
        return unique_trends
    
    def _deduplicate_trends(self, trends: list[dict]) -> list[dict]:
        """Remove duplicate trends based on title similarity."""
        seen_titles = set()
        unique = []
        
        for trend in trends:
            title = trend.get("title", "").lower().strip()
            
            # Skip if we've seen a similar title
            if title in seen_titles:
                continue
            
            # Skip very short titles
            if len(title) < 10:
                continue
            
            seen_titles.add(title)
            unique.append(trend)
        
        return unique


# ─── Topic Viability Scoring ───────────────────────────────────────────────────

VIABILITY_QUESTIONS = {
    # The Gap Test (Must pass all)
    "gap_1": "Does the topic have a clear 'mainstream assumption' that is factually incomplete or wrong?",
    "gap_2": "Can this gap be explained primarily through visual evidence?",
    "gap_3": "Is the hidden mechanism or hidden connection structurally simple enough to explain?",
    
    # The Anchor Test (Must pass 2+)
    "anchor_1": "Is there a specific, physical object or location that embodies this entire topic?",
    "anchor_2": "Is there a compelling human character whose immediate experience grounds the concept?",
    "anchor_3": "Is there a specific 'smoking gun' document, map, or chart that is visually striking?",
    "anchor_4": "Can we show the before/after or cause/effect entirely through visual contrast?",
    
    # The Audience Test (Must pass 2+)
    "audience_1": "Does this topic intersect directly with the daily economic or social reality of Pakistanis?",
    "audience_2": "Does this challenge a deeply held cultural narrative or historical assumption?",
    "audience_3": "Does this explain 'why things are the way they are' regarding a universal frustration?",
    "audience_4": "Is the initial 'hook' visually recognizable within 3 seconds to a layperson?",
    
    # The Production Test
    "prod_1": "Are the primary visual assets accessible without complex licensing?",
    "prod_2": "Can the emotional arc transition cleanly without reliance on interviews?",
    "prod_3": "Is the topic immune to immediate news-cycle irrelevance?",
    
    # The Timing Test
    "timing_1": "Is there a current behavioral macro-trend that makes audiences uniquely receptive?",
    "timing_2": "Does this avoid overlapping too closely with recently produced content?",
    "timing_3": "Is the subject matter emotionally resonant without violating platform safety constraints?"
}


class TopicScorer:
    """
    Scores topics against the 17 viability criteria.
    """
    
    def __init__(self, router_client=None):
        self.router = router_client
    
    async def score_topic(self, topic: dict, genre_id: str) -> Optional[dict]:
        """
        Score a topic against viability criteria.
        
        Returns scored topic or None if it fails basic checks.
        """
        from packages.router.client import RouterClient
        
        title = topic.get("title", "")
        description = topic.get("description", "")
        
        if len(title) < 15:
            return None
        
        # Build prompt for scoring
        prompt = f"""Analyze this potential video topic for a Johnny Harris-style investigative documentary targeting Pakistani audience.

Topic: {title}
Context: {description[:500]}

Evaluate against these 17 viability criteria. For each criterion, answer YES or NO.

QUESTIONS:
{json.dumps(VIABILITY_QUESTIONS, indent=2)}

Respond in JSON format:
{{
    "gap_1": true/false,
    "gap_2": true/false,
    "gap_3": true/false,
    "anchor_1": true/false,
    "anchor_2": true/false,
    "anchor_3": true/false,
    "anchor_4": true/false,
    "audience_1": true/false,
    "audience_2": true/false,
    "audience_3": true/false,
    "audience_4": true/false,
    "prod_1": true/false,
    "prod_2": true/false,
    "prod_3": true/false,
    "timing_1": true/false,
    "timing_2": true/false,
    "timing_3": true/false,
    "topic_statement": "One sentence summary of what this video would be about",
    "big_question": "The central question this video would answer",
    "gap_type": "Hidden Mechanism" | "Oversimplified Narrative" | "Hidden Connection",
    "mainstream_assumption": "What people incorrectly believe",
    "local_relevance": "Why this matters to Pakistani audience"
}}
"""
        
        try:
            async with RouterClient() as router:
                response = await router.complete_text(
                    prompt,
                    system="You are a topic viability analyst. Output only valid JSON.",
                    max_tokens=1000
                )
                
                # Parse JSON response
                import re
                match = re.search(r'\{.*\}', response, re.DOTALL)
                if not match:
                    return None
                
                scores = json.loads(match.group(0))
                
                # Calculate pass rates
                gap_pass = all(scores.get(k, False) for k in ["gap_1", "gap_2", "gap_3"])
                anchor_count = sum(1 for k in ["anchor_1", "anchor_2", "anchor_3", "anchor_4"] if scores.get(k, False))
                audience_count = sum(1 for k in ["audience_1", "audience_2", "audience_3", "audience_4"] if scores.get(k, False))
                
                # Determine tier
                is_tier_1 = gap_pass and anchor_count >= 2 and audience_count >= 2
                
                return {
                    "title": title,
                    "source": topic.get("source", ""),
                    "source_url": topic.get("source_url", ""),
                    "scores": scores,
                    "gap_pass": gap_pass,
                    "anchor_count": anchor_count,
                    "audience_count": audience_count,
                    "is_tier_1": is_tier_1,
                    "topic_statement": scores.get("topic_statement", title),
                    "big_question": scores.get("big_question", ""),
                    "gap_type": scores.get("gap_type", ""),
                    "mainstream_assumption": scores.get("mainstream_assumption", ""),
                    "local_relevance": scores.get("local_relevance", ""),
                    "genre_id": genre_id,
                    "scanned_at": datetime.now(timezone.utc).isoformat()
                }
                
        except Exception as e:
            log.warning(f"topic_scoring_failed: {title[:30]}... - {e}")
            return None


# ─── Topic Reservoir Storage ────────────────────────────────────────────────────

class TopicReservoir:
    """
    Simple file-based storage for topic reservoir.
    Could be upgraded to SQLite or database later.
    """
    
    def __init__(self, data_dir: Path = None):
        settings = get_settings()
        self.data_dir = data_dir or Path(settings.DATA_DIR) / "topic_reservoir"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.reservoir_file = self.data_dir / "topics.json"
    
    def load_topics(self) -> list[dict]:
        """Load existing topics from reservoir."""
        if not self.reservoir_file.exists():
            return []
        try:
            with open(self.reservoir_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    
    def save_topic(self, topic: dict) -> None:
        """Save a new topic to the reservoir."""
        topics = self.load_topics()
        
        # Check for duplicates
        existing_titles = {t.get("topic_statement", "").lower() for t in topics}
        if topic.get("topic_statement", "").lower() in existing_titles:
            log.debug(f"topic_already_exists: {topic.get('topic_statement', '')[:30]}")
            return
        
        # Add topic
        topic["id"] = self._generate_id()
        topic["status"] = "reservoir"
        topic["created_at"] = datetime.now(timezone.utc).isoformat()
        topics.append(topic)
        
        # Save
        with open(self.reservoir_file, "w", encoding="utf-8") as f:
            json.dump(topics, f, indent=2, ensure_ascii=False)
        
        log.info(f"topic_saved: {topic.get('topic_statement', '')[:50]}...")
    
    def _generate_id(self) -> str:
        """Generate unique topic ID."""
        import uuid
        return f"topic_{uuid.uuid4().hex[:8]}"


# ─── Main Daily Scan ────────────────────────────────────────────────────────────

async def run_daily_scan(genres: list[str] = None):
    """
    Execute daily topic scan.
    
    Args:
        genres: List of genre IDs to scan for
    """
    log.info(f"daily_scan_started: {datetime.now(timezone.utc).isoformat()}")
    
    if not genres:
        genres = [
            "current_situation",
            "history",
            "economics",
            "tech_systems",
            "islamic_history",
            "south_asian_history"
        ]
    
    # 1. Aggregate trends
    scanner = TrendScanner()
    trends = await scanner.aggregate_trends()
    
    if not trends:
        log.warning("no_trends_found: scan produced no results")
        return 0
    
    # 2. Score topics
    scorer = TopicScorer()
    reservoir = TopicReservoir()
    
    topics_saved = 0
    
    # Process top trends
    for trend in trends[:20]:  # Limit to top 20
        # Determine genre
        genre_id = _infer_genre(trend.get("title", ""), genres)
        
        # Score the topic
        scored = await scorer.score_topic(trend, genre_id)
        
        if scored and scored.get("is_tier_1"):
            reservoir.save_topic(scored)
            topics_saved += 1
    
    log.info(f"daily_scan_complete: {topics_saved} Tier 1 topics saved to reservoir")
    
    # 3. Update dashboard notification (if implemented)
    # await notify_dashboard(topics_saved)
    
    return topics_saved


def _infer_genre(title: str, available_genres: list[str]) -> str:
    """Infer the genre from the topic title."""
    title_lower = title.lower()
    
    genre_keywords = {
        "current_situation": ["pakistan", "government", "politics", "economy", "crisis", "news", "current", "today"],
        "history": ["history", "historical", "ancient", "century", "empire", "war", "partition"],
        "economics": ["economy", "economic", "money", "finance", "dollar", "inflation", "trade", "gdp"],
        "tech_systems": ["technology", "tech", "ai", "digital", "internet", "software", "system"],
        "islamic_history": ["islamic", "islam", "muslim", "caliphate", "quran", "prophet", "mosque"],
        "south_asian_history": ["india", "bangladesh", "south asia", "subcontinent", "kashmir", "punjab"]
    }
    
    for genre, keywords in genre_keywords.items():
        if genre in available_genres:
            for keyword in keywords:
                if keyword in title_lower:
                    return genre
    
    return available_genres[0] if available_genres else "current_situation"


# ─── CLI Entry Point ────────────────────────────────────────────────────────────

def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Daily Topic Discovery Scanner")
    parser.add_argument(
        "--genres",
        type=str,
        default=None,
        help="Comma-separated list of genres to scan"
    )
    args = parser.parse_args()
    
    # Parse genres
    genres = args.genres.split(",") if args.genres else None
    
    # Run scan
    asyncio.run(run_daily_scan(genres))


if __name__ == "__main__":
    main()

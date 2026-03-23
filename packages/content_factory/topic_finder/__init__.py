"""
Topic Discovery — Finds and Scores Candidate Video Topics.

Two discovery paths:
  Path 1 (Original): Generates new topic ideas from seed queries using
          17 viability questions. Stores Tier 1 candidates in SQLite reservoir.
  Path 2 (Adaptation): Scans SourceVideoLibrary for JH videos, checks which
          ones map to current Pakistani trends → generates adaptation briefs.

Viability criteria: Gap Test (3 questions), Anchor Test (4), Audience Test (4),
                    Production Test (3), Timing Test (3) = 17 total.
Tier 1 = passes ALL gap questions + 2+ anchors + 2+ audience.

Entry point: finder.py → TopicFinderAgent.generate_candidate(seed, genre_id)
Memory: TopicReservoirDB in db.py (SQLite), Zep for audience intelligence
"""

# packages/content_factory/topic_finder — Phase 5 Topic Finder & Feedback Loop

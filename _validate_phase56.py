"""Phase 5 & 6 Validation Script.

Tests the Topic Finder SQLite storage and the Music Agent parsing paths.
Run locally to verify the new modules.
"""

from packages.content_factory.topic_finder.models import TopicBrief
from packages.content_factory.topic_finder.db import TopicReservoirDB
from packages.content_factory.topic_finder.finder import TopicFinderAgent
from packages.content_factory.music.agent import MusicAgent
from packages.content_factory.music.models import MusicArchitectureDocument
from packages.content_factory.models import AdaptedScript, DualColumnEntry, SectionLabel
from datetime import datetime, timezone
import os
import sys

# 1. Topic Finder & Reservoir Mock
def test_topic_reservoir():
    print("Testing Topic Reservoir persistence...")
    db = TopicReservoirDB()
    
    mock_brief = TopicBrief(
        topic_statement="The systemic issues causing the energy crisis.",
        big_question="Why has energy generation failed to keep up with capacity payments?",
        genre_id="current_situation",
        gap_type="Hidden Mechanism",
        viability_score_breakdown={"gap_1": True, "anchor_1": True},
        anchor_candidates=["An idle power plant", "A monthly electricity bill"],
        mainstream_assumption="People assume it is just lack of fuel.",
        urgency_flag=True,
        timing_rationale="Current protests over bills",
        created_at=datetime.now(timezone.utc),
        status="reservoir"
    )
    
    # Save it and fetch it back
    db.save_topic(mock_brief)
    
    topics = db.get_top_topics(limit=1)
    assert len(topics) > 0, "Failed to retrieve topic from reservoir"
    print(f"Success: Retrieved topic '{topics[0].topic_statement}'")


# 2. Music Agent Pipeline Mock
def test_music_agent():
    print("Testing Music Agent constraints and document generation...")
    agent = MusicAgent()
    
    # Mock a Dual-Column Script
    mock_script = AdaptedScript(
        video_id="mock_video_123",
        source_video_id="source_video_456",
        genre="islamic_history",
        entries=[
            DualColumnEntry(section_label=SectionLabel.HOOK, visual_direction="A lone figure in the desert.", prose="This is the story of a forgotten battle. But the big question is why did they fight?"),
            DualColumnEntry(section_label=SectionLabel.ANCHOR, visual_direction="A ruined castle wall.", prose="Look at this wall. It has stood for a thousand years. It tells a story."),
            DualColumnEntry(section_label=SectionLabel.BRIDGE, visual_direction="A map showing trade routes.", prose="These routes were vital. They moved gold and spices across the continent."),
            DualColumnEntry(section_label=SectionLabel.REVEAL, visual_direction="A hidden manuscript page.", prose="The truth was hidden here. They didn't fight for religion. They fought for water."),
            DualColumnEntry(section_label=SectionLabel.CONCLUSION, visual_direction="Sun setting over modern city.", prose="That legacy remains today.")
        ]
    )
    
    doc = agent.generate_music_architecture("mock_video_123", mock_script)
    
    # Assertions
    assert isinstance(doc, MusicArchitectureDocument), "Music Agent failed to produce valid document type"
    assert len(doc.section_briefs) == 5, "Music Agent missed some sections"
    assert doc.section_briefs[0].state_assignment == 1, "HOOK must be State 1 Confusion Open"
    assert doc.section_briefs[4].state_assignment == 4, "CONCLUSION must be State 4 Contemplative Close"
    
    paks_palette = any(b.sonic_palette is not None for b in doc.section_briefs)
    assert paks_palette, "Islamic History genre should have triggered a Pakistani Sonic Palette flag"
    
    has_silence = any(s.section_index == 3 for s in doc.silence_map)
    assert has_silence, "Music Agent failed to place silence immediately before REVEAL"
    
    print("Success: Music Architecture generated perfectly.")

if __name__ == "__main__":
    try:
        test_topic_reservoir()
        test_music_agent()
        print("\n--- All Phase 5 & 6 Validation Tests Passed! ---")
    except Exception as e:
        print(f"Validation FAILED: {e}", file=sys.stderr)
        sys.exit(1)

"""Component 1: The Shame Draft Reader.

Parses the Shame Draft document from Phase 3 and extracts structured
information that the Emotional Arc Designer needs.
"""

import json
from packages.content_factory.models import AdaptedScript
from packages.core.logger import get_logger

logger = get_logger(__name__)

class ShameDraftData:
    """The structured data extracted from a Shame Draft."""
    def __init__(self, script: AdaptedScript):
        self.sections = script.entries
        self.genre_id = script.genre
        
        self.big_question_idx = -1
        self.reveal_idx = -1
        self.human_character_moments = []
        
        self.total_duration_estimate = 0
        
        # Analyze structure
        for i, section in enumerate(self.sections):
            word_count = len(section.prose.split())
            # Rough estimate: 2.5 words per second spoken
            duration = int(word_count / 2.5) 
            self.total_duration_estimate += duration
            
            # Simple heuristic matching
            lower_prose = section.prose.lower()
            if "big question" in lower_prose or "the real question" in lower_prose:
                self.big_question_idx = i
            
            if section.section_label == "REVEAL":
                self.reveal_idx = i
                
            if "human" in section.visual_direction.lower() or "person" in section.visual_direction.lower():
                self.human_character_moments.append(i)

        # Fallbacks
        if self.big_question_idx == -1:
            self.big_question_idx = 0 # Usually in HOOK
        if self.reveal_idx == -1:
            # Pick the last ANCHOR before CONCLUSION
            for i in range(len(self.sections)-1, -1, -1):
                if self.sections[i].section_label == "ANCHOR":
                    self.reveal_idx = i
                    break


class ShameDraftReader:
    def read(self, script: AdaptedScript) -> ShameDraftData:
        """Parse raw script into structured metadata for the Arc Designer."""
        logger.info(f"reading_shame_draft: sectors={len(script.entries)}")
        return ShameDraftData(script)

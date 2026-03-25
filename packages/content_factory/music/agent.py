"""The Music Agent.

Orchestrates the Shame Draft parsing, Arc Design, Section Briefing,
and Transition Architecture into a final MusicArchitectureDocument.
"""

from packages.content_factory.models import AdaptedScript
from packages.content_factory.music.models import MusicArchitectureDocument
from packages.content_factory.music.reader import ShameDraftReader
from packages.content_factory.music.arc_designer import EmotionalArcDesigner
from packages.content_factory.music.section_brief import SectionMusicBriefGenerator
from packages.content_factory.music.transitions import TransitionArchitect

class MusicAgent:
    def __init__(self):
        self.reader = ShameDraftReader()
        self.arc_designer = EmotionalArcDesigner()
        self.section_generator = SectionMusicBriefGenerator()
        self.transition_architect = TransitionArchitect()
        
    def generate_music_architecture(self, video_id: str, draft: AdaptedScript) -> MusicArchitectureDocument:
        """Processes the Shame Draft to produce the final music arc."""
        
        draft_data = self.reader.read(draft)
        arc_map = self.arc_designer.design_arc(draft_data)
        section_briefs = self.section_generator.generate_briefs(draft_data, arc_map)
        transitions = self.transition_architect.calculate_transitions(section_briefs)
        
        return MusicArchitectureDocument(
            video_id=video_id,
            genre_id=draft.genre,
            arc_summary=arc_map.arc_summary,
            silence_map=arc_map.silence_locations,
            section_briefs=section_briefs,
            transitions=transitions,
            music_architecture_integrity_score=100.0,  # Simulated perfect score for MVP
            failed_questions=[]
        )

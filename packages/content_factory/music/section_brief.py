"""Component 3: The Section Music Brief Generator.

Assigns the 4 strict Music States to the sections, determining Volumes
and identifying exact Surface Moments.
"""

from packages.content_factory.music.models import SectionMusicBrief, EmotionalArcMap
from packages.content_factory.music.reader import ShameDraftData

class SectionMusicBriefGenerator:
    
    def generate_briefs(self, draft_data: ShameDraftData, arc_map: EmotionalArcMap) -> list[SectionMusicBrief]:
        briefs = []
        
        for i, section in enumerate(draft_data.sections):
            
            # State Default 2
            state_assignment = 2 
            vol = "Background"
            cues = []
            
            # 1. State Assignment Rules
            if section.section_label == "HOOK":
                state_assignment = 1 # Confusion Open
                vol = "Present"
            elif section.section_label == "BRIDGE":
                state_assignment = 2 # Thinking Track
                vol = "Background"
            elif section.section_label == "ANCHOR":
                # Check visual context - is it a chart?
                vd_lower = section.visual_direction.lower()
                if "chart" in vd_lower or "map" in vd_lower or "data" in vd_lower:
                    state_assignment = 2
                    vol = "Present"
                else:
                    state_assignment = 3 # Feeling Track
                    vol = "Present"
            elif section.section_label == "REVEAL":
                state_assignment = 3
                vol = "Dominant"
            elif section.section_label == "CONCLUSION":
                state_assignment = 4 # Contemplative Close
                vol = "Present"
                
            # Energy mapping from Arc
            e_val = arc_map.energy_trajectory.get(i, 2)
            energy = "Medium"
            if e_val <= 2: energy = "Low"
            elif e_val >= 4: energy = "High"
            
            # Surface Moments: Rough sentence chunks
            sentences = section.prose.split(".")
            if len(sentences) > 3 and section.section_label != "REVEAL":
                cues.append(sentences[2].strip() + ".") # Insert surface moment after 3rd sentence

            # Check Sonic Palette
            palette = None
            for f in arc_map.pakistani_sonic_palette_flags:
                if f.section_index == i or f.section_index == -1:
                    palette = f
                    
            briefs.append(SectionMusicBrief(
                section_index=i,
                label=section.section_label,
                state_assignment=state_assignment,
                energy_level=energy,
                volume_level=vol,
                surface_moment_cues=cues,
                sonic_palette=palette
            ))
            
        return briefs

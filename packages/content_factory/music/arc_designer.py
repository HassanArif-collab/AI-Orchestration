"""Component 2: The Emotional Arc Designer.

Reads the ShameDraftData to produce an EmotionalArcMap.
Assigns peaks, plateaus, energy trajectories, silence moments, and 
determines if a Pakistani Sonic Palette is required.
"""

from packages.content_factory.music.models import EmotionalArcMap, RankedPeak, SilenceMoment, SonicPaletteFlag
from packages.content_factory.music.reader import ShameDraftData

class EmotionalArcDesigner:
    
    def design_arc(self, draft_data: ShameDraftData) -> EmotionalArcMap:
        """Processes the Shame Draft structure to produce the master arc."""
        
        peaks = []
        energy_traj = {}
        silences = []
        flags = []
        recovery_moments = []
        
        # 1. Identify Peaks & Plateaus & Energy Trajectory
        current_energy = 1
        
        for i, section in enumerate(draft_data.sections):
            duration = int(len(section.prose.split()) / 2.5)
            
            # Confusion Open -> Low energy
            if i <= draft_data.big_question_idx:
                current_energy = 1
                energy_traj[i] = 1
                continue
                
            if section.section_label == "ANCHOR":
                # Build energy
                current_energy = min(current_energy + 1, 4)
                energy_traj[i] = current_energy
                # Strong anchor -> Peak
                if i in draft_data.human_character_moments:
                    peaks.append(RankedPeak(section_index=i, label=section.section_label, intensity=current_energy, timestamp_estimate=i*60))
            
            elif section.section_label == "BRIDGE":
                # Drop slightly for cognitive plateaus
                current_energy = max(current_energy - 1, 2)
                energy_traj[i] = current_energy
                if duration > 60:
                    recovery_moments.append(i)
                    
            elif section.section_label == "REVEAL":
                current_energy = 5
                energy_traj[i] = 5
                peaks.append(RankedPeak(section_index=i, label=section.section_label, intensity=5, timestamp_estimate=i*60))
                
                # Insert Silence immediately before REVEAL
                silences.append(SilenceMoment(
                    section_index=i, 
                    timestamp_estimate=i*60 - 5, 
                    duration_seconds=5, 
                    reason="Absolute silence before maximum discovery payload."
                ))
                
            elif section.section_label == "CONCLUSION":
                current_energy = 2
                energy_traj[i] = 2
                peaks.append(RankedPeak(section_index=i, label=section.section_label, intensity=2, timestamp_estimate=i*60))

        # 2. Sonic Palette Routing for Pakistan
        # Rules: Islamic History and South Asian History mandate full-video flags.
        if draft_data.genre_id in ["islamic_history", "south_asian_history"]:
            flags.append(SonicPaletteFlag(
                section_index=-1, # -1 implies Full Video
                reason=f"Genre {draft_data.genre_id} requires deep cultural resonance rather than Hollywood dramatic scoring.",
                instrumentation_direction="Oud, minimal percussion, natural textures. Avoid unresolved synth bass tensions.",
                avoid_list=["Western Orchestral Swells", "Hollywood Trailer Braams"]
            ))
        else:
            # Check for CONCLUSION in general domains
            # If addressing a sensitive Pakistani topic, flag conclusion.
            # Simplified heuristic for MVP
            flags.append(SonicPaletteFlag(
                section_index=len(draft_data.sections) - 1,
                reason="Conclusion involves Pakistani societal reality; needs contemplative grounding.",
                instrumentation_direction="Subtle sitar or flute over minimal pad.",
                avoid_list=["Triumphant Western Strings"]
            ))

        return EmotionalArcMap(
            arc_summary=f"A steady build across {len(draft_data.sections)} sections peaking at the Reveal, with Pakistani sonic considerations.",
            peak_inventory=peaks,
            energy_trajectory=energy_traj,
            silence_locations=silences,
            pakistani_sonic_palette_flags=flags,
            recovery_moments=recovery_moments
        )

"""Component 4: The Transition Architect.

Defines mechanical transitions between the Music States.
(Thickening, Thinning, Silence Drops, Resolution Settles).
"""

from packages.content_factory.music.models import SectionMusicBrief, TransitionSpec

class TransitionArchitect:
    
    def calculate_transitions(self, briefs: list[SectionMusicBrief]) -> list[TransitionSpec]:
        """Iterates pair-wise to define the exact transition method."""
        
        transitions = []
        for i in range(len(briefs) - 1):
            curr = briefs[i]
            nxt = briefs[i+1]
            
            t_type = "Anticipatory Hold"
            
            # Rule definitions
            if nxt.label == "REVEAL":
                t_type = "Silence Drop"
            elif nxt.label == "CONCLUSION":
                t_type = "Resolution Settle"
            elif curr.state_assignment == 2 and nxt.state_assignment == 3:
                t_type = "Gradual Thickening"
            elif curr.state_assignment == 3 and nxt.state_assignment == 2:
                t_type = "Gradual Thinning"
            elif curr.state_assignment == 3 and nxt.state_assignment == 3:
                # E.g. Anchor -> Transition -> Anchor where Transition is very short
                t_type = "Hard State Reset"

            transitions.append(TransitionSpec(
                from_section_index=curr.section_index,
                to_section_index=nxt.section_index,
                transition_type=t_type,
                start_cue=f"End of section {curr.label}",
                end_cue=f"Start of section {nxt.label}",
                duration_seconds=5 if t_type != "Gradual Thickening" else 15,
                editor_note=f"Executing {t_type} into {nxt.state_assignment}"
            ))
            
        return transitions

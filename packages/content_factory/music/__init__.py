"""
Music Architecture Agent — Phase 6: Emotional Score Design.

Takes the final dual-column script and designs the complete music architecture
for the video — emotional arc, section-by-section briefs, silence placement,
and transition instructions for the video editor.

OUTPUT: MusicArchitectureDocument (see models.py)
INPUT:  AdaptedScript (from ExperimentLoop or ContentCreationRouter)

4 INTERNAL COMPONENTS (process in this order):

  reader.py → ShameDraftReader
    Parses the AdaptedScript and extracts structural data:
    section count, prose density, visual type distribution.
    Output: ShameDraftData (internal format for arc design)

  arc_designer.py → EmotionalArcDesigner
    Maps section labels to emotional states:
      HOOK       → State 1: Confusion Open (unsettled, questioning)
      ANCHOR     → State 2: Grounded Tension (familiar anchor, tension rises)
      BRIDGE     → State 2-3: Investigation (slow build, seeking)
      REVEAL     → State 3: Revelation (peak tension, then resolution)
      CONCLUSION → State 4: Contemplative Close (reflective, still)
    Special rule: silence MUST precede the REVEAL section.
    Output: EmotionalArcMap with silence_locations list

  section_brief.py → SectionMusicBriefGenerator
    Generates a MusicSectionBrief per section with:
      state_assignment (1-4), tempo range, instrumentation guidance,
      sonic_palette (Pakistani-specific for islamic_history genre),
      energy curve, key moments to accent.
    Output: list[MusicSectionBrief]

  transitions.py → TransitionArchitect
    Calculates transition type between consecutive sections.
    Types: hard_cut, cross_fade, silence_drop, energy_bridge, dissolve
    Output: list[TransitionInstruction]

GENRE-SPECIFIC RULES:
  islamic_history → triggers Pakistani sonic palette
                    (traditional instruments, Qawwali-inspired elements)
  south_asian_history → regional instruments, Mughal-era references
  current_situation → contemporary Pakistani music references

NOTE: The music agent is deterministic — no LLM calls.
All decisions are rule-based from the emotional state machine.
This keeps Phase 6 fast and reproducible.
"""

# packages/content_factory/music — Phase 6 Music Agent

"""Phase 6: Music Agent Data Structures."""

from typing import Literal
from pydantic import BaseModel, Field


class RankedPeak(BaseModel):
    section_index: int
    label: str
    intensity: int  # 1 to 5
    timestamp_estimate: int


class SilenceMoment(BaseModel):
    section_index: int
    timestamp_estimate: int
    duration_seconds: int = 4
    reason: str


class SonicPaletteFlag(BaseModel):
    section_index: int
    reason: str
    instrumentation_direction: str
    avoid_list: list[str] = Field(default_factory=list)


class EmotionalArcMap(BaseModel):
    arc_summary: str
    peak_inventory: list[RankedPeak]
    energy_trajectory: dict[int, int]  # section_index -> energy level (1-5)
    silence_locations: list[SilenceMoment]
    pakistani_sonic_palette_flags: list[SonicPaletteFlag]
    recovery_moments: list[int]  # section indices


class SectionMusicBrief(BaseModel):
    section_index: int
    label: str
    state_assignment: Literal[1, 2, 3, 4]  # 1:Confusion, 2:Thinking, 3:Feeling, 4:Contemplative
    energy_level: Literal["Low", "Medium", "High"]
    volume_level: Literal["Background", "Present", "Surface", "Dominant"]
    surface_moment_cues: list[str] = Field(default_factory=list)
    sonic_palette: SonicPaletteFlag | None = None


class TransitionSpec(BaseModel):
    from_section_index: int
    to_section_index: int
    transition_type: Literal[
        "Gradual Thickening", "Gradual Thinning", "Silence Drop",
        "Resolution Settle", "Anticipatory Hold", "Hard State Reset"
    ]
    start_cue: str
    end_cue: str
    duration_seconds: int
    sonic_palette_overlap_notes: str | None = None
    editor_note: str


class MusicArchitectureDocument(BaseModel):
    video_id: str
    genre_id: str
    arc_summary: str
    silence_map: list[SilenceMoment]
    section_briefs: list[SectionMusicBrief]
    transitions: list[TransitionSpec]
    music_architecture_integrity_score: float | None = None
    failed_questions: list[str] = Field(default_factory=list)

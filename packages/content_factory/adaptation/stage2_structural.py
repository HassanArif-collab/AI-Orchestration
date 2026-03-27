"""Stage 2: Structural DNA Extraction.

Takes the raw transcript and uses the LLM to classify it into
sections (HOOK, ANCHOR, BRIDGE, REVEAL, CONCLUSION, TRANSITION),
extract metrics, and identify visual anchors.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from packages.core.logger import get_logger
from packages.router.client import RouterClient

from ..error_log import ErrorLogger
from ..models import (
    ProcessingStatus,
    RawExtraction,
    StructuralMap,
    StructuralMetrics,
    StructuralSection,
    VisualAnchorCandidate,
)
from ..source_library import SourceVideoLibrary

logger = get_logger(__name__)

# Load Phase 1 outputs used in Stage 2
CONTENT_FACTORY_DIR = Path(__file__).parent.parent
GENRE_SCHEMA_PATH = CONTENT_FACTORY_DIR / "genre_schema.json"
EVALUATION_SUITE_PATH = CONTENT_FACTORY_DIR / "evaluation_suite.json"


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text("utf-8"))
    except Exception:
        return {}


async def stage2_analyze(
    extraction: RawExtraction,
    router_client: RouterClient,
    source_library: SourceVideoLibrary | None = None,
    error_logger: ErrorLogger | None = None,
    cycle_id: str | None = None,
) -> StructuralMap | None:
    """Stage 2: Extract structural DNA from the raw extraction.

    Args:
        extraction: RawExtraction from Stage 1.
        router_client: FreeRouter client (required).
        source_library: Source Video Library.
        error_logger: Error logger.
        cycle_id: Production cycle ID.

    Returns:
        StructuralMap on success, None on failure.
    """
    cycle_id = cycle_id or extraction.video_id
    errors = error_logger or ErrorLogger()
    library = source_library or SourceVideoLibrary()

    # Check cache first
    cached_record = library.load(extraction.video_id)
    if cached_record and cached_record.structural_map:
        logger.info(f"stage2_cache_hit: {extraction.video_id}")
        return cached_record.structural_map

    genre_schema = load_json(GENRE_SCHEMA_PATH)
    genre_names = [g["id"] for g in genre_schema.get("genres", [])]

    # Build prompt for LLM
    system_prompt = """
You are an expert documentary script analyst. Your task is to analyze a YouTube transcript
and classify it into structural sections following the Johnny Harris style.

The section types are:
- HOOK: The opening that sets the stakes
- ANCHOR: Physical evidence, documents, maps, or real-world objects
- BRIDGE: Narration connecting anchors, context, or argument
- REVEAL: The moment the hidden dimension is exposed
- CONCLUSION: The ending that shifts perspective
- TRANSITION: Minor connective tissue

You must output valid JSON ONLY, exactly matching this schema:
{
  "genre": "one of: " + ", ".join(genre_names) + "",
  "big_question": "The core mystery or question from the hook",
  "structural_integrity_score": 0-7,
  "sections": [
    {
      "label": "HOOK|ANCHOR|BRIDGE|REVEAL|CONCLUSION|TRANSITION",
      "start_seconds": 0.0,
      "end_seconds": 0.0,
      "content_summary": "Brief summary",
      "key_elements": ["List", "of", "elements"]
    }
  ],
  "visual_anchors": [
    {
      "description": "What the anchor is",
      "anchor_type": "object|location|person|document|data_viz",
      "hierarchy_level": 1-5,
      "section_index": 0
    }
  ]
}
"""

    user_prompt = f"""
Title: {extraction.title}
Duration: {extraction.duration_seconds}s

Transcript:
{extraction.full_transcript[:15000]} # truncate for context limits if needed
"""

    try:
        response_text = await router_client.complete_text(
            prompt=user_prompt,
            system_prompt=system_prompt,
            model="auto",
            temperature=0.1
        )
        
        # extract JSON from response
        import re
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if not json_match:
            raise ValueError("Could not extract JSON from LLM response")
        
        data = json.loads(json_match.group(0))

    except Exception as e:
        errors.log_error(
            cycle_id, 2, "Structural Analysis Failed",
            f"LLM extraction failed: {str(e)}",
            content_element=extraction.video_id
        )
        return None

    # Parse Sections
    sections = []
    total_anchor_duration = 0.0
    total_bridge_duration = 0.0
    hook_duration = 0.0
    reveal_position = 0.0
    conclusion_duration = 0.0
    first_anchor_pos = 0.0
    has_anchor = False

    for i, sec_data in enumerate(data.get("sections", [])):
        start = float(sec_data.get("start_seconds", 0))
        end = float(sec_data.get("end_seconds", 0))
        dur = max(0.0, end - start)
        label = sec_data.get("label", "BRIDGE")

        sections.append(StructuralSection(
            label=label,
            start_seconds=start,
            end_seconds=end,
            duration_seconds=dur,
            content_summary=sec_data.get("content_summary", ""),
            key_elements=sec_data.get("key_elements", [])
        ))

        if label == "ANCHOR":
            total_anchor_duration += dur
            if not has_anchor:
                first_anchor_pos = start
                has_anchor = True
        elif label == "BRIDGE":
            total_bridge_duration += dur
        elif label == "HOOK":
            hook_duration += dur
        elif label == "REVEAL":
            reveal_position = (start / extraction.duration_seconds) * 100 if extraction.duration_seconds else 0.0
        elif label == "CONCLUSION":
            conclusion_duration += dur

    # Build Metrics
    ratio = total_anchor_duration / total_bridge_duration if total_bridge_duration > 0 else 0.0
    conc_percent = (conclusion_duration / extraction.duration_seconds) * 100 if extraction.duration_seconds else 0.0

    metrics = StructuralMetrics(
        anchor_to_bridge_ratio=ratio,
        hook_duration_seconds=hook_duration,
        first_anchor_position_seconds=first_anchor_pos,
        reveal_position_percent=reveal_position,
        conclusion_duration_seconds=conclusion_duration,
        conclusion_duration_percent=conc_percent,
        total_anchor_duration=total_anchor_duration,
        total_bridge_duration=total_bridge_duration
    )

    # Validations / Warnings
    if hook_duration == 0:
        errors.log_warning(cycle_id, 2, "Missing Hook", "No HOOK section detected.")
    if len([s for s in sections if s.label == "ANCHOR"]) < 2:
        errors.log_warning(cycle_id, 2, "Low Anchors", "Fewer than 2 ANCHOR sections detected.")

    anchors = [
        VisualAnchorCandidate(
            description=a.get("description", ""),
            anchor_type=a.get("anchor_type", "object"),
            hierarchy_level=a.get("hierarchy_level", 1),
            section_index=a.get("section_index", 0)
        )
        for a in data.get("visual_anchors", [])
    ]

    smap = StructuralMap(
        video_id=extraction.video_id,
        sections=sections,
        section_sequence=[s.label.value for s in sections],
        metrics=metrics,
        big_question=data.get("big_question", ""),
        visual_anchors=anchors,
        genre=data.get("genre", "history"),
        structural_integrity_score=data.get("structural_integrity_score", 0),
    )

    # Update Source Video Library
    if cached_record:
        cached_record.structural_map = smap
        cached_record.genre = smap.genre
        cached_record.structural_integrity_score = smap.structural_integrity_score
        cached_record.anchor_to_bridge_ratio = metrics.anchor_to_bridge_ratio
        cached_record.section_sequence = smap.section_sequence
        cached_record.big_question = smap.big_question
        cached_record.processing_status = ProcessingStatus.FULLY_ANALYZED
        library.save(cached_record)

    logger.info(f"stage2_complete: {extraction.video_id} - Genre: {smap.genre}, A/B Ratio: {ratio:.2f}")

    return smap

"""Stage 4: Dual-Column Script Generation.

Assembles the final production-ready script with dual-column formatting
using the localization map and structural sections. Applies rule-based
pre-submission self-checks.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from packages.core.logger import get_logger
from packages.router.client import RouterClient

from ..error_log import ErrorLogger
from ..models import (
    AdaptedScript,
    DualColumnEntry,
    LocalizationMap,
    ProcessingStatus,
    SelfCheckResult,
    StructuralMap,
)
from ..source_library import SourceVideoLibrary

logger = get_logger(__name__)

CONTENT_FACTORY_DIR = Path(__file__).parent.parent
EVALUATION_SUITE_PATH = CONTENT_FACTORY_DIR / "evaluation_suite.json"


def load_evaluation_suite() -> dict:
    if not EVALUATION_SUITE_PATH.exists():
        return {}
    return json.loads(EVALUATION_SUITE_PATH.read_text("utf-8"))


async def stage4_generate(
    smap: StructuralMap,
    lmap: LocalizationMap,
    router_client: RouterClient,
    source_library: SourceVideoLibrary | None = None,
    error_logger: ErrorLogger | None = None,
    cycle_id: str | None = None,
) -> AdaptedScript | None:
    """Stage 4: Generate localized dual-column script.

    Args:
        smap: StructuralMap from Stage 2.
        lmap: LocalizationMap from Stage 3.
        router_client: FreeRouter client (required).
        source_library: Source Video Library.
        error_logger: Error logger.
        cycle_id: Production cycle ID.

    Returns:
        AdaptedScript on success, None on failure.
    """
    cycle_id = cycle_id or smap.video_id
    errors = error_logger or ErrorLogger()
    library = source_library or SourceVideoLibrary()

    eval_suite = load_evaluation_suite()

    system_prompt = """
You are generating a final dual-column script in the Johnny Harris style.
You are given the structural sections and the exact Pakistani localization mappings.
Apply the mappings. Write the narrative prose and pair it with visual production directions.

Respond strictly in JSON matching this schema:
{
  "adapted_title": "Video Title",
  "entries": [
    {
      "section_label": "HOOK|ANCHOR|BRIDGE|REVEAL|CONCLUSION|TRANSITION",
      "prose": "Left column words",
      "visual_direction": "Right column editing directions",
      "visual_type": "talking_head|broll|animation|archive|data_viz|soul_moment",
      "duration_estimate_seconds": 0.0,
      "anchor_hierarchy_level": 1,
      "low_confidence_flag": false
    }
  ]
}
"""

    user_prompt = f"""
Source Sections: {[s.model_dump() for s in smap.sections]}
Localization Mappings: {lmap.model_dump_json(exclude={'video_id'})}
"""

    try:
        response_text = await router_client.complete_text(
            prompt=user_prompt,
            system_prompt=system_prompt,
        )

        from packages.core.json_utils import extract_json_object
        json_str = extract_json_object(response_text)
        if not json_str:
            raise ValueError("Could not extract JSON from LLM response")

        data = json.loads(json_str)

    except Exception as e:
        errors.log_error(cycle_id, 4, "Script Generation Failed", str(e), content_element=smap.video_id)
        return None

    entries = []
    for item in data.get("entries", []):
        entries.append(DualColumnEntry(**item))

    # C10 FIX: Real structural self-check instead of mock that always passed ~90%
    # Tests actual script properties: section count, order, content quality
    check_results = []
    passed_count = 0

    structural_checks = [
        {
            "id": "S1", "text": "Script has at least 3 sections",
            "passed": len(entries) >= 3
        },
        {
            "id": "S2", "text": "First section is ANCHOR or HOOK",
            "passed": len(entries) > 0 and entries[0].section_label.value in ("ANCHOR", "HOOK")
        },
        {
            "id": "S3", "text": "BRIDGE section not placed first",
            "passed": not (len(entries) > 0 and entries[0].section_label.value == "BRIDGE")
        },
        {
            "id": "S4", "text": "Script has a CONCLUSION or REVEAL section",
            "passed": any(e.section_label.value in ("CONCLUSION", "REVEAL", "CLOSING") for e in entries)
        },
        {
            "id": "S5", "text": "All entries have non-empty prose",
            "passed": all(len(e.prose.strip()) > 0 for e in entries)
        },
        {
            "id": "S6", "text": "Average prose length > 20 characters per section",
            "passed": len(entries) > 0 and sum(len(e.prose.strip()) for e in entries) / len(entries) > 20
        },
        {
            "id": "S7", "text": "At least one entry has visual direction",
            "passed": any(len(e.visual_direction.strip()) > 0 for e in entries)
        },
        {
            "id": "S8", "text": "No section exceeds 500 characters prose",
            "passed": all(len(e.prose) <= 500 for e in entries)
        },
        {
            "id": "S9", "text": "Section sequence has logical flow (not all same type)",
            "passed": len(set(e.section_label.value for e in entries)) > 1
        },
        {
            "id": "S10", "text": "Script has been adapted with new content (not empty/placeholder)",
            "passed": len(entries) > 0 and any(len(e.prose.strip()) > 50 for e in entries)
        },
    ]

    for check in structural_checks:
        check_results.append(SelfCheckResult(
            question_id=check["id"],
            question_text=check["text"],
            passed=check["passed"],
            failure_reason=None if check["passed"] else f"Check failed: {check['text']}"
        ))
        if check["passed"]:
            passed_count += 1

    readiness = (passed_count / len(check_results) * 100) if check_results else 0.0

    script = AdaptedScript(
        video_id=smap.video_id,
        adapted_title=data.get("adapted_title", "Adapted Video"),
        genre=smap.genre,
        entries=entries,
        section_sequence=[e.section_label.value for e in entries],
        self_check_results=check_results,
        production_readiness_score=readiness,
    )

    # Update Source Video Library
    cached_record = library.load(smap.video_id)
    if cached_record:
        cached_record.processing_status = ProcessingStatus.ADAPTED
        library.save(cached_record)

    logger.info(f"stage4_complete: {smap.video_id} - Script ready ({readiness:.1f}% readiness)")
    return script

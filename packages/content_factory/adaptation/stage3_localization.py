"""Stage 3: Pakistani Localization Engine.

Uses structural DNA and raw transcript to map contextual
substitutions (Monetary, Names, Geographic, Cultural, Argument)
with confidence scoring.
"""

import json
from datetime import datetime, timezone

from packages.core.logger import get_logger
from packages.router.client import RouterClient

from ..error_log import ErrorLogger
from ..models import (
    ConfidenceLevel,
    CulturalSubstitution,
    GeographicSubstitution,
    LocalizationMap,
    LocalizationSummary,
    MonetarySubstitution,
    NameSubstitution,
    RawExtraction,
    StructuralArgumentLocalization,
    StructuralMap,
)

logger = get_logger(__name__)


async def stage3_localize(
    smap: StructuralMap,
    extraction: RawExtraction,
    router_client: RouterClient | None = None,
    error_logger: ErrorLogger | None = None,
    cycle_id: str | None = None,
) -> LocalizationMap | None:
    """Stage 3: Localize transcript content for Pakistan.

    Args:
        smap: The structural map of the video.
        extraction: The raw extraction data.
        router_client: FreeRouter client.
        error_logger: Error logger.
        cycle_id: Production cycle ID.

    Returns:
        LocalizationMap on success, None on failure.
    """
    cycle_id = cycle_id or smap.video_id
    errors = error_logger or ErrorLogger()

    system_prompt = \"\"\"
You are an expert cultural localization engine adapting western documentary
content for a Pakistani audience. Identify and map substitutions across 5 categories:
1. Monetary (price mappings by class reality, not just exchange rates)
2. Names (western pop culture/historical figures to Pakistani equivalents)
3. Geographic (symbolic locations to Pakistani counterparts)
4. Cultural (societal touchstones)
5. Structural Argument (document-wide thesis adaptation)

Respond in strictly valid JSON matching this schema:
{
  "monetary": [{ "original_figure": "", "original_context": "", "pakistani_figure": "", "pakistani_context": "", "confidence": "high|medium|low", "section_index": 0 }],
  "names": [{ "original_name": "", "name_type": "global_public_figure|western_reference|generic_illustrative", "narrative_function": "", "pakistani_replacement": "", "confidence": "high|medium|low", "retained": false, "section_index": 0 }],
  "geographic": [{ "original_location": "", "symbolic_function": "", "location_type": "functionally_replaceable|essential", "pakistani_replacement": "", "equivalence_basis": "", "confidence": "high|medium|low", "section_index": 0 }],
  "cultural": [{ "original_reference": "", "cultural_work": "", "pakistani_replacement": "", "replacement_cultural_work": "", "confidence": "high|medium|low", "section_index": 0 }],
  "structural_argument": { "original_argument": "", "translates_directly": true, "pakistani_argument": "", "sections_requiring_major_changes": [], "confidence": "high|medium|low" }
}
\"\"\"

    user_prompt = f\"\"\"
Transcript to localize:
{extraction.full_transcript[:15000]}
\"\"\"

    try:
        async with RouterClient() if not router_client else router_client as client:
            response_text = await client.complete_text(
                prompt=user_prompt,
                system_prompt=system_prompt,
            )

            import re
            json_match = re.search(r'\\{.*\\}', response_text, re.DOTALL)
            if not json_match:
                raise ValueError("Could not extract JSON from LLM response")

            data = json.loads(json_match.group(0))

    except Exception as e:
        errors.log_error(cycle_id, 3, "Localization Failed", f"LLM mapping failed: {e}", content_element=smap.video_id)
        return None

    # Parse mappings
    monetary = []
    names = []
    geographic = []
    cultural = []

    for item in data.get("monetary", []):
        monetary.append(MonetarySubstitution(**item))
    for item in data.get("names", []):
        names.append(NameSubstitution(**item))
    for item in data.get("geographic", []):
        geographic.append(GeographicSubstitution(**item))
    for item in data.get("cultural", []):
        cultural.append(CulturalSubstitution(**item))

    sa_data = data.get("structural_argument")
    struct_arg = StructuralArgumentLocalization(**sa_data) if sa_data else None

    # Compute Summary
    total = len(monetary) + len(names) + len(geographic) + len(cultural)
    low_conf_count = sum(
        1 for lst in (monetary, names, geographic, cultural)
        for i in lst if i.confidence == ConfidenceLevel.LOW
    )
    if struct_arg and struct_arg.confidence == ConfidenceLevel.LOW:
        low_conf_count += 1
        total += 1

    low_pct = (low_conf_count / total * 100) if total else 0.0
    warning = low_pct > 25.0

    summary = LocalizationSummary(
        total_substitutions=total,
        by_category={
            "monetary": len(monetary),
            "names": len(names),
            "geographic": len(geographic),
            "cultural": len(cultural)
        },
        by_confidence={},
        localization_integrity_warning=warning,
        low_confidence_percent=low_pct
    )

    if warning:
        errors.log_warning(cycle_id, 3, "Localization Integrity Warning", f"{low_pct:.1f}% low confidence substitutions.")

    lmap = LocalizationMap(
        video_id=smap.video_id,
        monetary=monetary,
        names=names,
        geographic=geographic,
        cultural=cultural,
        structural_argument=struct_arg,
        summary=summary
    )

    logger.info(f"stage3_complete: {smap.video_id} - {total} substitutions mapped")
    return lmap

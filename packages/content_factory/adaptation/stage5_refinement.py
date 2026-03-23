"""
Stage 5: Pakistani Context Refinement.

After mechanical transcript adaptation (Stages 1-4), this stage runs
the script through the Writer agent for cultural depth and active voice.

This is what makes Mode A output feel like original content rather than
a translated transcript. The LLM rewrites the prose in Pakistani cultural
context while keeping all structural decisions from Stage 4.

Input:  AdaptedScript from stage4_script.py
Output: AdaptedScript with refined Pakistani prose
"""

import json
import re
from packages.core.logger import get_logger
from packages.router.client import RouterClient
from packages.content_factory.models import AdaptedScript, DualColumnEntry

logger = get_logger(__name__)


async def stage5_refine(
    script: AdaptedScript,
    router_client: RouterClient | None = None,
    error_logger=None,
    cycle_id: str | None = None,
) -> AdaptedScript | None:
    """Refine the adapted script for Pakistani cultural resonance.

    Takes the mechanically localized script from Stage 4 and asks the
    writer agent to rewrite the prose for cultural depth and active voice,
    while keeping all visual direction unchanged.
    """
    entries_json = json.dumps(
        [{"section_label": e.section_label.value,
          "prose": e.prose,
          "visual_direction": e.visual_direction}
         for e in script.entries],
        ensure_ascii=False,
        indent=2
    )

    prompt = f"""You are the Lead Writer for a Pakistani YouTube documentary channel.
A mechanical transcript adaptation has been prepared. Your job is to rewrite ONLY
the prose (spoken narration) for deep Pakistani cultural resonance.

Rules you MUST follow:
1. Active voice only — every sentence has a clear agent doing a visible action
2. No jargon that requires prior domain knowledge
3. "Friend explaining at a coffee table" tone
4. Pakistani audience is intelligent and aware — do NOT be condescending
5. Do NOT assume Western cultural familiarity
6. Keep the VISUAL DIRECTION exactly unchanged — only rewrite prose

Script to refine:
{entries_json}

Return a JSON array with the same structure, prose rewritten:
[{{"section_label": "...", "prose": "REWRITTEN prose", "visual_direction": "UNCHANGED"}}]"""

    try:
        client_to_use = router_client
        async with (RouterClient() if not client_to_use else client_to_use) as client:
            response = await client.complete_text(
                prompt=prompt,
                system="Return only a valid JSON array.",
                model="auto"
            )

            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if not json_match:
                logger.warning(f"stage5_no_json_found: {cycle_id}")
                return script  # Return original if refinement fails

            data = json.loads(json_match.group(0))
            refined_entries = []
            for i, item in enumerate(data):
                try:
                    # Merge: use refined prose but keep original visual data
                    original = script.entries[i] if i < len(script.entries) else None
                    refined_entries.append(DualColumnEntry(
                        section_label=item.get("section_label",
                                               original.section_label if original else "ANCHOR"),
                        prose=item.get("prose", original.prose if original else ""),
                        visual_direction=item.get("visual_direction",
                                                  original.visual_direction if original else ""),
                        visual_type=original.visual_type if original else None,
                        duration_estimate_seconds=original.duration_estimate_seconds
                                                  if original else None,
                    ))
                except Exception as e:
                    logger.warning(f"stage5_entry_parse_failed: {e}")
                    if original:
                        refined_entries.append(original)

            if len(refined_entries) < len(script.entries) * 0.7:
                logger.warning(f"stage5_truncated_output: keeping original")
                return script

            refined = script.model_copy(deep=True)
            refined.entries = refined_entries
            return refined

    except Exception as e:
        logger.error(f"stage5_refinement_failed: {e} cycle={cycle_id}")
        return script  # Always return something, never block the pipeline

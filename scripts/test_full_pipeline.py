#!/usr/bin/env python3
"""
End-to-end production pipeline test.

Runs: Research → Draft → Score → (mutation loop) → Visuals → Publish to Notion
Tests the FULL production graph including deer-flow v2 research upgrades
and Notion publishing.

Usage:
    cd /home/z/AI-Orchestration
    python scripts/test_full_pipeline.py
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone

# Ensure project root is on path
sys.path.insert(0, "/home/z/AI-Orchestration")

# Configure logging to see what's happening
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)

from packages.content_factory.production.deep_research import DeepResearchEngine
from packages.content_factory.production.models import ResearchDossier
from packages.integrations.notion.client import NotionScriptClient
from packages.router.client import RouterClient
from packages.core.config import get_settings


TOPIC = "Pakistan's AI Revolution in 2026"


async def step_1_research():
    """Step 1: Run deer-flow v2 deep research on the topic."""
    print("\n" + "=" * 70)
    print("STEP 1: DEEP RESEARCH (deer-flow v2 methodology)")
    print("=" * 70)
    print(f"Topic: {TOPIC}")

    start = time.time()
    async with RouterClient() as router:
        engine = DeepResearchEngine(
            router_client=router,
            max_searches_per_dimension=3,
            max_total_searches=20,
            enable_checkpoints=False,
            enable_fact_validation=False,
        )

        dossier = await engine.research(
            TOPIC,
            genre="current_situation",
            target_completeness=0.7,
            max_iterations=2,
            resume_from_checkpoint=False,
        )

    elapsed = time.time() - start

    # Print summary
    print(f"\n--- Research Summary ({elapsed:.1f}s) ---")
    print(f"Completeness: {dossier.completeness_score:.0%}")
    print(f"Total facts: {len(dossier.all_facts)}")
    print(f"Sources: {len(dossier.all_sources)}")
    print(f"Searches: {dossier.search_queries_total}")
    print(f"Dimensions: {dossier.dimensions_explored}")
    print(f"Physical anchors: {len(dossier.physical_anchors)}")
    print(f"Human characters: {len(dossier.human_characters)}")
    print(f"Full articles read: {len(dossier.full_article_texts or {})}")

    # Print info type coverage
    print(f"\nInformation type coverage:")
    for itype, covered in (dossier.information_type_coverage or {}).items():
        print(f"  {itype}: {'✓' if covered else '✗'}")

    # Print quality report
    if dossier.quality_report:
        qr = dossier.quality_report
        print(f"\nQuality Report: score={qr.get('score', 'N/A')}/100")
        if qr.get('strengths'):
            print(f"  Strengths: {qr['strengths'][:3]}")
        if qr.get('weaknesses'):
            print(f"  Weaknesses: {qr['weaknesses'][:3]}")

    # Print first 5 facts with citations
    print(f"\nTop facts (with citations):")
    for f in dossier.all_facts[:5]:
        citation = f" [source]({f.source_url})" if f.source_url else ""
        print(f"  [{f.information_type.value}] {f.statement[:100]}{citation}")

    # Print markdown dossier (first 2000 chars)
    markdown = dossier.to_markdown()
    print(f"\nDossier markdown length: {len(markdown)} chars")
    print(f"Dossier preview:\n{markdown[:1500]}...")

    return dossier, markdown


async def step_2_script_writing(research_markdown: str):
    """Step 2: Write a documentary script from research."""
    print("\n" + "=" * 70)
    print("STEP 2: SCRIPT WRITING")
    print("=" * 70)

    prompt = f"""You are writing a Johnny Harris-style documentary script. This is NOT a generic overview — this is a specific, evidence-driven story.

TOPIC: {TOPIC}

RESEARCH DOSSIER:
{research_markdown[:8000]}

CRITICAL RULES — YOUR SCRIPT WILL BE REJECTED IF YOU VIOLATE THESE:
1. You MUST cite at least 3 specific numbers, statistics, or data points from the research above
2. You MUST name at least 2 real people, organizations, companies, or places mentioned in the research
3. You MUST reference at least 1 specific event, case study, or real-world example
4. NEVER write vague statements like "a new generation is emerging" or "things are changing" — be SPECIFIC
5. NEVER write filler like "in a country often defined by its tumultuous politics" — get straight to the point
6. Every paragraph must contain a concrete fact, name, number, or specific example from the research
7. Use active voice. Name who did what. Give numbers. Be specific about where and when.

STRUCTURE:
**HOOK** — Open with a specific, surprising fact or number. NOT a vague scene-setter.
**ANCHOR** — Ground the story in specific evidence: names, data, places, dates.
**BRIDGE** — Connect the specific evidence to the bigger picture. Show the mechanism.
**REVEAL** — The key insight that challenges the mainstream assumption. Back it with evidence.
**CONCLUSION** — End with a specific forward-looking fact or prediction. NOT a vague inspirational statement.

Write 500-700 words of narration text. Output ONLY the script with section headers. No meta-commentary."""

    start = time.time()
    async with RouterClient() as router:
        draft = await router.complete_text(
            prompt,
            system="You are an elite documentary scriptwriter in the style of Johnny Harris. You write scripts that are dense with specific facts, names, numbers, and real-world examples. You never write vague filler. Every sentence carries concrete information.",
            model="script_writer",
            max_tokens=2000,
        )

    elapsed = time.time() - start
    word_count = len(draft.split())
    print(f"Draft generated in {elapsed:.1f}s")
    print(f"Word count: {word_count}")
    print(f"\n--- SCRIPT ---\n{draft}\n")
    return draft


async def step_3_scoring(draft: str):
    """Step 3: Score the script."""
    print("\n" + "=" * 70)
    print("STEP 3: SCRIPT SCORING")
    print("=" * 70)

    prompt = f"""Evaluate this documentary script draft against the 56-question binary checklist.

DRAFT:
{draft}

Return JSON: {{"score": 85, "feedback": "Brief description", "score_categories": {{"structure": 88, "hook": 83, "clarity": 75, "engagement": 86, "credibility": 71, "emotional": 67, "visual": 83, "conclusion": 80, "impact": 67}}}}

Score = percentage of YES answers. Be honest but fair."""

    start = time.time()
    async with RouterClient() as router:
        from packages.core.json_utils import extract_json_object
        response = await router.complete_text(
            prompt,
            system="You are a strict script evaluator. Return ONLY valid JSON.",
            model="scorer",
            temperature=0.0,
        )
    elapsed = time.time() - start

    json_str = extract_json_object(response)
    if json_str:
        result = json.loads(json_str)
        score = max(0, min(100, int(result.get("score", 50))))
        feedback = result.get("feedback", "")
        categories = result.get("score_categories", {})
    else:
        score = 50
        feedback = "Could not parse evaluation"
        categories = {}

    print(f"Score computed in {elapsed:.1f}s")
    print(f"Overall score: {score}/100")
    print(f"Feedback: {feedback}")
    print(f"Categories: {json.dumps(categories, indent=2)}")

    return score, feedback, categories


async def step_4_visual_annotation(draft: str):
    """Step 4: Add visual annotations."""
    print("\n" + "=" * 70)
    print("STEP 4: VISUAL ANNOTATION")
    print("=" * 70)

    prompt = f"""You are a video director. Add visual cues to this script.
Use labels: [B-ROLL], [MAP], [DATA], [ARCHIVAL], [GRAPHIC], [TRANSITION], [SOUND].
Keep notes short — one sentence each.

SCRIPT:
{draft}

Add visual directions to each section."""

    start = time.time()
    async with RouterClient() as router:
        annotated = await router.complete_text(
            prompt,
            system="You are a video director. Output ONLY visual notes in plain text. NO JSON.",
            model="annotator",
        )

    elapsed = time.time() - start
    print(f"Visual annotations in {elapsed:.1f}s")
    print(f"\n--- VISUAL PLAN ---\n{annotated[:1000]}...\n")
    return annotated


async def step_5_publish_to_notion(title: str, draft: str, visual_plan: str):
    """Step 5: Publish to Notion."""
    print("\n" + "=" * 70)
    print("STEP 5: PUBLISH TO NOTION")
    print("=" * 70)

    settings = get_settings()
    if not settings.NOTION_API_KEY:
        print("SKIP: Notion API key not configured")
        return None

    if not settings.NOTION_DATABASE_ID:
        print("SKIP: Notion database ID not configured")
        return None

    print(f"Notion API key: configured ({settings.NOTION_API_KEY[:8]}...)")
    print(f"Notion database ID: {settings.NOTION_DATABASE_ID}")

    notion = NotionScriptClient()

    script_entries = [
        {
            "section_type": "Script",
            "narration": draft,
            "visual_cue": visual_plan,
            "visual_type": "broll",
        }
    ]

    result = await notion.create_script_page(
        title=title,
        script_data={"entries": script_entries},
        seo_data={},
    )

    if result.success:
        page_url = result.data or ""
        print(f"SUCCESS: Published to Notion!")
        print(f"Page URL: {page_url}")
    else:
        print(f"FAILED: {result.user_message or result.error_message or 'Unknown error'}")
        print(f"Error code: {result.error_code}")

    return result


async def main():
    """Run the full pipeline end-to-end."""
    total_start = time.time()

    print("=" * 70)
    print("KERAPATHYS FULL PIPELINE TEST")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    print(f"Topic: {TOPIC}")
    print("=" * 70)

    try:
        # Step 1: Research
        dossier, research_markdown = await step_1_research()

        # Step 2: Script Writing
        draft = await step_2_script_writing(research_markdown)

        # Step 3: Scoring
        score, feedback, categories = await step_3_scoring(draft)

        # Step 4: Visual Annotation
        visual_plan = await step_4_visual_annotation(draft)

        # Step 5: Publish to Notion
        notion_result = await step_5_publish_to_notion(TOPIC, draft, visual_plan)

        # Final Summary
        total_elapsed = time.time() - total_start
        print("\n" + "=" * 70)
        print("PIPELINE COMPLETE")
        print("=" * 70)
        print(f"Total time: {total_elapsed:.1f}s")
        print(f"Research: {len(dossier.all_facts)} facts, {len(dossier.all_sources)} sources")
        print(f"Script: {len(draft.split())} words")
        print(f"Score: {score}/100")
        print(f"Notion: {'Published' if notion_result and notion_result.success else 'Failed/Skipped'}")

        # Save results for reference
        results = {
            "topic": TOPIC,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "research": {
                "completeness": dossier.completeness_score,
                "facts": len(dossier.all_facts),
                "sources": len(dossier.all_sources),
                "searches": dossier.search_queries_total,
                "duration": dossier.research_duration_seconds,
            },
            "script": {
                "word_count": len(draft.split()),
                "score": score,
                "feedback": feedback,
            },
            "notion": {
                "published": notion_result.success if notion_result else False,
                "url": notion_result.data if notion_result and notion_result.success else None,
            },
            "total_duration": total_elapsed,
        }

        os.makedirs("/home/z/my-project/download", exist_ok=True)
        output_path = "/home/z/my-project/download/pipeline_test_results.json"
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\nResults saved to: {output_path}")

        return True

    except Exception as e:
        total_elapsed = time.time() - total_start
        print(f"\n{'=' * 70}")
        print(f"PIPELINE FAILED after {total_elapsed:.1f}s")
        print(f"Error: {e}")
        print(f"{'=' * 70}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

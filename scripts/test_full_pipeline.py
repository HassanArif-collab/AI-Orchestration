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


async def step_2_script_writing(research_markdown: str, visual_feedback: str = None):
    """Step 2: Write a documentary script from research — using the SAME prompt as draft_node."""
    print("\n" + "=" * 70)
    print("STEP 2: SCRIPT WRITING (with style constitution + genre rules)")
    if visual_feedback:
        print("  (Re-drafting with visual annotator feedback)")
    print("=" * 70)

    # Load style reference and genre rules (same as nodes.py does)
    from packages.content_factory.orchestration.nodes import (
        _STYLE_CONTEXT, _get_genre_rules, _GENRE_SCHEMA,
    )
    genre_rules = _get_genre_rules("current_situation", _GENRE_SCHEMA)

    style_block = _STYLE_CONTEXT or ""
    if style_block:
        style_block = f"\n\n=== JOHNNY HARRIS STYLE CONSTITUTION ===\n{style_block}"
    genre_block = f"\n\n=== GENRE-SPECIFIC RULES ===\n{genre_rules}" if genre_rules else ""

    context_parts = [f"RESEARCH DOSSIER:\n{research_markdown[:16000]}"]
    if visual_feedback:
        context_parts.append(f"VISUAL ANNOTATOR FEEDBACK TO ADDRESS:\n{visual_feedback}")
    context = "\n\n---\n\n".join(context_parts)

    prompt = f"""You are writing a Johnny Harris-style documentary script. This is NOT a generic overview — this is a specific, evidence-driven story.

TOPIC: {TOPIC}
{genre_block}
{style_block}

{context}

CRITICAL RULES — YOUR SCRIPT WILL BE REJECTED IF YOU VIOLATE THESE:
1. You MUST cite at least 3 specific numbers, statistics, or data points from the research above
2. You MUST name at least 2 real people, organizations, companies, or places mentioned in the research
3. You MUST reference at least 1 specific event, case study, or real-world example
4. NEVER write vague statements like "a new generation is emerging" or "things are changing" — be SPECIFIC
5. NEVER write filler like "in a country often defined by its tumultuous politics" — get straight to the point
6. Every paragraph must contain a concrete fact, name, number, or specific example from the research
7. Use active voice. Name who did what. Give numbers. Be specific about where and when.

VOICE RULES:
- Write like a friend who just discovered something fascinating: "Look at this." "Wait, come with me on this."
- Assign HUMAN MOTIVES to every entity (fear, ambition, desperation, pride).
- Use Anchor-Bridge rhythm: drop the viewer into something REAL, THEN explain.
- NEVER use nominalizations. Replace with plain actions.
- The last 10-20% must shift from precise evidence to personal, poetic, emotionally resonant.

STRUCTURE:
**HOOK** — Open IN MEDIAS RES. Drop the viewer into a surprising action, a specific number, a physical object.
**ANCHOR** — Ground in something tangible the camera can point at.
**BRIDGE** — Connect the anchor evidence to the bigger picture. Who did what to whom.
**REVEAL** — The key insight that challenges the mainstream assumption. Name who loses and who wins.
**CONCLUSION** — Shift to personal/poetic mode. Include unexpected praise. End with a resonant line.

Write 500-700 words of narration text. Output ONLY the script with section headers. No meta-commentary."""

    system_prompt = """You are an elite documentary scriptwriter in the style of Johnny Harris.

Your writing obeys these IRON RULES:
1. INVESTIGATION OVER EXPLANATION — Show the audience something real. Let meaning emerge.
2. EXPERIENCE OVER INFORMATION — Create discovery, not instruction.
3. AGENT-ACTION-OBJECT — Every sentence: visible agent doing something to visible object.
4. ANTI-ABSTRACTION — Never "the globalization of trade led to..." — write "America sent its factories to China and a million workers in Ohio lost their jobs."
5. PEER-TO-PEER — You are a friend saying "wait, look at this."
6. CONCRETE FACTS ONLY — Every sentence carries specific names, numbers, dates, or places.
7. PAKISTANI AUDIENCE — Use PKR, Pakistani locations, Pakistani cultural context.

You NEVER write: "In a country often defined by...", "Things are changing", "A new era is dawning", "The stakes are high"
You ALWAYS write: "On February 14th, 2025, the federal cabinet approved...", "i2i PSER's report shows..." """

    start = time.time()
    async with RouterClient() as router:
        draft = await router.complete_text(
            prompt,
            system=system_prompt,
            model="script_writer",
            max_tokens=2000,
        )

    elapsed = time.time() - start
    word_count = len(draft.split())
    print(f"Draft generated in {elapsed:.1f}s")
    print(f"Word count: {word_count}")
    print(f"Style context injected: {len(_STYLE_CONTEXT)} chars")
    print(f"Genre rules injected: {len(genre_rules)} chars")
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
    """Step 4: Add visual annotations + structural review (tests visual feedback loop logic)."""
    print("\n" + "=" * 70)
    print("STEP 4: VISUAL ANNOTATION + STRUCTURAL REVIEW")
    print("=" * 70)

    # Part A: Structural review (tests the new visual_node logic)
    structural_prompt = f"""You are a video production director reviewing a script for produceability.

Analyze this script and answer:
1. Is the script specific enough to film? (Are there concrete locations, people, objects the camera can point at?)
2. Is the script too abstract? (Too many ideas without visual anchors?)
3. What specific visual elements are missing that would make this produceable?

Return JSON: {{"produceable": true/false, "structural_issues": ["issue1", "issue2"], "missing_visuals": ["visual1", "visual2"]}}

SCRIPT:
{draft}

Be strict. A script that is mostly abstract ideas without concrete visuals is NOT produceable."""

    start = time.time()
    async with RouterClient() as router:
        structural_review = await router.complete_text(
            structural_prompt,
            system="You are a video production director. Return ONLY valid JSON.",
            model="annotator",
            temperature=0.0,
        )
    elapsed = time.time() - start

    from packages.core.json_utils import extract_json_object
    review_json = extract_json_object(structural_review)
    produceable = True
    structural_issues = []
    if review_json:
        try:
            review = json.loads(review_json)
            produceable = review.get("produceable", True)
            structural_issues = review.get("structural_issues", [])
            print(f"Structural review in {elapsed:.1f}s")
            print(f"Produceable: {produceable}")
            print(f"Issues found: {structural_issues}")
        except json.JSONDecodeError:
            print(f"Structural review parse failed, assuming produceable")
    else:
        print(f"Structural review in {elapsed:.1f}s (could not parse JSON, assuming produceable)")

    # Part B: Visual annotations
    visual_prompt = f"""You are a video director. Add visual cues to this script.
Use labels: [B-ROLL], [MAP], [DATA], [ARCHIVAL], [GRAPHIC], [TRANSITION], [SOUND], [TALKING HEAD].
Keep notes short — one sentence each.

SCRIPT:
{draft}

Add visual directions to each section."""

    start = time.time()
    async with RouterClient() as router:
        annotated = await router.complete_text(
            visual_prompt,
            system="You are a video director. Output ONLY visual notes in plain text. NO JSON.",
            model="annotator",
        )

    elapsed = time.time() - start
    print(f"Visual annotations in {elapsed:.1f}s")
    print(f"\n--- VISUAL PLAN ---\n{annotated[:1000]}...\n")

    return annotated, produceable, structural_issues


async def step_5_publish_to_notion(title: str, draft: str, visual_plan: str, score: int, categories: dict):
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

    print(f"Notion API key: {'configured' if settings.NOTION_API_KEY else 'NOT configured'}")
    print(f"Notion database ID: {settings.NOTION_DATABASE_ID}")

    notion = NotionScriptClient()

    # Build script entries with both narration and visual plan
    script_entries = [
        {
            "section_type": "Script",
            "narration": draft,
            "visual_cue": visual_plan,
            "visual_type": "broll",
        }
    ]

    # Include score metadata
    seo_data = {
        "score": score,
        "score_categories": categories,
        "pipeline_version": "feedback-loops-v2",
        "test_timestamp": datetime.now(timezone.utc).isoformat(),
    }

    result = await notion.create_script_page(
        title=title,
        script_data={"entries": script_entries},
        seo_data=seo_data,
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

        # TEST RESEARCH FEEDBACK LOOP: if credibility < 60%, test research gap
        credibility = categories.get("credibility", 100)
        if credibility < 60:
            print("\n[TEST] Research feedback loop would be triggered (credibility < 60%)")
            print(f"[TEST] Credibility score: {credibility}% — this would trigger research_gap_node")
        else:
            print(f"\n[TEST] Credibility score: {credibility}% — no research gap needed (threshold: 60%)")

        # TEST KARPATHY LOOP: if score < 85, show what mutation would do
        if score < 85:
            print(f"\n[TEST] Karpathy loop would activate (score {score} < 85 threshold)")
            print(f"[TEST] In production, the mutator would run up to 20 iterations to improve the script")
        else:
            print(f"\n[TEST] Score {score} >= 85 — script passes quality threshold")

        # Step 4: Visual Annotation + Structural Review
        visual_plan, produceable, structural_issues = await step_4_visual_annotation(draft)

        # TEST VISUAL FEEDBACK LOOP: if not produceable, re-draft with feedback
        if not produceable and structural_issues:
            print("\n[TEST] Visual feedback loop triggered — re-drafting with structural feedback...")
            visual_feedback_text = "STRUCTURAL ISSUES FROM VISUAL ANNOTATOR:\n" + "\n".join(f"- {issue}" for issue in structural_issues)
            draft = await step_2_script_writing(research_markdown, visual_feedback=visual_feedback_text)
            print("[TEST] Re-draft after visual feedback complete")

        # Step 5: Publish to Notion
        notion_result = await step_5_publish_to_notion(TOPIC, draft, visual_plan, score, categories)

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

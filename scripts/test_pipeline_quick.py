#!/usr/bin/env python3
"""
Focused end-to-end pipeline test — minimal search budget, quick validation.

Usage:
    cd /home/z/AI-Orchestration
    python scripts/test_pipeline_quick.py
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, "/home/z/AI-Orchestration")

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S")

from packages.content_factory.production.deep_research import DeepResearchEngine
from packages.integrations.notion.client import NotionScriptClient
from packages.router.client import RouterClient
from packages.core.config import get_settings

TOPIC = "Pakistan's AI Revolution in 2026"


async def test_router():
    """Quick test: can RouterClient talk to FreeRouter?"""
    print("\n[TEST] FreeRouter connectivity...")
    try:
        async with RouterClient() as router:
            result = await router.complete_text("Say 'hello' in one word.", model="scorer", max_tokens=10, temperature=0.0)
            print(f"[OK] Router response: {result[:100]}")
            return True
    except Exception as e:
        print(f"[FAIL] Router error: {e}")
        return False


async def test_research():
    """Quick test: minimal deep research."""
    print(f"\n[TEST] Deep Research (minimal budget) — Topic: {TOPIC}")
    start = time.time()
    try:
        async with RouterClient() as router:
            engine = DeepResearchEngine(
                router_client=router,
                max_searches_per_dimension=1,
                max_total_searches=8,
                enable_checkpoints=False,
                enable_fact_validation=False,
            )
            dossier = await engine.research(
                TOPIC,
                genre="current_situation",
                target_completeness=0.5,
                max_iterations=1,
                resume_from_checkpoint=False,
            )
        elapsed = time.time() - start
        md = dossier.to_markdown()
        print(f"[OK] Research completed in {elapsed:.1f}s")
        print(f"  Completeness: {dossier.completeness_score:.0%}")
        print(f"  Facts: {len(dossier.all_facts)}, Sources: {len(dossier.all_sources)}")
        print(f"  Articles read: {len(dossier.full_article_texts or {})}")
        print(f"  Dossier length: {len(md)} chars")

        # Show citations
        cited_facts = [f for f in dossier.all_facts if f.source_url]
        print(f"  Facts with citations: {len(cited_facts)}/{len(dossier.all_facts)}")
        if cited_facts:
            print(f"  Example citation: {cited_facts[0].statement[:80]}... -> {cited_facts[0].source_url[:60]}")

        # Quality report
        if dossier.quality_report:
            qr = dossier.quality_report
            print(f"  Quality score: {qr.get('score', 'N/A')}/100")
            if qr.get('weaknesses'):
                print(f"  Weaknesses: {qr['weaknesses'][:3]}")

        return dossier, md
    except Exception as e:
        elapsed = time.time() - start
        print(f"[FAIL] Research failed after {elapsed:.1f}s: {e}")
        import traceback
        traceback.print_exc()
        return None, None


async def test_script_writing(research_markdown: str):
    """Quick test: script generation."""
    print("\n[TEST] Script Writing...")
    start = time.time()
    try:
        prompt = f"""Write a 300-400 word Johnny Harris-style documentary script about: {TOPIC}

RESEARCH:
{research_markdown[:6000]}

RULES:
- Cite at least 3 specific numbers from the research
- Name at least 2 real people/organizations
- NO vague filler like "things are changing"
- Structure: HOOK → ANCHOR → BRIDGE → REVEAL → CONCLUSION
- Output ONLY the script with section headers"""

        async with RouterClient() as router:
            draft = await router.complete_text(
                prompt,
                system="You are an elite documentary scriptwriter in the style of Johnny Harris. Every sentence must carry concrete information.",
                model="script_writer",
                max_tokens=1500,
            )
        elapsed = time.time() - start
        words = len(draft.split())
        print(f"[OK] Script in {elapsed:.1f}s, {words} words")
        print(f"  Preview: {draft[:300]}...")
        return draft
    except Exception as e:
        print(f"[FAIL] Script writing failed: {e}")
        return None


async def test_scoring(draft: str):
    """Quick test: script scoring."""
    print("\n[TEST] Script Scoring...")
    start = time.time()
    try:
        prompt = f"""Score this script 0-100 for documentary quality. Check: specific facts, names, numbers, structure.

SCRIPT:
{draft}

Return JSON: {{"score": 85, "feedback": "Brief feedback"}}"""

        async with RouterClient() as router:
            from packages.core.json_utils import extract_json_object
            response = await router.complete_text(
                prompt,
                system="Return ONLY valid JSON.",
                model="scorer",
                temperature=0.0,
            )
        json_str = extract_json_object(response)
        if json_str:
            result = json.loads(json_str)
            score = max(0, min(100, int(result.get("score", 50))))
            feedback = result.get("feedback", "")
        else:
            score = 50
            feedback = "Parse failed"
        elapsed = time.time() - start
        print(f"[OK] Score: {score}/100 in {elapsed:.1f}s")
        print(f"  Feedback: {feedback}")
        return score, feedback
    except Exception as e:
        print(f"[FAIL] Scoring failed: {e}")
        return None, None


async def test_notion(title: str, draft: str):
    """Quick test: publish to Notion."""
    print("\n[TEST] Notion Publishing...")
    settings = get_settings()
    if not settings.NOTION_API_KEY:
        print("[SKIP] Notion API key not configured")
        return None
    if not settings.NOTION_DATABASE_ID:
        print("[SKIP] Notion database ID not configured")
        return None

    print(f"  API key: {settings.NOTION_API_KEY[:8]}...")
    print(f"  Database ID: {settings.NOTION_DATABASE_ID[:12]}...")

    try:
        notion = NotionScriptClient()
        result = await notion.create_script_page(
            title=title,
            script_data={
                "entries": [{
                    "section_type": "Script",
                    "narration": draft,
                    "visual_cue": "Auto-generated by Kerapathys Pipeline",
                    "visual_type": "broll",
                }]
            },
            seo_data={},
        )
        if result.success:
            print(f"[OK] Published to Notion!")
            print(f"  URL: {result.data}")
        else:
            print(f"[FAIL] Notion error: {result.user_message or result.error_message}")
        return result
    except Exception as e:
        print(f"[FAIL] Notion publish failed: {e}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    total_start = time.time()
    print("=" * 60)
    print("KERAPATHYS PIPELINE TEST (Quick)")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    print(f"Topic: {TOPIC}")
    print("=" * 60)

    results = {"topic": TOPIC, "timestamp": datetime.now(timezone.utc).isoformat()}

    # Test 1: Router
    router_ok = await test_router()
    results["router"] = router_ok

    # Test 2: Research
    dossier, research_md = await test_research()
    results["research"] = {
        "ok": dossier is not None,
        "facts": len(dossier.all_facts) if dossier else 0,
        "sources": len(dossier.all_sources) if dossier else 0,
        "completeness": dossier.completeness_score if dossier else 0,
        "articles_read": len(dossier.full_article_texts or {}) if dossier else 0,
    }

    # Test 3: Script Writing (only if research worked)
    draft = None
    if research_md:
        draft = await test_script_writing(research_md)
        results["script"] = {"ok": draft is not None, "words": len(draft.split()) if draft else 0}
    else:
        print("\n[SKIP] Script writing (no research)")
        results["script"] = {"ok": False, "reason": "no_research"}

    # Test 4: Scoring
    if draft:
        score, feedback = await test_scoring(draft)
        results["scoring"] = {"ok": score is not None, "score": score, "feedback": feedback}
    else:
        print("\n[SKIP] Scoring (no draft)")
        results["scoring"] = {"ok": False, "reason": "no_draft"}

    # Test 5: Notion
    if draft:
        notion_result = await test_notion(TOPIC, draft)
        results["notion"] = {
            "ok": notion_result is not None and notion_result.success if notion_result else False,
            "url": notion_result.data if notion_result and notion_result.success else None,
        }
    else:
        print("\n[SKIP] Notion (no draft)")
        results["notion"] = {"ok": False, "reason": "no_draft"}

    # Summary
    total = time.time() - total_start
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total time: {total:.1f}s")
    for step, info in results.items():
        if step in ("topic", "timestamp"):
            continue
        status = "PASS" if info.get("ok") else "FAIL"
        detail = ""
        if "facts" in info:
            detail = f"facts={info['facts']} sources={info['sources']} articles={info['articles_read']}"
        elif "words" in info:
            detail = f"words={info['words']}"
        elif "score" in info:
            detail = f"score={info.get('score', 'N/A')}"
        elif "url" in info:
            detail = f"url={info.get('url', 'N/A')}"
        print(f"  [{status}] {step}: {detail}")

    # Save results
    results["total_duration"] = total
    os.makedirs("/home/z/my-project/download", exist_ok=True)
    out_path = "/home/z/my-project/download/pipeline_test_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved: {out_path}")

    return all(results.get(k, {}).get("ok", False) for k in ["router", "research", "script", "scoring", "notion"])


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)

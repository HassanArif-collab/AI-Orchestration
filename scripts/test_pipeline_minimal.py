#!/usr/bin/env python3
"""
Minimal pipeline test — uses embedded LiteLLM, no FreeRouter needed.
Tests: Router → Research (1 search) → Script → Score → Notion publish.
"""
import asyncio, json, os, sys, time
from datetime import datetime, timezone
sys.path.insert(0, "/home/z/AI-Orchestration")

import logging
logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S")

TOPIC = "Pakistan AI startups 2026"

async def main():
    total_start = time.time()
    results = {"topic": TOPIC, "timestamp": datetime.now(timezone.utc).isoformat()}

    # ── Step 1: Router test ──
    print("\n[1/5] Router connectivity (embedded LiteLLM)...")
    try:
        from packages.router.client import RouterClient
        t0 = time.time()
        async with RouterClient() as r:
            resp = await r.complete_text("Say OK", model="auto", max_tokens=5, temperature=0.0)
        print(f"  OK in {time.time()-t0:.1f}s: {resp[:50]}")
        results["router"] = True
    except Exception as e:
        print(f"  FAIL: {e}")
        results["router"] = False
        return False

    # ── Step 2: Research (minimal) ──
    print(f"\n[2/5] Deep Research (minimal: 2 searches max)...")
    try:
        from packages.content_factory.production.deep_research import DeepResearchEngine
        t0 = time.time()
        async with RouterClient() as router:
            engine = DeepResearchEngine(
                router_client=router,
                max_searches_per_dimension=1,
                max_total_searches=3,
                enable_checkpoints=False,
                enable_fact_validation=False,
            )
            dossier = await engine.research(
                TOPIC,
                genre="current_situation",
                target_completeness=0.3,
                max_iterations=1,
                resume_from_checkpoint=False,
            )
        elapsed = time.time() - t0
        md = dossier.to_markdown()
        cited = sum(1 for f in dossier.all_facts if f.source_url)
        articles = len(dossier.full_article_texts or {})
        print(f"  OK in {elapsed:.1f}s")
        print(f"  Facts: {len(dossier.all_facts)}, Sources: {len(dossier.all_sources)}, Articles read: {articles}")
        print(f"  Facts with citations: {cited}/{len(dossier.all_facts)}")
        print(f"  Completeness: {dossier.completeness_score:.0%}")
        if dossier.quality_report:
            print(f"  Quality score: {dossier.quality_report.get('score', 'N/A')}/100")
        results["research"] = {"ok": True, "facts": len(dossier.all_facts), "sources": len(dossier.all_sources), "articles_read": articles, "cited_facts": cited, "completeness": dossier.completeness_score, "dossier_chars": len(md)}
    except Exception as e:
        print(f"  FAIL: {e}")
        results["research"] = {"ok": False, "error": str(e)[:200]}
        md = None

    # ── Step 3: Script writing ──
    if not md:
        print("\n[3/5] Script: SKIPPED (no research)")
        results["script"] = {"ok": False, "reason": "no_research"}
    else:
        print(f"\n[3/5] Script writing...")
        try:
            t0 = time.time()
            prompt = f"""Write a 200-300 word Johnny Harris-style documentary script about: {TOPIC}

RESEARCH:
{md[:5000]}

RULES: Cite specific numbers, name real organizations, NO vague filler.
Structure: HOOK → ANCHOR → REVEAL → CONCLUSION"""

            async with RouterClient() as r:
                draft = await r.complete_text(prompt, system="You are an elite documentary scriptwriter. Every sentence carries concrete information.", model="script_writer", max_tokens=1000)
            words = len(draft.split())
            print(f"  OK in {time.time()-t0:.1f}s, {words} words")
            print(f"  Preview: {draft[:200]}...")
            results["script"] = {"ok": True, "words": words}
        except Exception as e:
            print(f"  FAIL: {e}")
            draft = None
            results["script"] = {"ok": False, "error": str(e)[:200]}

    # ── Step 4: Scoring ──
    if not draft:
        print("\n[4/5] Score: SKIPPED (no draft)")
        results["scoring"] = {"ok": False, "reason": "no_draft"}
    else:
        print(f"\n[4/5] Scoring...")
        try:
            t0 = time.time()
            prompt = f"""Score this script 0-100: {draft}
Return JSON: {{"score": 85, "feedback": "brief"}}"""
            async with RouterClient() as r:
                from packages.core.json_utils import extract_json_object
                resp = await r.complete_text(prompt, system="Return ONLY valid JSON.", model="scorer", temperature=0.0)
            js = extract_json_object(resp)
            if js:
                parsed = json.loads(js)
                score = max(0, min(100, int(parsed.get("score", 50))))
                fb = parsed.get("feedback", "")
            else:
                score, fb = 50, "parse failed"
            print(f"  OK: {score}/100 in {time.time()-t0:.1f}s")
            print(f"  Feedback: {fb}")
            results["scoring"] = {"ok": True, "score": score, "feedback": fb}
        except Exception as e:
            print(f"  FAIL: {e}")
            results["scoring"] = {"ok": False, "error": str(e)[:200]}

    # ── Step 5: Notion publish ──
    if not draft:
        print("\n[5/5] Notion: SKIPPED (no draft)")
        results["notion"] = {"ok": False, "reason": "no_draft"}
    else:
        print(f"\n[5/5] Notion publishing...")
        try:
            from packages.integrations.notion.client import NotionScriptClient
            from packages.core.config import get_settings
            settings = get_settings()
            if not settings.NOTION_API_KEY or not settings.NOTION_DATABASE_ID:
                print(f"  SKIP: Notion not configured")
                results["notion"] = {"ok": False, "reason": "not_configured"}
            else:
                notion = NotionScriptClient()
                result = await notion.create_script_page(
                    title=f"[Pipeline Test] {TOPIC}",
                    script_data={"entries": [{"section_type": "Script", "narration": draft, "visual_cue": "Auto-generated by Kerapathys Pipeline", "visual_type": "broll"}]},
                    seo_data={},
                )
                if result.success:
                    print(f"  OK: Published to Notion!")
                    print(f"  URL: {result.data}")
                    results["notion"] = {"ok": True, "url": result.data}
                else:
                    print(f"  FAIL: {result.user_message or result.error_message}")
                    results["notion"] = {"ok": False, "error": str(result.user_message or result.error_message)[:200]}
        except Exception as e:
            print(f"  FAIL: {e}")
            results["notion"] = {"ok": False, "error": str(e)[:200]}

    # ── Summary ──
    total = time.time() - total_start
    print(f"\n{'='*60}")
    print(f"PIPELINE TEST COMPLETE ({total:.1f}s)")
    print(f"{'='*60}")
    for k in ["router", "research", "script", "scoring", "notion"]:
        info = results.get(k, {})
        status = "PASS" if info.get("ok") else "FAIL"
        detail = ""
        if "facts" in info: detail = f"facts={info['facts']} sources={info['sources']} articles={info['articles_read']} cited={info.get('cited_facts',0)}"
        elif "words" in info: detail = f"words={info['words']}"
        elif "score" in info: detail = f"score={info.get('score','N/A')}"
        elif "url" in info: detail = f"url={info.get('url','N/A')}"
        elif "error" in info: detail = f"error={info.get('error','')}"
        elif "reason" in info: detail = f"reason={info.get('reason','')}"
        print(f"  [{status}] {k}: {detail}")

    results["total_duration"] = total
    os.makedirs("/home/z/my-project/download", exist_ok=True)
    with open("/home/z/my-project/download/pipeline_test_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nSaved: /home/z/my-project/download/pipeline_test_results.json")

    return results.get("router", False) and results.get("research", {}).get("ok", False) and results.get("script", {}).get("ok", False)

if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)

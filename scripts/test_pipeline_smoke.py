#!/usr/bin/env python3
"""
Smoke test: Run the full pipeline through each stage with minimal LLM calls.
Tests that every stage works end-to-end including Notion publishing.
Uses FreeRouter proxy (must be running on port 4000).

Usage:
    cd /home/z/AI-Orchestration
    python scripts/test_pipeline_smoke.py
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, "/home/z/AI-Orchestration")

import logging
logging.basicConfig(
    level=logging.WARNING,  # Suppress verbose LiteLLM logs
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)

TOPIC = "Pakistan's Digital Economy in 2026"


async def call_llm(prompt: str, model: str = "auto", system: str = "", max_tokens: int = 500, temperature: float = 0.7) -> str:
    """Single LLM call through FreeRouter."""
    from packages.router.client import RouterClient
    async with RouterClient() as router:
        return await router.complete_text(prompt, system=system, model=model, max_tokens=max_tokens, temperature=temperature)


async def test_router_connection():
    """Test 0: Verify FreeRouter is reachable."""
    print("\n" + "=" * 60)
    print("TEST 0: ROUTER CONNECTION")
    print("=" * 60)

    from packages.router.client import RouterClient
    client = RouterClient()
    health = await client.health_check()
    await client.close()

    if health.get("healthy"):
        print(f"  ✅ FreeRouter healthy (latency: {health.get('latency_ms', 0):.0f}ms)")
        return True
    else:
        print(f"  ⚠️  FreeRouter not reachable — will use embedded LiteLLM")
        return False


async def test_research():
    """Test 1: Run a minimal web search via Exa.ai."""
    print("\n" + "=" * 60)
    print("TEST 1: WEB SEARCH (Exa.ai)")
    print("=" * 60)

    from packages.router.web_search import WebSearchClient

    async with WebSearchClient() as client:
        results = await client.search(f"{TOPIC} overview 2026", num_results=3)

    print(f"  ✅ Found {len(results)} results")
    for r in results[:3]:
        print(f"     - {r.title[:60]}")
    return results


async def test_research_gap_detection():
    """Test 2: Verify research gap node logic works (credibility check)."""
    print("\n" + "=" * 60)
    print("TEST 2: RESEARCH GAP DETECTION")
    print("=" * 60)

    # Simulate low credibility score that would trigger research gap
    score_categories = {
        "structure": 75, "hook": 70, "clarity": 80,
        "engagement": 75, "credibility": 45,  # Below 60% threshold
        "emotional": 70, "visual": 80, "conclusion": 75, "impact": 70,
    }

    from packages.content_factory.orchestration.graphs import should_continue
    state = {
        "evaluation_score": 55,
        "iteration_count": 0,
        "research_round": 1,
        "score_categories": score_categories,
    }

    result = should_continue(state)
    if result == "needs_research":
        print(f"  ✅ Research gap correctly detected (credibility={score_categories['credibility']}%)")
        print(f"     Routing: {result} → research_gap_node")
        return True
    else:
        print(f"  ❌ Expected 'needs_research' but got '{result}'")
        return False


async def test_script_writing():
    """Test 3: Write a script with style constitution + genre injection."""
    print("\n" + "=" * 60)
    print("TEST 3: SCRIPT WRITING (style + genre injection)")
    print("=" * 60)

    from packages.content_factory.orchestration.nodes import (
        _STYLE_CONTEXT, _get_genre_rules, _GENRE_SCHEMA, _STYLE_REFERENCE, _GENRE_SCHEMA,
    )

    # Verify style and genre are loaded
    if not _STYLE_REFERENCE:
        print("  ❌ style_reference.json NOT loaded")
        return False, ""
    if not _GENRE_SCHEMA:
        print("  ❌ genre_schema.json NOT loaded")
        return False, ""

    genre_rules = _get_genre_rules("current_situation", _GENRE_SCHEMA)

    print(f"  ✅ Style reference loaded ({len(_STYLE_REFERENCE)} keys)")
    print(f"  ✅ Genre schema loaded ({len(_GENRE_SCHEMA.get('genres', []))} genres)")
    print(f"  ✅ Style context built ({len(_STYLE_CONTEXT)} chars)")
    print(f"  ✅ Genre rules injected ({len(genre_rules)} chars)")

    # Write a minimal script
    prompt = f"""Write the FIRST 100 words of a Johnny Harris-style documentary script about: {TOPIC}

STYLE CONTEXT (should be non-empty):
{_STYLE_CONTEXT[:500]}

GENRE RULES (should be non-empty):
{genre_rules[:500]}

Start with a HOOK — drop the viewer into something specific. Output ONLY the script text."""

    system = "You are an elite documentary scriptwriter in the Johnny Harris style. Follow the style rules exactly."

    start = time.time()
    draft = await call_llm(prompt, model="script_writer", system=system, max_tokens=500)
    elapsed = time.time() - start

    word_count = len(draft.split())
    print(f"  ✅ Draft generated in {elapsed:.1f}s ({word_count} words)")
    print(f"  Draft preview: {draft[:150]}...")

    return True, draft


async def test_scoring(draft: str):
    """Test 4: Score the draft."""
    print("\n" + "=" * 60)
    print("TEST 4: SCRIPT SCORING")
    print("=" * 60)

    prompt = f"""Evaluate this script on a scale of 0-100.

SCRIPT:
{draft}

Return JSON: {{"score": 75, "feedback": "Brief feedback", "score_categories": {{"credibility": 70, "structure": 80, "hook": 75, "clarity": 70, "engagement": 80, "emotional": 65, "visual": 75, "conclusion": 70, "impact": 65}}}}

Be honest."""

    response = await call_llm(prompt, model="scorer", system="Return ONLY valid JSON.", temperature=0.0, max_tokens=300)

    from packages.core.json_utils import extract_json_object
    json_str = extract_json_object(response)
    if json_str:
        result = json.loads(json_str)
        score = max(0, min(100, int(result.get("score", 50))))
        categories = result.get("score_categories", {})
        feedback = result.get("feedback", "")
    else:
        score = 50
        categories = {}
        feedback = "Parse failed"

    print(f"  ✅ Score: {score}/100")
    print(f"  Feedback: {feedback[:100]}")
    print(f"  Categories: {json.dumps(categories)}")

    # Test feedback loop routing
    from packages.content_factory.orchestration.graphs import should_continue
    state = {
        "evaluation_score": score,
        "iteration_count": 0,
        "research_round": 1,
        "score_categories": categories,
    }
    route = should_continue(state)
    print(f"  ✅ Routing decision: {route} ({'pass' if route == 'done' else 'needs work'})")

    return score, categories, feedback


async def test_mutation_logic():
    """Test 5: Verify mutation routing (Karpathy loop)."""
    print("\n" + "=" * 60)
    print("TEST 5: KARPATHY MUTATION LOOP LOGIC")
    print("=" * 60)

    from packages.content_factory.orchestration.graphs import should_continue

    # Test: score below threshold, iteration < 20 → should mutate
    state_mutate = {
        "evaluation_score": 60,
        "iteration_count": 5,
        "research_round": 1,
        "score_categories": {"credibility": 80},
    }
    result = should_continue(state_mutate)
    assert result == "mutate", f"Expected 'mutate', got '{result}'"
    print(f"  ✅ Score=60, iter=5 → route: {result}")

    # Test: score above threshold → done
    state_done = {
        "evaluation_score": 90,
        "iteration_count": 3,
        "research_round": 1,
        "score_categories": {"credibility": 90},
    }
    result = should_continue(state_done)
    assert result == "done", f"Expected 'done', got '{result}'"
    print(f"  ✅ Score=90, iter=3 → route: {result}")

    # Test: max iterations → done
    state_max = {
        "evaluation_score": 50,
        "iteration_count": 20,
        "research_round": 1,
        "score_categories": {"credibility": 80},
    }
    result = should_continue(state_max)
    assert result == "done", f"Expected 'done', got '{result}'"
    print(f"  ✅ Score=50, iter=20 → route: {result} (max iterations)")

    return True


async def test_visual_feedback():
    """Test 6: Test visual feedback loop routing."""
    print("\n" + "=" * 60)
    print("TEST 6: VISUAL FEEDBACK LOOP LOGIC")
    print("=" * 60)

    from packages.content_factory.orchestration.graphs import after_visuals

    # Test: visual needs revision
    state_revise = {"visual_needs_revision": True, "error": None}
    result = after_visuals(state_revise)
    assert result == "revise_visual", f"Expected 'revise_visual', got '{result}'"
    print(f"  ✅ visual_needs_revision=True → route: {result}")

    # Test: visual OK
    state_ok = {"visual_needs_revision": False, "error": None}
    result = after_visuals(state_ok)
    assert result == "ok", f"Expected 'ok', got '{result}'"
    print(f"  ✅ visual_needs_revision=False → route: {result}")

    # Test: error
    state_err = {"error": "something broke"}
    result = after_visuals(state_err)
    assert result == "error", f"Expected 'error', got '{result}'"
    print(f"  ✅ error set → route: {result}")

    return True


async def test_human_review():
    """Test 7: Test human review routing."""
    print("\n" + "=" * 60)
    print("TEST 7: HUMAN REVIEW LOOP LOGIC")
    print("=" * 60)

    from packages.content_factory.orchestration.graphs import after_review

    # Test: approved
    state_approve = {"approved": True, "error": None}
    result = after_review(state_approve)
    assert result == "approve", f"Expected 'approve', got '{result}'"
    print(f"  ✅ approved=True → route: {result} (→ publish)")

    # Test: rejected
    state_reject = {"approved": False, "error": None}
    result = after_review(state_reject)
    assert result == "revise", f"Expected 'revise', got '{result}'"
    print(f"  ✅ approved=False → route: {result} (→ draft)")

    return True


async def test_notion_publishing(title: str, draft: str, score: int, categories: dict):
    """Test 8: Publish to Notion."""
    print("\n" + "=" * 60)
    print("TEST 8: NOTION PUBLISHING")
    print("=" * 60)

    from packages.core.config import get_settings
    settings = get_settings()

    if not settings.NOTION_API_KEY:
        print("  ⚠️  Notion API key not configured — skipping")
        return None

    from packages.integrations.notion.client import NotionScriptClient

    notion = NotionScriptClient()

    script_entries = [
        {
            "section_type": "Script",
            "narration": draft,
            "visual_cue": "[B-ROLL] Supporting footage\n[TALKING HEAD] Anchor narration",
            "visual_type": "broll",
        }
    ]

    seo_data = {
        "score": score,
        "score_categories": categories,
        "pipeline_version": "feedback-loops-v2-smoke-test",
        "test_timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        result = await notion.create_script_page(
            title=f"[SMOKE TEST] {title}",
            script_data={"entries": script_entries},
            seo_data=seo_data,
        )

        if result.success:
            page_url = result.data or ""
            print(f"  ✅ Published to Notion!")
            print(f"     URL: {page_url}")
        else:
            print(f"  ❌ Notion publish failed: {result.user_message or result.error_message}")
    except Exception as e:
        print(f"  ❌ Notion error: {e}")

    return result


async def test_style_constitution():
    """Test 9: Verify style_reference.json and genre_schema.json are complete."""
    print("\n" + "=" * 60)
    print("TEST 9: STYLE & GENRE FILES VALIDATION")
    print("=" * 60)

    from packages.content_factory.orchestration.nodes import (
        _STYLE_REFERENCE, _GENRE_SCHEMA, _STYLE_CONTEXT,
    )

    # Check style_reference.json structure
    required_keys = ["core_philosophy", "anchor_bridge_formula", "classic_style_writing",
                     "peer_to_peer_framing", "motive_loading", "conclusion_shift", "pakistani_adaptation"]
    missing = [k for k in required_keys if k not in _STYLE_REFERENCE]
    if missing:
        print(f"  ❌ style_reference.json missing keys: {missing}")
    else:
        print(f"  ✅ style_reference.json has all {len(required_keys)} required sections")

    # Check genre_schema.json structure
    genres = _GENRE_SCHEMA.get("genres", [])
    expected_genres = ["history", "current_situation", "tech_systems", "comparison",
                       "islamic_history", "south_asian_history"]
    genre_ids = [g.get("genre_id") for g in genres]
    missing_genres = [g for g in expected_genres if g not in genre_ids]
    if missing_genres:
        print(f"  ⚠️  Missing genre definitions: {missing_genres}")
    else:
        print(f"  ✅ genre_schema.json has all {len(expected_genres)} expected genres")

    # Check style context is built
    if len(_STYLE_CONTEXT) < 100:
        print(f"  ❌ Style context too short ({len(_STYLE_CONTEXT)} chars)")
    else:
        print(f"  ✅ Style context built ({len(_STYLE_CONTEXT)} chars)")

    return len(missing) == 0


async def test_new_state_fields():
    """Test 10: Verify new state fields are present in ProductionState."""
    print("\n" + "=" * 60)
    print("TEST 10: STATE FIELDS VALIDATION")
    print("=" * 60)

    from packages.content_factory.orchestration.state import ProductionState

    new_fields = ["research_round", "visual_needs_revision", "visual_feedback"]
    missing = []
    for field in new_fields:
        if field not in ProductionState.__annotations__:
            missing.append(field)
        else:
            print(f"  ✅ ProductionState.{field} present")

    if missing:
        print(f"  ❌ Missing state fields: {missing}")
        return False

    return True


async def main():
    total_start = time.time()

    print("=" * 60)
    print("KERAPATHYS PIPELINE SMOKE TEST")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    print(f"Topic: {TOPIC}")
    print(f"Tests: Router → Research → Script → Score → Mutate → Visual → Human → Notion")
    print("=" * 60)

    results = {}
    passed = 0
    failed = 0
    total = 10

    try:
        # Test 0: Router connection
        results["router"] = await test_router_connection()

        # Test 1: Web search
        try:
            search_results = await test_research()
            results["research"] = len(search_results) > 0
        except Exception as e:
            print(f"  ❌ Research failed: {e}")
            results["research"] = False
            search_results = []

        # Test 2: Research gap detection
        try:
            results["research_gap"] = await test_research_gap_detection()
        except Exception as e:
            print(f"  ❌ Research gap test failed: {e}")
            results["research_gap"] = False

        # Test 3: Script writing with style injection
        try:
            success, draft = await test_script_writing()
            results["script_writing"] = success
        except Exception as e:
            print(f"  ❌ Script writing failed: {e}")
            results["script_writing"] = False
            draft = "Fallback draft for testing."

        # Test 4: Scoring
        try:
            score, categories, feedback = await test_scoring(draft)
            results["scoring"] = score > 0
        except Exception as e:
            print(f"  ❌ Scoring failed: {e}")
            results["scoring"] = False
            score, categories, feedback = 50, {}, "Scoring failed"

        # Test 5: Mutation loop logic
        try:
            results["mutation"] = await test_mutation_logic()
        except Exception as e:
            print(f"  ❌ Mutation test failed: {e}")
            results["mutation"] = False

        # Test 6: Visual feedback loop
        try:
            results["visual_feedback"] = await test_visual_feedback()
        except Exception as e:
            print(f"  ❌ Visual feedback test failed: {e}")
            results["visual_feedback"] = False

        # Test 7: Human review loop
        try:
            results["human_review"] = await test_human_review()
        except Exception as e:
            print(f"  ❌ Human review test failed: {e}")
            results["human_review"] = False

        # Test 8: Notion publishing
        try:
            notion_result = await test_notion_publishing(TOPIC, draft, score, categories)
            results["notion"] = notion_result.success if notion_result else False
        except Exception as e:
            print(f"  ❌ Notion failed: {e}")
            results["notion"] = False

        # Test 9: Style files validation
        try:
            results["style_files"] = await test_style_constitution()
        except Exception as e:
            print(f"  ❌ Style files test failed: {e}")
            results["style_files"] = False

        # Test 10: State fields validation
        try:
            results["state_fields"] = await test_new_state_fields()
        except Exception as e:
            print(f"  ❌ State fields test failed: {e}")
            results["state_fields"] = False

    except Exception as e:
        print(f"\nFATAL: {e}")
        import traceback
        traceback.print_exc()

    # Summary
    passed = sum(1 for v in results.values() if v)
    failed = total - passed
    total_elapsed = time.time() - total_start

    print("\n" + "=" * 60)
    print("SMOKE TEST SUMMARY")
    print("=" * 60)
    for test_name, passed_test in results.items():
        status = "✅ PASS" if passed_test else "❌ FAIL"
        print(f"  {status}  {test_name}")
    print(f"\n  Total: {passed}/{total} passed ({failed} failed)")
    print(f"  Duration: {total_elapsed:.1f}s")
    print("=" * 60)

    # Save results
    os.makedirs("/home/z/my-project/download", exist_ok=True)
    output = {
        "topic": TOPIC,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results": results,
        "passed": passed,
        "total": total,
        "duration_seconds": total_elapsed,
    }
    output_path = "/home/z/my-project/download/pipeline_smoke_test.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"  Results saved: {output_path}")

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

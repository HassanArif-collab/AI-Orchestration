#!/usr/bin/env python3
"""End-to-end pipeline smoke test.

Tests the complete pipeline flow:
1. Create pipeline run
2. Run to HUMAN_TOPIC_APPROVAL gate
3. Approve with first idea
4. Run to HUMAN_REVIEW gate (SEO + VISUAL_PLANNING in parallel)
5. Approve
6. Run to completion
7. Print all outputs
"""

import sys
import asyncio

from packages.pipeline.runner import PipelineRunner
from packages.pipeline.state import RunStore
from packages.pipeline.stages import Stage


async def main():
    """Run the end-to-end pipeline test."""
    print("=" * 60)
    print("Pipeline End-to-End Test")
    print("=" * 60)

    # Create runner
    runner = PipelineRunner()
    print("\n[1] Created PipelineRunner")

    # Create run
    run = await runner.create_run()
    print(f"[2] Created new run: {run.run_id}")

    # Run until first gate (HUMAN_TOPIC_APPROVAL)
    gate = await runner.run_until_gate(run)
    assert gate == Stage.HUMAN_TOPIC_APPROVAL, f"Expected HUMAN_TOPIC_APPROVAL, got {gate}"
    print(f"[3] Reached HUMAN_TOPIC_APPROVAL gate")

    # Get video ideas
    ideas = run.get_output(Stage.TREND_ANALYSIS)
    print(f"[4] Got {len(ideas)} video ideas from trend analysis")

    # Approve with first idea
    await runner.approve_gate(run, gate, approved=True, selection=ideas[0])
    print(f"[5] Approved with idea: {ideas[0].get('title')}")

    # Run until next gate (HUMAN_REVIEW)
    gate = await runner.run_until_gate(run)
    assert gate == Stage.HUMAN_REVIEW, f"Expected HUMAN_REVIEW, got {gate}"
    print(f"[6] Reached HUMAN_REVIEW gate")

    # Approve
    await runner.approve_gate(run, gate, approved=True)
    print("[7] Approved at HUMAN_REVIEW")

    # Run to completion
    gate = await runner.run_until_gate(run)
    assert gate is None, f"Expected pipeline complete, got {gate}"
    assert run.status == "complete", f"Expected status='complete', got {run.status}"
    print("[8] Pipeline completed!")

    # Print all outputs
    print("\n" + "=" * 60)
    print("All Stage Outputs")
    print("=" * 60)

    for stage in Stage:
        output = run.get_output(stage)
        if output:
            print(f"\n[{stage.value}]")
            if isinstance(output, dict):
                for key, value in output.items():
                    print(f"  {key}: {value}")
            elif isinstance(output, list):
                for i, item in enumerate(output):
                    print(f"  [{i}] {item}")
            else:
                print(f"  {output}")

    print("\n" + "=" * 60)
    print("TEST PASSED!")
    print("=" * 60)

    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
scripts/auto_production.py — Fully Automated Production Loop.

This script:
1. Generates Tier 1 topic candidates across multiple genres.
2. For each candidate, runs:
   - Deep Research
   - Johnny Harris-style Scripting
   - Self-Evolution (until score > 85%)
   - Visual/Music Planning
   - SEO Generation
   - Publishing to Notion
"""

import asyncio
import sys
from typing import List, Optional

from packages.pipeline.runner import PipelineRunner
from packages.pipeline.stages import Stage
from packages.content_factory.topic_finder.finder import TopicFinderAgent
from packages.core.logger import get_logger

logger = get_logger(__name__)

async def run_auto_production(genres: List[str] = None, target_score: float = 85.0):
    """
    Automated Production Loop.
    """
    if not genres:
        # Define the set of genres to test
        genres = ["history", "current_situation", "tech_systems", "islamic_history", "south_asian_history"]

    finder = TopicFinderAgent()
    
    print(f"\n{'='*60}")
    print(f"AUTO-PRODUCTION: TARGET QUALITY {target_score}%")
    print(f"{'='*60}\n")

    # 1. Topic Generation for all genres
    all_candidates = []
    print(f"[1] Discovering topics for genres: {', '.join(genres)}...")
    
    for genre in genres:
        # Use a dynamic seed based on the genre
        seed = f"Pakistan {genre.replace('_', ' ')} investigation"
        try:
            # TopicFinderAgent.generate_candidate returns a single TopicBrief if Tier 1
            # It also saves it to the Topic Reservoir automatically.
            brief = await finder.generate_candidate(seed, genre)
            if brief:
                all_candidates.append(brief)
                print(f"    - Found Tier 1 topic for {genre}: {brief.topic_statement}")
            else:
                # Try finding an adaptation candidate if no original Tier 1 found
                adaptations = await finder.discover_adaptation_candidates(genre)
                if adaptations:
                    all_candidates.append(adaptations[0])
                    print(f"    - Found adaptation topic for {genre}: {adaptations[0].topic_statement}")
                else:
                    print(f"    - No Tier 1 topics found for {genre} at this time.")
        except Exception as e:
            print(f"    - Error searching for {genre}: {e}")

    if not all_candidates:
        print("\n    - CRITICAL: No topics found. Please ensure FreeRouter is working and seeds are valid.")
        return

    print(f"\n[2] Found {len(all_candidates)} topics to process.")

    # 2. Process each candidate through the pipeline
    runner = PipelineRunner()
    
    for i, brief in enumerate(all_candidates):
        print(f"\n{'-'*60}")
        print(f"TASK {i+1}/{len(all_candidates)}: {brief.topic_statement}")
        print(f"GENRE: {brief.genre_id} | TYPE: {getattr(brief, 'content_type', 'original')}")
        print(f"{'-'*60}\n")

        # Create a new pipeline run
        run = await runner.create_run()
        
        # AUTOMATION: Bypass Human Topic Approval Gate
        # We store the brief as the 'selection' for the approval stage.
        await runner.approve_gate(run, Stage.HUMAN_TOPIC_APPROVAL, approved=True, selection=brief.model_dump())
        
        try:
            # Execute Research (Mode A or B via handler)
            print(f"[+] Step 1: Deep Research & Initial Scripting...")
            await runner.execute_stage(run, Stage.RESEARCH)
            
            # Execute Script Writing (Experiment Loop / Evolution)
            print(f"[+] Step 2: Running Self-Evolution (Target: {target_score}%)...")
            # We pass threshold to handler via context
            await runner.execute_stage(run, Stage.SCRIPT_WRITING, context={"threshold": target_score})
            
            final_script_data = run.get_output(Stage.SCRIPT_WRITING)
            score = final_script_data.get("production_readiness_score", 0.0)
            
            print(f"    - Evolution complete. Score: {score:.1f}%")
            
            # Execute Visual Planning, SEO, and Publishing
            print(f"[+] Step 3: Visuals, SEO & Publishing...")
            
            # Run SEO and Visuals in parallel
            await asyncio.gather(
                runner.execute_stage(run, Stage.VISUAL_PLANNING),
                runner.execute_stage(run, Stage.SEO)
            )
            
            # Human Review Gate Bypass (Automation Mode)
            await runner.approve_gate(run, Stage.HUMAN_REVIEW, approved=True)
            
            # Final publish
            publish_result = await runner.execute_stage(run, Stage.PUBLISH)
            
            if publish_result.get("notion_page_id"):
                print(f"    - SUCCESS: Published to Notion.")
            else:
                print(f"    - NOTE: Processed but Notion publish was skipped or failed.")

        except Exception as e:
            print(f"    - FAILED: {e}")
            logger.error(f"auto_production_task_failed: {e}")

    print(f"\n{'='*60}")
    print("ALL TASKS COMPLETED")
    print(f"{'='*60}")

if __name__ == "__main__":
    # Handle genres passed as command line arguments
    user_genres = sys.argv[1].split(",") if len(sys.argv) > 1 else None
    asyncio.run(run_auto_production(genres=user_genres))

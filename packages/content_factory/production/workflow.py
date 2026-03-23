"""Phase 3 Core Production Workflow.

Combines the agents into a CrewAI process to generate an original
dual-column script from a topic idea.
"""

import json
from datetime import datetime, timezone
import uuid

from crewai import Crew, Process, Task
from pydantic import BaseModel

from packages.core.logger import get_logger
from packages.router.client import RouterClient

from ..models import AdaptedScript, DualColumnEntry, ProcessingStatus
from ..source_library import SourceVideoLibrary
from .agents import create_researcher, create_script_agent, create_visual_agent

logger = get_logger(__name__)


class VideoIdea(BaseModel):
    """Input for Phase 3 Production."""
    topic: str
    genre_id: str
    target_audience: str = "Pakistani"
    special_instructions: str = ""


async def run_production_workflow(
    idea: VideoIdea,
    source_library: SourceVideoLibrary | None = None,
    router_client: RouterClient | None = None,
) -> AdaptedScript | None:
    """Run the Phase 3 Core Production workflow.
    
    Args:
        idea: The video idea parameters.
        source_library: SQLite library to fetch structural references.
        router_client: Client for the LLM proxy.
        
    Returns:
        AdaptedScript (the final dual-column output) or None.
    """
    # 1. Fetch Architectural References
    library = source_library or SourceVideoLibrary()
    references = library.find_by_genre(idea.genre_id, limit=5)
    
    logger.info(f"production_started: topic='{idea.topic}' genre='{idea.genre_id}' refs_found={len(references)}")

    # 2. Instantiate Agents
    researcher = create_researcher(references)
    visual_agent = create_visual_agent()
    script_agent = create_script_agent()
    
    # 3. Define Tasks
    research_task = Task(
        description=f\"\"\"
        Conduct deep research on the topic: '{idea.topic}'.
        Target Audience: {idea.target_audience}.
        Special Instructions: {idea.special_instructions}.
        
        Output a detailed research dossier containing:
        - 3+ tangible physical anchors
        - 1+ specific human character illustrating the problem
        - Evidence contradicting the mainstream narrative
        - Chronological sequence or central Big Question
        \"\"\",
        expected_output="A structured markdown dossier of raw facts, anchors, and human stories.",
        agent=researcher
    )
    
    visual_task = Task(
        description=\"\"\"
        Take the research dossier and create a Visual Plan.
        Assign Anchor Substitution Hierarchy levels and visual types to all evidence.
        Ensure every piece of evidence can be pointed at by a camera or graphic.
        \"\"\",
        expected_output="A sequence of visual directions and assigned hierarchy levels.",
        agent=visual_agent,
        context=[research_task]
    )
    
    script_task = Task(
        description=f\"\"\"
        Take the research dossier and the visual plan and merge them into a Dual-Column Script.
        The genre is {idea.genre_id}.
        
        You MUST output STRICTLY VALID JSON exactly matching this schema, with no markdown formatting around it:
        {{
          "adapted_title": "The finalized title",
          "entries": [
            {{
              "section_label": "HOOK|ANCHOR|BRIDGE|REVEAL|CONCLUSION|TRANSITION",
              "prose": "spoken narration",
              "visual_direction": "visual plan details",
              "visual_type": "talking_head|broll|animation|archive|data_viz|soul_moment",
              "duration_estimate_seconds": 15.0,
              "anchor_hierarchy_level": 1,
              "low_confidence_flag": false
            }}
          ]
        }}
        \"\"\",
        expected_output="A JSON object matching the AdaptedScript dual-column schema.",
        agent=script_agent,
        context=[research_task, visual_task]
    )
    
    # 4. Run Crew
    crew = Crew(
        agents=[researcher, visual_agent, script_agent],
        tasks=[research_task, visual_task, script_task],
        process=Process.sequential,
        verbose=True
    )
    
    try:
        # Note: CrewAI kickoff is synchronous, but we'll await if run in a thread/async wrapper in real usage.
        # For FreeRouter we just call kickoff. In a real async environment we would use run_in_executor.
        result_text = crew.kickoff()
        
        import re
        json_match = re.search(r'\\{.*\\}', str(result_text), re.DOTALL)
        if not json_match:
            # Fallback to RouterClient to fix it if CrewAI output isn't clean JSON
            async with RouterClient() if not router_client else router_client as rc:
                fixed = await rc.complete_text(
                    prompt=f"Extract the JSON object from this text:\n\n{result_text}",
                    system_prompt="You return ONLY valid JSON. No markdown blocks.",
                    model="auto"
                )
                json_match = re.search(r'\\{.*\\}', fixed, re.DOTALL)
                if not json_match:
                    raise ValueError("Could not extract JSON from Script Agent output")
                result_text = json_match.group(0)
        else:
            result_text = json_match.group(0)
            
        data = json.loads(result_text)
        
        entries = []
        for item in data.get("entries", []):
            entries.append(DualColumnEntry(**item))
            
        script = AdaptedScript(
            video_id=f"orig_{uuid.uuid4().hex[:8]}", # Generate synthetic ID for original content
            source_title=idea.topic,
            adapted_title=data.get("adapted_title", idea.topic),
            genre=idea.genre_id,
            entries=entries,
            section_sequence=[e.section_label.value for e in entries],
            self_check_results=[], # Will be populated by Phase 4 Scoring Engine
            production_readiness_score=0.0
        )
        
        logger.info(f"production_complete: {script.video_id} - {script.adapted_title}")
        return script
        
    except Exception as e:
        logger.error(f"production_failed: {str(e)}")
        return None
